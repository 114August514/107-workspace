from collections.abc import Mapping
from dataclasses import replace
from uuid import UUID

from workspace107.application.access import require_workspace_access
from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import ResourceArchived, ResourceNotFound
from workspace107.domain.models import NewRunTemplate, ResourceSpec, RunTemplate, utc_now
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory


class TemplateService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        name: str,
        entrypoint: str,
        environment_spec: Mapping[str, object],
        resource_spec: ResourceSpec,
        output_spec: tuple[str, ...],
        description: str = "",
    ) -> RunTemplate:
        async with self._uow_factory() as uow:
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=workspace_id,
                minimum=WorkspaceRole.MEMBER,
                active=True,
            )
            template = await uow.templates.add(
                NewRunTemplate(
                    workspace_id=workspace_id,
                    name=name,
                    description=description,
                    entrypoint=entrypoint,
                    environment_spec=environment_spec,
                    resource_spec=resource_spec,
                    output_spec=output_spec,
                    created_by=actor_id,
                )
            )
            await uow.commit()
            return template

    async def list(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[RunTemplate, ...]:
        async with self._uow_factory() as uow:
            await require_workspace_access(uow, actor_id=actor_id, workspace_id=workspace_id)
            return await uow.templates.list_for_workspace(workspace_id, limit=limit, offset=offset)

    async def get(self, actor_id: UUID, template_id: UUID) -> RunTemplate:
        async with self._uow_factory() as uow:
            template = await self._load(uow, template_id)
            await require_workspace_access(
                uow, actor_id=actor_id, workspace_id=template.workspace_id
            )
            return template

    async def update(
        self,
        *,
        actor_id: UUID,
        template_id: UUID,
        name: str | None = None,
        description: str | None = None,
        entrypoint: str | None = None,
        environment_spec: Mapping[str, object] | None = None,
        resource_spec: ResourceSpec | None = None,
        output_spec: tuple[str, ...] | None = None,
    ) -> RunTemplate:
        async with self._uow_factory() as uow:
            template = await self._load(uow, template_id)
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=template.workspace_id,
                minimum=WorkspaceRole.MEMBER,
                active=True,
            )
            self._ensure_active(template)
            template = await uow.templates.save(
                replace(
                    template,
                    name=name if name is not None else template.name,
                    description=(description if description is not None else template.description),
                    entrypoint=(entrypoint if entrypoint is not None else template.entrypoint),
                    environment_spec=(
                        environment_spec
                        if environment_spec is not None
                        else template.environment_spec
                    ),
                    resource_spec=(
                        resource_spec if resource_spec is not None else template.resource_spec
                    ),
                    output_spec=(output_spec if output_spec is not None else template.output_spec),
                    updated_at=utc_now(),
                )
            )
            await uow.commit()
            return template

    async def archive(self, actor_id: UUID, template_id: UUID) -> RunTemplate:
        async with self._uow_factory() as uow:
            template = await self._load(uow, template_id)
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=template.workspace_id,
                minimum=WorkspaceRole.MANAGER,
                active=True,
            )
            if template.archived_at is None:
                now = utc_now()
                template = await uow.templates.save(
                    replace(template, archived_at=now, updated_at=now)
                )
                await uow.commit()
            return template

    @staticmethod
    async def _load(uow: UnitOfWork, template_id: UUID) -> RunTemplate:
        template = await uow.templates.get(template_id)
        if template is None:
            raise ResourceNotFound(f"run template {template_id} not found")
        return template

    @staticmethod
    def _ensure_active(template: RunTemplate) -> None:
        if template.archived_at is not None:
            raise ResourceArchived(f"run template {template.id} is archived")
