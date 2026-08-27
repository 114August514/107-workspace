"""Cross-owner USE Grant use cases.

A Grantor (User or User Group) creates a USE Grant to let another User or User
Group (Grantee) reference the Grantor's top-level Environment or Shared Resource
from their own Project.  Target can also be ALL to cover all current and future
Grantor assets.

Grant management requires the ``GRANT_MANAGE`` capability, which is available to
ADMIN and OWNER roles in UserGroup-owned assets, and to the exact User for
User-owned assets.  This deliberately does not hardcode ``MembershipRole.OWNER``
as the asset-Owner check.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability, capabilities_of, describe
from ..domain.errors import ConflictError, ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.grant import Grant, GrantAction, GrantTargetKind
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .ownership import OwnerSummary, owner_summaries


@dataclass(frozen=True, slots=True)
class GrantView:
    grant: Grant
    grantor: OwnerSummary
    grantee: OwnerSummary
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
        grantor: OwnerReference | None = None,
    ) -> GrantView:
        """Create a USE Grant.

        Cross-field invariants:
        - ALL target: ``target_id`` must be empty, ``grantor`` must be supplied
          explicitly, and the caller must have GRANT_MANAGE on that grantor.
        - Environment/SharedResource target: ``target_id`` must be non-empty,
          ``grantor`` is always derived from the target asset's current owner
          (explicit grantor is rejected to prevent cross-owner spoofing).
        """
        if target_kind is GrantTargetKind.ALL:
            if target_id:
                raise ValidationFailed("target_id must be empty when target_kind is 'all'")
            if grantor is None:
                raise ValidationFailed("grantor is required when target_kind is 'all'")
            await self._require_grant_manage(user_id, grantor)
        else:
            if not target_id:
                raise ValidationFailed("target_id is required for asset-specific grants")
            if grantor is not None:
                raise ValidationFailed(
                    "grantor must not be specified for asset-specific grants; "
                    "it is derived from the target asset's owner"
                )
            grantor = await self._resolve_grantor(user_id, target_kind, target_id)
        await self._validate_grantee_exists(grantee)
        if await self._repos.grants.exists_use_grant(grantee, target_kind, target_id, grantor):
            raise ConflictError("该 Grantee 已拥有此 Grantor 的相应 USE Grant")
        grant = Grant(
            id=ids.new_id(ids.GRANT),
            grantor=grantor,
            grantee=grantee,
            target_kind=target_kind,
            target_id=target_id,
            action=GrantAction.USE,
            granted_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.grants.add(grant)
        return await self._view(grant)

    async def list_for_target(
        self, user_id: str, target_kind: GrantTargetKind, target_id: str
    ) -> list[GrantView]:
        """List Grants directly pointing at a specific target asset.

        Requires GRANT_MANAGE capability on the target asset's current owner.
        Only returns grants with an exact ``(target_kind, target_id)`` match;
        ALL-type grants that also cover this asset are NOT included.  Use the
        grantor view (``list_for_grantor``) for a complete authorization picture.
        """
        grantor = await self._resolve_grantor(user_id, target_kind, target_id)
        grants = await self._repos.grants.list_for_target(target_kind, target_id)
        return [await self._view(g) for g in grants if g.grantor == grantor]

    async def list_for_grantor(self, user_id: str, grantor: OwnerReference) -> list[GrantView]:
        """List all Grants issued by ``grantor`` (ALL + asset). Requires GRANT_MANAGE."""
        await self._require_grant_manage(user_id, grantor)
        grants = await self._repos.grants.list_for_grantor(grantor)
        return [await self._view(g) for g in grants]

    async def revoke(self, user_id: str, grant_id: str) -> None:
        """Revoke a Grant. Requires GRANT_MANAGE capability on the grant's grantor."""
        grant = await self._repos.grants.get(grant_id)
        if grant is None:
            raise ObjectNotFound("Grant", grant_id)
        await self._require_grant_manage(user_id, grant.grantor)
        await self._repos.grants.delete(grant_id)

    # -- internals ------------------------------------------------------

    async def _resolve_grantor(
        self, user_id: str, target_kind: GrantTargetKind, target_id: str
    ) -> OwnerReference:
        """Verify the caller can manage Grants on the target and return its owner.

        For User-owned assets the exact owning User is the Grantor.
        For UserGroup-owned assets the caller must be an active member with the
        ``GRANT_MANAGE`` capability (ADMIN or OWNER role).
        """
        if target_kind is GrantTargetKind.ALL:
            raise ObjectNotFound("Grant target", target_id)
        if target_kind is GrantTargetKind.SHARED_RESOURCE:
            access = await self._guard.shared_resource(
                user_id, target_id, needs=Capability.GRANT_MANAGE
            )
            return access.resource.owner
        access = await self._guard.environment(user_id, target_id, needs=Capability.GRANT_MANAGE)
        return access.environment.owner

    async def _require_grant_manage(self, user_id: str, grantor: OwnerReference) -> None:
        """Verify the caller has GRANT_MANAGE on ``grantor`` (User or UserGroup).

        For a User grantor, the caller must be that exact User.
        For a UserGroup grantor, the caller must be an active member with
        GRANT_MANAGE capability (ADMIN or OWNER role).
        """
        if grantor.kind is OwnerKind.USER:
            if grantor.id != user_id:
                raise ObjectNotFound("User", grantor.id)
        else:
            access = await self._guard.user_group(user_id, grantor.id)
            if Capability.GRANT_MANAGE not in capabilities_of(access.role):
                raise PermissionDenied(
                    f"当前角色（{access.role.value}）无权{describe(Capability.GRANT_MANAGE)}"
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

    async def _view(self, grant: Grant) -> GrantView:
        granted_by_ref = OwnerReference(kind=OwnerKind.USER, id=grant.granted_by)
        summaries = await owner_summaries(
            self._repos, (grant.grantor, grant.grantee, granted_by_ref)
        )
        return GrantView(
            grant=grant,
            grantor=summaries[(grant.grantor.kind, grant.grantor.id)],
            grantee=summaries[(grant.grantee.kind, grant.grantee.id)],
            granted_by=summaries[(granted_by_ref.kind, granted_by_ref.id)],
        )
