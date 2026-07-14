from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.values import relative_posix_path

_ROOT_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(default="", max_length=5000)


class ProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=5000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str
    storage_key: str
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None


class ProjectScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_root: str = Field(pattern=_ROOT_PATTERN)
    ignore_patterns: tuple[str, ...] = ()


class ProjectPushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_root: str = Field(pattern=_ROOT_PATTERN)
    target_root: str = Field(pattern=_ROOT_PATTERN)
    ignore_patterns: tuple[str, ...] = ()


def _relative_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        try:
            normalized.append(str(relative_posix_path(value)))
        except InvalidRelativePath as exc:
            raise ValueError("include paths must be safe relative POSIX paths") from exc
    return tuple(normalized)


class ProjectPullRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_root: str = Field(pattern=_ROOT_PATTERN)
    target_root: str = Field(pattern=_ROOT_PATTERN)
    include: tuple[str, ...] = ()

    @field_validator("include")
    @classmethod
    def validate_include(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _relative_paths(values)


class FileSignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    size_bytes: int
    mtime_ns: int


class TransferWarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    path: str | None
    size_bytes: int | None
    count: int | None


class ProjectScanResponse(BaseModel):
    files: tuple[FileSignatureResponse, ...]
    warnings: tuple[TransferWarningResponse, ...]


class ProjectTransferResponse(BaseModel):
    transferred: tuple[str, ...]
    skipped: tuple[str, ...]
    removed: tuple[str, ...]
    manifest: dict[str, FileSignatureResponse]
    warnings: tuple[TransferWarningResponse, ...]
