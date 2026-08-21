"""HTTP 路由。"""

from typing import Any

from fastapi import APIRouter

from ..schemas import ErrorOut
from . import (
    catalog,
    configuration,
    health,
    home,
    notifications,
    projects,
    runs,
    shared_resources,
    user_groups,
    workspaces,
)

# 错误响应也是契约的一部分。不声明的话 OpenAPI 里就没有它，
# 前端只能靠猜错误体长什么样——那就又回到「瞎猜接口」了。
COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorOut, "description": "请求不合法"},
    403: {"model": ErrorOut, "description": "对象可见，但当前角色无权执行该操作"},
    404: {"model": ErrorOut, "description": "对象不存在，或当前用户没有发现权限"},
    409: {"model": ErrorOut, "description": "与现有状态冲突，例如重名或对象不可修改"},
    422: {"model": ErrorOut, "description": "参数校验或提交前检查未通过，problems 列出全部原因"},
    502: {"model": ErrorOut, "description": "底层调度系统返回错误"},
}

api_router = APIRouter(prefix="/api/v1", responses=COMMON_ERRORS)
api_router.include_router(health.router)
api_router.include_router(home.router)
api_router.include_router(user_groups.router)
api_router.include_router(configuration.router)
api_router.include_router(workspaces.router)
api_router.include_router(projects.router)
api_router.include_router(runs.router)
api_router.include_router(catalog.router)
api_router.include_router(notifications.router)
api_router.include_router(shared_resources.router)

__all__ = ["api_router"]
