"""Worker 进程级 PostgreSQL session advisory lock。"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable
from typing import TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

WORKER_LOCK_NAMESPACE = 0x57533130
WORKER_LOCK_KEY = 107
T = TypeVar("T")


class WorkerAlreadyActive(RuntimeError):
    """另一个 Worker session 已持有 M1 全局锁。"""


class WorkerLockLost(RuntimeError):
    """专用 advisory-lock 数据库连接已失效。"""


class PostgresWorkerLock:
    """持有一条专用连接；锁连接失败会中断正在执行的 Worker action。"""

    def __init__(self, connection: AsyncConnection, check_interval: float) -> None:
        self._connection = connection
        self._check_interval = check_interval
        self._lost = asyncio.Event()
        self._failure: BaseException | None = None
        self._monitor = asyncio.create_task(self._monitor_connection())

    @classmethod
    async def acquire(cls, engine: AsyncEngine, *, check_interval: float) -> PostgresWorkerLock:
        if engine.dialect.name != "postgresql":
            raise ValueError("Independent Worker advisory lock 必须使用 PostgreSQL")
        connection = await engine.connect()
        try:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:namespace, :key)"),
                {"namespace": WORKER_LOCK_NAMESPACE, "key": WORKER_LOCK_KEY},
            )
            await connection.commit()
            if acquired is not True:
                raise WorkerAlreadyActive("另一个 Independent Worker 已持有全局 advisory lock")
            return cls(connection, check_interval)
        except BaseException:
            await connection.close()
            raise

    async def run_guarded(self, operation: Awaitable[T]) -> T:
        action = asyncio.create_task(operation)
        lost = asyncio.create_task(self.wait_lost())
        done, _ = await asyncio.wait((action, lost), return_when=asyncio.FIRST_COMPLETED)
        if lost in done:
            action.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await action
            await lost
            raise AssertionError("wait_lost 必须抛出 WorkerLockLost")  # pragma: no cover
        lost.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lost
        return await action

    async def wait_lost(self) -> None:
        await self._lost.wait()
        raise WorkerLockLost("Worker advisory-lock 连接已失效") from self._failure

    async def close(self) -> None:
        self._monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._monitor
        if not self._lost.is_set():
            with contextlib.suppress(Exception):
                await self._connection.execute(
                    text("SELECT pg_advisory_unlock(:namespace, :key)"),
                    {"namespace": WORKER_LOCK_NAMESPACE, "key": WORKER_LOCK_KEY},
                )
                await self._connection.commit()
        await self._connection.close()

    async def _monitor_connection(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._check_interval)
                await self._connection.execute(text("SELECT 1"))
                await self._connection.commit()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            self._failure = exc
            self._lost.set()
