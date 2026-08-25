"""Application-layer authorization for using versioned assets in a Project.

Repository reads keep actor-scoped discovery.  This boundary additionally requires the
asset owner to be the consuming Project owner.  Issue #40 extends this seam with an
explicit USE Grant: when the asset Owner differs from the consuming Project Owner, a
valid USE Grant from the asset's current Owner (Grantor) to the consuming Owner or
acting User (Grantee) allows use.  A Grant with Target = ALL covers all Grantor assets.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.grant import Grant, GrantAction, GrantTargetKind, UseAvailabilitySource
from ..domain.models import EnvironmentVersion, SharedResource, SharedResourceVersion
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.repositories import Repositories


async def environment_version_for_owner_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> EnvironmentVersion | None:
    """Return an Environment Version authorized for ``target_owner`` use.

    1. Same-owner discovery path (Issue #39): actor-discoverable version whose
       Environment is owned by ``target_owner``.
    2. Grant path (Issue #40): trusted lookup of version + environment; if the
       environment Owner differs from ``target_owner``, a USE Grant for either
       ``target_owner`` or the acting user (as a User grantee) authorizes use.
    """
    # 1. Same-owner path (Issue #39 logic unchanged)
    version = await repos.environments.get_version_discoverable_for_user(user_id, version_id)
    if version is not None:
        environment = await repos.environments.get_discoverable_for_user(
            user_id, version.environment_id
        )
        if environment is not None and environment.owner == target_owner:
            return version
    # 2. Grant path: cross-owner use
    return await _environment_version_for_grant_use(repos, user_id, version_id, target_owner)


async def shared_resource_version_for_owner_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> SharedResourceVersion | None:
    """Return a Shared Resource Version authorized for ``target_owner`` use.

    Same two-path structure as :func:`environment_version_for_owner_use`.
    """
    # 1. Same-owner path (Issue #39 logic unchanged)
    version = await repos.shared_resources.get_version_discoverable_for_user(user_id, version_id)
    if version is not None:
        resource = await repos.shared_resources.get_discoverable_for_user(
            user_id, version.shared_resource_id
        )
        if resource is not None and resource.owner == target_owner:
            return version
    # 2. Grant path: cross-owner use
    return await _shared_resource_version_for_grant_use(repos, user_id, version_id, target_owner)


async def _environment_version_for_grant_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> EnvironmentVersion | None:
    version = await repos.environments.get_version_by_id(version_id)  # trusted lookup
    if version is None:
        return None
    environment = await repos.environments.get_by_id(version.environment_id)  # trusted lookup
    if environment is None:
        return None
    # Cross-owner use only: if the asset Owner IS the target_owner, discovery
    # should have found it in the same-owner path above.  Fail closed here.
    if environment.owner == target_owner:
        return None
    if await _has_use_grant(
        repos,
        user_id,
        target_owner,
        GrantTargetKind.ENVIRONMENT,
        environment.id,
        environment.owner,
    ):
        return version
    return None


async def _shared_resource_version_for_grant_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> SharedResourceVersion | None:
    version = await repos.shared_resources.get_version_by_id(version_id)  # trusted lookup
    if version is None:
        return None
    resource = await repos.shared_resources.get_by_id(version.shared_resource_id)  # trusted lookup
    if resource is None:
        return None
    # Cross-owner use only: same-owner discovery should have succeeded above.
    if resource.owner == target_owner:
        return None
    if await _has_use_grant(
        repos,
        user_id,
        target_owner,
        GrantTargetKind.SHARED_RESOURCE,
        resource.id,
        resource.owner,
    ):
        return version
    return None


async def _has_use_grant(
    repos: Repositories,
    user_id: str,
    target_owner: OwnerReference,
    target_kind: GrantTargetKind,
    target_id: str,
    asset_owner: OwnerReference,
) -> bool:
    """Check for a valid USE Grant matching either the consuming Owner or the
    acting User, issued under the asset's current Owner (GR-408).
    """
    if await repos.grants.exists_use_grant(target_owner, target_kind, target_id, asset_owner):
        return True
    # A personal User-level Grant for the acting user also authorizes use.
    user_grantee = OwnerReference(kind=OwnerKind.USER, id=user_id)
    return await repos.grants.exists_use_grant(user_grantee, target_kind, target_id, asset_owner)


@dataclass(frozen=True, slots=True)
class SharedResourceUseAvailability:
    """当前 User 对某个 Shared Resource 的使用资格。

    ``grants`` 只包含解释当前资格来源、且覆盖该资源的 USE Grant
    （Target = ALL 或精确指向该资源）；``OWNER`` 与 ``UNAVAILABLE`` 时为空。
    """

    source: UseAvailabilitySource
    grants: tuple[Grant, ...]

    @property
    def usable(self) -> bool:
        return self.source is not UseAvailabilitySource.UNAVAILABLE


async def shared_resource_use_availability(
    repos: Repositories,
    user_id: str,
    resource: SharedResource,
    *,
    active_group_ids: frozenset[str],
) -> SharedResourceUseAvailability:
    """Compute the acting User's USE availability for ``resource``.

    Mirrors the two preflight paths of :func:`shared_resource_version_for_owner_use`:
    owner scope first (same-owner path), then USE Grants issued by the resource's
    current Owner to the acting User personally or to a UserGroup they actively
    belong to (grant path).  Discovery itself is not extended here.
    """
    owner = resource.owner
    if owner.kind is OwnerKind.USER:
        if owner.id == user_id:
            return SharedResourceUseAvailability(source=UseAvailabilitySource.OWNER, grants=())
    elif owner.id in active_group_ids:
        return SharedResourceUseAvailability(source=UseAvailabilitySource.OWNER, grants=())

    covering = [
        grant
        for grant in await repos.grants.list_for_grantor(owner)
        if grant.action is GrantAction.USE
        and (
            grant.target_kind is GrantTargetKind.ALL
            or (
                grant.target_kind is GrantTargetKind.SHARED_RESOURCE
                and grant.target_id == resource.id
            )
        )
    ]
    user_grants = [
        grant
        for grant in covering
        if grant.grantee.kind is OwnerKind.USER and grant.grantee.id == user_id
    ]
    if user_grants:
        return SharedResourceUseAvailability(
            source=UseAvailabilitySource.USER_GRANT, grants=tuple(user_grants)
        )
    group_grants = [
        grant
        for grant in covering
        if grant.grantee.kind is OwnerKind.USER_GROUP and grant.grantee.id in active_group_ids
    ]
    if group_grants:
        return SharedResourceUseAvailability(
            source=UseAvailabilitySource.USER_GROUP_GRANT, grants=tuple(group_grants)
        )
    return SharedResourceUseAvailability(source=UseAvailabilitySource.UNAVAILABLE, grants=())
