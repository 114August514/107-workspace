"""Mock Scheduler Adapter 的平台适配。"""

from __future__ import annotations

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
        run_id="run_windows",
        job_name="Windows portability",
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
async def test_windows_uses_system_command_interpreter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    async def create_process(command: str, **options: Any) -> _FinishedProcess:
        captured["command"] = command
        captured.update(options)
        return _FinishedProcess()

    submission = _submission(tmp_path)
    monkeypatch.setattr(mock_module.os, "name", "nt")
    monkeypatch.setattr(mock_module.asyncio, "create_subprocess_shell", create_process)

    scheduler = mock_module.MockScheduler()
    job_id = await scheduler.submit(submission)
    await scheduler.poll(job_id)

    assert captured["command"] == submission.command
    assert "executable" not in captured


@pytest.mark.asyncio
async def test_posix_continues_to_use_bash(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    async def create_process(command: str, **options: Any) -> _FinishedProcess:
        captured.update(options)
        return _FinishedProcess()

    submission = _submission(tmp_path)
    monkeypatch.setattr(mock_module.os, "name", "posix")
    monkeypatch.setattr(mock_module.asyncio, "create_subprocess_shell", create_process)

    scheduler = mock_module.MockScheduler()
    job_id = await scheduler.submit(submission)
    await scheduler.poll(job_id)

    assert captured["executable"] == "/bin/bash"
