from uuid import UUID

from fastapi import APIRouter, status

from workspace107.api.dependencies import UserServiceDependency
from workspace107.api.schemas.users import UserCreateRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: UserCreateRequest, service: UserServiceDependency) -> UserResponse:
    user = await service.create(
        username=request.username,
        display_name=request.display_name,
        email=request.email,
    )
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, service: UserServiceDependency) -> UserResponse:
    return UserResponse.model_validate(await service.get(user_id))
