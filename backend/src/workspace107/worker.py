"""Single-active Independent Worker 进程入口。"""

from __future__ import annotations

import asyncio
import logging

from .application.run_worker import RunWorker
from .config import Settings, get_settings
from .domain.ports.scheduler import SchedulerPort
from .infrastructure.db.execution import SqlExecutionStore
from .infrastructure.db.session import create_engine, create_session_factory
from .infrastructure.db.worker_lock import PostgresWorkerLock
from .infrastructure.project_git import GitProjectContent
from .infrastructure.project_version_exporter import GitProjectVersionExporter
from .infrastructure.scheduler import (
    MockScheduler,
    SlurmRestApiContract,
    SlurmRestScheduler,
)
from .infrastructure.storage.run_workspace import PosixRunWorkspace
from .observability import configure_logging

logger = logging.getLogger(__name__)


def build_scheduler(settings: Settings) -> SchedulerPort:
    if settings.scheduler == "slurm":
        return SlurmRestScheduler(
            base_url=settings.slurm_api_base_url,
            user=settings.slurm_api_user,
            jwt=settings.slurm_jwt,
            contract=SlurmRestApiContract(
                target_cluster_id=settings.slurm_target_cluster_id,
                api_version=settings.slurm_api_version,
                schema_profile=settings.slurm_api_schema_profile,
                submit_path=settings.slurm_submit_path,
                job_path_template=settings.slurm_job_path_template,
                jobs_path=settings.slurm_jobs_path,
                cancel_path_template=settings.slurm_cancel_path_template,
                correlation_field=settings.slurm_correlation_field,
                correlation_query_parameter=settings.slurm_correlation_query_parameter,
                correlation_query_complete=settings.slurm_correlation_query_complete,
                correlation_max_bytes=settings.slurm_correlation_max_bytes,
            ),
            runtime_mode=settings.slurm_runtime_mode,
            timeout=settings.slurm_timeout_seconds,
        )
    return MockScheduler()


async def run(settings: Settings) -> None:
    settings.ensure_worker_configuration()
    settings.ensure_local_directories()
    configure_logging(settings.log_level, json_output=settings.use_json_logs)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    lock: PostgresWorkerLock | None = None
    try:
        lock = await PostgresWorkerLock.acquire(
            engine,
            check_interval=max(min(settings.worker_idle_seconds, 1.0), 0.1),
        )
        content = GitProjectContent(settings.storage_root / "projects")
        exporter = GitProjectVersionExporter(factory, content)
        workspace = PosixRunWorkspace(
            settings.storage_root,
            exporter,
            shared_gid=settings.resolved_shared_gid,
        )
        worker = RunWorker(
            store=SqlExecutionStore(factory),
            workspace=workspace,
            scheduler=build_scheduler(settings),
            action_delay_seconds=settings.worker_poll_seconds,
        )
        logger.info("Single-active Independent Worker 已启动")
        while True:
            handled = await lock.run_guarded(worker.run_once())
            if not handled:
                await lock.run_guarded(asyncio.sleep(settings.worker_idle_seconds))
    finally:
        if lock is not None:
            await lock.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run(get_settings()))


if __name__ == "__main__":
    main()
