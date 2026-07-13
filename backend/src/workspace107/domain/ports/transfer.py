from pathlib import Path
from typing import Protocol, runtime_checkable

from workspace107.domain.models import (
    IgnoreRules,
    ProjectSnapshot,
    PullRequest,
    TransferPlan,
    TransferResult,
)


@runtime_checkable
class ProjectTransferPort(Protocol):
    async def scan(self, source: Path, ignore: IgnoreRules) -> ProjectSnapshot: ...

    async def push(self, plan: TransferPlan) -> TransferResult: ...

    async def pull(self, request: PullRequest) -> TransferResult: ...
