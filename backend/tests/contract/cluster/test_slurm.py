import asyncio
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePosixPath
from typing import cast

import pytest

from workspace107.domain.enums import ArtifactKind
from workspace107.domain.models import DatasetMount, ResourceSpec, RunSubmission
from workspace107.infrastructure.cluster.slurm.adapter import SlurmClusterAdapter
from workspace107.infrastructure.cluster.slurm.command_runner import CommandResult

from . import test_contract as contract
from .conftest import ClusterHarness, FakeClock


@dataclass(slots=True)
class _Job:
    submitted_at: datetime
    cancelled: bool = False
    running_logged: bool = False
    terminal_logged: bool = False


class ScriptedSlurmRunner:
    def __init__(
        self,
        clock: FakeClock,
        *,
        queue_seconds: float,
        run_seconds: float,
        outcome: str = "success",
        cancel_metadata_write: bool = False,
    ) -> None:
        self.clock = clock
        self.queue_seconds = queue_seconds
        self.run_seconds = run_seconds
        self.outcome = outcome
        self.cancel_metadata_write = cancel_metadata_write
        self.calls: list[tuple[tuple[str, ...], bytes | None]] = []
        self.files: dict[str, bytes] = {}
        self.jobs: dict[str, _Job] = {}
        self._next_id = 1000

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        self.calls.append((arguments, input_data))
        if not arguments:
            return self._result(exit_code=2, stderr=b"empty command")
        command = arguments[0]
        if command == "sinfo":
            return self._result(stdout=b"Students\n")
        if command == "mkdir" or command == "chmod":
            return self._result()
        if command == "tee":
            path = arguments[-1]
            if self.cancel_metadata_write and "/metadata/" in path:
                raise asyncio.CancelledError
            data = input_data or b""
            self.files[path] = self.files.get(path, b"") + data if "-a" in arguments else data
            return self._result(stdout=data)
        if command == "sbatch":
            self._next_id += 1
            job_id = str(self._next_id)
            self.jobs[job_id] = _Job(submitted_at=self.clock())
            return self._result(stdout=f"{job_id};cluster\n".encode())
        if command == "squeue":
            return self._squeue(arguments)
        if command == "sacct":
            return self._sacct(arguments)
        if command == "scancel":
            job_id = arguments[-1]
            job = self.jobs.get(job_id)
            if job is None:
                return self._result(exit_code=1, stderr=b"unknown job")
            job.cancelled = True
            self._refresh(job_id)
            return self._result()
        if command == "test":
            path = arguments[-1]
            if arguments[1] == "-f":
                return self._result(exit_code=0 if path in self.files else 1)
            if arguments[1] == "-d":
                prefix = path.rstrip("/") + "/"
                return self._result(
                    exit_code=0 if any(name.startswith(prefix) for name in self.files) else 1
                )
        if command == "tail":
            path = arguments[-1]
            start = int(arguments[2][1:]) - 1
            return self._result(stdout=self.files.get(path, b"")[start:])
        if command == "stat":
            path = arguments[-1]
            data = self.files.get(path)
            if data is None:
                return self._result(exit_code=1, stderr=b"not found")
            return self._result(stdout=f"{len(data)}\n".encode())
        if command == "find":
            root = arguments[1].rstrip("/") + "/"
            names = sorted(name for name in self.files if name.startswith(root))
            return self._result(stdout=b"\0".join(name.encode() for name in names))
        if command == "cat":
            data = self.files.get(arguments[-1])
            if data is None:
                return self._result(exit_code=1, stderr=b"not found")
            return self._result(stdout=data)
        return self._result(exit_code=127, stderr=b"unsupported scripted command")

    def _squeue(self, arguments: tuple[str, ...]) -> CommandResult:
        job_id = arguments[arguments.index("-j") + 1]
        job = self.jobs.get(job_id)
        if job is None:
            return self._result()
        elapsed = (self.clock() - job.submitted_at).total_seconds()
        self._refresh(job_id)
        if job.cancelled or elapsed >= self.queue_seconds + self.run_seconds:
            return self._result()
        state = "PENDING" if elapsed < self.queue_seconds else "RUNNING"
        node = "(null)" if state == "PENDING" else "gpu01"
        return self._result(stdout=f"{job_id}|{state}|{node}|N/A\n".encode())

    def _sacct(self, arguments: tuple[str, ...]) -> CommandResult:
        job_id = arguments[arguments.index("-j") + 1]
        job = self.jobs.get(job_id)
        if job is None:
            return self._result()
        self._refresh(job_id)
        if job.cancelled:
            state, exit_code = "CANCELLED", 0
        elif self.outcome == "success":
            state, exit_code = "COMPLETED", 0
        else:
            state, exit_code = "FAILED", 1
        return self._result(stdout=f"{job_id}|{state}|{exit_code}:0|start|end\n".encode())

    def _refresh(self, job_id: str) -> None:
        job = self.jobs[job_id]
        elapsed = (self.clock() - job.submitted_at).total_seconds()
        log_path = f"/cluster/workspace107/logs/{job_id}.out"
        if elapsed >= self.queue_seconds and not job.running_logged and not job.cancelled:
            self.files[log_path] = self.files.get(log_path, b"") + (
                f"[workspace107] running job {job_id}\n".encode()
            )
            job.running_logged = True
        terminal = job.cancelled or elapsed >= self.queue_seconds + self.run_seconds
        if not terminal or job.terminal_logged:
            return
        state = (
            "cancelled" if job.cancelled else "succeeded" if self.outcome == "success" else "failed"
        )
        self.files[log_path] = self.files.get(log_path, b"") + (
            f"[workspace107] {state} job {job_id}\n".encode()
        )
        job.terminal_logged = True
        if self.outcome != "success" or job.cancelled:
            return
        metadata = json.loads(self.files[f"/cluster/workspace107/metadata/{job_id}.json"].decode())
        assert isinstance(metadata, dict)
        work_dir = cast(str, metadata["work_dir"])
        for output in cast(list[str], metadata["outputs"]):
            self.files[f"{work_dir}/{output}"] = (
                f'{{"job_id":"{job_id}","output":"{output}"}}\n'.encode()
            )

    @staticmethod
    def _result(
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        exit_code: int = 0,
    ) -> CommandResult:
        return CommandResult.completed(stdout=stdout, stderr=stderr, exit_code=exit_code)


