"""Single-active Worker persistence seam；每个方法拥有一个短事务。"""

from __future__ import annotations

from typing import Protocol

from ..execution import CollectedArtifact, PendingExecution, ValidatedExecutionContext
from ..models import Run
from ..run_snapshot import RunSnapshot
from .run_workspace import RunWorkspaceInput
from .scheduler import SchedulerJobState


class RunInputUnavailable(RuntimeError):
    """Snapshot-fixed input can no longer be materialized for this Run."""


class ExecutionContextPort(Protocol):
    """Revalidate persisted execution authority and exact Snapshot references."""

    async def validate(self, run: Run, snapshot: RunSnapshot) -> ValidatedExecutionContext: ...


class ExecutionStore(Protocol):
    async def next_due(self) -> PendingExecution | None: ...

    async def resolve_inputs(self, run_id: str) -> tuple[RunWorkspaceInput, ...]: ...

    async def defer(self, run_id: str, delay_seconds: float) -> None: ...

    async def arm(self, run_id: str) -> int | None: ...

    async def attach_job(self, run_id: str, job_id: str, *, reconciled: bool) -> bool: ...

    async def clear_reconciled_zero(self, run_id: str) -> None: ...

    async def record_uncertain(self, run_id: str, code: str, detail: str) -> None: ...

    async def record_submit_failed(self, run_id: str, reason: str) -> None: ...

    async def cancel_without_job(self, run_id: str) -> None: ...

    async def record_poll(
        self,
        run_id: str,
        state: SchedulerJobState,
        *,
        cancel_failure: str | None,
    ) -> None: ...

    async def finalize(
        self,
        run_id: str,
        artifacts: tuple[CollectedArtifact, ...],
    ) -> None: ...

    async def retain_secret_redactions(self, run_id: str, values: list[str]) -> None: ...
