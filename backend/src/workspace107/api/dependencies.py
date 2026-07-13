from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, Request

from workspace107.api.errors import ApiProblem
from workspace107.application.users import UserService
from workspace107.application.workspaces import WorkspaceService
from workspace107.domain.ports.repositories import UnitOfWorkFactory


def get_uow_factory(request: Request) -> UnitOfWorkFactory:
    factory = getattr(request.app.state, "uow_factory", None)
    if factory is None:
        raise RuntimeError("unit of work factory is not configured")
    return cast(UnitOfWorkFactory, factory)


UowFactoryDependency = Annotated[UnitOfWorkFactory, Depends(get_uow_factory)]


def get_user_service(uow_factory: UowFactoryDependency) -> UserService:
    return UserService(uow_factory)


def get_workspace_service(uow_factory: UowFactoryDependency) -> WorkspaceService:
    return WorkspaceService(uow_factory)


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


async def require_identity(
    uow_factory: UowFactoryDependency,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> UUID:
    if x_user_id is None:
        raise ApiProblem(
            status=401,
            title="Identity required",
            code="identity_required",
            detail="X-User-Id must identify an existing user.",
        )
    try:
        user_id = UUID(x_user_id)
    except ValueError as exc:
        raise ApiProblem(
            status=401,
            title="Identity required",
            code="identity_required",
            detail="X-User-Id must identify an existing user.",
        ) from exc

    async with uow_factory() as uow:
        if await uow.users.get(user_id) is None:
            raise ApiProblem(
                status=401,
                title="Identity required",
                code="identity_required",
                detail="X-User-Id must identify an existing user.",
            )
    return user_id


IdentityDependency = Annotated[UUID, Depends(require_identity)]
