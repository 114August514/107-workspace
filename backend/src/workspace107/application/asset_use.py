"""Application-layer authorization for using versioned assets in a Project.

Repository reads keep actor-scoped discovery.  This boundary additionally requires the
asset owner to be the consuming Project owner.  Issue #40 extends this seam with an
explicit USE Grant: when the asset Owner differs from the consuming Project Owner, a
valid USE Grant from the asset's current Owner (Grantor) to the consuming Owner or
acting User (Grantee) allows use.  A Grant with Target = ALL covers all Grantor assets.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.grant import Grant, GrantAction, GrantTargetKind, UseQualificationScope
from ..domain.models import Environment, EnvironmentVersion, SharedResource, SharedResourceVersion
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.repositories import Repositories


async def environment_for_owner_use(
    repos: Repositories,
    user_id: str,
    environment_id: str,
    target_owner: OwnerReference,
) -> Environment | None:
    """Return an Environment authorized for one consuming Owner context."""
    environment = await repos.environments.get_discoverable_for_user(user_id, environment_id)
    if environment is not None and environment.owner == target_owner:
        return environment

    environment = await repos.environments.get_by_id(environment_id)
    if environment is None or environment.owner == target_owner:
        return None
    if await _has_use_grant(
        repos,
        user_id,
        target_owner,
        GrantTargetKind.ENVIRONMENT,
        environment.id,
        environment.owner,
    ):
        return environment
    return None


async def environment_version_for_owner_use(
    repos: Repositories,
    user_id: str,
    version_id: str,
    target_owner: OwnerReference,
) -> EnvironmentVersion | None:
    """Return one exact version when its Environment is authorized for the Owner."""
    version = await repos.environments.get_version_by_id(version_id)
    if version is None:
        return None
    environment = await environment_for_owner_use(
        repos, user_id, version.environment_id, target_owner
    )
    return version if environment is not None else None


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
class SharedResourceUseQualification:
    """One actor-level route for using a Shared Resource in Project owner contexts."""

    scope: UseQualificationScope
    eligible_project_owner: OwnerReference | None
    grants: tuple[Grant, ...]


async def shared_resource_use_qualifications(
    repos: Repositories,
    user_id: str,
    resource: SharedResource,
    *,
    active_group_ids: frozenset[str],
) -> tuple[SharedResourceUseQualification, ...]:
    """Describe actor qualifications without making a concrete preflight decision.

    Owner qualification is limited to the asset Owner context. A direct User Grant
    follows the actor into any Project owner context where they can submit. Each
    UserGroup Grant names the exact grantee group that must own the Project.
    """
    owner = resource.owner
    qualifications: list[SharedResourceUseQualification] = []
    if (owner.kind is OwnerKind.USER and owner.id == user_id) or (
        owner.kind is OwnerKind.USER_GROUP and owner.id in active_group_ids
    ):
        qualifications.append(
            SharedResourceUseQualification(
                scope=UseQualificationScope.OWNER,
                eligible_project_owner=None,
                grants=(),
            )
        )

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
    user_grants = tuple(
        grant
        for grant in covering
        if grant.grantee.kind is OwnerKind.USER and grant.grantee.id == user_id
    )
    if user_grants:
        qualifications.append(
            SharedResourceUseQualification(
                scope=UseQualificationScope.USER_GRANT,
                eligible_project_owner=None,
                grants=user_grants,
            )
        )

    grants_by_group: dict[str, list[Grant]] = {}
    for grant in covering:
        if grant.grantee.kind is OwnerKind.USER_GROUP and grant.grantee.id in active_group_ids:
            grants_by_group.setdefault(grant.grantee.id, []).append(grant)
    qualifications.extend(
        SharedResourceUseQualification(
            scope=UseQualificationScope.USER_GROUP_GRANT,
            eligible_project_owner=OwnerReference(OwnerKind.USER_GROUP, group_id),
            grants=tuple(grants),
        )
        for group_id, grants in grants_by_group.items()
    )
    return tuple(qualifications)
