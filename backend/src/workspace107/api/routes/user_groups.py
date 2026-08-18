"""Public User Group governance API."""

from __future__ import annotations

from fastapi import APIRouter, status

from ...domain.enums import MembershipRole
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(prefix="/user-groups", tags=["user-group"])


@router.get("", response_model=list[s.UserGroupOut], summary="列出我的 User Group")
async def list_user_groups(user: CurrentUser, services: ServicesDep) -> list[s.UserGroupOut]:
    return [p.user_group_out(view) for view in await services.user_groups.list_for_user(user.id)]


@router.post(
    "",
    response_model=s.UserGroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建 User Group",
)
async def create_user_group(
    payload: s.UserGroupCreateIn, user: CurrentUser, services: ServicesDep
) -> s.UserGroupOut:
    return p.user_group_out(
        await services.user_groups.create(user.id, payload.name, payload.description)
    )


@router.get("/{user_group_id}", response_model=s.UserGroupOut, summary="获取 User Group")
async def get_user_group(
    user_group_id: str, user: CurrentUser, services: ServicesDep
) -> s.UserGroupOut:
    return p.user_group_out(await services.user_groups.get(user.id, user_group_id))


@router.patch("/{user_group_id}", response_model=s.UserGroupOut, summary="更新 User Group")
async def update_user_group(
    user_group_id: str,
    payload: s.UserGroupUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.UserGroupOut:
    await services.user_groups.update(
        user.id,
        user_group_id,
        name=payload.name,
        description=payload.description,
    )
    return p.user_group_out(await services.user_groups.get(user.id, user_group_id))


@router.get("/{user_group_id}/members", response_model=list[s.MemberOut], summary="列出 Membership")
async def list_members(
    user_group_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.MemberOut]:
    return [
        p.member_out(view)
        for view in await services.user_groups.list_members(user.id, user_group_id)
    ]


@router.post(
    "/{user_group_id}/members",
    response_model=s.MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="邀请 User Group 成员",
)
async def invite_member(
    user_group_id: str,
    payload: s.MemberInviteIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    await services.user_groups.invite_member(
        user.id, user_group_id, payload.username, MembershipRole(payload.role)
    )
    views = await services.user_groups.list_members(user.id, user_group_id)
    return p.member_out(next(view for view in views if view.user.username == payload.username))


@router.patch(
    "/{user_group_id}/members/{target_user_id}",
    response_model=s.MemberOut,
    summary="修改 Membership Role",
)
async def change_member_role(
    user_group_id: str,
    target_user_id: str,
    payload: s.MemberRoleUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    await services.user_groups.change_member_role(
        user.id, user_group_id, target_user_id, payload.role
    )
    views = await services.user_groups.list_members(user.id, user_group_id)
    return p.member_out(next(view for view in views if view.user.id == target_user_id))


@router.delete(
    "/{user_group_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除 User Group 成员",
)
async def remove_member(
    user_group_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.user_groups.remove_member(user.id, user_group_id, target_user_id)


@router.post(
    "/{user_group_id}/invitation",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="处理 User Group 邀请",
)
async def respond_to_invitation(
    user_group_id: str,
    payload: s.InvitationResponseIn,
    user: CurrentUser,
    services: ServicesDep,
) -> None:
    await services.user_groups.respond_to_invitation(user.id, user_group_id, accept=payload.accept)


@router.post(
    "/{user_group_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="退出 User Group",
)
async def leave_user_group(user_group_id: str, user: CurrentUser, services: ServicesDep) -> None:
    await services.user_groups.leave(user.id, user_group_id)


@router.post(
    "/{user_group_id}/transfer-ownership/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="转让 User Group 所有权",
)
async def transfer_ownership(
    user_group_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.user_groups.transfer_ownership(user.id, user_group_id, target_user_id)
