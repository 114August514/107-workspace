"""HTTP 中间件。

两件事：给每个请求绑定标识并记一条访问日志；在读请求体之前挡住超大请求。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..observability import REQUEST_ID_HEADER, bind_request_id, current_request_id

logger = logging.getLogger("workspace107.access")

Handler = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """绑定 request_id，并为每个请求记一条访问日志。

    响应头也会带上 ``X-Request-Id``：用户报问题时截图里就有它，
    照着去日志里搜就能找到这一次请求的完整经过。
    """

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        request_id = bind_request_id(request.headers.get(REQUEST_ID_HEADER))
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            # 未被捕获的异常同样要留下访问记录，否则日志里会出现一个「没有结果」的请求。
            logger.exception(
                "请求处理失败",
                extra={
                    "method": request.method,
                    # 只记路径不记 query：query 里可能带用户输入，不该进日志
                    "path": request.url.path,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """按 Content-Length 挡住超大请求。

    在读请求体之前就拒绝，避免先把几百兆读进内存再说不行。
    伪造或缺失 Content-Length 的请求挡不住，所以逐个文件的大小限制
    仍然要在用例层再校验一次——这一层只是省掉明显的浪费。
    """

    def __init__(self, app: object, *, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self._max_bytes:
            limit_mb = self._max_bytes // (1024 * 1024)
            return JSONResponse(
                status_code=413,
                content={
                    "code": "request_too_large",
                    "message": f"请求体超过上限 {limit_mb} MB",
                    "problems": [],
                    "request_id": current_request_id(),
                },
            )
        return await call_next(request)
