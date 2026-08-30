"""调度端口。

当前实现把底层调度系统作为实际调度状态来源，不在 107 内重新实现调度算法。

因此这个端口**只有** submit / poll / cancel 三个方法，
刻意不提供任何「把任务标记为成功」的入口——Run 状态只能由 poll 结果驱动。
平台记录与调度系统不一致时，保留异常状态并同步或人工处置，不伪造成功。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ..compute import ResolvedSchedulerConfiguration


class SchedulerState(StrEnum):
    """底层调度系统报告的任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    """调度系统里查不到这个任务。属于异常状态，不能当成成功处理。"""


@dataclass(frozen=True, slots=True)
class SchedulerSubmission:
    """一次提交请求。

    所有内容都来自 Run Snapshot，提交阶段不再读取 Run Configuration。
    """

    run_id: str
    job_name: str
    work_dir: Path
    command: str
    environment_execution_spec: dict[str, object]
    stdout_path: Path
    stderr_path: Path
    configuration: ResolvedSchedulerConfiguration
    environment: dict[str, str] = field(default_factory=dict)
    """已经注入 Secret 明文的最终环境变量。不得写入数据库或日志。"""


@dataclass(frozen=True, slots=True)
class SchedulerJobState:
    """一次轮询返回的任务状态。"""

    state: SchedulerState
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reason: str = ""


class SchedulerPort(Protocol):
    """底层调度系统适配器。"""

    name: str

    async def submit(self, submission: SchedulerSubmission) -> str:
        """提交任务，返回调度任务标识。失败时抛 ``SchedulerError``。"""
        ...

    async def poll(self, job_id: str) -> SchedulerJobState:
        """查询任务当前状态。"""
        ...

    async def cancel(self, job_id: str) -> None:
        """请求取消任务。取消是异步的，最终状态仍以 poll 结果为准。"""
        ...
