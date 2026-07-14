from datetime import UTC, datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from workspace107.config import Settings
from workspace107.infrastructure.cluster.mock import MockClusterAdapter
from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.main import create_app

from .conftest import ApiHarness, FakeClock
from .run_support import create_workflow


async def test_configured_transport_is_shared_by_sync_and_run_services(tmp_path: Path) -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    roots = {
        "source": tmp_path / "source",
        "cluster": tmp_path / "cluster",
        "downloads": tmp_path / "downloads",
    }
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    mock_root = tmp_path / "mock"
    storage_root = tmp_path / "storage"
    settings = Settings(
        cluster_transport="ssh",
        transfer_roots=roots,
        storage_root=storage_root,
        mock_cluster_root=mock_root,
        ssh_host="ustc-cluster",
        slurm_remote_root=Path("/cluster/workspace107"),
        slurm_log_root=Path("/cluster/logs"),
        slurm_storage_root=Path("/cluster/storage"),
    )
    app = create_app(
        settings=settings,
        uow_factory=lambda: SqlAlchemyUnitOfWork(factory),
        storage=LocalStorage(storage_root),
        transfer=LocalProjectTransfer(tuple(roots.values())),
        transfer_roots=roots,
        cluster=MockClusterAdapter(mock_root, clock=clock),
        start_reconciler=False,
        clock=clock,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        workflow = await create_workflow(
            ApiHarness(
                client=client,
                app=app,
                clock=clock,
                reconciler=app.state.reconciler,
                roots=roots,
                mock_root=mock_root,
                storage_root=storage_root,
            )
        )
    await engine.dispose()

    assert workflow.preflight["passed"] is True
    assert workflow.run is not None
    assert workflow.run["status"] == "queued"
