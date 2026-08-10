"""Slurm REST 调度适配器。

通过 Slurm REST API 提交作业。认证使用 SLURM_JWT，它等价于密码，
只能从环境变量注入，不写入代码、日志或数据库。

状态映射按 Slurm 返回值进行：Slurm 报什么状态就映射什么状态。查不到作业时返回
``UNKNOWN``，由上层保留异常状态并同步或人工处置，不伪造成功。

> 说明：当前迁移实现默认使用 ``mock``，尚未完成现行 M1 要求的真实 Slurm 验证。
> 本适配器的接口按 Slurm REST API
> v0.0.40 编写，实际接入时需要按目标集群启用的 API 版本核对路径与字段，
> **以平台页面和集群实际配置为准**。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ...domain.errors import SchedulerError, SchedulerSubmissionUncertain
from ...domain.ports.scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerState,
    SchedulerSubmission,
)
from .script import render_sbatch_script

API_VERSION = "v0.0.40"

# Slurm 作业状态 -> 平台调度状态
_STATE_MAP = {
    "PENDING": SchedulerState.PENDING,
    "CONFIGURING": SchedulerState.PENDING,
    "REQUEUED": SchedulerState.PENDING,
    "RUNNING": SchedulerState.RUNNING,
    "COMPLETING": SchedulerState.RUNNING,
    "SUSPENDED": SchedulerState.RUNNING,
    "COMPLETED": SchedulerState.COMPLETED,
    "FAILED": SchedulerState.FAILED,
    "NODE_FAIL": SchedulerState.FAILED,
    "OUT_OF_MEMORY": SchedulerState.FAILED,
    "TIMEOUT": SchedulerState.FAILED,
    "BOOT_FAIL": SchedulerState.FAILED,
    "DEADLINE": SchedulerState.FAILED,
    "CANCELLED": SchedulerState.CANCELLED,
    "PREEMPTED": SchedulerState.CANCELLED,
}


class SlurmRestScheduler:
    name = "slurm"

    def __init__(self, base_url: str, user: str, jwt: str, *, timeout: float = 20.0) -> None:
        if not base_url or not user or not jwt:
            raise SchedulerError(
                "Slurm 适配器需要 WORKSPACE107_SLURM_API_BASE_URL、"
                "WORKSPACE107_SLURM_API_USER 和 WORKSPACE107_SLURM_JWT 三项配置"
            )
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-SLURM-USER-NAME": user, "X-SLURM-USER-TOKEN": jwt}
        self._timeout = timeout

    async def submit(self, submission: SchedulerSubmission) -> str:
        config = submission.configuration
        payload: dict[str, Any] = {
            "script": render_sbatch_script(submission),
            "job": {
                "name": submission.job_name,
                "account": config.account,
                "partition": config.partition,
                "qos": config.qos,
                "current_working_directory": str(submission.work_dir),
                "standard_output": str(submission.stdout_path),
                "standard_error": str(submission.stderr_path),
                "tasks": config.nodes,
                "cpus_per_task": config.cpus,
                "memory_per_node": config.memory_mb,
                "time_limit": config.time_limit_minutes,
                # Secret 明文只走环境变量，不进脚本正文。
                "environment": submission.environment,
            },
        }
        if config.gpus > 0:
            payload["job"]["tres_per_node"] = f"gres/gpu:{config.gpus}"

        try:
            data = await self._request("POST", f"/slurm/{API_VERSION}/job/submit", json=payload)
        except SchedulerError as exc:
            raise SchedulerSubmissionUncertain(str(exc)) from exc
        job_id = data.get("job_id")
        if job_id is None:
            raise SchedulerSubmissionUncertain("Slurm submit 响应没有可关联的 job_id")
        return str(job_id)

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        """目标集群 correlation 字段尚未经 human gate 核验，不能伪造权威空结果。"""
        return SchedulerCorrelationResult(
            complete=False,
            reason="Slurm correlation 查询尚未完成目标环境核验",
        )

    async def poll(self, job_id: str) -> SchedulerJobState:
        try:
            data = await self._request("GET", f"/slurm/{API_VERSION}/job/{job_id}")
        except SchedulerError as exc:
            if "404" in str(exc):
                return SchedulerJobState(
                    state=SchedulerState.UNKNOWN,
                    reason=f"Slurm 中查不到作业 {job_id}",
                )
            raise

        jobs = data.get("jobs") or []
        if not jobs:
            return SchedulerJobState(
                state=SchedulerState.UNKNOWN,
                reason=f"Slurm 中查不到作业 {job_id}",
            )

        job = jobs[0]
        raw_state = _first_state(job.get("job_state"))
        state = _STATE_MAP.get(raw_state, SchedulerState.UNKNOWN)
        return SchedulerJobState(
            state=state,
            exit_code=_exit_code(job),
            started_at=_timestamp(job.get("start_time")),
            finished_at=_timestamp(job.get("end_time")),
            reason=job.get("state_reason", "") or "",
        )

    async def cancel(self, job_id: str) -> None:
        await self._request("DELETE", f"/slurm/{API_VERSION}/job/{job_id}")

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, headers=self._headers, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            raise SchedulerError(f"Slurm API 返回 HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise SchedulerError(f"无法连接 Slurm API：{exc}") from exc


def _first_state(raw: Any) -> str:
    """``job_state`` 在不同 API 版本里可能是字符串或字符串数组。"""
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw or "")


def _exit_code(job: dict[str, Any]) -> int | None:
    exit_code = job.get("exit_code")
    if isinstance(exit_code, dict):
        number = exit_code.get("return_code")
        if isinstance(number, dict):
            number = number.get("number")
        return int(number) if number is not None else None
    return int(exit_code) if isinstance(exit_code, int) else None


def _timestamp(raw: Any) -> datetime | None:
    if isinstance(raw, dict):
        raw = raw.get("number")
    if not isinstance(raw, int) or raw <= 0:
        return None
    return datetime.fromtimestamp(raw, tz=UTC)
