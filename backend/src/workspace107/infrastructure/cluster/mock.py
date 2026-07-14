import json
import os
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

import anyio.to_thread

from workspace107.domain.enums import ArtifactKind, RunStatus
from workspace107.domain.errors import PreflightFailed, ResourceNotFound
from workspace107.domain.models import (
    CollectedArtifact,
    JobObservation,
    LogChunk,
    PreflightCheck,
    RunSubmission,
    SubmittedJob,
    utc_now,
)

type MockOutcome = Literal["success", "failure"]
_TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
_READ_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class _JobState:
    external_job_id: str
    submitted_at: datetime
    queue_seconds: float
    run_seconds: float
    outcome: MockOutcome
    cancelled_at: datetime | None
    log_path: str
    result_path: str
    submission: Mapping[str, object]


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _required_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError("mock job state is invalid")
    return value


def _required_float(data: Mapping[str, object], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("mock job state is invalid")
    return float(value)


def _optional_datetime(data: Mapping[str, object], key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("mock job state is invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("mock job state is invalid")
    return parsed.astimezone(UTC)


def _state_from_bytes(content: bytes) -> _JobState:
    decoded: object = json.loads(content)
    if not isinstance(decoded, dict):
        raise ValueError("mock job state is invalid")
    data = cast(dict[str, object], decoded)
    outcome_value = _required_str(data, "outcome")
    if outcome_value not in ("success", "failure"):
        raise ValueError("mock job state is invalid")
    submission_value = data.get("submission")
    if not isinstance(submission_value, dict):
        raise ValueError("mock job state is invalid")
    submitted_at = _optional_datetime(data, "submitted_at")
    if submitted_at is None:
        raise ValueError("mock job state is invalid")
    return _JobState(
        external_job_id=_required_str(data, "external_job_id"),
        submitted_at=submitted_at,
        queue_seconds=_required_float(data, "queue_seconds"),
        run_seconds=_required_float(data, "run_seconds"),
        outcome=outcome_value,
        cancelled_at=_optional_datetime(data, "cancelled_at"),
        log_path=_required_str(data, "log_path"),
        result_path=_required_str(data, "result_path"),
        submission=cast(dict[str, object], submission_value),
    )


def _state_bytes(state: _JobState) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": 1,
                "external_job_id": state.external_job_id,
                "submitted_at": state.submitted_at.isoformat(),
                "queue_seconds": state.queue_seconds,
                "run_seconds": state.run_seconds,
                "outcome": state.outcome,
                "cancelled_at": (
                    state.cancelled_at.isoformat() if state.cancelled_at is not None else None
                ),
                "log_path": state.log_path,
                "result_path": state.result_path,
                "submission": dict(state.submission),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _is_json_serializable(value: object) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


class MockClusterAdapter:
    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        queue_seconds: float = 0.1,
        run_seconds: float = 0.2,
        outcome: MockOutcome = "success",
    ) -> None:
        if queue_seconds < 0 or run_seconds < 0:
            raise ValueError("mock durations must be non-negative")
        if outcome not in ("success", "failure"):
            raise ValueError("unsupported mock outcome")
        self._root = root.expanduser().resolve()
        self._jobs = self._root / "jobs"
        self._logs = self._root / "logs"
        self._results = self._root / "results"
        self._clock = clock
        self._queue_seconds = queue_seconds
        self._run_seconds = run_seconds
        self._outcome: MockOutcome = outcome
        for directory in (self._jobs, self._logs, self._results):
            directory.mkdir(parents=True, exist_ok=True)

    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]:
        resources_valid = (
            spec.resources.cpus > 0
            and spec.resources.memory_mb > 0
            and spec.resources.gpus >= 0
            and spec.resources.walltime_seconds > 0
        )
        environment_valid = _is_json_serializable(dict(spec.environment))
        return (
            PreflightCheck(
                code="mock_project_uri",
                passed=bool(spec.project_uri),
                message=(
                    "Project URI is available." if spec.project_uri else "Project URI is required."
                ),
            ),
            PreflightCheck(
                code="mock_resources",
                passed=resources_valid,
                message=(
                    "Resources are supported."
                    if resources_valid
                    else "Resources are not supported."
                ),
            ),
            PreflightCheck(
                code="mock_environment",
                passed=environment_valid,
                message=(
                    "Environment is serializable."
                    if environment_valid
                    else "Environment must be JSON serializable."
                ),
            ),
        )

    async def submit(self, spec: RunSubmission) -> SubmittedJob:
        checks = await self.preflight(spec)
        failed = tuple(check.code for check in checks if not check.passed)
        if failed:
            raise PreflightFailed(f"mock preflight failed: {', '.join(failed)}")

        external_job_id = str(uuid4())
        submitted_at = self._now()
        state = _JobState(
            external_job_id=external_job_id,
            submitted_at=submitted_at,
            queue_seconds=self._queue_seconds,
            run_seconds=self._run_seconds,
            outcome=self._outcome,
            cancelled_at=None,
            log_path=f"logs/{external_job_id}.log",
            result_path=f"results/{external_job_id}.json",
            submission=self._submission_summary(spec),
        )
        await self._save(state)
        await self._materialize(state, submitted_at)
        return SubmittedJob(external_job_id=external_job_id, submitted_at=submitted_at)

    async def status(self, external_job_id: str) -> JobObservation:
        state = await self._load(external_job_id)
        observed_at = self._now()
        status = self._status(state, observed_at)
        await self._materialize(state, observed_at)
        exit_code = {
            RunStatus.SUCCEEDED: 0,
            RunStatus.FAILED: 1,
            RunStatus.CANCELLED: 130,
        }.get(status)
        return JobObservation(
            status=status,
            observed_at=observed_at,
            exit_code=exit_code,
            details={"adapter": "mock", "outcome": state.outcome},
        )

    async def cancel(self, external_job_id: str) -> None:
        state = await self._load(external_job_id)
        now = self._now()
        if self._status(state, now) in _TERMINAL:
            await self._materialize(state, now)
            return
        state = replace(state, cancelled_at=now)
        await self._save(state)
        await self._materialize(state, now)

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk:
        if offset < 0:
            raise ValueError("log offset must be non-negative")
        state = await self._load(external_job_id)
        now = self._now()
        status = self._status(state, now)
        log_content, _ = await self._materialize(state, now)
        if offset > len(log_content):
            raise ValueError("log offset exceeds available content")
        data = log_content[offset:]
        next_offset = offset + len(data)
        return LogChunk(
            offset=offset,
            next_offset=next_offset,
            data=data.decode(),
            end_of_stream=status in _TERMINAL and next_offset == len(log_content),
        )

    async def collect_artifacts(self, external_job_id: str) -> tuple[CollectedArtifact, ...]:
        state = await self._load(external_job_id)
        now = self._now()
        status = self._status(state, now)
        if status not in _TERMINAL:
            return ()
        log_content, result_content = await self._materialize(state, now)
        log = CollectedArtifact(
            artifact_key="log",
            name="job.log",
            kind=ArtifactKind.LOG,
            media_type="text/plain",
            size_bytes=len(log_content),
        )
        if status is not RunStatus.SUCCEEDED or result_content is None:
            return (log,)
        result = CollectedArtifact(
            artifact_key="result",
            name="result.json",
            kind=ArtifactKind.RESULT,
            media_type="application/json",
            size_bytes=len(result_content),
        )
        return result, log

    def open_artifact(self, external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            state = await self._load(external_job_id)
            now = self._now()
            status = self._status(state, now)
            if status not in _TERMINAL:
                raise ResourceNotFound("mock artifact is not available")
            await self._materialize(state, now)
            if artifact_key == "log":
                path = self._logs / f"{external_job_id}.log"
            elif artifact_key == "result" and status is RunStatus.SUCCEEDED:
                path = self._results / f"{external_job_id}.json"
            else:
                raise ResourceNotFound("mock artifact not found")
            handle = await anyio.to_thread.run_sync(path.open, "rb")
            try:
                while content := await anyio.to_thread.run_sync(handle.read, _READ_SIZE):
                    yield content
            finally:
                await anyio.to_thread.run_sync(handle.close)

        return stream()

    async def _load(self, external_job_id: str) -> _JobState:
        self._validate_job_id(external_job_id)
        try:
            content = await anyio.to_thread.run_sync(
                (self._jobs / f"{external_job_id}.json").read_bytes
            )
        except FileNotFoundError as exc:
            raise ResourceNotFound("mock job not found") from exc
        state = _state_from_bytes(content)
        if state.external_job_id != external_job_id:
            raise ValueError("mock job state is invalid")
        return state

    async def _save(self, state: _JobState) -> None:
        await anyio.to_thread.run_sync(
            _atomic_write,
            self._jobs / f"{state.external_job_id}.json",
            _state_bytes(state),
        )

    async def _materialize(self, state: _JobState, now: datetime) -> tuple[bytes, bytes | None]:
        status = self._status(state, now)
        log_content = self._log_content(state, status)
        await anyio.to_thread.run_sync(
            _atomic_write,
            self._logs / f"{state.external_job_id}.log",
            log_content,
        )
        result_content: bytes | None = None
        if status is RunStatus.SUCCEEDED:
            result_content = self._result_content(state)
            await anyio.to_thread.run_sync(
                _atomic_write,
                self._results / f"{state.external_job_id}.json",
                result_content,
            )
        return log_content, result_content

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("mock clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _status(state: _JobState, now: datetime) -> RunStatus:
        if state.cancelled_at is not None:
            return RunStatus.CANCELLED
        elapsed = (now - state.submitted_at).total_seconds()
        if elapsed < state.queue_seconds:
            return RunStatus.QUEUED
        if elapsed < state.queue_seconds + state.run_seconds:
            return RunStatus.RUNNING
        return RunStatus.SUCCEEDED if state.outcome == "success" else RunStatus.FAILED

    @staticmethod
    def _log_content(state: _JobState, status: RunStatus) -> bytes:
        lines = [f"job {state.external_job_id} queued\n"]
        if status in (RunStatus.RUNNING, RunStatus.SUCCEEDED, RunStatus.FAILED):
            lines.append(f"job {state.external_job_id} running {state.submission['entrypoint']}\n")
        if status in _TERMINAL:
            lines.append(f"job {state.external_job_id} {status.value}\n")
        return "".join(lines).encode()

    @staticmethod
    def _result_content(state: _JobState) -> bytes:
        return (
            json.dumps(
                {
                    "external_job_id": state.external_job_id,
                    "status": "succeeded",
                    "submission": dict(state.submission),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()

    @staticmethod
    def _submission_summary(spec: RunSubmission) -> dict[str, object]:
        return {
            "entrypoint": spec.entrypoint,
            "resources": {
                "cpus": spec.resources.cpus,
                "memory_mb": spec.resources.memory_mb,
                "gpus": spec.resources.gpus,
                "walltime_seconds": spec.resources.walltime_seconds,
                "account": spec.resources.account,
                "partition": spec.resources.partition,
                "qos": spec.resources.qos,
            },
            "mounts": [
                {
                    "dataset_version_id": mount.dataset_version_id,
                    "mount_path": mount.mount_path,
                }
                for mount in spec.mounts
            ],
            "outputs": list(spec.outputs),
            "environment": dict(spec.environment),
        }

    @staticmethod
    def _validate_job_id(external_job_id: str) -> None:
        try:
            parsed = UUID(external_job_id)
        except ValueError as exc:
            raise ResourceNotFound("mock job not found") from exc
        if str(parsed) != external_job_id:
            raise ResourceNotFound("mock job not found")
