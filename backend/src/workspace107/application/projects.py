from dataclasses import replace
from uuid import UUID, uuid4

from workspace107.application.access import require_workspace_access
from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import ResourceArchived, ResourceConflict, ResourceNotFound
from workspace107.domain.models import NewProject, Project, utc_now
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory


class ProjectService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        name: str,
        slug: str,
        description: str = "",
    ) -> Project:
        async with self._uow_factory() as uow:
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=workspace_id,
                minimum=WorkspaceRole.MEMBER,
                active=True,
            )
            if await uow.projects.get_by_slug(workspace_id, slug) is not None:
                raise ResourceConflict(f"project slug {slug!r} already exists")
            project_id = uuid4()
            project = await uow.projects.add(
                NewProject(
                    id=project_id,
                    workspace_id=workspace_id,
                    name=name,
                    slug=slug,
                    description=description,
                    storage_key=f"projects/{project_id}",
                    created_by=actor_id,
                )
            )
            await uow.commit()
            return project

    async def list(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[Project, ...]:
        async with self._uow_factory() as uow:
            await require_workspace_access(uow, actor_id=actor_id, workspace_id=workspace_id)
            return await uow.projects.list_for_workspace(workspace_id, limit=limit, offset=offset)

    async def get(self, actor_id: UUID, project_id: UUID) -> Project:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ResourceNotFound(f"project {project_id} not found")
            await require_workspace_access(
                uow, actor_id=actor_id, workspace_id=project.workspace_id
            )
            return project

    async def update(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
    ) -> Project:
        async with self._uow_factory() as uow:
            project = await self._load(uow, project_id)
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=project.workspace_id,
                minimum=WorkspaceRole.MEMBER,
                active=True,
            )
            self._ensure_active(project)
            if (
                slug is not None
                and slug != project.slug
                and await uow.projects.get_by_slug(project.workspace_id, slug) is not None
            ):
                raise ResourceConflict(f"project slug {slug!r} already exists")
            project = await uow.projects.save(
                replace(
                    project,
                    name=name if name is not None else project.name,
                    slug=slug if slug is not None else project.slug,
                    description=description if description is not None else project.description,
                )
            )
            await uow.commit()
            return project

    async def archive(self, actor_id: UUID, project_id: UUID) -> Project:
        async with self._uow_factory() as uow:
            project = await self._load(uow, project_id)
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=project.workspace_id,
                minimum=WorkspaceRole.MANAGER,
                active=True,
            )
            if project.archived_at is None:
                project = await uow.projects.save(replace(project, archived_at=utc_now()))
                await uow.commit()
            return project

    @staticmethod
    async def _load(uow: UnitOfWork, project_id: UUID) -> Project:
        project = await uow.projects.get(project_id)
        if project is None:
            raise ResourceNotFound(f"project {project_id} not found")
        return project

    @staticmethod
    def _ensure_active(project: Project) -> None:
        if project.archived_at is not None:
            raise ResourceArchived(f"project {project.id} is archived")
