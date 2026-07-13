import asyncio
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path, PurePosixPath

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
from workspace107.config import Settings, get_settings
from workspace107.domain.errors import DomainError
from workspace107.domain.models import utc_now
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.domain.ports.storage import StoragePort
from workspace107.domain.ports.transfer import ProjectTransferPort
from workspace107.infrastructure.cluster.mock import MockClusterAdapter
from workspace107.infrastructure.cluster.slurm.adapter import SlurmClusterAdapter
from workspace107.infrastructure.cluster.slurm.command_runner import CommandRunner
from workspace107.infrastructure.cluster.slurm.transports.local import LocalCommandRunner
from workspace107.infrastructure.cluster.slurm.transports.ssh import SshCommandRunner
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.infrastructure.transfer.ssh import SshProjectTransfer
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


def _configured_path(path: Path, *, remote: bool) -> PurePosixPath:
    return PurePosixPath(str(path if remote else path.expanduser().resolve()))


def _required_root(roots: Mapping[str, Path], name: str) -> Path:
    root = roots.get(name)
    if root is None:
        raise RuntimeError(f"transfer root {name!r} must be configured")
    return root


def create_app(
    *,
    settings: Settings | None = None,
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
    configured_settings = settings or get_settings()
    interval_seconds = (
        configured_settings.reconcile_interval_seconds
        if reconcile_interval_seconds is None
        else reconcile_interval_seconds
    )
    if interval_seconds <= 0:
        raise ValueError("reconcile interval must be positive")

    owned_engine: AsyncEngine | None = None
    if uow_factory is None:
        owned_engine = create_engine(configured_settings.database_url)
        session_factory = create_session_factory(owned_engine)

        def configured_uow_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(session_factory)

        uow_factory = configured_uow_factory
    configured_storage = storage or LocalStorage(configured_settings.storage_root)
    configured_roots = dict(transfer_roots or configured_settings.transfer_roots)
    remote_transport = configured_settings.cluster_transport == "ssh"
    ssh_host = configured_settings.ssh_host
    if remote_transport and ssh_host is None and (transfer is None or cluster is None):
        raise RuntimeError("SSH host must be configured for the SSH transport")

    if transfer is not None:
        configured_transfer = transfer
    elif remote_transport:
        if ssh_host is None:
            raise RuntimeError("SSH host must be configured for the SSH transport")
        configured_transfer = SshProjectTransfer(
            ssh_host,
            local_roots=(
                _required_root(configured_roots, "source"),
                _required_root(configured_roots, "downloads"),
            ),
            remote_roots=(
                _configured_path(
                    _required_root(configured_roots, "cluster"),
                    remote=True,
                ),
            ),
        )
    else:
        configured_transfer = LocalProjectTransfer(tuple(configured_roots.values()))

    if cluster is None:
        if configured_settings.cluster_adapter == "mock":
            cluster = MockClusterAdapter(configured_settings.mock_cluster_root, clock=clock)
        else:
            runner: CommandRunner
            if remote_transport:
                if ssh_host is None:
                    raise RuntimeError("SSH host must be configured for the SSH transport")
                runner = SshCommandRunner(ssh_host)
            else:
                runner = LocalCommandRunner()
            cluster = SlurmClusterAdapter(
                runner,
                remote_root=_configured_path(
                    configured_settings.slurm_remote_root,
                    remote=remote_transport,
                ),
                log_root=_configured_path(
                    configured_settings.slurm_log_root,
                    remote=remote_transport,
                ),
                project_roots=(
                    _configured_path(
                        _required_root(configured_roots, "cluster"),
                        remote=remote_transport,
                    ),
                ),
                dataset_roots=(
                    _configured_path(
                        configured_settings.slurm_storage_root,
                        remote=remote_transport,
                    ),
                ),
                storage_root=_configured_path(
                    configured_settings.slurm_storage_root,
                    remote=remote_transport,
                ),
                clock=clock,
            )
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
    app.state.project_transport = configured_settings.cluster_transport
    app.state.clock = clock
    app.state.log_poll_interval_seconds = interval_seconds

    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.include_router(router)
    return app
