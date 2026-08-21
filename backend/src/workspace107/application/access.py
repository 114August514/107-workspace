"""Repository-backed authorization with 404 non-disclosure."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.capabilities import (
    Capability,
    UserGroupCapability,
    capabilities_of,
    describe,
    user_group_capabilities_of,
)
from ..domain.enums import MembershipRole, ProjectVisibility
from ..domain.errors import ObjectNotFound, PermissionDenied
from ..domain.models import (
    LegacyWorkspace,
    Project,
    Run,
    SharedResource,
    SharedResourceVersion,
    UserGroup,
)
from ..domain.ownership import OwnerKind
from ..domain.ports.repositories import Repositories


@dataclass(frozen=True, slots=True)
class UserGroupAccess:
    user_group: UserGroup
    role: MembershipRole

    @property
    def capabilities(self) -> frozenset[UserGroupCapability]:
        return user_group_capabilities_of(self.role)

    def can(self, capability: UserGroupCapability) -> bool:
        return capability in self.capabilities

    def require(self, capability: UserGroupCapability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class LegacyWorkspaceAccess:
    """Private access context for unmigrated child-domain rows."""

    workspace: LegacyWorkspace
    role: MembershipRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    project: Project
    workspace: LegacyWorkspace
    role: MembershipRole
    owner_scope: bool

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")

    def require_owner_scope(self) -> None:
        if not self.owner_scope:
            raise PermissionDenied("当前 Project 仅公开其元数据和不可变版本")


@dataclass(frozen=True, slots=True)
class RunAccess:
    run: Run
    project: Project
    workspace: LegacyWorkspace
    role: MembershipRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class SharedResourceAccess:
    """当前用户对某个 Shared Resource 的访问上下文。

    Platform 资源（``owner_workspace_id is None``）对全平台可见，
    ``role=None``——只允许读，所有写能力 ``require`` 均失败。
    Platform 资源通过 §2.6 D V2 公共发布申请 → 平台管理员审核流程产生，
    本 Core 子集仅预留数据结构与读路径。
    """

    resource: SharedResource
    workspace: LegacyWorkspace | None
    role: MembershipRole | None

    @property
    def capabilities(self) -> frozenset[Capability]:
        if self.role is None:
            return frozenset()
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(
                f"当前角色（{self.role.value if self.role else '匿名'}）无权{describe(capability)}"
            )


class AccessGuard:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def user_group(
        self,
        user_id: str,
        user_group_id: str,
        *,
        needs: UserGroupCapability | None = None,
    ) -> UserGroupAccess:
        user_group = await self._repos.user_groups.get_for_active_member(user_group_id, user_id)
        if user_group is None:
            raise ObjectNotFound("User Group", user_group_id)
        membership = await self._repos.memberships.get(user_group_id, user_id)
        if membership is None or not membership.is_active:
            raise ObjectNotFound("User Group", user_group_id)
        access = UserGroupAccess(user_group=user_group, role=membership.role)
        if needs is not None:
            access.require(needs)
        return access

    async def legacy_workspace(
        self, user_id: str, workspace_id: str, *, needs: Capability | None = None
    ) -> LegacyWorkspaceAccess:
        workspace = await self._repos.legacy_workspaces.get(workspace_id)
        if workspace is None:
            raise ObjectNotFound("Workspace compatibility context", workspace_id)
        role = await self._resolve_legacy_role(user_id, workspace)
        if role is None:
            raise ObjectNotFound("Workspace compatibility context", workspace_id)
        access = LegacyWorkspaceAccess(workspace=workspace, role=role)
        if needs is not None:
            access.require(needs)
        return access

    async def project(
        self,
        user_id: str,
        project_id: str,
        *,
        needs: Capability | None = None,
        owner_scope: bool = False,
    ) -> ProjectAccess:
        project = await self._repos.projects.get(project_id)
        if project is None:
            raise ObjectNotFound("Project", project_id)
        is_owner = False
        role = MembershipRole.VIEWER
        if project.owner.kind is OwnerKind.USER:
            is_owner = project.owner.id == user_id
            if is_owner:
                role = MembershipRole.OWNER
        else:
            membership = await self._repos.memberships.get(project.owner.id, user_id)
            if membership is not None and membership.is_active:
                is_owner = True
                role = membership.role
        if not is_owner and project.visibility is not ProjectVisibility.PUBLIC:
            raise ObjectNotFound("Project", project_id)
        if owner_scope and not is_owner:
            raise ObjectNotFound("Project", project_id)

        access = ProjectAccess(
            project=project,
            workspace=await self._compatibility_workspace(project),
            role=role,
            owner_scope=is_owner,
        )
        if needs is not None:
            if needs is Capability.PROJECT_VIEW and not is_owner:
                if project.visibility is not ProjectVisibility.PUBLIC:
                    raise ObjectNotFound("Project", project_id)
            else:
                access.require(needs)
        return access

    async def _compatibility_workspace(self, project: Project) -> LegacyWorkspace:
        workspace = await self._repos.legacy_workspaces.get(project.workspace_id)
        if workspace is None:
            raise ObjectNotFound("Project", project.id)
        return workspace

    async def run(self, user_id: str, run_id: str, *, needs: Capability | None = None) -> RunAccess:
        run = await self._repos.runs.get(run_id)
        if run is None:
            raise ObjectNotFound("Run", run_id)
        try:
            project_access = await self.project(user_id, run.project_id, owner_scope=True)
        except ObjectNotFound as exc:
            raise ObjectNotFound("Run", run_id) from exc

        access = RunAccess(
            run=run,
            project=project_access.project,
            workspace=project_access.workspace,
            role=project_access.role,
        )
        if needs is not None:
            access.require(needs)
        return access

    async def shared_resource(
        self, user_id: str, resource_id: str, *, needs: Capability | None = None
    ) -> SharedResourceAccess:
        """解析 Shared Resource 访问上下文。

        Platform 持有的资源对全平台可见，``role`` 为 ``None``——
        上层只能做读操作，不能调用 ``require`` 任何写能力。

        Workspace 持有的资源走 Workspace 成员校验：成员看不见就视为不存在，
        和现有 Project 路径一致。
        """
        resource = await self._repos.shared_resources.get(resource_id)
        if resource is None:
            raise ObjectNotFound("Shared Resource", resource_id)

        if resource.is_platform_owned:
            access = SharedResourceAccess(resource=resource, workspace=None, role=None)
            if needs is not None:
                # Platform 资源当前 Core 子集只允许读，没有任何写能力可以 require。
                access.require(needs)
            return access

        try:
            workspace_access = await self.legacy_workspace(
                user_id, resource.owner_workspace_id or ""
            )
        except ObjectNotFound as exc:
            raise ObjectNotFound("Shared Resource", resource_id) from exc

        access = SharedResourceAccess(
            resource=resource,
            workspace=workspace_access.workspace,
            role=workspace_access.role,
        )
        if needs is not None:
            access.require(needs)
        return access

    async def shared_resource_version(
        self, user_id: str, version_id: str, *, needs: Capability | None = None
    ) -> tuple[SharedResourceVersion, SharedResourceAccess]:
        """解析 Shared Resource Version 访问上下文。

        版本归属其 Shared Resource，可见性跟着资源走；找不到版本或无权访问
        归属资源时统一抛 ``ObjectNotFound``。
        """
        version = await self._repos.shared_resources.get_version(version_id)
        if version is None:
            raise ObjectNotFound("Shared Resource Version", version_id)
        access = await self.shared_resource(user_id, version.shared_resource_id, needs=needs)
        return version, access

    async def _resolve_legacy_role(
        self, user_id: str, workspace: LegacyWorkspace
    ) -> MembershipRole | None:
        if workspace.is_personal:
            return MembershipRole.OWNER if workspace.owner_id == user_id else None
        membership = await self._repos.memberships.get(workspace.id, user_id)
        if membership is None or not membership.is_active:
            return None
        return membership.role
