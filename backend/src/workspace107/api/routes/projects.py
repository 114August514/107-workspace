from uuid import UUID

from fastapi import APIRouter, Query, status

from workspace107.api.dependencies import IdentityDependency, ProjectServiceDependency
from workspace107.api.schemas.projects import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)

router = APIRouter(tags=["projects"])


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    workspace_id: UUID,
    request: ProjectCreateRequest,
    actor_id: IdentityDependency,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    project = await service.create(
        actor_id=actor_id,
        workspace_id=workspace_id,
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    return ProjectResponse.model_validate(project)


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: ProjectServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectResponse]:
    projects = await service.list(
        actor_id=actor_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    actor_id: IdentityDependency,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    return ProjectResponse.model_validate(await service.get(actor_id, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    actor_id: IdentityDependency,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    project = await service.update(
        actor_id=actor_id,
        project_id=project_id,
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: UUID,
    actor_id: IdentityDependency,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    return ProjectResponse.model_validate(await service.archive(actor_id, project_id))
