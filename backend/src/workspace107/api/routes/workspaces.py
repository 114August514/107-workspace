from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from workspace107.api.dependencies import IdentityDependency, WorkspaceServiceDependency
from workspace107.api.schemas.workspaces import (
    MemberCreateRequest,
    MemberResponse,
    MemberUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreateRequest,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    workspace = await service.create(
        actor_id=actor_id,
        kind=request.kind,
        name=request.name,
        slug=request.slug,
        description=request.description,
        parent_id=request.parent_id,
    )
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[WorkspaceResponse]:
    workspaces = await service.list_visible(actor_id, limit=limit, offset=offset)
    return [WorkspaceResponse.model_validate(workspace) for workspace in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(await service.get(actor_id, workspace_id))


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    request: WorkspaceUpdateRequest,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    workspace = await service.update(
        actor_id=actor_id,
        workspace_id=workspace_id,
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    return WorkspaceResponse.model_validate(workspace)


@router.post("/{workspace_id}/archive", response_model=WorkspaceResponse)
async def archive_workspace(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(await service.archive(actor_id, workspace_id))


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> list[MemberResponse]:
    members = await service.list_members(actor_id, workspace_id)
    return [MemberResponse.model_validate(member) for member in members]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: UUID,
    request: MemberCreateRequest,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> MemberResponse:
    member = await service.add_member(
        actor_id=actor_id,
        workspace_id=workspace_id,
        user_id=request.user_id,
        role=request.role,
    )
    return MemberResponse.model_validate(member)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberResponse)
async def change_member_role(
    workspace_id: UUID,
    user_id: UUID,
    request: MemberUpdateRequest,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> MemberResponse:
    member = await service.change_role(
        actor_id=actor_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role=request.role,
    )
    return MemberResponse.model_validate(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    actor_id: IdentityDependency,
    service: WorkspaceServiceDependency,
) -> Response:
    await service.remove_member(
        actor_id=actor_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
