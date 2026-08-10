"""目标集群调度端口。

底层调度系统是状态事实来源；端口不提供伪造成功状态的入口。提交由完整稳定的
``correlation`` 标识，响应不确定时只能先调用 ``find_by_correlation`` 恢复。
查询结果用 ``complete`` 区分权威的零匹配与网络、权限、分页或 schema 不确定；
调用方绝不能把 ``complete=False`` 的空列表当成没有作业。
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
    """一次逻辑执行的完整稳定标识；不能退化为可能截断的 job name。"""
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
class SchedulerCorrelatedJob:
    """按 correlation 找到的一个调度作业。"""

    job_id: str


@dataclass(frozen=True, slots=True)
class SchedulerCorrelationResult:
    """correlation 查询结果及其完整性。"""

    complete: bool
    jobs: tuple[SchedulerCorrelatedJob, ...] = ()


class SchedulerPort(Protocol):
    """底层调度系统适配器。"""

    name: str

    async def submit(self, submission: SchedulerSubmission) -> str:
        """提交任务，返回调度任务标识。

        明确拒绝与结果不确定必须使用不同异常类型；不确定时禁止直接重提。
        """
        ...

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        """查找逻辑执行对应作业；只有 ``complete=True`` 的零匹配才是权威零。"""
        ...

    async def poll(self, job_id: str) -> SchedulerJobState:
        """查询任务当前状态；不可见或未映射状态返回 ``UNKNOWN``。"""
        ...

    async def cancel(self, job_id: str) -> None:
        """请求取消任务。取消是异步的，最终状态仍以 poll 结果为准。"""
        ...
