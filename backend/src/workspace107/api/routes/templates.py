from uuid import UUID

from fastapi import APIRouter, Query, status

from workspace107.api.dependencies import IdentityDependency, TemplateServiceDependency
from workspace107.api.schemas.templates import (
    TemplateCreateRequest,
    TemplateResponse,
    TemplateUpdateRequest,
)

router = APIRouter(tags=["run templates"])


@router.post(
    "/workspaces/{workspace_id}/run-templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    workspace_id: UUID,
    request: TemplateCreateRequest,
    actor_id: IdentityDependency,
    service: TemplateServiceDependency,
) -> TemplateResponse:
    template = await service.create(
        actor_id=actor_id,
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        entrypoint=request.entrypoint,
        environment_spec=request.environment_spec.as_mapping(),
        resource_spec=request.resource_spec.as_domain(),
        output_spec=request.output_spec,
    )
    return TemplateResponse.model_validate(template)


@router.get(
    "/workspaces/{workspace_id}/run-templates",
    response_model=list[TemplateResponse],
)
async def list_templates(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: TemplateServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[TemplateResponse]:
    templates = await service.list(
        actor_id=actor_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [TemplateResponse.model_validate(template) for template in templates]


@router.get("/run-templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    actor_id: IdentityDependency,
    service: TemplateServiceDependency,
) -> TemplateResponse:
    return TemplateResponse.model_validate(await service.get(actor_id, template_id))


@router.patch("/run-templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    request: TemplateUpdateRequest,
    actor_id: IdentityDependency,
    service: TemplateServiceDependency,
) -> TemplateResponse:
    template = await service.update(
        actor_id=actor_id,
        template_id=template_id,
        name=request.name,
        description=request.description,
        entrypoint=request.entrypoint,
        environment_spec=(
            request.environment_spec.as_mapping() if request.environment_spec is not None else None
        ),
        resource_spec=(
            request.resource_spec.as_domain() if request.resource_spec is not None else None
        ),
        output_spec=request.output_spec,
    )
    return TemplateResponse.model_validate(template)


@router.post("/run-templates/{template_id}/archive", response_model=TemplateResponse)
async def archive_template(
    template_id: UUID,
    actor_id: IdentityDependency,
    service: TemplateServiceDependency,
) -> TemplateResponse:
    return TemplateResponse.model_validate(await service.archive(actor_id, template_id))
