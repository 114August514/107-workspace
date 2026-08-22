"""Cross-owner USE Grant use cases.

An asset Owner creates a USE Grant to let another User or User Group reference a
top-level Environment or Shared Resource from their own Project.  Grants do not
confer management permission — only the Owner role on the target asset may create
or revoke a Grant.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.enums import ActivityAction, MembershipRole, TargetType
from ..domain.errors import ConflictError, ObjectNotFound, PermissionDenied
from ..domain.grant import Grant, GrantAction, GrantTargetKind
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .activity import ActivityRecorder
from .ownership import OwnerSummary, owner_summaries


@dataclass(frozen=True, slots=True)
class GrantView:
    grant: Grant
    grantee: OwnerSummary
    target_owner: OwnerSummary


class GrantService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        activity: ActivityRecorder,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._activity = activity

    async def create(
        self,
        user_id: str,
        *,
        target_kind: GrantTargetKind,
        target_id: str,
        grantee: OwnerReference,
    ) -> GrantView:
        """Create a USE Grant.  Only the target asset's Owner may grant."""
        asset_owner = await self._resolve_target_owner(user_id, target_kind, target_id)
        if await self._repos.grants.exists_use_grant(grantee, target_kind, target_id):
            raise ConflictError("该 Grantee 已拥有此资产的 USE Grant")
        grant = Grant(
            id=ids.new_id(ids.GRANT),
            grantee=grantee,
            target_kind=target_kind,
            target_id=target_id,
            action=GrantAction.USE,
            granted_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.grants.add(grant)
        await self._record_activity(user_id, asset_owner, ActivityAction.GRANT_CREATED, grant.id)
        return await self._view(grant, asset_owner)

    async def list_for_target(
        self, user_id: str, target_kind: GrantTargetKind, target_id: str
    ) -> list[GrantView]:
        """List all Grants for a target asset.  Only the asset Owner may list."""
        asset_owner = await self._resolve_target_owner(user_id, target_kind, target_id)
        grants = await self._repos.grants.list_for_target(target_kind, target_id)
        return [await self._view(g, asset_owner) for g in grants]

    async def revoke(self, user_id: str, grant_id: str) -> None:
        """Revoke a Grant.  Only the target asset's Owner may revoke."""
        grant = await self._repos.grants.get(grant_id)
        if grant is None:
            raise ObjectNotFound("Grant", grant_id)
        asset_owner = await self._resolve_target_owner(user_id, grant.target_kind, grant.target_id)
        await self._repos.grants.delete(grant_id)
        await self._record_activity(user_id, asset_owner, ActivityAction.GRANT_REVOKED, grant_id)

    # -- internals ------------------------------------------------------

    async def _resolve_target_owner(
        self, user_id: str, target_kind: GrantTargetKind, target_id: str
    ) -> OwnerReference:
        """Verify the caller is the Owner of the target asset and return its owner."""
        if target_kind is GrantTargetKind.SHARED_RESOURCE:
            access = await self._guard.shared_resource(user_id, target_id)
        else:
            access = await self._guard.environment(user_id, target_id)
        if access.role != MembershipRole.OWNER:
            raise PermissionDenied("只有资产 Owner 可以管理 USE Grant")
        return (
            access.resource.owner
            if target_kind is GrantTargetKind.SHARED_RESOURCE
            else access.environment.owner
        )

    async def _view(self, grant: Grant, asset_owner: OwnerReference) -> GrantView:
        summaries = await owner_summaries(self._repos, (grant.grantee, asset_owner))
        return GrantView(
            grant=grant,
            grantee=summaries[(grant.grantee.kind, grant.grantee.id)],
            target_owner=summaries[(asset_owner.kind, asset_owner.id)],
        )

    async def _record_activity(
        self,
        user_id: str,
        asset_owner: OwnerReference,
        action: ActivityAction,
        grant_id: str,
    ) -> None:
        # Activity is UserGroup-scoped; User-owned assets have no Workspace feed.
        workspace_id = asset_owner.id if asset_owner.kind is OwnerKind.USER_GROUP else None
        if workspace_id is not None:
            await self._activity.record(
                actor_id=user_id,
                workspace_id=workspace_id,
                action=action,
                target_type=TargetType.GRANT,
                target_id=grant_id,
                target_name=grant_id,
            )
