import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePosixPath
from typing import cast

import pytest

from workspace107.domain.enums import ArtifactKind
from workspace107.domain.errors import (
    ClusterUnavailable,
    ExternalCommandFailed,
    ResourceConflict,
    ResourceNotFound,
)
from workspace107.domain.models import DatasetMount, ResourceSpec, RunSubmission
from workspace107.infrastructure.cluster.slurm.adapter import SlurmClusterAdapter
from workspace107.infrastructure.cluster.slurm.command_runner import CommandResult, CommandRunner

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


class RoutingRunner:
    def __init__(self, responses: dict[str, CommandResult] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        del input_data
        self.calls.append(arguments)
        return self.responses.get(arguments[0], CommandResult.completed())


class OutputOverrideRunner(ScriptedSlurmRunner):
    find_output: bytes | None = None
    stat_output: bytes | None = None

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        if arguments[0] == "find" and self.find_output is not None:
            self.calls.append((arguments, input_data))
            return self._result(stdout=self.find_output)
        if arguments[0] == "stat" and self.stat_output is not None:
            self.calls.append((arguments, input_data))
            return self._result(stdout=self.stat_output)
        return await super().run(arguments, input_data=input_data)


EDGE_NOW = datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def edge_adapter(
    runner: CommandRunner,
    *,
    clock: Callable[[], datetime] = lambda: EDGE_NOW,
    project_roots: tuple[PurePosixPath, ...] = (PurePosixPath("/projects"),),
) -> SlurmClusterAdapter:
    return SlurmClusterAdapter(
        runner,
        remote_root=PurePosixPath("/cluster/workspace107"),
        project_roots=project_roots,
        dataset_roots=(PurePosixPath("/datasets"),),
        storage_root=PurePosixPath("/storage"),
        clock=clock,
    )


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


def test_slurm_constructor_rejects_unsafe_or_missing_roots() -> None:
    runner = RoutingRunner()

    with pytest.raises(ValueError, match="project root"):
        edge_adapter(runner, project_roots=())
    with pytest.raises(ValueError, match="remote_root"):
        SlurmClusterAdapter(
            runner,
            remote_root=PurePosixPath("relative/root"),
            project_roots=(PurePosixPath("/projects"),),
            dataset_roots=(PurePosixPath("/datasets"),),
            storage_root=PurePosixPath("/storage"),
        )


async def test_slurm_preflight_reports_unavailable_partition(
    valid_submission: RunSubmission,
) -> None:
    runner = RoutingRunner({"sinfo": CommandResult.completed(stderr=b"unavailable", exit_code=1)})

    checks = await edge_adapter(runner).preflight(valid_submission)

    assert len(checks) == 1
    assert checks[0].passed is False
    assert "unavailable" in checks[0].message


async def test_slurm_normalizes_failed_external_command(
    valid_submission: RunSubmission,
) -> None:
    runner = RoutingRunner({"mkdir": CommandResult.completed(exit_code=2)})

    with pytest.raises(ExternalCommandFailed, match="prepare Slurm directories"):
        await edge_adapter(runner).submit(valid_submission)


@pytest.mark.parametrize(
    ("accounting", "error", "message"),
    [
        (
            CommandResult.completed(exit_code=2),
            ExternalCommandFailed,
            "accounting lookup",
        ),
        (CommandResult.completed(), ResourceNotFound, "was not found"),
    ],
)
async def test_slurm_status_normalizes_accounting_failures(
    accounting: CommandResult,
    error: type[Exception],
    message: str,
) -> None:
    runner = RoutingRunner(
        {
            "squeue": CommandResult.completed(exit_code=1),
            "sacct": accounting,
        }
    )

    with pytest.raises(error, match=message):
        await edge_adapter(runner).status("1001")


async def test_slurm_rejects_invalid_job_id_before_running_command() -> None:
    runner = RoutingRunner()

    with pytest.raises(ResourceNotFound, match="was not found"):
        await edge_adapter(runner).status("1; scancel 2")

    assert runner.calls == []


async def test_slurm_terminal_cancel_is_idempotent() -> None:
    runner = RoutingRunner(
        {
            "squeue": CommandResult.completed(),
            "sacct": CommandResult.completed(stdout=b"1001|COMPLETED|0:0|start|end\n"),
        }
    )

    await edge_adapter(runner).cancel("1001")

    assert not any(call[0] == "scancel" for call in runner.calls)


async def test_slurm_log_and_nonterminal_artifact_boundaries() -> None:
    runner = RoutingRunner(
        {
            "squeue": CommandResult.completed(stdout=b"1001|RUNNING|gpu01|start\n"),
            "test": CommandResult.completed(exit_code=1),
        }
    )
    adapter = edge_adapter(runner)

    with pytest.raises(ValueError, match="non-negative"):
        await adapter.read_log("1001", -1)
    chunk = await adapter.read_log("1001", 7)
    with pytest.raises(ResourceConflict, match="before terminal"):
        await adapter.collect_artifacts("1001")

    assert chunk.offset == 7
    assert chunk.next_offset == 7
    assert chunk.data == ""
    assert chunk.end_of_stream is False


@pytest.mark.parametrize(
    "project_uri",
    [
        "ssh://cluster/projects/demo",
        "file:///outside/demo",
        "file:///projects/demo?unexpected=true",
    ],
)
async def test_slurm_rejects_unsupported_project_uri(
    valid_submission: RunSubmission,
    project_uri: str,
) -> None:
    with pytest.raises(ClusterUnavailable, match="project"):
        await edge_adapter(RoutingRunner()).submit(
            replace(valid_submission, project_uri=project_uri)
        )


@pytest.mark.parametrize(
    "source_uri",
    [
        "https://example.invalid/dataset",
        "storage://host/key",
        "storage:///../secret",
        "file:///outside/dataset",
    ],
)
async def test_slurm_rejects_unsupported_dataset_uri(
    valid_submission: RunSubmission,
    source_uri: str,
) -> None:
    submission = replace(
        valid_submission,
        mounts=(
            DatasetMount(
                dataset_version_id="version-1",
                source_uri=source_uri,
                mount_path="input/data",
            ),
        ),
    )

    with pytest.raises(ClusterUnavailable, match=r"dataset|storage"):
        await edge_adapter(RoutingRunner()).submit(submission)


@pytest.mark.parametrize(
    "record",
    [
        [],
        {"outputs": "not-a-list", "work_dir": "/cluster/workspace107/jobs/1001/workspace"},
        {"outputs": [], "work_dir": 1},
        {"outputs": [], "work_dir": "/outside/workspace"},
        {
            "outputs": ["../secret"],
            "work_dir": "/cluster/workspace107/jobs/1001/workspace",
        },
        {},
    ],
)
async def test_slurm_rejects_malformed_durable_metadata(
    valid_submission: RunSubmission,
    record: object,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = ScriptedSlurmRunner(clock, queue_seconds=1, run_seconds=1)
    first = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await first.adapter.submit(valid_submission)
    runner.jobs[job.external_job_id].terminal_logged = True
    runner.files[f"/cluster/workspace107/metadata/{job.external_job_id}.json"] = json.dumps(
        record
    ).encode()
    clock.advance(2)
    reconstructed = _harness(clock, runner, queue_seconds=1, run_seconds=1)

    with pytest.raises(ClusterUnavailable, match="metadata is malformed"):
        await reconstructed.adapter.collect_artifacts(job.external_job_id)


async def test_slurm_collects_files_under_declared_output_directory(
    valid_submission: RunSubmission,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = ScriptedSlurmRunner(clock, queue_seconds=1, run_seconds=1)
    harness = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await harness.adapter.submit(replace(valid_submission, outputs=("results",)))
    clock.advance(2)
    await harness.adapter.status(job.external_job_id)
    work_dir = f"/cluster/workspace107/jobs/{job.external_job_id}/workspace"
    runner.files.pop(f"{work_dir}/results")
    runner.files[f"{work_dir}/results/metrics.json"] = b"{}\n"

    artifacts = await harness.adapter.collect_artifacts(job.external_job_id)

    assert any(artifact.artifact_key == "output:results/metrics.json" for artifact in artifacts)


@pytest.mark.parametrize(
    ("find_output", "message"),
    [
        (b"\xff\x00", "non-UTF-8"),
        (b"/outside/result.txt\x00", "outside the run directory"),
        (
            b"/cluster/workspace107/jobs/1001/workspace/other.txt\x00",
            "undeclared output",
        ),
    ],
)
async def test_slurm_rejects_unsafe_output_enumeration(
    valid_submission: RunSubmission,
    find_output: bytes,
    message: str,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = OutputOverrideRunner(clock, queue_seconds=1, run_seconds=1)
    harness = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await harness.adapter.submit(replace(valid_submission, outputs=("results",)))
    clock.advance(2)
    await harness.adapter.status(job.external_job_id)
    work_dir = f"/cluster/workspace107/jobs/{job.external_job_id}/workspace"
    runner.files.pop(f"{work_dir}/results")
    runner.files[f"{work_dir}/results/placeholder"] = b"x"
    runner.find_output = find_output

    with pytest.raises(ClusterUnavailable, match=message):
        await harness.adapter.collect_artifacts(job.external_job_id)


async def test_slurm_rejects_malformed_artifact_size(
    valid_submission: RunSubmission,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = OutputOverrideRunner(clock, queue_seconds=1, run_seconds=1)
    harness = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await harness.adapter.submit(valid_submission)
    clock.advance(2)
    await harness.adapter.status(job.external_job_id)
    runner.stat_output = b"not-a-size\n"

    with pytest.raises(ClusterUnavailable, match="artifact size"):
        await harness.adapter.collect_artifacts(job.external_job_id)


@pytest.mark.parametrize(
    "artifact_key",
    ["unknown", "output:../secret", "output:not-declared.txt"],
)
async def test_slurm_rejects_unknown_or_unsafe_artifact_key(
    valid_submission: RunSubmission,
    artifact_key: str,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = ScriptedSlurmRunner(clock, queue_seconds=1, run_seconds=1)
    harness = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await harness.adapter.submit(valid_submission)
    clock.advance(2)

    with pytest.raises(ResourceNotFound, match="artifact"):
        await contract.read_all(harness.adapter.open_artifact(job.external_job_id, artifact_key))


async def test_slurm_rejects_missing_declared_artifact(
    valid_submission: RunSubmission,
) -> None:
    clock = FakeClock(EDGE_NOW)
    runner = ScriptedSlurmRunner(clock, queue_seconds=1, run_seconds=1)
    harness = _harness(clock, runner, queue_seconds=1, run_seconds=1)
    job = await harness.adapter.submit(valid_submission)
    clock.advance(2)
    await harness.adapter.status(job.external_job_id)
    work_dir = f"/cluster/workspace107/jobs/{job.external_job_id}/workspace"
    runner.files.pop(f"{work_dir}/result.json", None)

    with pytest.raises(ResourceNotFound, match="artifact"):
        await contract.read_all(
            harness.adapter.open_artifact(job.external_job_id, "output:result.json")
        )


async def test_slurm_requires_aware_clock() -> None:
    runner = RoutingRunner(
        {"squeue": CommandResult.completed(stdout=b"1001|RUNNING|gpu01|start\n")}
    )
    adapter = edge_adapter(runner, clock=lambda: datetime(2026, 1, 1))

    with pytest.raises(ValueError, match="timezone-aware"):
        await adapter.status("1001")
