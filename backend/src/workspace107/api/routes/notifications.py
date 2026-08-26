"""Recipient-authorized notification center.

Notifications remain readable after target access changes, but every read and mutation
is scoped to the current recipient. Targets use only current User Group, Project, or Run routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(prefix="/notifications", tags=["notification"])


@router.get("", response_model=s.PageOut[s.NotificationOut], summary="我的通知")
async def list_notifications(
    user: CurrentUser,
    services: ServicesDep,
    page: PageDep,
    unread_only: bool = Query(False, description="只看未读"),
) -> s.PageOut[s.NotificationOut]:
    """分页返回当前用户收到的通知，可筛选未读项。"""
    result = await services.notifications.list_for_user(user.id, page, unread_only=unread_only)
    return p.page_out(result, p.notification_out)


@router.get("/unread-count", response_model=s.UnreadCountOut, summary="未读数")
async def unread_count(user: CurrentUser, services: ServicesDep) -> s.UnreadCountOut:
    """仅统计当前用户收到且尚未读取的通知。"""
    return s.UnreadCountOut(unread=await services.notifications.count_unread(user.id))


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="将通知标记为已读",
)
async def mark_read(notification_id: str, user: CurrentUser, services: ServicesDep) -> None:
    """仅处理当前用户的通知；不存在、已读或不属于当前用户时同样返回成功。"""
    # 不存在、已读过、或者不是自己的，都当作已经处理完了。
    # 分别返回不同状态码没有意义，反而会泄露「这个 ID 存在」。
    await services.notifications.mark_read(user.id, notification_id)


@router.post("/read-all", response_model=s.UnreadCountOut, summary="全部标记为已读")
async def mark_all_read(user: CurrentUser, services: ServicesDep) -> s.UnreadCountOut:
    """将当前用户的全部未读通知标记为已读，并返回归零后的未读数。"""
    await services.notifications.mark_all_read(user.id)
    return s.UnreadCountOut(unread=0)
