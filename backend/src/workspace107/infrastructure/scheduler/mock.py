"""Mock 调度适配器。

它在本机以子进程**真实执行**作业，而不是伪造状态——这样开发、测试和演示
走的是同一条代码路径，只有排队和资源分配被省略了。

状态来自子进程的真实退出码，适配器不提供任何
「把任务标记为成功」的入口。查不到任务时返回 ``UNKNOWN``，
由上层保留异常状态，不伪造成功。
"""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import IO
from uuid import uuid4

from ...domain.errors import SchedulerError
from ...domain.ports.scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerState,
    SchedulerSubmission,
)
from .script import render_sbatch_script

# 用户作业只继承这些基础变量。
#
# 平台服务进程的环境里可能有 WORKSPACE107_SLURM_JWT、数据库口令这类东西，
# 整份 os.environ 传给用户作业等于把它们直接交出去。用户需要的变量应当
# 通过 Run Configuration 的 environment 显式声明。
INHERITED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR", "SHELL", "USER")


def build_job_environment(submission: SchedulerSubmission) -> dict[str, str]:
    base = {name: os.environ[name] for name in INHERITED_ENV if name in os.environ}
    return {**base, **submission.environment}


@dataclass
class _MockJob:
    process: asyncio.subprocess.Process
    correlation: str
    stdout: IO[bytes]
    stderr: IO[bytes]
    started_at: datetime
    finished_at: datetime | None = None
    cancelled: bool = False


class MockScheduler:
    """本机进程调度器。"""

    name = "mock"

    def __init__(self, *, cancel_grace_seconds: float = 1.0) -> None:
        if cancel_grace_seconds < 0:
            raise ValueError("cancel_grace_seconds must be non-negative")
        self._cancel_grace_seconds = cancel_grace_seconds
        self._jobs: dict[str, _MockJob] = {}

    async def submit(self, submission: SchedulerSubmission) -> str:
        work_dir = submission.work_dir
        if not work_dir.exists():
            work_dir.mkdir(parents=True, exist_ok=True)

        # 把渲染出的作业脚本留在 Run 目录里，用户可以直接看到平台生成了什么。
        script_path = submission.stdout_path.parent.parent / "job.sh"
        script_path.write_text(render_sbatch_script(submission), encoding="utf-8")
        os.chown(script_path, -1, submission.stdout_path.parent.stat().st_gid)
        script_path.chmod(0o660)

        environment = build_job_environment(submission)
        stdout = submission.stdout_path.open("ab")
        stderr = submission.stderr_path.open("ab")
        shell_options = {"executable": "/bin/bash", "start_new_session": True}

        try:
            process = await asyncio.create_subprocess_shell(
                submission.command,
                cwd=str(work_dir),
                stdout=stdout,
                stderr=stderr,
                env=environment,
                **shell_options,
            )
        except OSError as exc:  # pragma: no cover - 取决于宿主机环境
            stdout.close()
            stderr.close()
            raise SchedulerError(f"无法启动任务：{exc}") from exc

        job_id = f"mock-{uuid4().hex[:12]}"
        self._jobs[job_id] = _MockJob(
            process=process,
            correlation=submission.correlation,
            stdout=stdout,
            stderr=stderr,
            started_at=datetime.now(UTC),
        )
        return job_id

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        job_ids = tuple(
            job_id for job_id, job in self._jobs.items() if job.correlation == correlation
        )
        return SchedulerCorrelationResult(complete=True, job_ids=job_ids)

    async def poll(self, job_id: str) -> SchedulerJobState:
        job = self._jobs.get(job_id)
        if job is None:
            # The registry is process-local. After Worker restart the backend has lost both
            # observability and control; UNKNOWN keeps that local-only limitation explicit.
            return SchedulerJobState(
                state=SchedulerState.UNKNOWN,
                reason=(
                    f"Mock task {job_id} is absent from the process-local registry; "
                    "Worker restart loses observability and control"
                ),
            )

        return_code = job.process.returncode
        if return_code is None:
            return SchedulerJobState(state=SchedulerState.RUNNING, started_at=job.started_at)

        if job.finished_at is None:
            job.finished_at = datetime.now(UTC)
            job.stdout.close()
            job.stderr.close()

        if job.cancelled:
            return SchedulerJobState(
                state=SchedulerState.CANCELLED,
                exit_code=return_code,
                started_at=job.started_at,
                finished_at=job.finished_at,
                reason="任务已被取消",
            )
        if return_code != 0:
            return SchedulerJobState(
                state=SchedulerState.FAILED,
                exit_code=return_code,
                started_at=job.started_at,
                finished_at=job.finished_at,
                reason=f"任务退出码为 {return_code}",
            )
        return SchedulerJobState(
            state=SchedulerState.COMPLETED,
            exit_code=return_code,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    async def cancel(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            raise SchedulerError(f"调度系统中没有任务 {job_id} 的记录")
        job.cancelled = True
        if job.process.returncode is not None:
            return

        process_group = job.process.pid
        try:
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            return
        await asyncio.sleep(self._cancel_grace_seconds)
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            pass
        else:
            os.killpg(process_group, signal.SIGKILL)
        await job.process.wait()

    async def close(self) -> None:
        """Graceful Worker shutdown must not leave owned local workloads running."""
        for job_id, job in tuple(self._jobs.items()):
            if job.process.returncode is None:
                await self.cancel(job_id)
            if job.finished_at is None:
                job.finished_at = datetime.now(UTC)
                job.stdout.close()
                job.stderr.close()

    async def wait_for_exit(self, job_id: str, *, seconds: float = 30.0) -> None:
        """等待任务结束。仅供测试和 demo 脚本使用，不属于 SchedulerPort。"""
        job = self._jobs.get(job_id)
        if job is None:
            raise SchedulerError(f"调度系统中没有任务 {job_id} 的记录")
        async with asyncio.timeout(seconds):
            await job.process.wait()
