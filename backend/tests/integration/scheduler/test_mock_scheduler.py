"""Mock Scheduler Adapter 的 Bash 解释器行为。"""

from __future__ import annotations

import asyncio
import shlex
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.ports.scheduler import SchedulerSubmission
from workspace107.infrastructure.scheduler import mock as mock_module


class _FinishedProcess:
    returncode = 0


def _submission(root: Path) -> SchedulerSubmission:
    work = root / "run" / "work"
    logs = root / "run" / "logs"
    work.mkdir(parents=True)
    logs.mkdir(parents=True)
    return SchedulerSubmission(
        run_id="run_mock",
        correlation="run_mock:snapshot_1:version_1:commit_1",
        job_name="Mock scheduler",
        work_dir=work,
        command="python main.py",
        setup_command="",
        environment_image="python:3.12-slim",
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
async def test_mock_scheduler_uses_bash(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    async def create_process(command: str, **options: Any) -> _FinishedProcess:
        captured.update(options)
        return _FinishedProcess()

    submission = _submission(tmp_path)
    monkeypatch.setattr(mock_module.asyncio, "create_subprocess_shell", create_process)

    scheduler = mock_module.MockScheduler()
    job_id = await scheduler.submit(submission)
    correlation = await scheduler.find_by_correlation(submission.correlation)
    missing = await scheduler.find_by_correlation("run_missing:snapshot_1:version_1:commit_1")
    await scheduler.poll(job_id)

    assert captured["executable"] == "/bin/bash"
    assert correlation.complete is True
    assert correlation.job_ids == (job_id,)
    assert correlation.reason == ""
    assert missing.complete is True
    assert missing.job_ids == ()


@pytest.mark.asyncio
async def test_mock_scheduler_maps_nonzero_exit_to_failed(tmp_path: Path) -> None:
    submission = replace(_submission(tmp_path), command="exit 7")
    scheduler = mock_module.MockScheduler()

    job_id = await scheduler.submit(submission)
    await scheduler.wait_for_exit(job_id)
    state = await scheduler.poll(job_id)

    assert state.state.value == "failed"
    assert state.exit_code == 7


@pytest.mark.asyncio
async def test_mock_cancel_terminates_the_entire_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "orphan.txt"
    child = (
        "import signal,time,pathlib; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(0.5); "
        f"pathlib.Path({str(marker)!r}).write_text('orphan')"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(child)} & wait"
    scheduler = mock_module.MockScheduler(cancel_grace_seconds=0.05)
    job_id = await scheduler.submit(replace(_submission(tmp_path), command=command))
    await asyncio.sleep(0.1)

    await scheduler.cancel(job_id)
    state = await scheduler.poll(job_id)
    await asyncio.sleep(0.6)

    assert state.state.value == "cancelled"
    assert not marker.exists()


@pytest.mark.asyncio
async def test_mock_close_cleans_owned_workloads(tmp_path: Path) -> None:
    scheduler = mock_module.MockScheduler(cancel_grace_seconds=0)
    job_id = await scheduler.submit(replace(_submission(tmp_path), command="sleep 30"))

    await scheduler.close()
    state = await scheduler.poll(job_id)

    assert state.state.value == "cancelled"


@pytest.mark.asyncio
async def test_missing_mock_job_reports_process_local_ownership_loss() -> None:
    state = await mock_module.MockScheduler().poll("mock-lost")

    assert state.state.value == "unknown"
    assert "process-local" in state.reason
    assert "loses observability and control" in state.reason
