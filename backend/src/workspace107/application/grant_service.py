"""Cross-owner USE Grant use cases.

An asset Owner creates a USE Grant to let another User or User Group reference a
top-level Environment or Shared Resource from their own Project.  Grants do not
confer management permission — only the Owner role on the target asset may create
or revoke a Grant.

``grantor_owner`` (the asset Owner at creation time) is persisted on the Grant row.
GR-408: after an asset Ownership transfer, Grants issued under the old Owner are
automatically invalid because ``exists_use_grant`` checks ``grantor_owner == current
asset owner``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.enums import MembershipRole
from ..domain.errors import ConflictError, ObjectNotFound, PermissionDenied
from ..domain.grant import Grant, GrantAction, GrantTargetKind
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .ownership import OwnerSummary, owner_summaries


@dataclass(frozen=True, slots=True)
class GrantView:
    grant: Grant
    grantee: OwnerSummary
    target_owner: OwnerSummary
    granted_by: OwnerSummary


class GrantService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock

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
        await self._validate_grantee_exists(grantee)
        if await self._repos.grants.exists_use_grant(grantee, target_kind, target_id, asset_owner):
            raise ConflictError("该 Grantee 已拥有此资产的 USE Grant")
        grant = Grant(
            id=ids.new_id(ids.GRANT),
            grantee=grantee,
            target_kind=target_kind,
            target_id=target_id,
            action=GrantAction.USE,
            granted_by=user_id,
            grantor_owner=asset_owner,
            created_at=self._clock.now(),
        )
        await self._repos.grants.add(grant)
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
        await self._resolve_target_owner(user_id, grant.target_kind, grant.target_id)
        await self._repos.grants.delete(grant_id)

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

    async def _validate_grantee_exists(self, grantee: OwnerReference) -> None:
        """Reject grants to nonexistent Users or UserGroups (stable 404)."""
        if grantee.kind is OwnerKind.USER:
            user = await self._repos.users.get(grantee.id)
            if user is None:
                raise ObjectNotFound("User", grantee.id)
        else:
            group = await self._repos.user_groups.get(grantee.id)
            if group is None:
                raise ObjectNotFound("UserGroup", grantee.id)

    async def _view(self, grant: Grant, asset_owner: OwnerReference) -> GrantView:
        granted_by_ref = OwnerReference(kind=OwnerKind.USER, id=grant.granted_by)
        summaries = await owner_summaries(self._repos, (grant.grantee, asset_owner, granted_by_ref))
        return GrantView(
            grant=grant,
            grantee=summaries[(grant.grantee.kind, grant.grantee.id)],
            target_owner=summaries[(asset_owner.kind, asset_owner.id)],
            granted_by=summaries[(granted_by_ref.kind, granted_by_ref.id)],
        )
