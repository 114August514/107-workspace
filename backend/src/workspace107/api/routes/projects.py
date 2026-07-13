from uuid import UUID

from fastapi import APIRouter, Query, status

from workspace107.api.dependencies import (
    IdentityDependency,
    ProjectServiceDependency,
    TransferServiceDependency,
)
from workspace107.api.schemas.projects import (
    FileSignatureResponse,
    ProjectCreateRequest,
    ProjectPullRequest,
    ProjectPushRequest,
    ProjectResponse,
    ProjectScanRequest,
    ProjectScanResponse,
    ProjectTransferResponse,
    ProjectUpdateRequest,
    TransferWarningResponse,
)
from workspace107.domain.models import TransferResult

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


@router.post("/projects/{project_id}/scan", response_model=ProjectScanResponse)
async def scan_project(
    project_id: UUID,
    request: ProjectScanRequest,
    actor_id: IdentityDependency,
    service: TransferServiceDependency,
) -> ProjectScanResponse:
    snapshot = await service.scan(
        actor_id=actor_id,
        project_id=project_id,
        source_root=request.source_root,
        ignore_patterns=request.ignore_patterns,
    )
    return ProjectScanResponse(
        files=tuple(FileSignatureResponse.model_validate(item) for item in snapshot.files),
        warnings=tuple(
            TransferWarningResponse.model_validate(warning) for warning in snapshot.warnings
        ),
    )


def _transfer_response(result: TransferResult) -> ProjectTransferResponse:
    return ProjectTransferResponse(
        transferred=result.transferred,
        skipped=result.skipped,
        removed=result.removed,
        manifest={
            path: FileSignatureResponse.model_validate(signature)
            for path, signature in result.manifest.items()
        },
        warnings=tuple(
            TransferWarningResponse.model_validate(warning) for warning in result.warnings
        ),
    )


@router.post("/projects/{project_id}/push", response_model=ProjectTransferResponse)
async def push_project(
    project_id: UUID,
    request: ProjectPushRequest,
    actor_id: IdentityDependency,
    service: TransferServiceDependency,
) -> ProjectTransferResponse:
    result = await service.push(
        actor_id=actor_id,
        project_id=project_id,
        source_root=request.source_root,
        target_root=request.target_root,
        ignore_patterns=request.ignore_patterns,
    )
    return _transfer_response(result)


@router.post("/projects/{project_id}/pull", response_model=ProjectTransferResponse)
async def pull_project(
    project_id: UUID,
    request: ProjectPullRequest,
    actor_id: IdentityDependency,
    service: TransferServiceDependency,
) -> ProjectTransferResponse:
    result = await service.pull(
        actor_id=actor_id,
        project_id=project_id,
        source_root=request.source_root,
        target_root=request.target_root,
        include=request.include,
    )
    return _transfer_response(result)
