import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from workspace107.domain.enums import RunStatus
from workspace107.domain.models import ResourceSpec, RunSubmission
from workspace107.infrastructure.cluster.mock import MockClusterAdapter


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def submission() -> RunSubmission:
    return RunSubmission(
        project_uri="file:///projects/demo",
        entrypoint="train.py",
        resources=ResourceSpec(cpus=2, memory_mb=4096, gpus=0, walltime_seconds=60),
        mounts=(),
        outputs=("results.json",),
        environment={"kind": "system"},
    )


async def test_job_state_survives_adapter_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "mock"
    clock = FakeClock()
    first = MockClusterAdapter(root, clock=clock, queue_seconds=2, run_seconds=3)
    job = await first.submit(submission())
    state_path = root / "jobs" / f"{job.external_job_id}.json"
    serialized = state_path.read_text(encoding="utf-8")

    second = MockClusterAdapter(root, clock=clock, queue_seconds=99, run_seconds=99)
    clock.advance(2)
    running = await second.status(job.external_job_id)
    clock.advance(3)
    succeeded = await second.status(job.external_job_id)
    artifacts = await second.collect_artifacts(job.external_job_id)

    assert running.status is RunStatus.RUNNING
    assert succeeded.status is RunStatus.SUCCEEDED
    assert artifacts
    assert "run_id" not in serialized
    assert json.loads(serialized)["external_job_id"] == job.external_job_id
    assert not tuple(root.rglob("*.tmp"))


async def test_cancellation_survives_adapter_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "mock"
    clock = FakeClock()
    first = MockClusterAdapter(root, clock=clock)
    job = await first.submit(submission())
    await first.cancel(job.external_job_id)

    second = MockClusterAdapter(root, clock=clock)

    assert (await second.status(job.external_job_id)).status is RunStatus.CANCELLED
