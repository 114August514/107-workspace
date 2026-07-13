import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from httpx import ASGITransport, AsyncClient

from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.infrastructure.cluster.mock import MockClusterAdapter
from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.workers.reconciler import RunReconciler
from workspace107.main import create_app

from .conftest import ApiHarness, FakeClock
from .run_support import create_workflow, identity


async def test_mock_run_survives_application_reconstruction(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'restart.db'}"
    roots = {
        "source": tmp_path / "transfer" / "source",
        "cluster": tmp_path / "transfer" / "cluster",
        "downloads": tmp_path / "transfer" / "downloads",
    }
    storage_root = tmp_path / "storage"
    mock_root = tmp_path / "mock-cluster"
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))

    first_engine = create_engine(database_url)
    async with first_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    first_factory = create_session_factory(first_engine)
    first_app = create_app(
        uow_factory=lambda: SqlAlchemyUnitOfWork(first_factory),
        storage=LocalStorage(storage_root),
        transfer_roots=roots,
        cluster=MockClusterAdapter(
            mock_root,
            clock=clock,
            queue_seconds=2,
            run_seconds=3,
        ),
        start_reconciler=False,
        clock=clock,
    )
    async with AsyncClient(
        transport=ASGITransport(app=first_app), base_url="http://test"
    ) as client:
        first_harness = ApiHarness(
            client=client,
            app=first_app,
            clock=clock,
            reconciler=first_app.state.reconciler,
            roots=roots,
            mock_root=mock_root,
            storage_root=storage_root,
        )
        workflow = await create_workflow(first_harness)
    await first_engine.dispose()
    assert workflow.run is not None

    second_engine = create_engine(database_url)
    second_factory = create_session_factory(second_engine)
    second_app = create_app(
        uow_factory=lambda: SqlAlchemyUnitOfWork(second_factory),
        storage=LocalStorage(storage_root),
        transfer_roots=roots,
        cluster=MockClusterAdapter(mock_root, clock=clock),
        start_reconciler=False,
        clock=clock,
    )
    clock.advance(2)
    await cast(RunReconciler, second_app.state.reconciler).reconcile_once()
    clock.advance(3)
    await cast(RunReconciler, second_app.state.reconciler).reconcile_once()
    async with AsyncClient(
        transport=ASGITransport(app=second_app), base_url="http://test"
    ) as client:
        fetched = await client.get(
            f"/api/v1/runs/{workflow.run['id']}",
            headers=identity(workflow.user),
        )
        artifacts = await client.get(
            f"/api/v1/runs/{workflow.run['id']}/artifacts",
            headers=identity(workflow.user),
        )
    await second_engine.dispose()

    assert fetched.status_code == 200
    assert fetched.json()["status"] == "succeeded"
    assert artifacts.status_code == 200
    assert artifacts.json()


@dataclass(slots=True)
class CountingReconciler:
    called: asyncio.Event
    calls: int = 0

    async def reconcile_once(self) -> None:
        self.calls += 1
        self.called.set()


async def test_lifespan_starts_and_stops_one_reconciler_loop(tmp_path: Path) -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    factory = create_session_factory(engine)
    counter = CountingReconciler(asyncio.Event())
    app = create_app(
        uow_factory=cast(UnitOfWorkFactory, lambda: SqlAlchemyUnitOfWork(factory)),
        storage=LocalStorage(tmp_path / "storage"),
        cluster=MockClusterAdapter(tmp_path / "mock"),
        reconciler=cast(RunReconciler, counter),
        reconcile_interval_seconds=0.01,
    )

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(counter.called.wait(), timeout=1)
        calls_during_lifespan = counter.calls
    await asyncio.sleep(0.03)
    await engine.dispose()

    assert calls_during_lifespan >= 1
    assert counter.calls == calls_during_lifespan
