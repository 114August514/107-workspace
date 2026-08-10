"""Independent Worker 的内部持久协调事实。不会序列化到 public API。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import ProjectVersion, Run
from .run_snapshot import RunSnapshot


class ExecutionPhase(StrEnum):
    READY = "ready"
    SUBMITTING = "submitting"
    MONITORING = "monitoring"
    FINALIZING = "finalizing"
    UNCERTAIN = "uncertain"
    COMPLETE = "complete"


class SubmissionOutcome(StrEnum):
    ARMED = "armed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    RECONCILED_ZERO = "reconciled_zero"
    RECONCILED_ONE = "reconciled_one"
    RECONCILED_MULTIPLE = "reconciled_multiple"


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    run_id: str
    phase: ExecutionPhase
    correlation: str
    attempt_no: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    cancel_requested_at: datetime | None = None
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_generation: int = 0
    lease_expires_at: datetime | None = None
    uncertainty_code: str | None = None
    uncertainty_detail: str = ""
    observed_scheduler_state: str | None = None
    observed_exit_code: int | None = None
    observed_started_at: datetime | None = None
    observed_finished_at: datetime | None = None
    observed_reason: str = ""
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ClaimedExecution:
    run: Run
    snapshot: RunSnapshot
    project_version: ProjectVersion
    intent: ExecutionIntent


@dataclass(frozen=True, slots=True)
class CollectedArtifact:
    id: str
    source_path: str
    name: str
    optional: bool
    size: int | None
    file_count: int | None
    content_hash: str | None


class LeaseLost(RuntimeError):
    """当前 Worker 的 fencing token 已失效。"""
