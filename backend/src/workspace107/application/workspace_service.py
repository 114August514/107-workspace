"""Workspace 用例。

覆盖设计稿 2.2 中标记为 [Core] 的能力子集：查看基本信息、修改名称和说明、
查看成员与角色、创建 Collaborative Workspace、邀请与移除成员、
查看资源权益，以及 Workspace 的 Variable / Secret 管理。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability, capabilities_of
from ..domain.compute import ComputePlan, ResourceEntitlement
from ..domain.enums import (
    ActivityAction,
    MembershipStatus,
    TargetType,
    WorkspaceKind,
    WorkspaceRole,
)
from ..domain.errors import ConflictError, ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.models import Membership, User, Workspace, WorkspaceVariable
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.secret_vault import SecretVault
from .access import AccessGuard
from .activity import ActivityRecorder, SupportsNestedTransaction
from .notifier import Notifier

DEFAULT_ENTITLEMENT_CONCURRENCY = 2


def _reject_owner_role(role: WorkspaceRole) -> None:
    """挡住一切「把 role 直接写成 owner」的路径。

    ``memberships.role == owner`` 这个值**只能由转让流程写入**（ADR-0008 第 3 节）。
    否则一个 Admin 就能凭空造出第二个所有者：对方接受邀请后拿到
    ``ownership.transfer``，转手把整个空间转走。

    这条规则当初只写在改角色那条路上，邀请接口漏了，被审查实跑复现出来。
    所以现在收成一个函数，**每个写 role 的入口都要调它**——
    新增接口时先回答「我属于 ADR-0008 那张路径表的哪一行」。
    """
    if role is WorkspaceRole.OWNER:
        raise ConflictError("不能直接把成员设为 Owner，请使用转让所有权")


@dataclass(frozen=True, slots=True)
class WorkspaceView:
    """一个 Workspace 加上当前用户在其中的角色与能力。

    能力由后端算好交给前端，前端不要自己按角色推导——
    推导就意味着规则有两份，早晚会不一致。前端权限只管「显不显示入口」，
    真正的拦截永远在后端（GR-001）。
    """

    workspace: Workspace
    role: WorkspaceRole
    capabilities: frozenset[Capability]


@dataclass(frozen=True, slots=True)
class MemberView:
    membership: Membership
    user: User


@dataclass(frozen=True, slots=True)
class InvitationView:
    """一条待处理的邀请。

    只带空间的名称和说明，**不带内容也不带能力**——还没接受，
    就还不该看到里面有什么。
    """

    workspace: Workspace
    membership: Membership


@dataclass(frozen=True, slots=True)
class EntitlementView:
    entitlement: ResourceEntitlement
    plan: ComputePlan


class WorkspaceService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        secrets: SecretVault,
        activity: ActivityRecorder,
        notifier: Notifier,
        session: SupportsNestedTransaction,
    ) -> None:
        self._session = session
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._secrets = secrets
        self._activity = activity
        self._notifier = notifier

    # -- 身份 -----------------------------------------------------------

    async def ensure_user(self, username: str, display_name: str = "") -> User:
        """按用户名取用户，不存在时创建，并同时准备好 Personal Workspace。

        对接学校统一身份认证之后，这里改为从认证结果建立用户，
        Personal Workspace 的准备逻辑不变。

        **这是每个请求都会走的路径**（`api/deps.get_current_user`），
        包括纯读接口。新用户第一次打开页面时，前端会并发发出好几个请求
        （未读数、首页数据……），它们同时走到这里、同时发现用户不存在、
        同时插入——`users.username` 有唯一约束，输掉的那个会拿到
        IntegrityError。这不是理论上的竞态，是新用户**必然**遇到的首屏。

        处理方式是「抢输了就读别人建好的」：插入包在 SAVEPOINT 里，
        冲突后回到已存在的那条记录继续。SAVEPOINT 不能省——
        ORM flush 失败会把整个 session 标记成需要回滚，
        后面的查询一条也走不了（和活动、通知踩的是同一个坑）。
        """
        existing = await self._repos.users.get_by_username(username)
        if existing is not None:
            await self._ensure_personal_workspace(existing)
            return existing

        user = User(
            id=ids.new_id(ids.USER),
            username=username,
            display_name=display_name or username,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin_nested():
                await self._repos.users.add(user)
        except Exception:
            # 并发的另一个请求抢先建好了。重新读出来用它，
            # 而不是把这次请求变成 500。
            winner = await self._repos.users.get_by_username(username)
            if winner is None:  # pragma: no cover - 不是唯一冲突，交给上层
                raise
            await self._ensure_personal_workspace(winner)
            return winner

        await self._ensure_personal_workspace(user)
        return user

    async def _ensure_personal_workspace(self, user: User) -> Workspace:
        existing = await self._repos.workspaces.get_personal(user.id)
        if existing is not None:
            return existing

        workspace = Workspace(
            id=ids.new_id(ids.WORKSPACE),
            kind=WorkspaceKind.PERSONAL,
            name=f"{user.display_name} 的个人空间",
            description="默认 Personal Workspace",
            owner_id=user.id,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin_nested():
                await self._repos.workspaces.add(workspace)
        except Exception:
            # 并发的另一个请求刚建好。数据库上的部分唯一索引保证只会有一个，
            # 这里读回来用它——重复建出两个个人空间比报错更难收拾。
            winner = await self._repos.workspaces.get_personal(user.id)
            if winner is None:  # pragma: no cover - 不是唯一冲突，交给上层
                raise
            return winner

        await self._grant_default_entitlements(workspace.id)
        return workspace

    async def _grant_default_entitlements(self, workspace_id: str) -> None:
        """为新 Workspace 授予平台默认算力方案的使用资格。

        真实平台上这里应该由权益申请与审批流程产生（V1）；
        M1 阶段直接授予全部公开方案，保证核心闭环可用。
        """
        for plan in await self._repos.compute_plans.list_all():
            await self._repos.entitlements.add(
                ResourceEntitlement(
                    id=ids.new_id(ids.ENTITLEMENT),
                    workspace_id=workspace_id,
                    compute_plan_id=plan.id,
                    max_concurrent_runs=DEFAULT_ENTITLEMENT_CONCURRENCY,
                )
            )

    # -- 查询 -----------------------------------------------------------

    async def list_for_user(self, user_id: str) -> list[WorkspaceView]:
        """列出用户可见的 Workspace，并带上他在每个空间里的能力。

        这里逐个解析角色（N+1）。N 是一个人参与的空间数，量级很小；
        真变多了再考虑一次查询把 membership 一起取出来。
        """
        views: list[WorkspaceView] = []
        for workspace in await self._repos.workspaces.list_for_user(user_id):
            access = await self._guard.workspace(user_id, workspace.id)
            views.append(
                WorkspaceView(
                    workspace=access.workspace,
                    role=access.role,
                    capabilities=access.capabilities,
                )
            )
        return views

    async def get(self, user_id: str, workspace_id: str) -> WorkspaceView:
        access = await self._guard.workspace(user_id, workspace_id)
        return WorkspaceView(
            workspace=access.workspace, role=access.role, capabilities=access.capabilities
        )

    async def list_invitations(self, user_id: str) -> list[InvitationView]:
        """我收到的、还没处理的邀请。

        **不走 AccessGuard**：被邀请的人对这个空间还没有访问权，
        用 guard 查会被判成看不见（GR-013），那样他就永远看不到邀请，
        也就永远进不来。这里只按「这条 membership 是不是发给我的」过滤。
        """
        views: list[InvitationView] = []
        for membership in await self._repos.memberships.list_pending_for_user(user_id):
            workspace = await self._repos.workspaces.get(membership.workspace_id)
            if workspace is not None:
                views.append(InvitationView(workspace=workspace, membership=membership))
        return views

    async def personal_workspace(self, user_id: str) -> Workspace:
        workspace = await self._repos.workspaces.get_personal(user_id)
        if workspace is None:
            raise ObjectNotFound("Personal Workspace")
        return workspace

    # -- 创建与修改 -----------------------------------------------------

    async def create_collaborative(
        self, user_id: str, name: str, description: str
    ) -> WorkspaceView:
        name = name.strip()
        if not name:
            raise ValidationFailed("Workspace 名称不能为空")

        workspace = Workspace(
            id=ids.new_id(ids.WORKSPACE),
            kind=WorkspaceKind.COLLABORATIVE,
            name=name,
            description=description,
            owner_id=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.workspaces.add(workspace)
        await self._repos.memberships.add(
            Membership(
                id=ids.new_id(ids.MEMBERSHIP),
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=self._clock.now(),
            )
        )
        await self._grant_default_entitlements(workspace.id)
        await self._activity.record(
            actor_id=user_id,
            workspace_id=workspace.id,
            action=ActivityAction.WORKSPACE_CREATED,
            target_type=TargetType.WORKSPACE,
            target_id=workspace.id,
            target_name=workspace.name,
        )
        return WorkspaceView(
            workspace=workspace,
            role=WorkspaceRole.OWNER,
            capabilities=capabilities_of(WorkspaceRole.OWNER),
        )

    async def update(
        self,
        user_id: str,
        workspace_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        default_environment_version_id: str | None = None,
    ) -> Workspace:
        access = await self._guard.workspace(
            user_id, workspace_id, needs=Capability.WORKSPACE_UPDATE
        )
        workspace = access.workspace

        if name is not None:
            if not name.strip():
                raise ValidationFailed("Workspace 名称不能为空")
            workspace.name = name.strip()
        if description is not None:
            workspace.description = description
        if default_environment_version_id is not None:
            version = await self._repos.environments.get_version(default_environment_version_id)
            if version is None:
                raise ObjectNotFound("Environment Version", default_environment_version_id)
            workspace.default_environment_version_id = version.id

        await self._repos.workspaces.update(workspace)
        await self._activity.record(
            actor_id=user_id,
            workspace_id=workspace.id,
            action=ActivityAction.WORKSPACE_UPDATED,
            target_type=TargetType.WORKSPACE,
            target_id=workspace.id,
            target_name=workspace.name,
        )
        return workspace

    # -- 成员 -----------------------------------------------------------

    async def list_members(self, user_id: str, workspace_id: str) -> list[MemberView]:
        access = await self._guard.workspace(user_id, workspace_id, needs=Capability.MEMBER_VIEW)
        if access.workspace.is_personal:
            owner = await self._repos.users.get(access.workspace.owner_id)
            if owner is None:  # pragma: no cover - 数据损坏才会发生
                raise ObjectNotFound("User", access.workspace.owner_id)
            return [
                MemberView(
                    membership=Membership(
                        id=f"virtual_{owner.id}",
                        workspace_id=workspace_id,
                        user_id=owner.id,
                        role=WorkspaceRole.OWNER,
                        status=MembershipStatus.ACTIVE,
                        created_at=access.workspace.created_at,
                    ),
                    user=owner,
                )
            ]

        views: list[MemberView] = []
        for membership in await self._repos.memberships.list_for_workspace(workspace_id):
            member = await self._repos.users.get(membership.user_id)
            if member is not None:
                views.append(MemberView(membership=membership, user=member))
        return views

    async def invite_member(
        self, user_id: str, workspace_id: str, username: str, role: WorkspaceRole
    ) -> Membership:
        access = await self._guard.workspace(user_id, workspace_id, needs=Capability.MEMBER_MANAGE)
        if access.workspace.is_personal:
            raise ConflictError("Personal Workspace 不能邀请成员")
        _reject_owner_role(role)

        invitee = await self._repos.users.get_by_username(username)
        if invitee is None:
            raise ObjectNotFound("User", username)

        existing = await self._repos.memberships.get(workspace_id, invitee.id)
        if existing is not None and existing.status in {
            MembershipStatus.INVITED,
            MembershipStatus.ACTIVE,
        }:
            raise ConflictError(f"{username} 已经是该 Workspace 的成员或已被邀请")

        if existing is not None:
            # 复用旧 membership（这个人退出过或被移除过）。
            # **活动和通知要照发**——对被邀请的人来说这就是一次全新的邀请，
            # 他没有理由因为「以前来过」就收不到通知。
            existing.role = role
            existing.status = MembershipStatus.INVITED
            await self._repos.memberships.update(existing)
            await self._record_member_activity(
                actor_id=user_id,
                workspace_id=workspace_id,
                action=ActivityAction.MEMBER_INVITED,
                member=invitee,
                detail=f"角色 {role.value}",
            )
            await self._notifier.workspace_invited(
                actor_id=user_id,
                invitee_id=invitee.id,
                workspace_id=workspace_id,
                workspace_name=access.workspace.name,
                role=role.value,
            )
            return existing

        membership = Membership(
            id=ids.new_id(ids.MEMBERSHIP),
            workspace_id=workspace_id,
            user_id=invitee.id,
            role=role,
            status=MembershipStatus.INVITED,
            created_at=self._clock.now(),
        )
        await self._repos.memberships.add(membership)
        await self._record_member_activity(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.MEMBER_INVITED,
            member=invitee,
            detail=f"角色 {role.value}",
        )
        await self._notifier.workspace_invited(
            actor_id=user_id,
            invitee_id=invitee.id,
            workspace_id=workspace_id,
            workspace_name=access.workspace.name,
            role=role.value,
        )
        return membership

    async def respond_to_invitation(
        self, user_id: str, workspace_id: str, *, accept: bool
    ) -> Membership:
        membership = await self._repos.memberships.get(workspace_id, user_id)
        if membership is None or membership.status is not MembershipStatus.INVITED:
            raise ObjectNotFound("Workspace 邀请", workspace_id)

        membership.status = MembershipStatus.ACTIVE if accept else MembershipStatus.LEFT
        await self._repos.memberships.update(membership)
        # 拒绝邀请不记活动：被邀请的人没有加入，这个空间里也就没发生什么
        if accept:
            await self._record_member_activity(
                actor_id=user_id,
                workspace_id=workspace_id,
                action=ActivityAction.MEMBER_JOINED,
                member=await self._repos.users.get(user_id),
            )
        return membership

    async def remove_member(self, user_id: str, workspace_id: str, target_user_id: str) -> None:
        access = await self._guard.workspace(user_id, workspace_id, needs=Capability.MEMBER_MANAGE)
        if target_user_id == access.workspace.owner_id:
            raise ConflictError("不能移除 Workspace 所有者，请先转让所有权")

        membership = await self._repos.memberships.get(workspace_id, target_user_id)
        if membership is None:
            raise ObjectNotFound("Membership", target_user_id)
        if membership.status is MembershipStatus.REMOVED:
            # 已经移除过了。再发一遍「你被移出了」是骚扰——
            # 而且那是一条 mandatory 通知，用户关都关不掉。
            return

        membership.status = MembershipStatus.REMOVED
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.MEMBER_REMOVED,
            member=await self._repos.users.get(target_user_id),
        )
        await self._notifier.member_removed(
            actor_id=user_id,
            member_id=target_user_id,
            workspace_id=workspace_id,
            workspace_name=access.workspace.name,
        )

    async def change_member_role(
        self, user_id: str, workspace_id: str, target_user_id: str, role: WorkspaceRole
    ) -> Membership:
        """修改成员角色。

        两条限制都和「所有权是一件独立的事」有关：

        - 不能改 Owner 的角色。要换所有者就走转让流程，那是一次明确的交接。
        - 不能把别人**设成** Owner。同上——否则就有两个所有者，或者
          一个 Admin 可以自己造出一个所有者来。
        """
        access = await self._guard.workspace(user_id, workspace_id, needs=Capability.MEMBER_MANAGE)
        if access.workspace.is_personal:
            raise ConflictError("Personal Workspace 没有成员角色")

        _reject_owner_role(role)
        if target_user_id == access.workspace.owner_id:
            raise ConflictError("不能修改 Workspace 所有者的角色，请先转让所有权")

        membership = await self._repos.memberships.get(workspace_id, target_user_id)
        if membership is None or not membership.is_active:
            raise ObjectNotFound("Membership", target_user_id)

        previous = membership.role
        membership.role = role
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.MEMBER_ROLE_CHANGED,
            member=await self._repos.users.get(target_user_id),
            detail=f"{previous.value} → {role.value}",
        )
        await self._notifier.role_changed(
            actor_id=user_id,
            member_id=target_user_id,
            workspace_id=workspace_id,
            workspace_name=access.workspace.name,
            role=role.value,
        )
        return membership

    async def leave(self, user_id: str, workspace_id: str) -> None:
        access = await self._guard.workspace(user_id, workspace_id)
        if access.workspace.is_personal:
            raise ConflictError("不能退出 Personal Workspace")
        if access.workspace.owner_id == user_id:
            raise PermissionDenied("Owner 不能直接退出，请先转让 Workspace 所有权")

        membership = await self._repos.memberships.get(workspace_id, user_id)
        if membership is None:  # pragma: no cover - guard 已经保证存在
            raise ObjectNotFound("Membership", user_id)
        membership.status = MembershipStatus.LEFT
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.MEMBER_LEFT,
            member=await self._repos.users.get(user_id),
        )

    async def transfer_ownership(
        self, user_id: str, workspace_id: str, target_user_id: str
    ) -> None:
        access = await self._guard.workspace(
            user_id, workspace_id, needs=Capability.OWNERSHIP_TRANSFER
        )
        if access.workspace.is_personal:
            raise ConflictError("Personal Workspace 不能转让所有权")

        target = await self._repos.memberships.get(workspace_id, target_user_id)
        if target is None or not target.is_active:
            raise ObjectNotFound("Membership", target_user_id)

        if target_user_id == access.workspace.owner_id:
            raise ConflictError("这个成员已经是 Workspace 所有者")

        # 降级的是**在册的那个所有者**（workspace.owner_id），不是碰巧发起调用的人。
        #
        # 按 ADR-0008，owner_id 和「role 为 owner 的 membership」必须一一对应。
        # 早先这里降的是 user_id，正常路径下两者相同看不出问题；一旦出现过
        # 第二个 role=owner 的成员（邀请接口的漏洞造出来的），由他发起转让就会
        # 只降他自己，把真正的 owner 留在 owner 角色上——一个 role=owner
        # 但不是 owner_id 的成员，他还能再转让一次。
        previous_owner = await self._repos.memberships.get(workspace_id, access.workspace.owner_id)
        if previous_owner is not None:
            # 交出的是所有权，不是团队。原所有者留在 Admin，
            # 新所有者觉得不合适可以再降级。
            previous_owner.role = WorkspaceRole.ADMIN
            await self._repos.memberships.update(previous_owner)

        target.role = WorkspaceRole.OWNER
        await self._repos.memberships.update(target)

        access.workspace.owner_id = target_user_id
        await self._repos.workspaces.update(access.workspace)
        await self._record_member_activity(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.OWNERSHIP_TRANSFERRED,
            member=await self._repos.users.get(target_user_id),
        )
        await self._notifier.ownership_received(
            actor_id=user_id,
            new_owner_id=target_user_id,
            workspace_id=workspace_id,
            workspace_name=access.workspace.name,
        )

    async def _record_member_activity(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        action: ActivityAction,
        member: User | None,
        detail: str = "",
    ) -> None:
        """成员类活动的公共部分。

        对象是「被操作的那个人」，所以 target_name 用他的用户名——
        活动流里读起来是「alice 移除了 bob」，而不是「alice 移除了 mbr_3f2a...」。
        """
        if member is None:  # pragma: no cover - 上游都已经确认过存在
            return
        await self._activity.record(
            actor_id=actor_id,
            workspace_id=workspace_id,
            action=action,
            target_type=TargetType.MEMBER,
            target_id=member.id,
            target_name=member.username,
            detail=detail,
        )

    # -- 资源权益 -------------------------------------------------------

    async def list_entitlements(self, user_id: str, workspace_id: str) -> list[EntitlementView]:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.ENTITLEMENT_VIEW)
        views: list[EntitlementView] = []
        for entitlement in await self._repos.entitlements.list_for_workspace(workspace_id):
            plan = await self._repos.compute_plans.get(entitlement.compute_plan_id)
            if plan is not None:
                views.append(EntitlementView(entitlement=entitlement, plan=plan))
        return views

    # -- Variable 与 Secret ---------------------------------------------

    async def list_variables(self, user_id: str, workspace_id: str) -> list[WorkspaceVariable]:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_VIEW)
        return await self._repos.variables.list_for_workspace(workspace_id)

    async def set_variable(
        self, user_id: str, workspace_id: str, name: str, value: str
    ) -> WorkspaceVariable:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_MANAGE)
        variable = WorkspaceVariable(workspace_id=workspace_id, name=name, value=value)
        await self._repos.variables.upsert(variable)
        return variable

    async def delete_variable(self, user_id: str, workspace_id: str, name: str) -> None:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_MANAGE)
        await self._repos.variables.delete(workspace_id, name)

    async def list_secret_names(self, user_id: str, workspace_id: str) -> list[str]:
        """只返回名称。Secret 的值没有任何读取路径（GR-012）。"""
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_VIEW)
        return sorted(await self._secrets.list_names(workspace_id))

    async def set_secret(self, user_id: str, workspace_id: str, name: str, value: str) -> None:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_MANAGE)
        if not value:
            raise ValidationFailed("Secret 值不能为空")
        await self._secrets.set_secret(workspace_id, name, value)

    async def delete_secret(self, user_id: str, workspace_id: str, name: str) -> None:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.CONFIG_MANAGE)
        await self._secrets.delete_secret(workspace_id, name)
