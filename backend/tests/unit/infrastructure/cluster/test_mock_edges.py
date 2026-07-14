import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from workspace107.domain.errors import PreflightFailed, ResourceNotFound
from workspace107.domain.models import ResourceSpec, RunSubmission
from workspace107.infrastructure.cluster.mock import MockClusterAdapter, MockOutcome

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(slots=True)
class MutableClock:
    current: datetime = NOW

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def submission() -> RunSubmission:
    return RunSubmission(
        project_uri="file:///projects/demo",
        entrypoint="train.py",
        resources=ResourceSpec(cpus=1, memory_mb=1024, gpus=0, walltime_seconds=60),
        mounts=(),
        outputs=("result.json",),
        environment={"kind": "system"},
    )


async def read_all(stream: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in stream])


def test_mock_rejects_invalid_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="durations"):
        MockClusterAdapter(tmp_path / "negative", queue_seconds=-1)
    with pytest.raises(ValueError, match="outcome"):
        MockClusterAdapter(tmp_path / "outcome", outcome=cast(MockOutcome, "unknown"))


async def test_mock_preflight_reports_invalid_submission(tmp_path: Path) -> None:
    adapter = MockClusterAdapter(tmp_path / "mock")
    invalid = replace(
        submission(),
        project_uri="",
        resources=ResourceSpec(cpus=0, memory_mb=0, gpus=-1, walltime_seconds=0),
        environment={"not_json": {"a", "set"}},
    )

    checks = await adapter.preflight(invalid)

    assert [check.passed for check in checks] == [False, False, False]
    with pytest.raises(PreflightFailed, match="mock preflight failed"):
        await adapter.submit(invalid)


async def test_mock_log_and_artifact_boundaries(tmp_path: Path) -> None:
    clock = MutableClock()
    adapter = MockClusterAdapter(
        tmp_path / "mock",
        clock=clock,
        queue_seconds=2,
        run_seconds=3,
    )
    job = await adapter.submit(submission())

    assert await adapter.collect_artifacts(job.external_job_id) == ()
    with pytest.raises(ValueError, match="non-negative"):
        await adapter.read_log(job.external_job_id, -1)
    chunk = await adapter.read_log(job.external_job_id, 0)
    with pytest.raises(ValueError, match="exceeds"):
        await adapter.read_log(job.external_job_id, chunk.next_offset + 1)
    with pytest.raises(ResourceNotFound, match="not available"):
        await read_all(adapter.open_artifact(job.external_job_id, "log"))

    clock.advance(5)
    assert (await adapter.status(job.external_job_id)).status.value == "succeeded"
    await adapter.cancel(job.external_job_id)
    assert (await adapter.status(job.external_job_id)).status.value == "succeeded"
    with pytest.raises(ResourceNotFound, match="not found"):
        await read_all(adapter.open_artifact(job.external_job_id, "unknown"))


async def test_failed_mock_exposes_only_log_artifact(tmp_path: Path) -> None:
    adapter = MockClusterAdapter(
        tmp_path / "failure",
        queue_seconds=0,
        run_seconds=0,
        outcome="failure",
        clock=lambda: NOW,
    )
    job = await adapter.submit(submission())

    artifacts = await adapter.collect_artifacts(job.external_job_id)

    assert [artifact.artifact_key for artifact in artifacts] == ["log"]
    with pytest.raises(ResourceNotFound, match="not found"):
        await read_all(adapter.open_artifact(job.external_job_id, "result"))


async def test_mock_requires_aware_clock(tmp_path: Path) -> None:
    adapter = MockClusterAdapter(
        tmp_path / "naive",
        clock=lambda: datetime(2026, 1, 1),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        await adapter.submit(submission())


async def test_mock_rejects_missing_and_malformed_durable_state(tmp_path: Path) -> None:
    root = tmp_path / "mock"
    adapter = MockClusterAdapter(root)

    with pytest.raises(ResourceNotFound, match="not found"):
        await adapter.status("not-a-job-id")
    with pytest.raises(ResourceNotFound, match="not found"):
        await adapter.status(str(uuid4()))

    job_id = str(uuid4())
    state_path = root / "jobs" / f"{job_id}.json"
    valid: dict[str, object] = {
        "external_job_id": job_id,
        "submitted_at": NOW.isoformat(),
        "queue_seconds": 1.0,
        "run_seconds": 1.0,
        "outcome": "success",
        "cancelled_at": None,
        "log_path": f"logs/{job_id}.log",
        "result_path": f"results/{job_id}.json",
        "submission": {"entrypoint": "train.py"},
    }
    invalid_records: tuple[object, ...] = (
        [],
        {**valid, "outcome": 1},
        {**valid, "outcome": "unknown"},
        {**valid, "submission": []},
        {**valid, "submitted_at": None},
        {**valid, "submitted_at": 1},
        {**valid, "submitted_at": "2026-01-01T00:00:00"},
        {**valid, "queue_seconds": True},
        {**valid, "external_job_id": str(uuid4())},
    )
    for record in invalid_records:
        state_path.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(ValueError, match="mock job state is invalid"):
            await adapter.status(job_id)
