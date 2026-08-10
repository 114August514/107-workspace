"""Scheduler correlation 是 Worker 恢复提交歧义的安全边界。"""

from __future__ import annotations

from pathlib import Path

import pytest

from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.ports.scheduler import SchedulerSubmission
from workspace107.infrastructure.scheduler.mock import MockScheduler


def _submission(root: Path, correlation: str) -> SchedulerSubmission:
    work = root / "work"
    logs = root / "logs"
    work.mkdir()
    logs.mkdir()
    return SchedulerSubmission(
        run_id="run_reconcile",
        correlation=correlation,
        job_name="reconcile",
        work_dir=work,
        command="true",
        setup_command="",
        environment_image="",
        stdout_path=logs / "stdout.log",
        stderr_path=logs / "stderr.log",
        configuration=ResolvedSchedulerConfiguration(
            cluster="local",
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


@pytest.mark.asyncio
async def test_mock_reconciles_full_correlation_without_resubmitting(tmp_path: Path) -> None:
    scheduler = MockScheduler()
    correlation = "workspace107:run_0123456789abcdef0123"
    job_id = await scheduler.submit(_submission(tmp_path, correlation))

    result = await scheduler.find_by_correlation(correlation)

    assert result.complete is True
    assert result.job_ids == (job_id,)


@pytest.mark.asyncio
async def test_fresh_mock_cannot_claim_authoritative_zero_after_restart(tmp_path: Path) -> None:
    correlation = "workspace107:run_restart"
    first = MockScheduler()
    await first.submit(_submission(tmp_path, correlation))

    restarted = MockScheduler()
    result = await restarted.find_by_correlation(correlation)

    assert result.complete is False
    assert result.job_ids == ()
