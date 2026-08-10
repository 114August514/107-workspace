"""Independent Worker 进程入口：``python -m workspace107.worker``。"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from .application.run_worker import RunWorker
from .config import Settings, get_settings
from .domain.ports.scheduler import SchedulerPort
from .infrastructure.clock import SystemClock
from .infrastructure.db.execution import SqlExecutionStore
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


async def run(settings: Settings) -> None:
    settings.ensure_worker_database()
    settings.ensure_local_directories()
    configure_logging(settings.log_level, json_output=settings.use_json_logs)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    worker = RunWorker(
        worker_id=f"{socket.gethostname()}:{os.getpid()}",
        store=SqlExecutionStore(factory),
        storage=LocalStorage(settings.storage_root),
        scheduler=build_scheduler(settings),
        clock=SystemClock(),
        lease_seconds=settings.worker_lease_seconds,
        poll_seconds=settings.worker_poll_seconds,
    )
    logger.info("Independent Worker 已启动")
    try:
        while True:
            if not await worker.run_once():
                await asyncio.sleep(settings.worker_idle_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run(get_settings()))


if __name__ == "__main__":
    main()
