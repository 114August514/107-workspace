"""通知中心。

**这些接口不做 Workspace 权限校验**，只按当前用户过滤。通知是发给这个人的，
与他现在还能不能看见相关对象无关——被移除的成员已经看不到那个空间，
但「你被移除了」这条必须还能读到（ADR-0003）。
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
    result = await services.notifications.list_for_user(user.id, page, unread_only=unread_only)
    return p.page_out(result, p.notification_out)


@router.get("/unread-count", response_model=s.UnreadCountOut, summary="未读数")
async def unread_count(user: CurrentUser, services: ServicesDep) -> s.UnreadCountOut:
    return s.UnreadCountOut(unread=await services.notifications.count_unread(user.id))


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="标记一条为已读",
)
async def mark_read(notification_id: str, user: CurrentUser, services: ServicesDep) -> None:
    # 不存在、已读过、或者不是自己的，都当作已经处理完了。
    # 分别返回不同状态码没有意义，反而会泄露「这个 ID 存在」。
    await services.notifications.mark_read(user.id, notification_id)


@router.post("/read-all", response_model=s.UnreadCountOut, summary="全部标记为已读")
async def mark_all_read(user: CurrentUser, services: ServicesDep) -> s.UnreadCountOut:
    await services.notifications.mark_all_read(user.id)
    return s.UnreadCountOut(unread=0)
