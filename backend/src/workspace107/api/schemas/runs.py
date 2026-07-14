from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from workspace107.domain.enums import ArtifactKind, RunStatus
from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.values import relative_posix_path


class RunDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: UUID
    mount_path: str = Field(max_length=500)

    @field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, value: str) -> str:
        try:
            return str(relative_posix_path(value))
        except InvalidRelativePath as exc:
            raise ValueError("must be a safe relative POSIX path") from exc


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    template_id: UUID
    datasets: tuple[RunDatasetRequest, ...] = ()


class PreflightCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    passed: bool
    message: str


class PreflightResponse(BaseModel):
    passed: bool
    checks: tuple[PreflightCheckResponse, ...]


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    template_id: UUID
    submitted_by: UUID
    status: RunStatus
    external_job_id: str | None
    exit_code: int | None
    failure_code: str | None
    failure_message: str | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    event_type: str
    from_status: RunStatus | None
    to_status: RunStatus | None
    message: str | None
    details: dict[str, object]
    created_at: datetime


class LogChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offset: int
    next_offset: int
    data: str
    end_of_stream: bool


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    kind: ArtifactKind
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
