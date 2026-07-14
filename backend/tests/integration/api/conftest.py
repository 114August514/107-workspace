from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from workspace107.infrastructure.cluster.mock import MockClusterAdapter
from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.workers.reconciler import RunReconciler
from workspace107.main import create_app


@dataclass(slots=True)
class FakeClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@dataclass(frozen=True, slots=True)
class ApiHarness:
    client: AsyncClient
    app: FastAPI
    clock: FakeClock
    reconciler: RunReconciler
    roots: dict[str, Path]
    mock_root: Path
    storage_root: Path
    queue_seconds: float = 2.0
    run_seconds: float = 3.0


@asynccontextmanager
async def api_harness(
    root: Path,
    *,
    outcome: Literal["success", "failure"] = "success",
) -> AsyncGenerator[ApiHarness]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    roots = {
        "source": root / "transfer" / "source",
        "cluster": root / "transfer" / "cluster",
        "downloads": root / "transfer" / "downloads",
    }
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    mock_root = root / "mock-cluster"
    storage_root = root / "storage"
    cluster = MockClusterAdapter(
        mock_root,
        clock=clock,
        queue_seconds=2.0,
        run_seconds=3.0,
        outcome=outcome,
    )
    app = create_app(
        uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        storage=LocalStorage(storage_root),
        transfer_roots=roots,
        cluster=cluster,
        start_reconciler=False,
        clock=clock,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as current:
        yield ApiHarness(
            client=current,
            app=app,
            clock=clock,
            reconciler=app.state.reconciler,
            roots=roots,
            mock_root=mock_root,
            storage_root=storage_root,
        )
    await engine.dispose()


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    app = create_app(
        uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        storage=LocalStorage(tmp_path / "storage"),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as current:
        yield current

    await engine.dispose()


@pytest.fixture
async def run_api(tmp_path: Path) -> AsyncIterator[ApiHarness]:
    async with api_harness(tmp_path / "success-api") as harness:
        yield harness


@pytest.fixture
async def failure_api(tmp_path: Path) -> AsyncIterator[ApiHarness]:
    async with api_harness(tmp_path / "failure-api", outcome="failure") as harness:
        yield harness
