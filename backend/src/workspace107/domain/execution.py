"""Single-active Independent Worker 的最小持久恢复事实。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import ProjectVersion, Run
from .run_snapshot import RunSnapshot


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    run_id: str
    correlation: str
    attempt_no: int
    next_action_at: datetime
    created_at: datetime
    updated_at: datetime
    cancel_requested_at: datetime | None = None
    uncertainty_code: str | None = None
    uncertainty_detail: str = ""
    observed_scheduler_state: str | None = None
    observed_exit_code: int | None = None
    observed_started_at: datetime | None = None
    observed_finished_at: datetime | None = None
    observed_reason: str = ""


@dataclass(frozen=True, slots=True)
class PendingExecution:
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
