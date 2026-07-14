from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from workspace107.domain.models import (
    CollectedArtifact,
    JobObservation,
    LogChunk,
    PreflightCheck,
    RunSubmission,
    SubmittedJob,
)


@runtime_checkable
class ClusterPort(Protocol):
    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]: ...

    async def submit(self, spec: RunSubmission) -> SubmittedJob: ...

    async def status(self, external_job_id: str) -> JobObservation: ...

    async def cancel(self, external_job_id: str) -> None: ...

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk: ...

    async def collect_artifacts(self, external_job_id: str) -> tuple[CollectedArtifact, ...]: ...

    def open_artifact(self, external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]: ...
