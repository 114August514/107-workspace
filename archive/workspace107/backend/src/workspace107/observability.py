"""请求追踪与日志。

放在包根目录而不是某一层里，理由和 ``config.py`` 一样：它是横切关注点，
每一层都可能要用，但它自己不依赖任何层，也不依赖 Web 框架。

核心是一条能把「用户看到的报错」和「服务端日志」连起来的线索：

    用户截图里的 request_id
        ↓
    日志里同一个 request_id
        ↓
    这次请求做了什么、在哪一步失败

没有这条线索，线上收到「用不了」的反馈时只能靠猜。
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# 请求标识在协程之间传递。contextvar 而不是全局变量：
# 并发请求各自持有自己的值，互不干扰。
_request_id: ContextVar[str] = ContextVar("request_id", default="")

REQUEST_ID_HEADER = "X-Request-Id"
MAX_REQUEST_ID_LENGTH = 64

# 这些字段是 LogRecord 自带的，不属于业务附加信息。
_RESERVED_LOG_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def new_request_id() -> str:
    return f"req_{uuid4().hex[:20]}"


def current_request_id() -> str:
    """当前请求的标识。不在请求上下文里时返回空串。"""
    return _request_id.get()


def bind_request_id(value: str | None) -> str:
    """绑定请求标识，返回最终使用的值。

    上游（网关、反向代理）传了就沿用，方便跨服务串联；没传就生成一个。
    传进来的值会被截断——它会进日志，不能让调用方塞任意长度的内容。
    """
    resolved = (value or "").strip()[:MAX_REQUEST_ID_LENGTH] or new_request_id()
    _request_id.set(resolved)
    return resolved


class RequestIdFilter(logging.Filter):
    """给每条日志补上当前请求标识。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """输出单行 JSON，方便被日志系统采集和检索。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        # 调用方通过 extra= 传进来的业务字段原样带上
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_FIELDS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """本地开发用的可读格式。"""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "")
        prefix = f"[{request_id}] " if request_id else ""
        return f"{record.levelname:<8} {record.name}: {prefix}{record.getMessage()}"


def configure_logging(level: str, *, json_output: bool) -> None:
    """配置根日志器。只在组合根调用一次。

    生产用 JSON（可采集、可检索），本地开发用文本（人能读）。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn 自己的访问日志和我们的中间件重复，关掉它的那一路。
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
