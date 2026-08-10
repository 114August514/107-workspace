"""Slurm adapter 错误边界不得泄露响应体或伪造确定拒绝。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.errors import SchedulerError, SchedulerSubmissionUncertain
from workspace107.domain.ports.scheduler import SchedulerSubmission
from workspace107.infrastructure.scheduler import slurm as slurm_module


class _Client:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def request(self, *args, **kwargs) -> httpx.Response:
        return self.response


@pytest.mark.asyncio
async def test_http_error_never_includes_scheduler_response_body(monkeypatch) -> None:
    secret = "scheduler-echoed-secret"
    request = httpx.Request("POST", "https://slurm.invalid/slurm/job/submit")
    response = httpx.Response(400, text=f"invalid token {secret}", request=request)
    monkeypatch.setattr(slurm_module.httpx, "AsyncClient", lambda *a, **kw: _Client(response))
    scheduler = slurm_module.SlurmRestScheduler("https://slurm.invalid", "user", "jwt")

    with pytest.raises(SchedulerError) as captured:
        await scheduler._request("POST", "/slurm/job/submit", json={})

    assert "HTTP 400" in str(captured.value)
    assert secret not in str(captured.value)
    assert "invalid token" not in str(captured.value)


@pytest.mark.asyncio
async def test_unverified_submit_failure_is_uncertain(monkeypatch, tmp_path: Path) -> None:
    scheduler = slurm_module.SlurmRestScheduler("https://slurm.invalid", "user", "jwt")

    async def fail(*args, **kwargs):
        raise SchedulerError("transport failed")

    monkeypatch.setattr(scheduler, "_request", fail)
    submission = SchedulerSubmission(
        run_id="run_secret",
        correlation="workspace107:run_secret",
        job_name="secret",
        work_dir=tmp_path,
        command="true",
        setup_command="",
        environment_image="",
        stdout_path=tmp_path / "stdout.log",
        stderr_path=tmp_path / "stderr.log",
        configuration=ResolvedSchedulerConfiguration(
            cluster="test",
            account="test",
            partition="test",
            qos="normal",
            nodes=1,
            cpus=1,
            memory_mb=512,
            gpus=0,
            time_limit_minutes=5,
        ),
    )

    with pytest.raises(SchedulerSubmissionUncertain):
        await scheduler.submit(submission)
