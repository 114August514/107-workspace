"""Slurm submission uses platform-owned batch I/O paths over HTTP."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx

from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.ports.scheduler import SchedulerSubmission
from workspace107.infrastructure.scheduler.slurm import SlurmRestScheduler


def _submission(root: Path) -> SchedulerSubmission:
    work = root / "run" / "work"
    logs = root / "run" / "logs"
    work.mkdir(parents=True)
    logs.mkdir(parents=True)
    return SchedulerSubmission(
        run_id="run_slurm",
        job_name="Slurm batch IO",
        work_dir=work,
        command="python main.py",
        environment_execution_spec={"kind": "modules", "commands": []},
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


async def test_slurm_batch_io_request(monkeypatch, tmp_path):
    submission = replace(_submission(tmp_path), command="cat; echo finished")
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"job_id": 81})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )
    scheduler = SlurmRestScheduler("https://slurm.test", "test-user", "test-token")
    assert await scheduler.submit(submission) == "81"
    payload = captured[0]
    assert payload["job"]["standard_input"] == "/dev/null"
    assert payload["job"]["standard_output"] == str(submission.stdout_path)
    assert payload["job"]["standard_error"] == str(submission.stderr_path)
    assert "#SBATCH --input=/dev/null" in payload["script"]
    assert "test-token" not in payload["script"]
