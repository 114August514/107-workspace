"""Application-facing ownership display summaries.

Domain ``OwnerReference`` stays identity-only. Presentation labels are resolved here
with one batched User query and one batched UserGroup query per caller request, so
list endpoints never fall into presenter-level N+1.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.repositories import Repositories


@dataclass(frozen=True, slots=True)
class OwnerSummary:
    kind: OwnerKind
    id: str
    display_name: str


async def owner_summaries(
    repos: Repositories, owners: Iterable[OwnerReference]
) -> dict[tuple[OwnerKind, str], OwnerSummary]:
    """Resolve User display names and UserGroup names in two bounded queries."""

    unique = set(owners)
    user_ids = {owner.id for owner in unique if owner.kind is OwnerKind.USER}
    user_group_ids = {owner.id for owner in unique if owner.kind is OwnerKind.USER_GROUP}
    users = await repos.users.list_by_ids(user_ids)
    user_groups = await repos.user_groups.list_by_ids(user_group_ids)

    resolved: dict[tuple[OwnerKind, str], OwnerSummary] = {}
    for owner in unique:
        if owner.kind is OwnerKind.USER:
            user = users.get(owner.id)
            if user is not None:
                resolved[(owner.kind, owner.id)] = OwnerSummary(
                    kind=owner.kind, id=owner.id, display_name=user.display_name
                )
        else:
            user_group = user_groups.get(owner.id)
            if user_group is not None:
                resolved[(owner.kind, owner.id)] = OwnerSummary(
                    kind=owner.kind, id=owner.id, display_name=user_group.name
                )
    return resolved
