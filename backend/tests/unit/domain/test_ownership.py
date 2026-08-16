from __future__ import annotations

from workspace107.domain.models import User, UserGroup
from workspace107.domain.ownership import OwnerKind, OwnerReference


def test_user_and_user_group_are_distinct_owner_references() -> None:
    user = User(id="usr_alice", username="alice", display_name="Alice")
    group = UserGroup(id="grp_lab", name="Lab", created_by_id=user.id)

    assert user.owner_reference == OwnerReference(kind=OwnerKind.USER, id="usr_alice")
    assert group.owner_reference == OwnerReference(kind=OwnerKind.USER_GROUP, id="grp_lab")
    assert user.owner_reference != group.owner_reference


def test_migrated_user_group_may_truthfully_have_unknown_creator() -> None:
    group = UserGroup(id="ws_legacy", name="Migrated Lab", created_by_id=None)

    assert group.created_by_id is None
