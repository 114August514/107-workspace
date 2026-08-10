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


async def run(settings: Settings) -> None:
    settings.ensure_worker_database()
    settings.ensure_local_directories()
    configure_logging(settings.log_level, json_output=settings.use_json_logs)
    engine = create_engine(settings)
    lock: PostgresWorkerLock | None = None
    try:
        lock = await PostgresWorkerLock.acquire(
            engine,
            check_interval=max(min(settings.worker_idle_seconds, 1.0), 0.1),
        )
        worker = RunWorker(
            store=SqlExecutionStore(create_session_factory(engine)),
            storage=LocalStorage(settings.storage_root),
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
