import json
import mimetypes
import re
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import cast
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from workspace107.domain.enums import ArtifactKind, RunStatus
from workspace107.domain.errors import (
    ClusterUnavailable,
    ExternalCommandFailed,
    InvalidRelativePath,
    ResourceConflict,
    ResourceNotFound,
)
from workspace107.domain.models import (
    CollectedArtifact,
    JobObservation,
    LogChunk,
    PreflightCheck,
    RunSubmission,
    SubmittedJob,
    utc_now,
)
from workspace107.domain.values import relative_posix_path
from workspace107.infrastructure.cluster.slurm.command_runner import (
    CommandResult,
    CommandRunner,
)
from workspace107.infrastructure.cluster.slurm.parser import (
    parse_sacct,
    parse_sbatch_job_id,
    parse_squeue,
)
from workspace107.infrastructure.cluster.slurm.renderer import (
    SlurmMount,
    SlurmRenderSpec,
    render_sbatch,
)

_JOB_ID = re.compile(r"[0-9]+")
_TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
_LOG_KEY = "log:stdout"


@dataclass(frozen=True, slots=True)
class _JobMetadata:
    outputs: tuple[str, ...]
    work_dir: PurePosixPath


def _root(value: PurePosixPath, name: str) -> PurePosixPath:
    rendered = str(value)
    if (
        not value.is_absolute()
        or ".." in value.parts
        or any(character in rendered for character in "\r\n\x00")
    ):
        raise ValueError(f"{name} must be a safe absolute POSIX path")
    return value


