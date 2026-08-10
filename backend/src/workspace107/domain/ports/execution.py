"""Independent Worker persistence seam。所有方法各自拥有短事务。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..execution import ClaimedExecution, CollectedArtifact
from .scheduler import SchedulerJobState


class ExecutionStore(Protocol):
    async def claim_one(self, worker_id: str, lease_seconds: float) -> ClaimedExecution | None: ...

    async def renew(self, run_id: str, token: str, lease_seconds: float) -> bool: ...

    async def release(self, run_id: str, token: str, delay_seconds: float) -> None: ...

    async def arm(self, run_id: str, token: str, now: datetime) -> int: ...

    async def attach_job(
        self, run_id: str, token: str, job_id: str, now: datetime, *, reconciled: bool
    ) -> bool: ...

    async def record_reconcile_zero(self, run_id: str, token: str, now: datetime) -> None: ...

    async def record_uncertain(
        self,
        run_id: str,
        token: str,
        now: datetime,
        code: str,
        detail: str,
        *,
        multiple: bool = False,
    ) -> None: ...

    async def record_submit_failed(
        self, run_id: str, token: str, now: datetime, reason: str
    ) -> None: ...

    async def cancel_without_job(self, run_id: str, token: str, now: datetime) -> None: ...

    async def record_poll(
        self, run_id: str, token: str, now: datetime, state: SchedulerJobState
    ) -> None: ...

    async def finalize(
        self,
        run_id: str,
        token: str,
        now: datetime,
        artifacts: tuple[CollectedArtifact, ...],
    ) -> None: ...

    async def resolve_secrets(self, workspace_id: str, names: list[str]) -> dict[str, str]: ...
