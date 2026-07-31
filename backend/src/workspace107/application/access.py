"""访问控制。

GR-101、GR-102 和 GR-103 共同定义 Workspace 归属与成员操作边界。
所有读写路径都必须先经过这里，由它根据 Membership 解析当前用户在目标 Workspace 中的角色。
API 层不允许直接拿 ``project_id`` 查询而跳过归属校验。

没有发现权限时统一抛 :class:`ObjectNotFound`，**不抛**
:class:`PermissionDenied`——否则错误码本身就泄露了对象是否存在。
只有在用户已经能看见对象、但能力不足以执行该操作时才用 PermissionDenied。

**判断的对象是能力，不是角色。** 写成 ``role is OWNER`` 的话，
每加一个角色就要把所有判断点翻一遍，漏掉的那处就是一个越权。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.capabilities import Capability, capabilities_of, describe
from ..domain.enums import WorkspaceRole
from ..domain.errors import ObjectNotFound, PermissionDenied
from ..domain.models import Project, Run, Workspace
from ..domain.ports.repositories import Repositories


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    """当前用户对某个 Workspace 的访问上下文。"""

    workspace: Workspace
    role: WorkspaceRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        """用于「要不要显示这个入口」这类判断。真正的拦截用 :meth:`require`。"""
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    project: Project
    workspace: Workspace
    role: WorkspaceRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class RunAccess:
    run: Run
    project: Project
    workspace: Workspace
    role: WorkspaceRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


class AccessGuard:
    """解析并校验当前用户的访问权限。

    三个方法都接受可选的 ``needs``：解析出访问上下文之后立刻校验能力。
    把校验放在同一次调用里，是为了让「取对象」和「查权限」不容易被拆开——
    拆开之后就有人会忘掉第二步。
    """

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def workspace(
        self, user_id: str, workspace_id: str, *, needs: Capability | None = None
    ) -> WorkspaceAccess:
        workspace = await self._repos.workspaces.get(workspace_id)
        if workspace is None:
            raise ObjectNotFound("Workspace", workspace_id)

        role = await self._resolve_role(user_id, workspace)
        if role is None:
            # 用户看不见这个 Workspace，对他来说它就不存在。
            raise ObjectNotFound("Workspace", workspace_id)

        access = WorkspaceAccess(workspace=workspace, role=role)
        if needs is not None:
            access.require(needs)
        return access

    async def project(
        self, user_id: str, project_id: str, *, needs: Capability | None = None
    ) -> ProjectAccess:
        project = await self._repos.projects.get(project_id)
        if project is None:
            raise ObjectNotFound("Project", project_id)
        try:
            workspace_access = await self.workspace(user_id, project.workspace_id)
        except ObjectNotFound as exc:
            # 归属 Workspace 不可见时，Project 同样视为不存在。
            raise ObjectNotFound("Project", project_id) from exc

        access = ProjectAccess(
            project=project, workspace=workspace_access.workspace, role=workspace_access.role
        )
        if needs is not None:
            access.require(needs)
        return access

    async def run(self, user_id: str, run_id: str, *, needs: Capability | None = None) -> RunAccess:
        run = await self._repos.runs.get(run_id)
        if run is None:
            raise ObjectNotFound("Run", run_id)
        try:
            project_access = await self.project(user_id, run.project_id)
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

    async def _resolve_role(self, user_id: str, workspace: Workspace) -> WorkspaceRole | None:
        if workspace.is_personal:
            # Personal Workspace 默认只有所属用户管理。
            return WorkspaceRole.OWNER if workspace.owner_id == user_id else None

        membership = await self._repos.memberships.get(workspace.id, user_id)
        if membership is None or not membership.is_active:
            return None
        return membership.role
