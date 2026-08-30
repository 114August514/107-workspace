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
    Environment,
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
class ProjectAccess:
    project: Project
    role: MembershipRole | None
    owner_scope: bool

    @property
    def capabilities(self) -> frozenset[Capability]:
        if self.role is None:
            # PUBLIC reader: metadata + immutable version read only.
            return _PUBLIC_READER_CAPABILITIES
        return capabilities_of(self.role)

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            label = "公开读者" if self.role is None else self.role.value
            raise PermissionDenied(f"当前角色（{label}）无权{describe(capability)}")

    def require_owner_scope(self) -> None:
        if not self.owner_scope:
            raise PermissionDenied("当前 Project 仅公开其元数据和不可变版本")


_PUBLIC_READER_CAPABILITIES = frozenset({Capability.PROJECT_VIEW})


@dataclass(frozen=True, slots=True)
class RunAccess:
    run: Run
    project: Project
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
    """Current User's role-derived access to a repository-visible resource.

    ``role`` is None for Users who only reach the resource through a USE Grant:
    Grants authorize use, never management, so no capabilities are derived.
    """

    resource: SharedResource
    role: MembershipRole | None

    @property
    def capabilities(self) -> frozenset[Capability]:
        return capabilities_of(self.role) if self.role is not None else frozenset()

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            role_name = self.role.value if self.role is not None else "无"
            raise PermissionDenied(f"当前角色（{role_name}）无权{describe(capability)}")


@dataclass(frozen=True, slots=True)
class EnvironmentAccess:
    """Current User's role-derived access to a repository-visible environment."""

    environment: Environment
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

    async def scoped_config_group(self, user_id: str, user_group_id: str, *, manage: bool) -> None:
        """Authorize config without exposing governance capability projections."""
        group = await self._repos.user_groups.get_for_active_member(user_group_id, user_id)
        membership = await self._repos.memberships.get(user_group_id, user_id)
        if group is None or membership is None or not membership.is_active:
            raise ObjectNotFound("User Group", user_group_id)
        required = Capability.CONFIG_MANAGE if manage else Capability.CONFIG_VIEW
        if required not in capabilities_of(membership.role):
            raise PermissionDenied(f"当前角色（{membership.role.value}）无权{describe(required)}")

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

        role: MembershipRole | None = None
        is_owner = False
        if project.owner.kind is OwnerKind.USER:
            if project.owner.id == user_id:
                is_owner = True
                role = MembershipRole.OWNER
        else:
            membership = await self._repos.memberships.get(project.owner.id, user_id)
            if membership is not None and membership.is_active:
                is_owner = True
                role = membership.role

        if not is_owner:
            if project.visibility is not ProjectVisibility.PUBLIC:
                raise ObjectNotFound("Project", project_id)
            if owner_scope:
                # Owner-scope operations (working state, runs, configs) never
                # cross into the public read boundary.
                raise ObjectNotFound("Project", project_id)

        access = ProjectAccess(project=project, role=role, owner_scope=is_owner)
        if needs is not None:
            access.require(needs)
        return access

    async def run(self, user_id: str, run_id: str, *, needs: Capability | None = None) -> RunAccess:
        run = await self._repos.runs.get(run_id)
        if run is None:
            raise ObjectNotFound("Run", run_id)
        try:
            project_access = await self.project(user_id, run.project_id, owner_scope=True)
        except ObjectNotFound as exc:
            raise ObjectNotFound("Run", run_id) from exc
        # owner_scope=True above guarantees project_access.role is a real membership
        # role, never the PUBLIC reader's None.
        role = project_access.role
        if role is None:  # pragma: no cover - enforced by the guard above
            raise ObjectNotFound("Run", run_id)

        access = RunAccess(
            run=run,
            project=project_access.project,
            role=role,
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

        role: MembershipRole | None = None
        if resource.owner.kind is OwnerKind.USER:
            if resource.owner.id == user_id:
                role = MembershipRole.OWNER
        else:
            membership = await self._repos.memberships.get(resource.owner.id, user_id)
            if membership is not None and membership.is_active:
                role = membership.role
        # role stays None for grant-only viewers: USE Grants never add management.

        access = SharedResourceAccess(resource=resource, role=role)
        if needs is not None:
            access.require(needs)
        return access

    async def environment(
        self, user_id: str, environment_id: str, *, needs: Capability | None = None
    ) -> EnvironmentAccess:
        environment = await self._repos.environments.get_discoverable_for_user(
            user_id, environment_id
        )
        if environment is None:
            raise ObjectNotFound("Environment", environment_id)

        if environment.owner.kind is OwnerKind.USER:
            # Repository visibility already proved the exact User owner is the actor.
            role = MembershipRole.OWNER
        else:
            membership = await self._repos.memberships.get(environment.owner.id, user_id)
            if membership is None or not membership.is_active:  # pragma: no cover - SQL guard
                raise ObjectNotFound("Environment", environment_id)
            role = membership.role

        access = EnvironmentAccess(environment=environment, role=role)
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
