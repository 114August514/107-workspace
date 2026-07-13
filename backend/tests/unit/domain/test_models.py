from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError
from datetime import UTC
from pathlib import Path
from typing import cast

import pytest

from workspace107.domain.enums import ArtifactKind, RunStatus
from workspace107.domain.models import (
    CollectedArtifact,
    DatasetMount,
    FileSignature,
    IgnoreRules,
    JobObservation,
    LogChunk,
    NewUser,
    ObjectMetadata,
    PreflightCheck,
    ProjectSnapshot,
    PullRequest,
    ResourceSpec,
    RunSubmission,
    StoredObject,
    SubmittedJob,
    TransferPlan,
    TransferResult,
    utc_now,
)
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.storage import StoragePort
from workspace107.domain.ports.transfer import ProjectTransferPort


def make_submission(environment: dict[str, object] | None = None) -> RunSubmission:
    return RunSubmission(
        project_uri="file:///projects/demo",
        entrypoint="code/./train.py",
        resources=ResourceSpec(cpus=4, memory_mb=16384, gpus=1, walltime_seconds=7200),
        mounts=(
            DatasetMount(
                dataset_version_id="version-1",
                source_uri="file:///datasets/version-1",
                mount_path="input/./data",
            ),
        ),
        outputs=("results/./metrics",),
        environment=environment or {"kind": "uv"},
    )


def test_run_submission_normalizes_paths_and_is_frozen() -> None:
    submission = make_submission()

    assert submission.entrypoint == "code/train.py"
    assert submission.mounts[0].mount_path == "input/data"
    assert submission.outputs == ("results/metrics",)
    with pytest.raises(FrozenInstanceError):
        submission.__setattr__("entrypoint", "other.py")


def test_run_submission_copies_and_freezes_environment() -> None:
    environment: dict[str, object] = {"kind": "uv"}
    submission = make_submission(environment)

    environment["kind"] = "conda"
    assert submission.environment["kind"] == "uv"
    with pytest.raises(TypeError):
        cast(dict[str, object], submission.environment)["kind"] = "system"


def test_transfer_values_normalize_relative_paths(tmp_path: Path) -> None:
    plan = TransferPlan(
        source=tmp_path,
        target_uri="file:///target",
        files=("src/./main.py",),
        removed=("old/./main.py",),
    )
    request = PullRequest(
        source_uri="file:///target",
        destination=tmp_path,
        include=("results/./metrics.json",),
    )

    assert plan.files == ("src/main.py",)
    assert plan.removed == ("old/main.py",)
    assert request.include == ("results/metrics.json",)


def test_mapping_results_are_copied_and_read_only(tmp_path: Path) -> None:
    details: dict[str, object] = {"raw_state": "RUNNING"}
    signature = FileSignature(path="src/./main.py", size_bytes=10, mtime_ns=1)
    manifest = {"src/main.py": signature}

    observation = JobObservation(status=RunStatus.RUNNING, observed_at=utc_now(), details=details)
    result = TransferResult(
        transferred=("src/./main.py",),
        skipped=(),
        removed=(),
        manifest=manifest,
    )

    details["raw_state"] = "FAILED"
    manifest.clear()
    assert observation.details["raw_state"] == "RUNNING"
    assert result.manifest["src/main.py"] == signature
    assert result.transferred == ("src/main.py",)


def test_new_user_generates_application_identity_and_utc_time() -> None:
    first = NewUser(username="alice", display_name="Alice")
    second = NewUser(username="bob", display_name="Bob")

    assert first.id != second.id
    assert first.created_at.tzinfo is UTC


class FakeCluster:
    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]:
        return (PreflightCheck(code="ok", passed=True, message=spec.entrypoint),)

    async def submit(self, spec: RunSubmission) -> SubmittedJob:
        return SubmittedJob(external_job_id=spec.entrypoint, submitted_at=utc_now())

    async def status(self, external_job_id: str) -> JobObservation:
        return JobObservation(status=RunStatus.QUEUED, observed_at=utc_now())

    async def cancel(self, external_job_id: str) -> None:
        return None

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk:
        return LogChunk(offset=offset, next_offset=offset, data="", end_of_stream=True)

    async def collect_artifacts(self, external_job_id: str) -> tuple[CollectedArtifact, ...]:
        return (
            CollectedArtifact(
                artifact_key=external_job_id,
                name="result.json",
                kind=ArtifactKind.RESULT,
                media_type="application/json",
            ),
        )

    async def _artifact_chunks(self) -> AsyncIterator[bytes]:
        yield b"result"

    def open_artifact(self, external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]:
        return self._artifact_chunks()


class FakeStorage:
    async def _chunks(self) -> AsyncIterator[bytes]:
        yield b"stored"

    async def put(self, chunks: AsyncIterator[bytes], metadata: ObjectMetadata) -> StoredObject:
        async for _ in chunks:
            pass
        return StoredObject(
            storage_key=metadata.name,
            size_bytes=0,
            sha256="0" * 64,
            created=True,
        )

    def open(self, storage_key: str) -> AsyncIterator[bytes]:
        return self._chunks()

    async def delete_unreferenced(self, storage_key: str) -> None:
        return None


class FakeTransfer:
    async def scan(self, source: Path, ignore: IgnoreRules) -> ProjectSnapshot:
        return ProjectSnapshot(source=source, files=())

    async def push(self, plan: TransferPlan) -> TransferResult:
        return TransferResult((), plan.files, plan.removed, {})

    async def pull(self, request: PullRequest) -> TransferResult:
        return TransferResult(request.include, (), (), {})


def test_runtime_port_contracts_accept_structural_implementations() -> None:
    assert isinstance(FakeCluster(), ClusterPort)
    assert isinstance(FakeStorage(), StoragePort)
    assert isinstance(FakeTransfer(), ProjectTransferPort)
