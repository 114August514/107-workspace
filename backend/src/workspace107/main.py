import asyncio
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from workspace107.api.errors import (
    ApiProblem,
    api_problem_handler,
    domain_error_handler,
    request_validation_handler,
)
from workspace107.api.router import router
from workspace107.config import get_settings
from workspace107.domain.errors import DomainError
from workspace107.domain.models import utc_now
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.domain.ports.storage import StoragePort
from workspace107.domain.ports.transfer import ProjectTransferPort
from workspace107.infrastructure.cluster.mock import MockClusterAdapter
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.infrastructure.workers.reconciler import RunReconciler


async def _reconcile_loop(
    reconciler: RunReconciler,
    stop: asyncio.Event,
    interval_seconds: float,
) -> None:
    while not stop.is_set():
        await reconciler.reconcile_once()
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)


def create_app(
    *,
    uow_factory: UnitOfWorkFactory | None = None,
    storage: StoragePort | None = None,
    transfer: ProjectTransferPort | None = None,
    transfer_roots: Mapping[str, Path] | None = None,
    cluster: ClusterPort | None = None,
    reconciler: RunReconciler | None = None,
    start_reconciler: bool = True,
    reconcile_interval_seconds: float | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
    settings = get_settings()
    interval_seconds = (
        settings.reconcile_interval_seconds
        if reconcile_interval_seconds is None
        else reconcile_interval_seconds
    )
    if interval_seconds <= 0:
        raise ValueError("reconcile interval must be positive")

    owned_engine: AsyncEngine | None = None
    if uow_factory is None:
        owned_engine = create_engine(settings.database_url)
        session_factory = create_session_factory(owned_engine)

        def configured_uow_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(session_factory)

        uow_factory = configured_uow_factory
    configured_storage = storage or LocalStorage(settings.storage_root)
    configured_roots = dict(transfer_roots or settings.transfer_roots)
    configured_transfer = transfer or LocalProjectTransfer(tuple(configured_roots.values()))
    if cluster is None:
        if settings.cluster_adapter != "mock":
            raise RuntimeError("the configured cluster adapter is not available")
        cluster = MockClusterAdapter(settings.mock_cluster_root, clock=clock)
    configured_reconciler = reconciler or RunReconciler(
        uow_factory,
        cluster,
        configured_storage,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop = asyncio.Event()
        task: asyncio.Task[None] | None = None
        if start_reconciler:
            task = asyncio.create_task(
                _reconcile_loop(configured_reconciler, stop, interval_seconds),
                name="workspace107-run-reconciler",
            )
        try:
            yield
        finally:
            try:
                if task is not None:
                    stop.set()
                    await task
            finally:
                if owned_engine is not None:
                    await owned_engine.dispose()

    app = FastAPI(title="107 Workspace API", version="0.1.0", lifespan=lifespan)
    if owned_engine is not None:
        app.state.database_engine = owned_engine
    app.state.uow_factory = uow_factory
    app.state.storage = configured_storage
    app.state.transfer_roots = configured_roots
    app.state.transfer = configured_transfer
    app.state.cluster = cluster
    app.state.reconciler = configured_reconciler
    app.state.project_transport = settings.cluster_transport
    app.state.clock = clock
    app.state.log_poll_interval_seconds = interval_seconds

    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.include_router(router)
    return app
