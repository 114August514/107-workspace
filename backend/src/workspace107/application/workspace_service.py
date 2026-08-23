"""Private bounded compatibility for child domains still keyed by workspace_id.

Delete this service as #36-#42 migrate their respective tables and routes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.capabilities import Capability
from ..domain.enums import MembershipRole
from ..domain.errors import ObjectNotFound
from ..domain.models import LegacyWorkspace
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .asset_use import environment_version_for_owner_use


@dataclass(frozen=True, slots=True)
class LegacyWorkspaceView:
    workspace: LegacyWorkspace
    role: MembershipRole
    capabilities: frozenset[Capability]


class LegacyWorkspaceService:
    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def get(self, user_id: str, workspace_id: str) -> LegacyWorkspaceView:
        access = await self._guard.legacy_workspace(user_id, workspace_id)
        return LegacyWorkspaceView(
            workspace=access.workspace,
            role=access.role,
            capabilities=access.capabilities,
        )

    async def find_personal(self, user_id: str) -> LegacyWorkspace | None:
        return await self._repos.legacy_workspaces.get_personal(user_id)

    async def set_default_environment(
        self, user_id: str, workspace_id: str, environment_version_id: str | None
    ) -> LegacyWorkspace:
        access = await self._guard.legacy_workspace(
            user_id, workspace_id, needs=Capability.USER_GROUP_UPDATE
        )
        if environment_version_id is not None:
            version = await environment_version_for_owner_use(
                self._repos,
                user_id,
                environment_version_id,
                access.workspace.owner_reference,
            )
            if version is None or not version.available:
                raise ObjectNotFound("Environment Version", environment_version_id)
        access.workspace.default_environment_version_id = environment_version_id
        await self._repos.legacy_workspaces.update(access.workspace)
        return access.workspace