def _within(path: PurePosixPath, roots: tuple[PurePosixPath, ...]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


class SlurmClusterAdapter:
    def __init__(
        self,
        runner: CommandRunner,
        *,
        remote_root: PurePosixPath,
        log_root: PurePosixPath | None = None,
        project_roots: tuple[PurePosixPath, ...],
        dataset_roots: tuple[PurePosixPath, ...],
        storage_root: PurePosixPath,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not project_roots:
            raise ValueError("at least one Slurm project root is required")
        self._runner = runner
        self._remote_root = _root(remote_root, "remote_root")
        self._project_roots = tuple(_root(root, "project_root") for root in project_roots)
        self._dataset_roots = tuple(_root(root, "dataset_root") for root in dataset_roots)
        self._storage_root = _root(storage_root, "storage_root")
        self._clock = clock
        self._submissions_root = self._remote_root / "submissions"
        self._jobs_root = self._remote_root / "jobs"
        self._log_root = _root(log_root or self._remote_root / "logs", "log_root")
        self._metadata_root = self._remote_root / "metadata"
        self._metadata: dict[str, _JobMetadata] = {}

    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]:
        result = await self._runner.run(
            ("sinfo", "-h", "-p", spec.resources.partition),
        )
        passed = result.exit_code == 0 and bool(result.stdout.strip())
        return (
            PreflightCheck(
                code="slurm_partition_available",
                passed=passed,
                message=(
                    "The configured Slurm partition is available."
                    if passed
                    else "The configured Slurm partition is unavailable."
                ),
            ),
        )

    async def submit(self, spec: RunSubmission) -> SubmittedJob:
        token = uuid4().hex
        project_path = self._file_uri(spec.project_uri, self._project_roots, "project")
        mounts = tuple(
            SlurmMount(
                source=self._dataset_uri(mount.source_uri),
                target=mount.mount_path,
            )
            for mount in spec.mounts
        )
        script = render_sbatch(
            SlurmRenderSpec(
                job_name=f"workspace107-{token[:12]}",
                project_path=project_path,
                jobs_root=self._jobs_root,
                log_root=self._log_root,
                entrypoint=spec.entrypoint,
                resources=spec.resources,
                mounts=mounts,
                outputs=spec.outputs,
                environment=spec.environment,
            )
        )
        await self._run(
            (
                "mkdir",
                "-p",
                "--",
                str(self._submissions_root),
                str(self._jobs_root),
                str(self._log_root),
                str(self._metadata_root),
            ),
            operation="prepare Slurm directories",
        )
        script_path = self._submissions_root / f"{token}.sbatch"
        await self._run(
            ("tee", "--", str(script_path)),
            input_data=script.encode("utf-8"),
            operation="write Slurm script",
        )
        await self._run(
            ("chmod", "700", "--", str(script_path)),
            operation="protect Slurm script",
        )
        submitted = await self._run(
            ("sbatch", "--parsable", str(script_path)),
            operation="submit Slurm job",
        )
        external_job_id = parse_sbatch_job_id(submitted.stdout)
        work_dir = self._jobs_root / external_job_id / "workspace"
        metadata = _JobMetadata(outputs=tuple(sorted(spec.outputs)), work_dir=work_dir)
        metadata_payload = json.dumps(
            {
                "schema_version": 1,
                "outputs": list(metadata.outputs),
                "work_dir": str(metadata.work_dir),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            await self._run(
                ("tee", "--", str(self._metadata_path(external_job_id))),
                input_data=metadata_payload,
                operation="write Slurm job metadata",
            )
            await self._run(
                ("tee", "-a", "--", str(self._stdout_path(external_job_id))),
                input_data=f"[workspace107] queued job {external_job_id}\n".encode(),
                operation="initialize Slurm log",
            )
        except BaseException:
            with suppress(Exception):
                await self._runner.run(("scancel", external_job_id))
            raise
        self._metadata[external_job_id] = metadata
        return SubmittedJob(external_job_id=external_job_id, submitted_at=self._now())

    async def status(self, external_job_id: str) -> JobObservation:
        job_id = self._job_id(external_job_id)
        active_result = await self._runner.run(("squeue", "-h", "-j", job_id, "-o", "%i|%T|%N|%S"))
        if active_result.exit_code == 0:
            active = parse_squeue(active_result.stdout, self._now())
            if active is not None:
                return active
        accounting = await self._runner.run(
            (
                "sacct",
                "-n",
                "-P",
                "-j",
                job_id,
                "--format=JobIDRaw,State,ExitCode,Start,End",
            )
        )
        if accounting.exit_code != 0:
            raise ExternalCommandFailed("Slurm accounting lookup failed.")
        if not accounting.stdout.strip():
            raise ResourceNotFound(f"Slurm job {job_id} was not found")
        return parse_sacct(accounting.stdout, job_id, self._now())

    async def cancel(self, external_job_id: str) -> None:
        observation = await self.status(external_job_id)
        if observation.status in _TERMINAL:
            return
        await self._run(
            ("scancel", self._job_id(external_job_id)),
            operation="cancel Slurm job",
        )

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk:
        if offset < 0:
            raise ValueError("log offset must be non-negative")
        observation = await self.status(external_job_id)
        path = self._stdout_path(external_job_id)
        exists = await self._runner.run(("test", "-f", "--", str(path)))
        if exists.exit_code != 0:
            return LogChunk(
                offset=offset,
                next_offset=offset,
                data="",
                end_of_stream=observation.status in _TERMINAL,
            )
        result = await self._run(
            ("tail", "-c", f"+{offset + 1}", "--", str(path)),
            operation="read Slurm log",
        )
        return LogChunk(
            offset=offset,
            next_offset=offset + len(result.stdout),
            data=result.stdout.decode("utf-8", errors="replace"),
            end_of_stream=observation.status in _TERMINAL,
        )

    async def collect_artifacts(
        self,
        external_job_id: str,
    ) -> tuple[CollectedArtifact, ...]:
        observation = await self.status(external_job_id)
        if observation.status not in _TERMINAL:
            raise ResourceConflict("Slurm artifacts are not available before terminal state")
        metadata = await self._load_metadata(external_job_id)
        artifacts: list[CollectedArtifact] = []
        log_path = self._stdout_path(external_job_id)
        log_size = await self._file_size(log_path)
        if log_size is not None:
            artifacts.append(
                CollectedArtifact(
                    artifact_key=_LOG_KEY,
                    name=f"slurm-{external_job_id}.out",
                    kind=ArtifactKind.LOG,
                    media_type="text/plain; charset=utf-8",
                    size_bytes=log_size,
                )
            )
        if observation.status is RunStatus.SUCCEEDED:
            for relative in await self._output_files(metadata):
                path = metadata.work_dir.joinpath(*PurePosixPath(relative).parts)
                size = await self._file_size(path)
                if size is None:
                    continue
                artifacts.append(
                    CollectedArtifact(
                        artifact_key=f"output:{relative}",
                        name=PurePosixPath(relative).name,
                        kind=ArtifactKind.RESULT,
                        media_type=mimetypes.guess_type(relative)[0] or "application/octet-stream",
                        size_bytes=size,
                    )
                )
        return tuple(artifacts)

    def open_artifact(
        self,
        external_job_id: str,
        artifact_key: str,
    ) -> AsyncIterator[bytes]:
        async def chunks() -> AsyncIterator[bytes]:
            await self.status(external_job_id)
            metadata = await self._load_metadata(external_job_id)
            path = self._artifact_path(external_job_id, artifact_key, metadata)
            exists = await self._runner.run(("test", "-f", "--", str(path)))
            if exists.exit_code != 0:
                raise ResourceNotFound(f"Slurm artifact {artifact_key!r} was not found")
            result = await self._run(
                ("cat", "--", str(path)),
                operation="read Slurm artifact",
            )
            for start in range(0, len(result.stdout), 64 * 1024):
                yield result.stdout[start : start + 64 * 1024]

        return chunks()

    async def _run(
        self,
        arguments: tuple[str, ...],
        *,
        operation: str,
        input_data: bytes | None = None,
    ) -> CommandResult:
        result = await self._runner.run(arguments, input_data=input_data)
        if result.exit_code != 0:
            raise ExternalCommandFailed(f"External command failed to {operation}.")
        return result

    async def _load_metadata(self, external_job_id: str) -> _JobMetadata:
        job_id = self._job_id(external_job_id)
        cached = self._metadata.get(job_id)
        if cached is not None:
            return cached
        result = await self._run(
            ("cat", "--", str(self._metadata_path(job_id))),
            operation="read Slurm job metadata",
        )
        try:
            decoded = cast(object, json.loads(result.stdout))
            if not isinstance(decoded, dict):
                raise TypeError
            record = cast(dict[str, object], decoded)
            outputs_value = record["outputs"]
            work_dir_value = record["work_dir"]
            if not isinstance(outputs_value, list) or not all(
                isinstance(value, str) for value in cast(list[object], outputs_value)
            ):
                raise TypeError
            if not isinstance(work_dir_value, str):
                raise TypeError
            work_dir = _root(PurePosixPath(work_dir_value), "metadata work_dir")
            expected_work_dir = self._jobs_root / job_id / "workspace"
            if work_dir != expected_work_dir:
                raise ValueError
            outputs = cast(list[str], outputs_value)
            metadata = _JobMetadata(
                outputs=tuple(str(relative_posix_path(value)) for value in outputs),
                work_dir=work_dir,
            )
        except (
            InvalidRelativePath,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise ClusterUnavailable("Slurm job metadata is malformed") from error
        self._metadata[job_id] = metadata
        return metadata

    async def _output_files(self, metadata: _JobMetadata) -> tuple[str, ...]:
        collected: set[str] = set()
        for declared in metadata.outputs:
            path = metadata.work_dir.joinpath(*PurePosixPath(declared).parts)
            is_file = await self._runner.run(("test", "-f", "--", str(path)))
            if is_file.exit_code == 0:
                collected.add(declared)
                continue
            is_directory = await self._runner.run(("test", "-d", "--", str(path)))
            if is_directory.exit_code != 0:
                continue
            result = await self._run(
                ("find", str(path), "-type", "f", "-print0"),
                operation="enumerate Slurm outputs",
            )
            for raw_path in result.stdout.split(b"\x00"):
                if not raw_path:
                    continue
                try:
                    found = PurePosixPath(raw_path.decode("utf-8"))
                except UnicodeDecodeError as error:
                    raise ClusterUnavailable("Slurm returned a non-UTF-8 output path") from error
                if not found.is_relative_to(metadata.work_dir):
                    raise ClusterUnavailable("Slurm returned an output outside the run directory")
                relative = str(found.relative_to(metadata.work_dir))
                normalized = str(relative_posix_path(relative))
                if not PurePosixPath(normalized).is_relative_to(PurePosixPath(declared)):
                    raise ClusterUnavailable("Slurm returned an undeclared output path")
                collected.add(normalized)
        return tuple(sorted(collected))

    async def _file_size(self, path: PurePosixPath) -> int | None:
        exists = await self._runner.run(("test", "-f", "--", str(path)))
        if exists.exit_code != 0:
            return None
        result = await self._run(
            ("stat", "-c", "%s", "--", str(path)),
            operation="inspect Slurm artifact",
        )
        value = result.stdout.strip()
        if not value.isdigit():
            raise ClusterUnavailable("Slurm returned a malformed artifact size")
        return int(value)

    def _artifact_path(
        self,
        external_job_id: str,
        artifact_key: str,
        metadata: _JobMetadata,
    ) -> PurePosixPath:
        if artifact_key == _LOG_KEY:
            return self._stdout_path(external_job_id)
        if not artifact_key.startswith("output:"):
            raise ResourceNotFound(f"Slurm artifact {artifact_key!r} was not found")
        try:
            relative = str(relative_posix_path(artifact_key.removeprefix("output:")))
        except InvalidRelativePath as error:
            raise ResourceNotFound(f"Slurm artifact {artifact_key!r} was not found") from error
        relative_path = PurePosixPath(relative)
        if not any(
            relative_path == PurePosixPath(declared)
            or relative_path.is_relative_to(PurePosixPath(declared))
            for declared in metadata.outputs
        ):
            raise ResourceNotFound(f"Slurm artifact {artifact_key!r} was not found")
        return metadata.work_dir.joinpath(*relative_path.parts)

    def _file_uri(
        self,
        value: str,
        roots: tuple[PurePosixPath, ...],
        name: str,
    ) -> PurePosixPath:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "file"
            or parsed.netloc not in ("", "localhost")
            or parsed.query
            or parsed.fragment
        ):
            raise ClusterUnavailable(f"Slurm {name} URI is unsupported")
        path = _root(PurePosixPath(unquote(parsed.path)), f"{name} path")
        if not _within(path, roots):
            raise ClusterUnavailable(f"Slurm {name} path is outside configured roots")
        return path

    def _dataset_uri(self, value: str) -> PurePosixPath:
        parsed = urlsplit(value)
        if parsed.scheme == "file":
            return self._file_uri(value, self._dataset_roots, "dataset")
        if parsed.scheme != "storage" or parsed.netloc or parsed.query or parsed.fragment:
            raise ClusterUnavailable("Slurm dataset URI is unsupported")
        try:
            key = relative_posix_path(unquote(parsed.path).lstrip("/"))
        except InvalidRelativePath as error:
            raise ClusterUnavailable("Slurm storage URI is malformed") from error
        return self._storage_root.joinpath(*key.parts)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Slurm adapter clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _job_id(value: str) -> str:
        if _JOB_ID.fullmatch(value) is None:
            raise ResourceNotFound(f"Slurm job {value!r} was not found")
        return value

    def _stdout_path(self, external_job_id: str) -> PurePosixPath:
        return self._log_root / f"{self._job_id(external_job_id)}.out"

    def _metadata_path(self, external_job_id: str) -> PurePosixPath:
        return self._metadata_root / f"{self._job_id(external_job_id)}.json"
