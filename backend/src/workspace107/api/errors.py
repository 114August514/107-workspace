"""领域错误 -> HTTP 状态码。

注意 :class:`ObjectNotFound` 和 :class:`PermissionDenied` 的区别：
没有发现权限时领域层抛 ``ObjectNotFound`` 并最终返回 404，
错误信息里也不区分「不存在」和「无权访问」。
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain.errors import (
    ConflictError,
    DomainError,
    ObjectNotFound,
    PermissionDenied,
    PreflightRejected,
    SchedulerError,
    ValidationFailed,
)
from ..observability import current_request_id

# 422 直接写数值：Starlette 在 1.x 把常量名从 UNPROCESSABLE_ENTITY 改成了
# UNPROCESSABLE_CONTENT，写死数值可以同时兼容两个版本。
HTTP_422 = 422

_STATUS_BY_TYPE: list[tuple[type[DomainError], int]] = [
    (ObjectNotFound, status.HTTP_404_NOT_FOUND),
    (PermissionDenied, status.HTTP_403_FORBIDDEN),
    # ImmutableObjectError 是 ConflictError 的子类，同样返回 409。
    (ConflictError, status.HTTP_409_CONFLICT),
    (PreflightRejected, HTTP_422),
    (ValidationFailed, HTTP_422),
    (SchedulerError, status.HTTP_502_BAD_GATEWAY),
]


def status_for(error: DomainError) -> int:
    for error_type, http_status in _STATUS_BY_TYPE:
        if isinstance(error, error_type):
            return http_status
    return status.HTTP_400_BAD_REQUEST


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        problems = error.problems if isinstance(error, PreflightRejected) else []
        return JSONResponse(
            status_code=status_for(error),
            content={
                "code": error.code,
                "message": error.message,
                "problems": problems,
                "request_id": current_request_id(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, error: RequestValidationError) -> JSONResponse:
        """把框架的参数校验错误也转成同一种错误体。

        FastAPI 默认返回 HTTPValidationError，形状和领域错误不一样。
        两种形状意味着前端要写两套解析——统一成一种，契约里也只需声明一种。
        """
        problems = [
            f"{'.'.join(str(part) for part in item['loc'][1:]) or '请求体'}：{item['msg']}"
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=HTTP_422,
            content={
                "code": "validation_failed",
                "message": "请求参数不合法",
                "problems": problems,
                "request_id": current_request_id(),
            },
        )
