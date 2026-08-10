"""Temporary synchronous consumer must preserve ambiguous submission recovery semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from workspace107.application.run_service import RunService
from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.enums import RunEventType, RunStatus
from workspace107.domain.errors import (
    SchedulerError,
    SchedulerSubmissionRejected,
    SchedulerSubmissionUncertain,
)

SECRET_MARKER = "fixture-secret-must-not-enter-event"


class _Runs:
    def __init__(self) -> None:
        self.updated: list[Any] = []

    async def update(self, run: Any) -> None:
        self.updated.append(run)


class _RunEvents:
    def __init__(self) -> None:
        self.added: list[Any] = []

    async def add(self, event: Any) -> None:
        self.added.append(event)


class _Storage:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def prepare_run_directory(self, *_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(
            work=self.root,
            inputs=self.root / "inputs",
            stdout=self.root / "stdout.log",
            stderr=self.root / "stderr.log",
        )


class _Scheduler:
    name = "fixture"

    def __init__(self, error: SchedulerError) -> None:
        self.error = error

    async def submit(self, _submission: Any) -> str:
        raise self.error


class _Notifier:
    def __init__(self) -> None:
        self.submit_failed: list[dict[str, Any]] = []

    async def run_submit_failed(self, **kwargs: Any) -> None:
        self.submit_failed.append(kwargs)


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 10, tzinfo=UTC)


def _service(tmp_path: Path, error: SchedulerError) -> tuple[RunService, Any, _Notifier]:
    repos = SimpleNamespace(runs=_Runs(), run_events=_RunEvents())
    notifier = _Notifier()
    service = RunService(
        repos=repos,
        guard=object(),
        clock=_Clock(),
        storage=_Storage(tmp_path),
        scheduler=_Scheduler(error),
        secrets=object(),
        activity=object(),
        notifier=notifier,
    )
    return service, repos, notifier


def _inputs() -> tuple[Any, Any, Any]:
    run = SimpleNamespace(
        id="run_fixture",
        name="fixture run",
        created_by="user_fixture",
        status=RunStatus.QUEUED,
        failure_reason="",
        finished_at=None,
        scheduler_job_id=None,
        submitted_at=None,
    )
    snapshot = SimpleNamespace(
        input_bindings=(),
        env_literals={},
        env_secret_refs={},
        working_directory=".",
        command="true",
        environment_setup_command="",
        environment_image="",
        scheduler=ResolvedSchedulerConfiguration(
            cluster="fixture",
            account="fixture",
            partition="fixture",
            qos="fixture",
            nodes=1,
            cpus=1,
            memory_mb=64,
            gpus=0,
            time_limit_minutes=1,
        ),
    )
    version = SimpleNamespace(files=[])
    return run, snapshot, version


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        SchedulerSubmissionUncertain(SECRET_MARKER),
        SchedulerError(SECRET_MARKER),
    ],
)
async def test_ambiguous_or_unproven_submit_stays_queued_with_safe_event(
    tmp_path: Path, error: SchedulerError
) -> None:
    service, repos, notifier = _service(tmp_path, error)
    run, snapshot, version = _inputs()

    await service._submit(run, snapshot, version, "workspace_fixture")

    assert run.status is RunStatus.QUEUED
    assert run.failure_reason == ""
    assert run.finished_at is None
    assert repos.runs.updated == []
    assert len(repos.run_events.added) == 1
    assert repos.run_events.added[0].type is RunEventType.ERROR
    assert SECRET_MARKER not in repos.run_events.added[0].message
    assert notifier.submit_failed == []


@pytest.mark.asyncio
async def test_local_rejection_is_the_only_submit_failed_path(tmp_path: Path) -> None:
    service, repos, notifier = _service(
        tmp_path, SchedulerSubmissionRejected("local resource validation rejected")
    )
    run, snapshot, version = _inputs()

    await service._submit(run, snapshot, version, "workspace_fixture")

    assert run.status is RunStatus.SUBMIT_FAILED
    assert run.failure_reason == "local resource validation rejected"
    assert run.finished_at == datetime(2026, 8, 10, tzinfo=UTC)
    assert repos.runs.updated == [run]
    assert repos.run_events.added[0].type is RunEventType.SUBMIT_FAILED
    assert len(notifier.submit_failed) == 1