def _harness(
    clock: FakeClock,
    runner: ScriptedSlurmRunner,
    *,
    queue_seconds: float,
    run_seconds: float,
) -> ClusterHarness:
    adapter = SlurmClusterAdapter(
        runner,
        remote_root=PurePosixPath("/cluster/workspace107"),
        project_roots=(PurePosixPath("/projects"),),
        dataset_roots=(PurePosixPath("/datasets"),),
        storage_root=PurePosixPath("/storage"),
        clock=clock,
    )
    return ClusterHarness(
        adapter=adapter,
        clock=clock,
        queue_seconds=queue_seconds,
        run_seconds=run_seconds,
    )


@pytest.fixture
def slurm_harness() -> ClusterHarness:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    queue_seconds = 2.0
    run_seconds = 3.0
    runner = ScriptedSlurmRunner(
        clock,
        queue_seconds=queue_seconds,
        run_seconds=run_seconds,
    )
    return _harness(
        clock,
        runner,
        queue_seconds=queue_seconds,
        run_seconds=run_seconds,
    )


@pytest.fixture
def failed_slurm_harness() -> ClusterHarness:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = ScriptedSlurmRunner(
        clock,
        queue_seconds=1.0,
        run_seconds=1.0,
        outcome="failure",
    )
    return _harness(clock, runner, queue_seconds=1.0, run_seconds=1.0)


