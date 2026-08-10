"""调度端口。

调度系统是实际状态来源，端口既不提供「标记成功」入口，也不把查询失败
伪装成「没有任务」。提交 correlation 必须能精确对应完整 Run identity；
只有 ``reconcile.complete`` 为真时，空结果才是可安全重提的权威事实。
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
    correlation: str
    """完整、稳定的逻辑执行关联值。禁止使用会截断的展示名。"""
    job_name: str
    work_dir: Path
    command: str
    setup_command: str
    environment_image: str
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


@dataclass(frozen=True, slots=True)
class SchedulerCorrelationResult:
    """按 correlation 查询 Scheduler 的完整性与匹配结果。"""

    complete: bool
    job_ids: tuple[str, ...] = ()
    reason: str = ""


class SchedulerPort(Protocol):
    """底层调度系统适配器。"""

    name: str

    async def submit(self, submission: SchedulerSubmission) -> str:
        """返回 job id；确定未创建抛 SubmissionRejected，其余歧义抛 SubmissionUncertain。"""
        ...

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        """查询 correlation；权限、网络或分页不完整时必须返回 complete=False。"""
        ...

    async def poll(self, job_id: str) -> SchedulerJobState:
        """查询任务当前状态。"""
        ...

    async def cancel(self, job_id: str) -> None:
        """请求取消任务。取消是异步的，最终状态仍以 poll 结果为准。"""
        ...
