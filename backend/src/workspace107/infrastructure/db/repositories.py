from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from workspace107.domain.enums import ArtifactKind, RunStatus, WorkspaceKind, WorkspaceRole
from workspace107.domain.errors import ResourceNotFound
from workspace107.domain.models import (
    Artifact,
    Dataset,
    DatasetVersion,
    FileSignature,
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
    ResourceSpec,
    Run,
    RunDataset,
    RunEvent,
    RunTemplate,
    User,
    Workspace,
    WorkspaceMember,
)
from workspace107.infrastructure.db.models import (
    ArtifactRow,
    DatasetRow,
    DatasetVersionRow,
    ProjectRow,
    ProjectSyncRow,
    RunDatasetRow,
    RunEventRow,
    RunRow,
    RunTemplateRow,
    UserRow,
    WorkspaceMemberRow,
    WorkspaceRow,
)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required_utc(value: datetime) -> datetime:
    converted = _utc(value)
    if converted is None:
        raise TypeError("required timestamp is missing")
    return converted


def _required_int(value: object, key: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return value


def _required_str(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _resource_to_json(spec: ResourceSpec) -> dict[str, object]:
    return {
        "cpus": spec.cpus,
        "memory_mb": spec.memory_mb,
        "gpus": spec.gpus,
        "walltime_seconds": spec.walltime_seconds,
        "account": spec.account,
        "partition": spec.partition,
        "qos": spec.qos,
    }


def _resource_from_json(value: Mapping[str, object]) -> ResourceSpec:
    return ResourceSpec(
        cpus=_required_int(value.get("cpus"), "cpus"),
        memory_mb=_required_int(value.get("memory_mb"), "memory_mb"),
        gpus=_required_int(value.get("gpus"), "gpus"),
        walltime_seconds=_required_int(value.get("walltime_seconds"), "walltime_seconds"),
        account=_required_str(value.get("account"), "account"),
        partition=_required_str(value.get("partition"), "partition"),
        qos=_required_str(value.get("qos"), "qos"),
    )


def _manifest_to_json(manifest: Mapping[str, FileSignature]) -> dict[str, object]:
    return {
        path: {
            "path": signature.path,
            "size_bytes": signature.size_bytes,
            "mtime_ns": signature.mtime_ns,
        }
        for path, signature in manifest.items()
    }


def _manifest_from_json(value: Mapping[str, object]) -> dict[str, FileSignature]:
    manifest: dict[str, FileSignature] = {}
    for key, raw_signature in value.items():
        if not isinstance(raw_signature, Mapping):
            raise TypeError("manifest signature must be an object")
        signature = cast(Mapping[str, object], raw_signature)
        manifest[key] = FileSignature(
            path=_required_str(signature.get("path"), "path"),
            size_bytes=_required_int(signature.get("size_bytes"), "size_bytes"),
            mtime_ns=_required_int(signature.get("mtime_ns"), "mtime_ns"),
        )
    return manifest


def _user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        email=row.email,
        created_at=_required_utc(row.created_at),
        archived_at=_utc(row.archived_at),
    )


def _workspace(row: WorkspaceRow) -> Workspace:
    return Workspace(
        id=row.id,
        kind=WorkspaceKind(row.kind),
        name=row.name,
        slug=row.slug,
        description=row.description,
        parent_id=row.parent_id,
        created_by=row.created_by,
        created_at=_required_utc(row.created_at),
        archived_at=_utc(row.archived_at),
    )


def _member(row: WorkspaceMemberRow) -> WorkspaceMember:
    return WorkspaceMember(
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=WorkspaceRole(row.role),
        joined_at=_required_utc(row.joined_at),
    )


def _project(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        storage_key=row.storage_key,
        created_by=row.created_by,
        created_at=_required_utc(row.created_at),
        archived_at=_utc(row.archived_at),
    )


def _dataset(row: DatasetRow) -> Dataset:
    return Dataset(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        created_by=row.created_by,
        created_at=_required_utc(row.created_at),
        archived_at=_utc(row.archived_at),
    )


def _dataset_version(row: DatasetVersionRow) -> DatasetVersion:
    return DatasetVersion(
        id=row.id,
        dataset_id=row.dataset_id,
        version=row.version,
        storage_key=row.storage_key,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_by=row.created_by,
        created_at=_required_utc(row.created_at),
    )


def _template(row: RunTemplateRow) -> RunTemplate:
    return RunTemplate(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        entrypoint=row.entrypoint,
        environment_spec=row.environment_spec,
        resource_spec=_resource_from_json(row.resource_spec),
        output_spec=tuple(row.output_spec),
        created_by=row.created_by,
        created_at=_required_utc(row.created_at),
        updated_at=_required_utc(row.updated_at),
        archived_at=_utc(row.archived_at),
    )


def _run(row: RunRow) -> Run:
    return Run(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        template_id=row.template_id,
        submitted_by=row.submitted_by,
        status=RunStatus(row.status),
        external_job_id=row.external_job_id,
        submission_snapshot=row.submission_snapshot,
        exit_code=row.exit_code,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        submitted_at=_utc(row.submitted_at),
        started_at=_utc(row.started_at),
        finished_at=_utc(row.finished_at),
        created_at=_required_utc(row.created_at),
        updated_at=_required_utc(row.updated_at),
    )


def _run_dataset(row: RunDatasetRow) -> RunDataset:
    return RunDataset(
        run_id=row.run_id,
        dataset_version_id=row.dataset_version_id,
        mount_path=row.mount_path,
    )


def _event(row: RunEventRow) -> RunEvent:
    return RunEvent(
        id=row.id,
        run_id=row.run_id,
        event_type=row.event_type,
        from_status=RunStatus(row.from_status) if row.from_status else None,
        to_status=RunStatus(row.to_status) if row.to_status else None,
        message=row.message,
        details=row.details,
        created_at=_required_utc(row.created_at),
    )


def _artifact(row: ArtifactRow) -> Artifact:
    return Artifact(
        id=row.id,
        run_id=row.run_id,
        kind=ArtifactKind(row.kind),
        name=row.name,
        storage_key=row.storage_key,
        media_type=row.media_type,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=_required_utc(row.created_at),
    )


def _sync(row: ProjectSyncRow) -> ProjectSync:
    return ProjectSync(
        id=row.id,
        project_id=row.project_id,
        transport=row.transport,
        target_uri=row.target_uri,
        manifest=_manifest_from_json(row.manifest),
        last_synced_at=_utc(row.last_synced_at),
        created_at=_required_utc(row.created_at),
        updated_at=_required_utc(row.updated_at),
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewUser) -> User:
        row = UserRow(
            id=new.id,
            username=new.username,
            display_name=new.display_name,
            email=new.email,
            created_at=new.created_at,
            archived_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return _user(row)

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return _user(row) if row is not None else None

    async def get_by_username(self, username: str) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.username == username))
        return _user(row) if row is not None else None


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewWorkspace) -> Workspace:
        row = WorkspaceRow(
            id=new.id,
            kind=new.kind.value,
            name=new.name,
            slug=new.slug,
            description=new.description,
            parent_id=new.parent_id,
            created_by=new.created_by,
            created_at=new.created_at,
            archived_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return _workspace(row)

    async def get(self, workspace_id: UUID) -> Workspace | None:
        row = await self._session.get(WorkspaceRow, workspace_id)
        return _workspace(row) if row is not None else None

    async def get_by_slug(self, slug: str) -> Workspace | None:
        row = await self._session.scalar(select(WorkspaceRow).where(WorkspaceRow.slug == slug))
        return _workspace(row) if row is not None else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> tuple[Workspace, ...]:
        statement = (
            select(WorkspaceRow)
            .join(
                WorkspaceMemberRow,
                WorkspaceMemberRow.workspace_id == WorkspaceRow.id,
            )
            .where(WorkspaceMemberRow.user_id == user_id)
            .order_by(WorkspaceRow.created_at, WorkspaceRow.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.scalars(statement)).all()
        return tuple(_workspace(row) for row in rows)

    async def save(self, workspace: Workspace) -> Workspace:
        row = await self._session.get(WorkspaceRow, workspace.id)
        if row is None:
            raise ResourceNotFound(f"workspace {workspace.id} not found")
        row.kind = workspace.kind.value
        row.name = workspace.name
        row.slug = workspace.slug
        row.description = workspace.description
        row.parent_id = workspace.parent_id
        row.archived_at = workspace.archived_at
        await self._session.flush()
        return _workspace(row)


class SqlAlchemyMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewWorkspaceMember) -> WorkspaceMember:
        row = WorkspaceMemberRow(
            workspace_id=new.workspace_id,
            user_id=new.user_id,
            role=new.role.value,
            joined_at=new.joined_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _member(row)

    async def get(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        row = await self._session.get(WorkspaceMemberRow, (workspace_id, user_id))
        return _member(row) if row is not None else None

    async def list_for_workspace(self, workspace_id: UUID) -> tuple[WorkspaceMember, ...]:
        rows = (
            await self._session.scalars(
                select(WorkspaceMemberRow)
                .where(WorkspaceMemberRow.workspace_id == workspace_id)
                .order_by(WorkspaceMemberRow.joined_at, WorkspaceMemberRow.user_id)
            )
        ).all()
        return tuple(_member(row) for row in rows)

    async def set_role(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember | None:
        row = await self._session.get(WorkspaceMemberRow, (workspace_id, user_id))
        if row is None:
            return None
        row.role = role.value
        await self._session.flush()
        return _member(row)

    async def remove(self, workspace_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            delete(WorkspaceMemberRow).where(
                WorkspaceMemberRow.workspace_id == workspace_id,
                WorkspaceMemberRow.user_id == user_id,
            )
        )
        return cast(CursorResult[tuple[()]], result).rowcount == 1

    async def count_owners(self, workspace_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(WorkspaceMemberRow)
            .where(
                WorkspaceMemberRow.workspace_id == workspace_id,
                WorkspaceMemberRow.role == WorkspaceRole.OWNER.value,
            )
        )
        return int(count or 0)


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewProject) -> Project:
        row = ProjectRow(
            id=new.id,
            workspace_id=new.workspace_id,
            name=new.name,
            slug=new.slug,
            description=new.description,
            storage_key=new.storage_key,
            created_by=new.created_by,
            created_at=new.created_at,
            archived_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return _project(row)

    async def get(self, project_id: UUID) -> Project | None:
        row = await self._session.get(ProjectRow, project_id)
        return _project(row) if row is not None else None

    async def get_by_slug(self, workspace_id: UUID, slug: str) -> Project | None:
        row = await self._session.scalar(
            select(ProjectRow).where(
                ProjectRow.workspace_id == workspace_id,
                ProjectRow.slug == slug,
            )
        )
        return _project(row) if row is not None else None

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Project, ...]:
        rows = (
            await self._session.scalars(
                select(ProjectRow)
                .where(ProjectRow.workspace_id == workspace_id)
                .order_by(ProjectRow.created_at, ProjectRow.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return tuple(_project(row) for row in rows)

    async def save(self, project: Project) -> Project:
        row = await self._session.get(ProjectRow, project.id)
        if row is None:
            raise ResourceNotFound(f"project {project.id} not found")
        row.name = project.name
        row.slug = project.slug
        row.description = project.description
        row.storage_key = project.storage_key
        row.archived_at = project.archived_at
        await self._session.flush()
        return _project(row)


class SqlAlchemyDatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewDataset) -> Dataset:
        row = DatasetRow(
            id=new.id,
            workspace_id=new.workspace_id,
            name=new.name,
            slug=new.slug,
            description=new.description,
            created_by=new.created_by,
            created_at=new.created_at,
            archived_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return _dataset(row)

    async def get(self, dataset_id: UUID) -> Dataset | None:
        row = await self._session.get(DatasetRow, dataset_id)
        return _dataset(row) if row is not None else None

    async def get_by_slug(self, workspace_id: UUID, slug: str) -> Dataset | None:
        row = await self._session.scalar(
            select(DatasetRow).where(
                DatasetRow.workspace_id == workspace_id,
                DatasetRow.slug == slug,
            )
        )
        return _dataset(row) if row is not None else None

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Dataset, ...]:
        rows = (
            await self._session.scalars(
                select(DatasetRow)
                .where(DatasetRow.workspace_id == workspace_id)
                .order_by(DatasetRow.created_at, DatasetRow.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return tuple(_dataset(row) for row in rows)

    async def save(self, dataset: Dataset) -> Dataset:
        row = await self._session.get(DatasetRow, dataset.id)
        if row is None:
            raise ResourceNotFound(f"dataset {dataset.id} not found")
        row.name = dataset.name
        row.slug = dataset.slug
        row.description = dataset.description
        row.archived_at = dataset.archived_at
        await self._session.flush()
        return _dataset(row)

    async def add_version(self, new: NewDatasetVersion) -> DatasetVersion:
        row = DatasetVersionRow(
            id=new.id,
            dataset_id=new.dataset_id,
            version=new.version,
            storage_key=new.storage_key,
            size_bytes=new.size_bytes,
            sha256=new.sha256,
            created_by=new.created_by,
            created_at=new.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _dataset_version(row)

    async def get_version(self, version_id: UUID) -> DatasetVersion | None:
        row = await self._session.get(DatasetVersionRow, version_id)
        return _dataset_version(row) if row is not None else None

    async def get_version_by_name(self, dataset_id: UUID, version: str) -> DatasetVersion | None:
        row = await self._session.scalar(
            select(DatasetVersionRow).where(
                DatasetVersionRow.dataset_id == dataset_id,
                DatasetVersionRow.version == version,
            )
        )
        return _dataset_version(row) if row is not None else None

    async def list_versions(self, dataset_id: UUID) -> tuple[DatasetVersion, ...]:
        rows = (
            await self._session.scalars(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.dataset_id == dataset_id)
                .order_by(DatasetVersionRow.created_at, DatasetVersionRow.id)
            )
        ).all()
        return tuple(_dataset_version(row) for row in rows)

    async def count_versions_by_storage_key(self, storage_key: str) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(DatasetVersionRow)
            .where(DatasetVersionRow.storage_key == storage_key)
        )
        return int(count or 0)


class SqlAlchemyTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewRunTemplate) -> RunTemplate:
        row = RunTemplateRow(
            id=new.id,
            workspace_id=new.workspace_id,
            name=new.name,
            description=new.description,
            entrypoint=new.entrypoint,
            environment_spec=dict(new.environment_spec),
            resource_spec=_resource_to_json(new.resource_spec),
            output_spec=list(new.output_spec),
            created_by=new.created_by,
            created_at=new.created_at,
            updated_at=new.updated_at,
            archived_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return _template(row)

    async def get(self, template_id: UUID) -> RunTemplate | None:
        row = await self._session.get(RunTemplateRow, template_id)
        return _template(row) if row is not None else None

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[RunTemplate, ...]:
        rows = (
            await self._session.scalars(
                select(RunTemplateRow)
                .where(RunTemplateRow.workspace_id == workspace_id)
                .order_by(RunTemplateRow.created_at, RunTemplateRow.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return tuple(_template(row) for row in rows)

    async def save(self, template: RunTemplate) -> RunTemplate:
        row = await self._session.get(RunTemplateRow, template.id)
        if row is None:
            raise ResourceNotFound(f"run template {template.id} not found")
        row.name = template.name
        row.description = template.description
        row.entrypoint = template.entrypoint
        row.environment_spec = dict(template.environment_spec)
        row.resource_spec = _resource_to_json(template.resource_spec)
        row.output_spec = list(template.output_spec)
        row.updated_at = template.updated_at
        row.archived_at = template.archived_at
        await self._session.flush()
        return _template(row)


class SqlAlchemyRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewRun, datasets: tuple[RunDataset, ...] = ()) -> Run:
        row = RunRow(
            id=new.id,
            workspace_id=new.workspace_id,
            project_id=new.project_id,
            template_id=new.template_id,
            submitted_by=new.submitted_by,
            status=new.status.value,
            external_job_id=None,
            submission_snapshot=dict(new.submission_snapshot),
            exit_code=None,
            failure_code=None,
            failure_message=None,
            submitted_at=None,
            started_at=None,
            finished_at=None,
            created_at=new.created_at,
            updated_at=new.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        for dataset in datasets:
            if dataset.run_id != new.id:
                raise ValueError("run dataset belongs to another run")
            self._session.add(
                RunDatasetRow(
                    run_id=dataset.run_id,
                    dataset_version_id=dataset.dataset_version_id,
                    mount_path=dataset.mount_path,
                )
            )
        await self._session.flush()
        return _run(row)

    async def get(self, run_id: UUID) -> Run | None:
        row = await self._session.get(RunRow, run_id)
        return _run(row) if row is not None else None

    async def list_for_workspace(
        self, workspace_id: UUID, *, limit: int, offset: int
    ) -> tuple[Run, ...]:
        rows = (
            await self._session.scalars(
                select(RunRow)
                .where(RunRow.workspace_id == workspace_id)
                .order_by(RunRow.created_at, RunRow.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return tuple(_run(row) for row in rows)

    async def list_non_terminal(self) -> tuple[Run, ...]:
        terminal = (
            RunStatus.SUCCEEDED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        )
        rows = (
            await self._session.scalars(
                select(RunRow)
                .where(RunRow.status.not_in(terminal))
                .order_by(RunRow.created_at, RunRow.id)
            )
        ).all()
        return tuple(_run(row) for row in rows)

    async def list_datasets(self, run_id: UUID) -> tuple[RunDataset, ...]:
        rows = (
            await self._session.scalars(
                select(RunDatasetRow)
                .where(RunDatasetRow.run_id == run_id)
                .order_by(RunDatasetRow.mount_path)
            )
        ).all()
        return tuple(_run_dataset(row) for row in rows)

    async def compare_and_set_status(self, expected: RunStatus, replacement: Run) -> bool:
        result = await self._session.execute(
            update(RunRow)
            .where(RunRow.id == replacement.id, RunRow.status == expected.value)
            .values(
                status=replacement.status.value,
                external_job_id=replacement.external_job_id,
                submission_snapshot=dict(replacement.submission_snapshot),
                exit_code=replacement.exit_code,
                failure_code=replacement.failure_code,
                failure_message=replacement.failure_message,
                submitted_at=replacement.submitted_at,
                started_at=replacement.started_at,
                finished_at=replacement.finished_at,
                updated_at=replacement.updated_at,
            )
        )
        return cast(CursorResult[tuple[()]], result).rowcount == 1


class SqlAlchemyRunEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewRunEvent) -> RunEvent:
        row = RunEventRow(
            id=new.id,
            run_id=new.run_id,
            event_type=new.event_type,
            from_status=new.from_status.value if new.from_status else None,
            to_status=new.to_status.value if new.to_status else None,
            message=new.message,
            details=dict(new.details),
            created_at=new.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _event(row)

    async def list_for_run(self, run_id: UUID) -> tuple[RunEvent, ...]:
        rows = (
            await self._session.scalars(
                select(RunEventRow)
                .where(RunEventRow.run_id == run_id)
                .order_by(RunEventRow.created_at, RunEventRow.id)
            )
        ).all()
        return tuple(_event(row) for row in rows)


class SqlAlchemyArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, new: NewArtifact) -> Artifact:
        row = ArtifactRow(
            id=new.id,
            run_id=new.run_id,
            kind=new.kind.value,
            name=new.name,
            storage_key=new.storage_key,
            media_type=new.media_type,
            size_bytes=new.size_bytes,
            sha256=new.sha256,
            created_at=new.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _artifact(row)

    async def get(self, artifact_id: UUID) -> Artifact | None:
        row = await self._session.get(ArtifactRow, artifact_id)
        return _artifact(row) if row is not None else None

    async def list_for_run(self, run_id: UUID) -> tuple[Artifact, ...]:
        rows = (
            await self._session.scalars(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run_id)
                .order_by(ArtifactRow.created_at, ArtifactRow.id)
            )
        ).all()
        return tuple(_artifact(row) for row in rows)

    async def exists_for_run_and_storage_key(self, run_id: UUID, storage_key: str) -> bool:
        value = await self._session.scalar(
            select(ArtifactRow.id).where(
                ArtifactRow.run_id == run_id,
                ArtifactRow.storage_key == storage_key,
            )
        )
        return value is not None


class SqlAlchemyProjectSyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: UUID, transport: str, target_uri: str) -> ProjectSync | None:
        row = await self._session.scalar(
            select(ProjectSyncRow).where(
                ProjectSyncRow.project_id == project_id,
                ProjectSyncRow.transport == transport,
                ProjectSyncRow.target_uri == target_uri,
            )
        )
        return _sync(row) if row is not None else None

    async def upsert(self, new: NewProjectSync) -> ProjectSync:
        row = await self._session.scalar(
            select(ProjectSyncRow).where(
                ProjectSyncRow.project_id == new.project_id,
                ProjectSyncRow.transport == new.transport,
                ProjectSyncRow.target_uri == new.target_uri,
            )
        )
        if row is None:
            row = ProjectSyncRow(
                id=new.id,
                project_id=new.project_id,
                transport=new.transport,
                target_uri=new.target_uri,
                manifest=_manifest_to_json(new.manifest),
                last_synced_at=new.last_synced_at,
                created_at=new.created_at,
                updated_at=new.updated_at,
            )
            self._session.add(row)
        else:
            row.manifest = _manifest_to_json(new.manifest)
            row.last_synced_at = new.last_synced_at
            row.updated_at = new.updated_at
        await self._session.flush()
        return _sync(row)
