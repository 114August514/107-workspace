from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from workspace107.application.access import require_workspace_access
from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import (
    PathOutsideAllowedRoot,
    ResourceArchived,
    ResourceNotFound,
)
from workspace107.domain.manifests import diff_manifests
from workspace107.domain.models import (
    FileSignature,
    IgnoreRules,
    NewProjectSync,
    Project,
    ProjectSnapshot,
    PullRequest,
    TransferPlan,
    TransferResult,
    utc_now,
)
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory
from workspace107.domain.ports.transfer import ProjectTransferPort


class TransferService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        transfer: ProjectTransferPort,
        roots: Mapping[str, Path],
    ) -> None:
        self._uow_factory = uow_factory
        self._transfer = transfer
        self._roots = {name: path.expanduser().resolve() for name, path in roots.items()}

    async def scan(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        source_root: str,
        ignore_patterns: tuple[str, ...] = (),
    ) -> ProjectSnapshot:
        async with self._uow_factory() as uow:
            await self._load_authorized(uow, actor_id, project_id, WorkspaceRole.VIEWER)
        source = self._project_path(source_root, project_id)
        return await self._transfer.scan(source, IgnoreRules(ignore_patterns))

    async def push(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        source_root: str,
        target_root: str,
        ignore_patterns: tuple[str, ...] = (),
    ) -> TransferResult:
        source = self._project_path(source_root, project_id)
        target = self._project_path(target_root, project_id)
        target_uri = target.as_uri()

        async with self._uow_factory() as uow:
            await self._load_authorized(
                uow,
                actor_id,
                project_id,
                WorkspaceRole.MEMBER,
                active=True,
            )
            previous_sync = await uow.syncs.get(project_id, "local", target_uri)
            previous: Mapping[str, FileSignature] = (
                previous_sync.manifest if previous_sync is not None else {}
            )

        snapshot = await self._transfer.scan(source, IgnoreRules(ignore_patterns))
        current = {signature.path: signature for signature in snapshot.files}
        difference = diff_manifests(previous, current)
        transferred = await self._transfer.push(
            TransferPlan(
                source=source,
                target_uri=target_uri,
                files=difference.upload_paths,
                removed=difference.removed,
            )
        )

        async with self._uow_factory() as uow:
            await self._load_authorized(
                uow,
                actor_id,
                project_id,
                WorkspaceRole.MEMBER,
                active=True,
            )
            now = utc_now()
            await uow.syncs.upsert(
                NewProjectSync(
                    project_id=project_id,
                    transport="local",
                    target_uri=target_uri,
                    manifest=current,
                    last_synced_at=now,
                    updated_at=now,
                )
            )
            await uow.commit()

        return TransferResult(
            transferred=transferred.transferred,
            skipped=difference.unchanged,
            removed=difference.removed,
            manifest=current,
            warnings=snapshot.warnings,
        )

    async def pull(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        source_root: str,
        target_root: str,
        include: tuple[str, ...],
    ) -> TransferResult:
        async with self._uow_factory() as uow:
            await self._load_authorized(
                uow,
                actor_id,
                project_id,
                WorkspaceRole.MEMBER,
                active=True,
            )
        return await self._transfer.pull(
            PullRequest(
                source_uri=self._project_path(source_root, project_id).as_uri(),
                destination=self._project_path(target_root, project_id),
                include=include,
            )
        )

    def _project_path(self, root_name: str, project_id: UUID) -> Path:
        root = self._roots.get(root_name)
        if root is None:
            raise ResourceNotFound(f"transfer root {root_name!r} is not configured")
        path = (root / str(project_id)).resolve()
        if not path.is_relative_to(root):
            raise PathOutsideAllowedRoot("project path is outside the configured root")
        return path

    @staticmethod
    async def _load_authorized(
        uow: UnitOfWork,
        actor_id: UUID,
        project_id: UUID,
        minimum: WorkspaceRole,
        *,
        active: bool = False,
    ) -> Project:
        project = await uow.projects.get(project_id)
        if project is None:
            raise ResourceNotFound(f"project {project_id} not found")
        await require_workspace_access(
            uow,
            actor_id=actor_id,
            workspace_id=project.workspace_id,
            minimum=minimum,
            active=active,
        )
        if active and project.archived_at is not None:
            raise ResourceArchived(f"project {project_id} is archived")
        return project
