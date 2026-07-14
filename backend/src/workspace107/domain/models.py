from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from uuid import UUID, uuid4

from workspace107.domain.enums import ArtifactKind, RunStatus, WorkspaceKind, WorkspaceRole
from workspace107.domain.values import relative_posix_path


def utc_now() -> datetime:
    return datetime.now(UTC)


def _frozen_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(value))


def _normalized_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(relative_posix_path(value)) for value in values)


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    display_name: str
    email: str | None
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewUser:
    username: str
    display_name: str
    email: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    kind: WorkspaceKind
    name: str
    slug: str
    description: str
    parent_id: UUID | None
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewWorkspace:
    kind: WorkspaceKind
    name: str
    slug: str
    created_by: UUID
    description: str = ""
    parent_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class NewWorkspaceMember:
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str
    storage_key: str
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewProject:
    workspace_id: UUID
    name: str
    slug: str
    storage_key: str
    created_by: UUID
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Dataset:
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewDataset:
    workspace_id: UUID
    name: str
    slug: str
    created_by: UUID
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    id: UUID
    dataset_id: UUID
    version: str
    storage_key: str
    size_bytes: int
    sha256: str
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewDatasetVersion:
    dataset_id: UUID
    version: str
    storage_key: str
    size_bytes: int
    sha256: str
    created_by: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    cpus: int
    memory_mb: int
    gpus: int
    walltime_seconds: int
    account: str = "stu"
    partition: str = "Students"
    qos: str = "qos_stu_default"


@dataclass(frozen=True, slots=True)
class RunTemplate:
    id: UUID
    workspace_id: UUID
    name: str
    description: str
    entrypoint: str
    environment_spec: Mapping[str, object]
    resource_spec: ResourceSpec
    output_spec: tuple[str, ...]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entrypoint", str(relative_posix_path(self.entrypoint)))
        object.__setattr__(self, "environment_spec", _frozen_mapping(self.environment_spec))
        object.__setattr__(self, "output_spec", _normalized_paths(self.output_spec))


@dataclass(frozen=True, slots=True)
class NewRunTemplate:
    workspace_id: UUID
    name: str
    entrypoint: str
    environment_spec: Mapping[str, object]
    resource_spec: ResourceSpec
    output_spec: tuple[str, ...]
    created_by: UUID
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entrypoint", str(relative_posix_path(self.entrypoint)))
        object.__setattr__(self, "environment_spec", _frozen_mapping(self.environment_spec))
        object.__setattr__(self, "output_spec", _normalized_paths(self.output_spec))


@dataclass(frozen=True, slots=True)
class DatasetMount:
    dataset_version_id: str
    source_uri: str
    mount_path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mount_path", str(relative_posix_path(self.mount_path)))


@dataclass(frozen=True, slots=True)
class RunSubmission:
    project_uri: str
    entrypoint: str
    resources: ResourceSpec
    mounts: tuple[DatasetMount, ...]
    outputs: tuple[str, ...]
    environment: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entrypoint", str(relative_posix_path(self.entrypoint)))
        object.__setattr__(self, "outputs", _normalized_paths(self.outputs))
        object.__setattr__(self, "environment", _frozen_mapping(self.environment))


@dataclass(frozen=True, slots=True)
class Run:
    id: UUID
    workspace_id: UUID
    project_id: UUID
    template_id: UUID
    submitted_by: UUID
    status: RunStatus
    external_job_id: str | None
    submission_snapshot: Mapping[str, object]
    exit_code: int | None
    failure_code: str | None
    failure_message: str | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "submission_snapshot", _frozen_mapping(self.submission_snapshot))


@dataclass(frozen=True, slots=True)
class NewRun:
    workspace_id: UUID
    project_id: UUID
    template_id: UUID
    submitted_by: UUID
    submission_snapshot: Mapping[str, object]
    id: UUID = field(default_factory=uuid4)
    status: RunStatus = RunStatus.SUBMITTING
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "submission_snapshot", _frozen_mapping(self.submission_snapshot))


@dataclass(frozen=True, slots=True)
class RunDataset:
    run_id: UUID
    dataset_version_id: UUID
    mount_path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mount_path", str(relative_posix_path(self.mount_path)))


@dataclass(frozen=True, slots=True)
class RunEvent:
    id: UUID
    run_id: UUID
    event_type: str
    from_status: RunStatus | None
    to_status: RunStatus | None
    message: str | None
    details: Mapping[str, object]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _frozen_mapping(self.details))


@dataclass(frozen=True, slots=True)
class NewRunEvent:
    run_id: UUID
    event_type: str
    from_status: RunStatus | None = None
    to_status: RunStatus | None = None
    message: str | None = None
    details: Mapping[str, object] = field(default_factory=dict[str, object])
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _frozen_mapping(self.details))


@dataclass(frozen=True, slots=True)
class Artifact:
    id: UUID
    run_id: UUID
    kind: ArtifactKind
    name: str
    storage_key: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewArtifact:
    run_id: UUID
    kind: ArtifactKind
    name: str
    storage_key: str
    media_type: str
    size_bytes: int
    sha256: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class FileSignature:
    path: str
    size_bytes: int
    mtime_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", str(relative_posix_path(self.path)))


@dataclass(frozen=True, slots=True)
class ProjectSync:
    id: UUID
    project_id: UUID
    transport: str
    target_uri: str
    manifest: Mapping[str, FileSignature]
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))


@dataclass(frozen=True, slots=True)
class NewProjectSync:
    project_id: UUID
    transport: str
    target_uri: str
    manifest: Mapping[str, FileSignature]
    last_synced_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    code: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class SubmittedJob:
    external_job_id: str
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class JobObservation:
    status: RunStatus
    observed_at: datetime
    exit_code: int | None = None
    details: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _frozen_mapping(self.details))


@dataclass(frozen=True, slots=True)
class LogChunk:
    offset: int
    next_offset: int
    data: str
    end_of_stream: bool


@dataclass(frozen=True, slots=True)
class CollectedArtifact:
    artifact_key: str
    name: str
    kind: ArtifactKind
    media_type: str
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    name: str
    media_type: str


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_key: str
    size_bytes: int
    sha256: str
    created: bool


@dataclass(frozen=True, slots=True)
class IgnoreRules:
    patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransferWarning:
    code: str
    message: str
    path: str | None = None
    size_bytes: int | None = None
    count: int | None = None


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    source: Path
    files: tuple[FileSignature, ...]
    warnings: tuple[TransferWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class TransferPlan:
    source: Path
    target_uri: str
    files: tuple[str, ...]
    removed: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", _normalized_paths(self.files))
        object.__setattr__(self, "removed", _normalized_paths(self.removed))


@dataclass(frozen=True, slots=True)
class TransferResult:
    transferred: tuple[str, ...]
    skipped: tuple[str, ...]
    removed: tuple[str, ...]
    manifest: Mapping[str, FileSignature]
    warnings: tuple[TransferWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "transferred", _normalized_paths(self.transferred))
        object.__setattr__(self, "skipped", _normalized_paths(self.skipped))
        object.__setattr__(self, "removed", _normalized_paths(self.removed))
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))


@dataclass(frozen=True, slots=True)
class PullRequest:
    source_uri: str
    destination: Path
    include: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "include", _normalized_paths(self.include))
