"""HTTP API composition root.

Scheduler credentials and execution progression belong exclusively to the independent Worker.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.deps import AppContext
from .api.errors import register_error_handlers
from .api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from .api.routes import api_router
from .config import Settings, get_settings
from .infrastructure.clock import SystemClock
from .infrastructure.db.session import create_engine, create_session_factory
from .infrastructure.project_git import GitProjectContent
from .infrastructure.storage.local import LocalStorage
from .observability import configure_logging


def build_context(settings: Settings) -> AppContext:
    settings.ensure_local_directories()
    engine = create_engine(settings)
    return AppContext(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        storage=LocalStorage(settings.storage_root),
        project_content=GitProjectContent(settings.storage_root / "projects"),
        clock=SystemClock(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level, json_output=resolved.use_json_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.context = build_context(resolved)
        try:
            yield
        finally:
            await app.state.context.engine.dispose()

    app = FastAPI(
        title="107 Workspace API",
        version=__version__,
        description=(
            "面向 USTC 107 算力平台的协作式计算工作空间。\n\n"
            "Run 由独立 Worker 从持久执行意图推进；真实 107 service identity、"
            "Shared FS、Slurm profile 与 credential lifecycle 尚未完成验收。"
        ),
        lifespan=lifespan,
    )

    # 本地开发时前端跑在 5174 端口。生产部署由反向代理同源提供，不需要放开 CORS。
    if resolved.env == "local":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 中间件是后加的先执行，所以请求标识要最后加——
    # 这样它包在最外层，body 超限那种早退响应也能带上 X-Request-Id。
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=resolved.max_request_bytes)
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)
    app.include_router(api_router)
    return app
