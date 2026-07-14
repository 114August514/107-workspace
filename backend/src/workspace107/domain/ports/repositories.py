from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self, runtime_checkable
from uuid import UUID

from workspace107.domain.enums import RunStatus, WorkspaceRole
from workspace107.domain.models import (
    Artifact,
    Dataset,
    DatasetVersion,
    NewArtifact,
    NewDataset,
    NewDatasetVersion,
    NewProject,
    NewProjectSync,
    NewRun,
    NewRunEvent,
    NewRunTemplate,
    NewUser,
    NewWorkspace,
    NewWorkspaceMember,
    Project,
    ProjectSync,
    Run,
    RunDataset,
    RunEvent,
    RunTemplate,
    User,
    Workspace,
    WorkspaceMember,
)


@runtime_checkable
class UserRepository(Protocol):
    async def add(self, new: NewUser) -> User: ...

    async def get(self, user_id: UUID) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...


@runtime_checkable
class WorkspaceRepository(Protocol):
    async def add(self, new: NewWorkspace) -> Workspace: ...

    async def get(self, workspace_id: UUID) -> Workspace | None: ...

    async def get_by_slug(self, slug: str) -> Workspace | None: ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> tuple[Workspace, ...]: ...

    async def save(self, workspace: Workspace) -> Workspace: ...


@runtime_checkable
class MemberRepository(Protocol):
    async def add(self, new: NewWorkspaceMember) -> WorkspaceMember: ...

    async def get(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None: ...

    async def list_for_workspace(self, workspace_id: UUID) -> tuple[WorkspaceMember, ...]: ...

    async def set_role(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember | None: ...

    async def remove(self, workspace_id: UUID, user_id: UUID) -> bool: ...

    async def count_owners(self, workspace_id: UUID) -> int: ...


@runtime_checkable
class ProjectRepository(Protocol):
    async def add(self, new: NewProject) -> Project: ...

    async def get(self, project_id: UUID) -> Project | None: ...

    async def get_by_slug(self, workspace_id: UUID, slug: str) -> Project | None: ...

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Project, ...]: ...

    async def save(self, project: Project) -> Project: ...


@runtime_checkable
class DatasetRepository(Protocol):
    async def add(self, new: NewDataset) -> Dataset: ...

    async def get(self, dataset_id: UUID) -> Dataset | None: ...

    async def get_by_slug(self, workspace_id: UUID, slug: str) -> Dataset | None: ...

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Dataset, ...]: ...

    async def save(self, dataset: Dataset) -> Dataset: ...

    async def add_version(self, new: NewDatasetVersion) -> DatasetVersion: ...

    async def get_version(self, version_id: UUID) -> DatasetVersion | None: ...

    async def get_version_by_name(
        self, dataset_id: UUID, version: str
    ) -> DatasetVersion | None: ...

    async def list_versions(self, dataset_id: UUID) -> tuple[DatasetVersion, ...]: ...

    async def count_versions_by_storage_key(self, storage_key: str) -> int: ...


@runtime_checkable
class TemplateRepository(Protocol):
    async def add(self, new: NewRunTemplate) -> RunTemplate: ...

    async def get(self, template_id: UUID) -> RunTemplate | None: ...

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[RunTemplate, ...]: ...

    async def save(self, template: RunTemplate) -> RunTemplate: ...


@runtime_checkable
class RunRepository(Protocol):
    async def add(self, new: NewRun, datasets: tuple[RunDataset, ...] = ()) -> Run: ...

    async def get(self, run_id: UUID) -> Run | None: ...

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Run, ...]: ...

    async def list_non_terminal(self) -> tuple[Run, ...]: ...

    async def list_datasets(self, run_id: UUID) -> tuple[RunDataset, ...]: ...

    async def compare_and_set_status(self, expected: RunStatus, replacement: Run) -> bool: ...


@runtime_checkable
class RunEventRepository(Protocol):
    async def add(self, new: NewRunEvent) -> RunEvent: ...

    async def list_for_run(self, run_id: UUID) -> tuple[RunEvent, ...]: ...


@runtime_checkable
class ArtifactRepository(Protocol):
    async def add(self, new: NewArtifact) -> Artifact: ...

    async def get(self, artifact_id: UUID) -> Artifact | None: ...

    async def list_for_run(self, run_id: UUID) -> tuple[Artifact, ...]: ...

    async def exists_for_run_and_storage_key(self, run_id: UUID, storage_key: str) -> bool: ...


@runtime_checkable
class ProjectSyncRepository(Protocol):
    async def get(
        self, project_id: UUID, transport: str, target_uri: str
    ) -> ProjectSync | None: ...

    async def upsert(self, new: NewProjectSync) -> ProjectSync: ...

    async def get_latest(self, project_id: UUID, transport: str) -> ProjectSync | None: ...


@runtime_checkable
class UnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def workspaces(self) -> WorkspaceRepository: ...

    @property
    def members(self) -> MemberRepository: ...

    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def datasets(self) -> DatasetRepository: ...

    @property
    def templates(self) -> TemplateRepository: ...

    @property
    def runs(self) -> RunRepository: ...

    @property
    def events(self) -> RunEventRepository: ...

    @property
    def artifacts(self) -> ArtifactRepository: ...

    @property
    def syncs(self) -> ProjectSyncRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]
