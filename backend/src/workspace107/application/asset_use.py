"""Application-layer authorization for using versioned assets in a Project.

Repository reads keep actor-scoped discovery.  This boundary additionally requires the
asset owner to be the consuming Project owner.  Issue #40 can extend this one seam with
an explicit USE Grant; Issue #39 intentionally allows exact same-owner use only.
"""

from __future__ import annotations

from ..domain.models import EnvironmentVersion, SharedResourceVersion
from ..domain.ownership import OwnerReference
from ..domain.ports.repositories import Repositories


async def environment_version_for_owner_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> EnvironmentVersion | None:
    """Return an actor-discoverable Environment Version only for the exact target owner."""
    version = await repos.environments.get_version_discoverable_for_user(user_id, version_id)
    if version is None:
        return None
    environment = await repos.environments.get_discoverable_for_user(
        user_id, version.environment_id
    )
    if environment is None or environment.owner != target_owner:
        return None
    return version


async def shared_resource_version_for_owner_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> SharedResourceVersion | None:
    """Return an actor-discoverable Shared Resource Version for the exact target owner."""
    version = await repos.shared_resources.get_version_discoverable_for_user(user_id, version_id)
    if version is None:
        return None
    resource = await repos.shared_resources.get_discoverable_for_user(
        user_id, version.shared_resource_id
    )
    if resource is None or resource.owner != target_owner:
        return None
    return version
