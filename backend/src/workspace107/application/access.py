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
from ..domain.enums import MembershipRole
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
    """Current User's role-derived access to a repository-visible resource."""

    resource: SharedResource
    role: MembershipRole

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise PermissionDenied(f"当前角色（{self.role.value}）无权{describe(capability)}")


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
        self, user_id: str, project_id: str, *, needs: Capability | None = None
    ) -> ProjectAccess:
        project = await self._repos.projects.get(project_id)
        if project is None:
            raise ObjectNotFound("Project", project_id)
        try:
            workspace_access = await self.legacy_workspace(user_id, project.workspace_id)
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

    async def shared_resource(
        self, user_id: str, resource_id: str, *, needs: Capability | None = None
    ) -> SharedResourceAccess:
        resource = await self._repos.shared_resources.get_discoverable_for_user(
            user_id, resource_id
        )
        if resource is None:
            raise ObjectNotFound("Shared Resource", resource_id)

        if resource.owner.kind is OwnerKind.USER:
            # Repository visibility already proved the exact User owner is the actor.
            role = MembershipRole.OWNER
        else:
            membership = await self._repos.memberships.get(resource.owner.id, user_id)
            if membership is None or not membership.is_active:  # pragma: no cover - SQL guard
                raise ObjectNotFound("Shared Resource", resource_id)
            role = membership.role

        access = SharedResourceAccess(resource=resource, role=role)
        if needs is not None:
            access.require(needs)
        return access

    async def shared_resource_version(
        self, user_id: str, version_id: str, *, needs: Capability | None = None
    ) -> tuple[SharedResourceVersion, SharedResourceAccess]:
        version = await self._repos.shared_resources.get_version_discoverable_for_user(
            user_id, version_id
        )
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
