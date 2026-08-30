"""应用装配。

这里是唯一一个把 domain、application 和 infrastructure 接在一起的地方。
换调度器、换存储、换数据库都只改这个文件，用例代码不动。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.deps import AppContext, build_services
from .api.errors import register_error_handlers
from .api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from .api.routes import api_router
from .config import Settings, get_settings
from .domain.ports.scheduler import SchedulerPort
from .infrastructure.clock import SystemClock
from .infrastructure.db.session import create_engine, create_session_factory
from .infrastructure.scheduler import MockScheduler, SlurmRestScheduler
from .infrastructure.storage.local import LocalStorage
from .observability import configure_logging

logger = logging.getLogger(__name__)


def build_scheduler(settings: Settings) -> SchedulerPort:
    if settings.scheduler == "slurm":
        return SlurmRestScheduler(
            base_url=settings.slurm_api_base_url,
            user=settings.slurm_api_user,
            jwt=settings.slurm_jwt,
        )
    return MockScheduler()


def build_context(settings: Settings) -> AppContext:
    settings.ensure_local_directories()
    engine = create_engine(settings)
    return AppContext(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        storage=LocalStorage(settings.storage_root),
        scheduler=build_scheduler(settings),
        clock=SystemClock(),
    )


async def _sync_loop(app: FastAPI, interval: float) -> None:
    """周期性把调度系统的任务状态同步到 Run。

    这是当前实现中 Run 状态的唯一来源。同步失败只记录日志，
    不改动 Run 状态——宁可保留过期状态，也不伪造结果。
    """
    context: AppContext = app.state.context
    while True:
        await asyncio.sleep(interval)
        try:
            session = context.session_factory()
            try:
                services = build_services(context, session)
                changed = await services.lifecycle.sync_all()
                await session.commit()
                if changed:
                    logger.info("同步了 %d 个 Run 的状态", changed)
            finally:
                await session.close()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - 后台任务不应因单次失败退出
            logger.exception("Run 状态同步失败")


async def _shared_resource_publication_loop(app: FastAPI, interval: float) -> None:
    """Claim and process durable Shared Resource publication attempts."""
    context: AppContext = app.state.context
    while True:
        await asyncio.sleep(interval)
        try:
            claim_session = context.session_factory()
            try:
                services = build_services(context, claim_session)
                attempt = await services.shared_resource_publications.claim_next()
                await claim_session.commit()
            finally:
                await claim_session.close()
            if attempt is None:
                continue

            process_session = context.session_factory()
            try:
                services = build_services(context, process_session)
                result = await services.shared_resource_publications.process(attempt.id)
                await process_session.commit()
                logger.info(
                    "Shared Resource 发布尝试 %s 处理完成：%s",
                    result.id,
                    result.status.value,
                )
            finally:
                await process_session.close()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - interrupted claim remains durably recoverable
            logger.exception("Shared Resource 发布处理失败")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level, json_output=resolved.use_json_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.context = build_context(resolved)
        tasks: list[asyncio.Task[None]] = []
        if resolved.run_sync_interval_seconds > 0:
            tasks.append(asyncio.create_task(_sync_loop(app, resolved.run_sync_interval_seconds)))
        if resolved.shared_resource_publication_interval_seconds > 0:
            tasks.append(
                asyncio.create_task(
                    _shared_resource_publication_loop(
                        app, resolved.shared_resource_publication_interval_seconds
                    )
                )
            )
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await app.state.context.engine.dispose()

    app = FastAPI(
        title="107 Workspace API",
        version=__version__,
        description=(
            "面向 USTC 107 算力平台的协作式计算工作空间。\n\n"
            "当前迁移实现支持本地 Mock 执行闭环；真实 Worker、Git / Shared FS "
            "和 Slurm 链路尚未完成验证。"
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
