import pytest

from workspace107.application.access import AccessGuard
from workspace107.domain.enums import MembershipRole, MembershipStatus
from workspace107.domain.errors import ObjectNotFound, PermissionDenied
from workspace107.domain.models import Membership, UserGroup


class _Groups:
    async def get_for_active_member(self, group_id: str, user_id: str):
        return UserGroup(id=group_id, name="g") if user_id != "foreign" else None


class _Memberships:
    def __init__(self, role: MembershipRole, status: MembershipStatus = MembershipStatus.ACTIVE):
        self.membership = Membership("m", "g", "u", role, status)

    async def get(self, group_id: str, user_id: str):
        return self.membership if user_id != "foreign" else None


class _Repos:
    def __init__(self, role: MembershipRole, status: MembershipStatus = MembershipStatus.ACTIVE):
        self.user_groups = _Groups()
        self.memberships = _Memberships(role, status)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(MembershipRole))
async def test_config_group_view_follows_active_membership(role: MembershipRole) -> None:
    await AccessGuard(_Repos(role)).scoped_config_group("u", "g", manage=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [MembershipRole.OWNER, MembershipRole.ADMIN])
async def test_only_admin_and_owner_manage_group_config(role: MembershipRole) -> None:
    await AccessGuard(_Repos(role)).scoped_config_group("u", "g", manage=True)


@pytest.mark.asyncio
async def test_member_cannot_manage_group_config() -> None:
    with pytest.raises(PermissionDenied):
        await AccessGuard(_Repos(MembershipRole.MEMBER)).scoped_config_group("u", "g", manage=True)


@pytest.mark.asyncio
async def test_inactive_or_foreign_group_members_are_hidden() -> None:
    with pytest.raises(ObjectNotFound):
        await AccessGuard(_Repos(MembershipRole.OWNER, MembershipStatus.LEFT)).scoped_config_group(
            "u", "g", manage=False
        )
    with pytest.raises(ObjectNotFound):
        await AccessGuard(_Repos(MembershipRole.OWNER)).scoped_config_group(
            "foreign", "g", manage=False
        )