async def test_slurm_contract_lifecycle(
    slurm_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    await contract.test_cluster_lifecycle_logs_and_artifacts(
        slurm_harness,
        valid_submission,
    )


async def test_slurm_contract_failure(
    failed_slurm_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    await contract.test_deterministic_failure(failed_slurm_harness, valid_submission)


async def test_slurm_contract_cancel(
    slurm_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    await contract.test_cancel_is_idempotent_and_terminal_jobs_stay_terminal(
        slurm_harness,
        valid_submission,
    )


async def test_slurm_contract_unknown_job(slurm_harness: ClusterHarness) -> None:
    await contract.test_unknown_job_and_artifact_are_not_found(slurm_harness)


async def test_slurm_contract_log_offsets(
    slurm_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    await contract.test_log_reads_resume_from_byte_offset(slurm_harness, valid_submission)


async def test_slurm_contract_artifact_idempotency(
    slurm_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    await contract.test_terminal_artifact_collection_is_idempotent(
        slurm_harness,
        valid_submission,
    )


async def test_slurm_submit_uses_strict_script_and_parsable_output(
    valid_submission: RunSubmission,
) -> None:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = ScriptedSlurmRunner(clock, queue_seconds=2, run_seconds=3)
    harness = _harness(clock, runner, queue_seconds=2, run_seconds=3)

    job = await harness.adapter.submit(valid_submission)

    scripts = [data.decode() for path, data in runner.files.items() if path.endswith(".sbatch")]
    assert len(scripts) == 1
    assert "set -euo pipefail" in scripts[0]
    assert "#SBATCH --gres=gpu:1" in scripts[0]
    assert any(call[0][:2] == ("sbatch", "--parsable") for call in runner.calls)
    assert job.external_job_id == "1001"


async def test_slurm_submit_cancels_created_job_when_metadata_write_is_cancelled() -> None:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = ScriptedSlurmRunner(
        clock,
        queue_seconds=2,
        run_seconds=3,
        cancel_metadata_write=True,
    )
    harness = _harness(clock, runner, queue_seconds=2, run_seconds=3)
    submission = RunSubmission(
        project_uri="file:///projects/demo",
        entrypoint="train.py",
        resources=ResourceSpec(cpus=1, memory_mb=1024, gpus=0, walltime_seconds=60),
        mounts=(),
        outputs=("result.json",),
        environment={"kind": "system"},
    )

    with pytest.raises(asyncio.CancelledError):
        await harness.adapter.submit(submission)

    assert any(call[0] == ("scancel", "1001") for call in runner.calls)


async def test_slurm_resolves_storage_uri_under_configured_root(
    valid_submission: RunSubmission,
) -> None:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = ScriptedSlurmRunner(clock, queue_seconds=2, run_seconds=3)
    harness = _harness(clock, runner, queue_seconds=2, run_seconds=3)
    submission = replace(
        valid_submission,
        mounts=(
            DatasetMount(
                dataset_version_id="version-1",
                source_uri="storage:///sha256/ab/abcdef",
                mount_path="input/data",
            ),
        ),
    )

    await harness.adapter.submit(submission)

    script = next(data.decode() for path, data in runner.files.items() if path.endswith(".sbatch"))
    assert "'/storage/sha256/ab/abcdef'" in script


async def test_slurm_output_metadata_survives_adapter_reconstruction(
    valid_submission: RunSubmission,
) -> None:
    from datetime import UTC

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = ScriptedSlurmRunner(clock, queue_seconds=2, run_seconds=3)
    first = _harness(clock, runner, queue_seconds=2, run_seconds=3)
    job = await first.adapter.submit(valid_submission)
    clock.advance(5)
    reconstructed = _harness(clock, runner, queue_seconds=2, run_seconds=3)

    artifacts = await reconstructed.adapter.collect_artifacts(job.external_job_id)
    result = next(artifact for artifact in artifacts if artifact.kind is ArtifactKind.RESULT)
    content = await contract.read_all(
        reconstructed.adapter.open_artifact(job.external_job_id, result.artifact_key)
    )

    assert job.external_job_id.encode() in content
