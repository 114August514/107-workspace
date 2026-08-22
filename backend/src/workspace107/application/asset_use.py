"""Application-layer authorization for using versioned assets in a Project.

Repository reads keep actor-scoped discovery.  This boundary additionally requires the
asset owner to be the consuming Project owner.  Issue #40 extends this seam with an
explicit USE Grant: when the asset Owner differs from the consuming Project Owner, a
valid USE Grant pointing at the consuming Owner allows use.
"""

from __future__ import annotations

from ..domain.grant import GrantTargetKind
from ..domain.models import EnvironmentVersion, SharedResourceVersion
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
