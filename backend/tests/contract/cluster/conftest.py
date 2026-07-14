from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from workspace107.domain.models import DatasetMount, ResourceSpec, RunSubmission
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.infrastructure.cluster.mock import MockClusterAdapter


@dataclass(slots=True)
class FakeClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@dataclass(frozen=True, slots=True)
class ClusterHarness:
    adapter: ClusterPort
    clock: FakeClock
    queue_seconds: float
    run_seconds: float


@pytest.fixture
def valid_submission() -> RunSubmission:
    return RunSubmission(
        project_uri="file:///projects/demo",
        entrypoint="train.py",
        resources=ResourceSpec(
            cpus=4,
            memory_mb=4096,
            gpus=1,
            walltime_seconds=3600,
        ),
        mounts=(
            DatasetMount(
                dataset_version_id="version-1",
                source_uri="file:///datasets/version-1",
                mount_path="input/data",
            ),
        ),
        outputs=("results/metrics.json",),
        environment={"kind": "uv"},
    )


@pytest.fixture
def cluster_harness(tmp_path: Path) -> ClusterHarness:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    queue_seconds = 2.0
    run_seconds = 3.0
    return ClusterHarness(
        adapter=MockClusterAdapter(
            tmp_path / "mock",
            clock=clock,
            queue_seconds=queue_seconds,
            run_seconds=run_seconds,
        ),
        clock=clock,
        queue_seconds=queue_seconds,
        run_seconds=run_seconds,
    )


@pytest.fixture
def failure_harness(tmp_path: Path) -> ClusterHarness:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    return ClusterHarness(
        adapter=MockClusterAdapter(
            tmp_path / "failed-mock",
            clock=clock,
            queue_seconds=1.0,
            run_seconds=1.0,
            outcome="failure",
        ),
        clock=clock,
        queue_seconds=1.0,
        run_seconds=1.0,
    )
