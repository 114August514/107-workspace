"""测试夹具。

每个测试用独立的临时目录和独立的 SQLite 文件，互不干扰。
调度器是真正的 MockScheduler——集成测试里作业会以子进程真实执行。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from workspace107.api.deps import AppContext, build_services
from workspace107.application.access import AccessGuard
from workspace107.config import Settings
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.tables import Base
from workspace107.main import build_context, create_app
from workspace107.tools.seed import seed_catalog


class FrozenClock:
    """可控时钟。每次调用推进一秒，保证事件顺序稳定又不需要 sleep。"""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._now = self._now.replace(microsecond=0)
        current = self._now
        self._now = current.fromtimestamp(current.timestamp() + 1, tz=UTC)
        return current


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        # 访问日志在测试输出里只是噪音，出问题时临时调回 INFO 即可
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
        scheduler="mock",
        auth_mode="dev",
    )


@pytest.fixture
async def context(settings: Settings) -> AsyncIterator[AppContext]:
    ctx = build_context(settings)
    async with ctx.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session = ctx.session_factory()
    try:
        await seed_catalog(session)
        await session.commit()
    finally:
        await session.close()

    yield ctx
    await ctx.engine.dispose()


@pytest.fixture
async def session(context: AppContext) -> AsyncIterator[AsyncSession]:
    session = context.session_factory()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def services(context: AppContext, session: AsyncSession):
    """直接拿到用例服务，用于绕过 HTTP 的服务层测试。

    它只暴露 application 层的服务，和路由拿到的是同一组东西。
    """
    return build_services(context, session)


@pytest.fixture
def guard(session: AsyncSession) -> AccessGuard:
    """单独构造 AccessGuard，用于直接测试权限解析。

    Services 容器刻意不暴露它——路由不该自己做权限判断。
    测试要测这块逻辑，就在这里自己装一个，和被测服务共用同一个 session。
    """
    return AccessGuard(SqlRepositories(session))


@pytest.fixture
async def client(context: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(context.settings)
    # ASGITransport 不触发 lifespan，这里直接注入进程级依赖。
    app.state.context = context
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-User": "student"},
    ) as http_client:
        yield http_client
