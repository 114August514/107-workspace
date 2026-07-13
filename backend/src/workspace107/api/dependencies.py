from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, Request

from workspace107.api.errors import ApiProblem
from workspace107.application.datasets import DatasetService
from workspace107.application.projects import ProjectService
from workspace107.application.templates import TemplateService
from workspace107.application.transfers import TransferService
from workspace107.application.users import UserService
from workspace107.application.workspaces import WorkspaceService
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.domain.ports.storage import StoragePort
from workspace107.domain.ports.transfer import ProjectTransferPort


def get_uow_factory(request: Request) -> UnitOfWorkFactory:
    factory = getattr(request.app.state, "uow_factory", None)
    if factory is None:
        raise RuntimeError("unit of work factory is not configured")
    return cast(UnitOfWorkFactory, factory)


UowFactoryDependency = Annotated[UnitOfWorkFactory, Depends(get_uow_factory)]


def get_storage(request: Request) -> StoragePort:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise RuntimeError("storage is not configured")
    return cast(StoragePort, storage)


StorageDependency = Annotated[StoragePort, Depends(get_storage)]


def get_transfer(request: Request) -> ProjectTransferPort:
    transfer = getattr(request.app.state, "transfer", None)
    if transfer is None:
        raise RuntimeError("project transfer is not configured")
    return cast(ProjectTransferPort, transfer)


def get_transfer_roots(request: Request) -> dict[str, Path]:
    roots = getattr(request.app.state, "transfer_roots", None)
    if roots is None:
        raise RuntimeError("project transfer roots are not configured")
    return cast(dict[str, Path], roots)


TransferDependency = Annotated[ProjectTransferPort, Depends(get_transfer)]
TransferRootsDependency = Annotated[dict[str, Path], Depends(get_transfer_roots)]


def get_user_service(uow_factory: UowFactoryDependency) -> UserService:
    return UserService(uow_factory)


def get_workspace_service(uow_factory: UowFactoryDependency) -> WorkspaceService:
    return WorkspaceService(uow_factory)


def get_project_service(uow_factory: UowFactoryDependency) -> ProjectService:
    return ProjectService(uow_factory)


def get_dataset_service(
    uow_factory: UowFactoryDependency, storage: StorageDependency
) -> DatasetService:
    return DatasetService(uow_factory, storage)


def get_template_service(uow_factory: UowFactoryDependency) -> TemplateService:
    return TemplateService(uow_factory)


def get_transfer_service(
    uow_factory: UowFactoryDependency,
    transfer: TransferDependency,
    roots: TransferRootsDependency,
) -> TransferService:
    return TransferService(uow_factory, transfer, roots)


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]
ProjectServiceDependency = Annotated[ProjectService, Depends(get_project_service)]
DatasetServiceDependency = Annotated[DatasetService, Depends(get_dataset_service)]
TemplateServiceDependency = Annotated[TemplateService, Depends(get_template_service)]
TransferServiceDependency = Annotated[TransferService, Depends(get_transfer_service)]


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
