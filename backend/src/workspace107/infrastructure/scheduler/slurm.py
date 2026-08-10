"""Configurable slurmrestd adapter candidate.

The only implemented schema profile is exercised by local v0.0.40 fixtures. Selecting Slurm still
requires an explicit, human-verified version/path/query contract; this module does not claim those
fixtures match the target 107 deployment. Authentication remains in memory and error messages never
include response bodies, request payloads, URLs with credentials, or exception text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from ...domain.errors import (
    SchedulerError,
    SchedulerJobNotFound,
    SchedulerProtocolError,
    SchedulerSubmissionRejected,
    SchedulerSubmissionUncertain,
)
from ...domain.ports.scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerState,
    SchedulerSubmission,
)
from .script import render_sbatch_script

_SUPPORTED_SCHEMA_PROFILE = "slurm-v0.0.40"
_SUPPORTED_API_VERSION = "v0.0.40"
_CORRELATION_PATTERN = re.compile(r"[A-Za-z0-9_.:-]+")

_STATE_MAP = {
    "PENDING": SchedulerState.PENDING,
    "CONFIGURING": SchedulerState.PENDING,
    "REQUEUED": SchedulerState.PENDING,
    "RESIZING": SchedulerState.PENDING,
    "RUNNING": SchedulerState.RUNNING,
    "COMPLETING": SchedulerState.RUNNING,
    "SUSPENDED": SchedulerState.RUNNING,
    "COMPLETED": SchedulerState.COMPLETED,
    "FAILED": SchedulerState.FAILED,
    "NODE_FAIL": SchedulerState.FAILED,
    "OUT_OF_MEMORY": SchedulerState.FAILED,
    "TIMEOUT": SchedulerState.FAILED,
    "BOOT_FAIL": SchedulerState.FAILED,
    "DEADLINE": SchedulerState.FAILED,
    "CANCELLED": SchedulerState.CANCELLED,
    "PREEMPTED": SchedulerState.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class SlurmRestApiContract:
    """Human-verified external API facts consumed by the adapter.

    Paths are complete URL paths relative to ``base_url``. They deliberately live in deployment
    configuration instead of being inferred from an unverified version number.
    """

    api_version: str
    schema_profile: str
    submit_path: str
    job_path_template: str
    jobs_path: str
    cancel_path_template: str
    correlation_field: str
    correlation_query_parameter: str
    correlation_query_complete: bool
    correlation_max_bytes: int

    def __post_init__(self) -> None:
        if self.schema_profile != _SUPPORTED_SCHEMA_PROFILE:
            raise ValueError(
                "unsupported Slurm schema profile; target version requires a reviewed "
                "adapter profile"
            )
        if self.api_version != _SUPPORTED_API_VERSION:
            raise ValueError(
                "configured Slurm API version is not covered by the local fixture profile"
            )
        paths = {
            "submit_path": self.submit_path,
            "job_path_template": self.job_path_template,
            "jobs_path": self.jobs_path,
            "cancel_path_template": self.cancel_path_template,
        }
        for name, path in paths.items():
            invalid_path = (
                not path.startswith("/")
                or path.startswith("//")
                or "://" in path
                or any(character in path for character in ("\\", "?", "#"))
            )
            if invalid_path:
                raise ValueError(f"{name} must be an absolute path relative to the configured host")
            if self.api_version not in path:
                raise ValueError(f"{name} must contain the explicitly configured API version")
        for name, template in (
            ("job_path_template", self.job_path_template),
            ("cancel_path_template", self.cancel_path_template),
        ):
            if template.count("{job_id}") != 1:
                raise ValueError(f"{name} must contain exactly one {{job_id}} placeholder")
        if "{job_id}" in self.submit_path or "{job_id}" in self.jobs_path:
            raise ValueError("collection and submit paths cannot contain {job_id}")
        if self.correlation_field != "comment":
            raise ValueError("only the fixture-backed Slurm comment correlation field is supported")
        if not self.correlation_query_parameter.strip():
            raise ValueError("correlation query parameter must be explicit")
        if self.correlation_max_bytes < 1:
            raise ValueError("correlation_max_bytes must be positive")


class SlurmRestScheduler:
    """HTTP adapter for one explicit, locally fixture-backed slurmrestd profile."""

    name = "slurm"

    def __init__(
        self,
        base_url: str,
        user: str,
        jwt: str,
        contract: SlurmRestApiContract,
        *,
        runtime_mode: str,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url or not user or not jwt:
            raise ValueError("Slurm base URL, user, and JWT must be injected at runtime")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Slurm base URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Slurm base URL cannot contain credentials, query, or fragment")
        if timeout <= 0:
            raise ValueError("Slurm HTTP timeout must be positive")
        if runtime_mode != "native":
            raise ValueError(
                "Apptainer runtime is not implemented or target-validated; human approval "
                "is required"
            )

        self._base_url = base_url.rstrip("/")
        self._headers = {"X-SLURM-USER-NAME": user, "X-SLURM-USER-TOKEN": jwt}
        self._authentication_secret = jwt
        self._contract = contract
        self._runtime_mode = runtime_mode
        self._timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return (
            "SlurmRestScheduler("
            f"base_url={self._base_url!r}, api_version={self._contract.api_version!r}, "
            f"runtime_mode={self._runtime_mode!r}, credentials='[REDACTED]')"
        )

    async def submit(self, submission: SchedulerSubmission) -> str:
        try:
            self._validate_correlation(submission.correlation)
        except ValueError:
            raise SchedulerSubmissionRejected(
                "submission correlation is invalid for the configured Slurm comment field"
            ) from None
        if submission.environment_image.strip():
            raise SchedulerSubmissionRejected(
                "native runtime does not apply environment_image; use an explicitly native "
                "environment or wait for the human-approved Apptainer implementation"
            )

        config = submission.configuration
        if config.nodes != 1:
            raise SchedulerSubmissionRejected(
                "M1 Slurm adapter requires nodes=1 because compute resources are total values"
            )
        payload: dict[str, Any] = {
            "script": render_sbatch_script(submission),
            "job": {
                "name": submission.job_name,
                self._contract.correlation_field: submission.correlation,
                "account": config.account,
                "partition": config.partition,
                "qos": config.qos,
                "current_working_directory": str(submission.work_dir),
                "standard_output": str(submission.stdout_path),
                "standard_error": str(submission.stderr_path),
                "tasks": config.nodes,
                "cpus_per_task": config.cpus,
                "memory_per_node": config.memory_mb,
                "time_limit": config.time_limit_minutes,
                "environment": submission.environment,
            },
        }
        if config.gpus > 0:
            payload["job"]["tres_per_node"] = f"gres/gpu:{config.gpus}"

        data = await self._request_json(
            "submit", "POST", self._contract.submit_path, ambiguous_submit=True, json=payload
        )
        try:
            return _job_id(data.get("job_id"))
        except ValueError as exc:
            raise SchedulerSubmissionUncertain(
                "Slurm submit response did not contain a valid job_id; reconcile by correlation"
            ) from exc

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        try:
            self._validate_correlation(correlation)
        except ValueError:
            return SchedulerCorrelationResult(
                complete=False,
                reason="correlation is invalid for the configured Slurm comment field",
            )

        try:
            data = await self._request_json(
                "find by correlation",
                "GET",
                self._contract.jobs_path,
                params={self._contract.correlation_query_parameter: correlation},
            )
        except SchedulerError:
            return SchedulerCorrelationResult(
                complete=False,
                reason="correlation query failed, was unauthorized, or returned non-2xx",
            )
        return _parse_v0040_correlation_result(data, correlation, self._contract)

    async def poll(self, job_id: str) -> SchedulerJobState:
        path = self._job_path(self._contract.job_path_template, job_id)
        try:
            data = await self._request_json("poll", "GET", path)
        except SchedulerJobNotFound:
            return SchedulerJobState(
                state=SchedulerState.UNKNOWN,
                reason="Slurm job is not visible to the configured identity",
            )

        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise SchedulerProtocolError("Slurm poll response field jobs is not a list")
        if not jobs:
            return SchedulerJobState(
                state=SchedulerState.UNKNOWN,
                reason="Slurm poll returned no visible job",
            )
        if len(jobs) != 1 or not isinstance(jobs[0], dict):
            raise SchedulerProtocolError("Slurm poll response did not contain exactly one job")

        job = jobs[0]
        if job.get("job_id") is not None:
            try:
                returned_job_id = _job_id(job["job_id"])
            except ValueError as exc:
                raise SchedulerProtocolError("Slurm poll response has an invalid job_id") from exc
            if returned_job_id != job_id:
                raise SchedulerProtocolError(
                    "Slurm poll response job_id does not match the request"
                )

        try:
            raw_state = _state_name(job.get("job_state"))
            exit_code = _exit_code(job.get("exit_code"))
            started_at = _timestamp(job.get("start_time"))
            finished_at = _timestamp(job.get("end_time"))
        except (TypeError, ValueError) as exc:
            raise SchedulerProtocolError(
                "Slurm poll response contains invalid state or timing data"
            ) from exc

        state = _STATE_MAP.get(raw_state, SchedulerState.UNKNOWN)
        reason = self._redact(job.get("state_reason", ""))
        if state is SchedulerState.UNKNOWN and not reason:
            reason = f"Slurm state {raw_state or '[empty]'} is not mapped"
        return SchedulerJobState(
            state=state,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            reason=reason,
        )

    async def cancel(self, job_id: str) -> None:
        path = self._job_path(self._contract.cancel_path_template, job_id)
        await self._request("cancel", "DELETE", path)

    def _validate_correlation(self, correlation: str) -> None:
        if not correlation or _CORRELATION_PATTERN.fullmatch(correlation) is None:
            raise ValueError(
                "correlation must use only ASCII letters, digits, dot, colon, dash, underscore"
            )
        if len(correlation.encode("utf-8")) > self._contract.correlation_max_bytes:
            raise ValueError("correlation exceeds the human-verified Slurm field capacity")

    @staticmethod
    def _job_path(template: str, job_id: str) -> str:
        if not job_id or any(ord(character) < 32 for character in job_id):
            raise SchedulerProtocolError("job_id is empty or contains control characters")
        return template.replace("{job_id}", quote(job_id, safe=""))

    async def _request_json(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        ambiguous_submit: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        response = await self._request(
            operation, method, path, ambiguous_submit=ambiguous_submit, **kwargs
        )
        try:
            data = response.json()
        except ValueError:
            error_type = (
                SchedulerSubmissionUncertain if ambiguous_submit else SchedulerProtocolError
            )
            raise error_type(f"Slurm {operation} response was not valid JSON") from None
        if not isinstance(data, dict):
            error_type = (
                SchedulerSubmissionUncertain if ambiguous_submit else SchedulerProtocolError
            )
            raise error_type(f"Slurm {operation} response was not a JSON object")
        return data

    async def _request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        ambiguous_submit: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.RequestError:
            error_type = SchedulerSubmissionUncertain if ambiguous_submit else SchedulerError
            raise error_type(
                f"Slurm {operation} transport failed; credentials and body redacted"
            ) from None

        status = response.status_code
        if 200 <= status < 300:
            return response
        if ambiguous_submit:
            raise SchedulerSubmissionUncertain(
                f"Slurm submit returned HTTP {status}; reconcile by correlation"
            )
        if status == 404:
            raise SchedulerJobNotFound(f"Slurm {operation} returned 404")
        raise SchedulerError(f"Slurm {operation} returned HTTP {status}; response body redacted")

    def _redact(self, raw: Any) -> str:
        if raw is None:
            return ""
        text = str(raw).replace(self._authentication_secret, "[REDACTED]")
        text = re.sub(r"(?i)(bearer\s+|token\s*[=:]\s*)\S+", r"\1[REDACTED]", text)
        return text[:256]


def _job_id(raw: Any) -> str:
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ValueError("invalid job id")
    value = str(raw).strip()
    if not value or any(ord(character) < 32 for character in value):
        raise ValueError("invalid job id")
    return value


def _state_name(raw: Any) -> str:
    if isinstance(raw, list):
        if len(raw) != 1 or not isinstance(raw[0], str):
            raise ValueError("invalid job state list")
        raw = raw[0]
    if not isinstance(raw, str):
        raise ValueError("invalid job state")
    return raw.strip().upper().split(maxsplit=1)[0].rstrip("+")


def _exit_code(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("return_code")
        if isinstance(raw, dict):
            raw = raw.get("number")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("invalid exit code")
    return raw


def _timestamp(raw: Any) -> datetime | None:
    if raw is None or raw == 0:
        return None
    if isinstance(raw, dict):
        raw = raw.get("number")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError("invalid timestamp")
    return datetime.fromtimestamp(raw, tz=UTC)


def _parse_v0040_correlation_result(
    data: dict[str, Any], correlation: str, contract: SlurmRestApiContract
) -> SchedulerCorrelationResult:
    """Parse the exact locally-fixtured non-paginated correlation response shape."""
    if not contract.correlation_query_complete:
        return SchedulerCorrelationResult(
            complete=False,
            reason="target query completeness and pagination behavior are not verified",
        )

    unknown_fields = set(data) - {"jobs", "errors", "warnings"}
    if unknown_fields:
        return SchedulerCorrelationResult(
            complete=False,
            reason="response contains unsupported pagination or metadata fields",
        )
    for field in ("errors", "warnings"):
        messages = data.get(field, [])
        if not isinstance(messages, list) or messages:
            return SchedulerCorrelationResult(
                complete=False,
                reason=f"response field {field} is non-empty or has an unsupported shape",
            )

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        return SchedulerCorrelationResult(
            complete=False,
            reason="response field jobs is not a list",
        )

    job_ids: list[str] = []
    seen_ids: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict) or job.get(contract.correlation_field) != correlation:
            return SchedulerCorrelationResult(
                complete=False,
                reason="response does not prove an exact correlation filter",
            )
        try:
            job_id = _job_id(job.get("job_id"))
        except ValueError:
            return SchedulerCorrelationResult(
                complete=False,
                reason="response contains a job without a valid job_id",
            )
        if job_id in seen_ids:
            return SchedulerCorrelationResult(
                complete=False,
                reason="response contains duplicate job ids",
            )
        seen_ids.add(job_id)
        job_ids.append(job_id)

    return SchedulerCorrelationResult(complete=True, job_ids=tuple(job_ids))
