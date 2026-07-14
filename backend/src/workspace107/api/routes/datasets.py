from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from workspace107.api.dependencies import DatasetServiceDependency, IdentityDependency
from workspace107.api.schemas.datasets import (
    DatasetCreateRequest,
    DatasetResponse,
    DatasetVersionResponse,
)
from workspace107.domain.models import ObjectMetadata

router = APIRouter(tags=["datasets"])
_UPLOAD_CHUNK_SIZE = 64 * 1024


async def _upload_chunks(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
        yield chunk


@router.post(
    "/workspaces/{workspace_id}/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    workspace_id: UUID,
    request: DatasetCreateRequest,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
) -> DatasetResponse:
    dataset = await service.create(
        actor_id=actor_id,
        workspace_id=workspace_id,
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    return DatasetResponse.model_validate(dataset)


@router.get("/workspaces/{workspace_id}/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DatasetResponse]:
    datasets = await service.list(
        actor_id=actor_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [DatasetResponse.model_validate(dataset) for dataset in datasets]


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
) -> DatasetResponse:
    return DatasetResponse.model_validate(await service.get(actor_id, dataset_id))


@router.post("/datasets/{dataset_id}/archive", response_model=DatasetResponse)
async def archive_dataset(
    dataset_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
) -> DatasetResponse:
    return DatasetResponse.model_validate(await service.archive(actor_id, dataset_id))


@router.post(
    "/datasets/{dataset_id}/versions",
    response_model=DatasetVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version(
    dataset_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
    version: Annotated[str, Form(min_length=1, max_length=100)],
    file: Annotated[UploadFile, File()],
) -> DatasetVersionResponse:
    created = await service.create_version(
        actor_id=actor_id,
        dataset_id=dataset_id,
        version=version,
        chunks=_upload_chunks(file),
        metadata=ObjectMetadata(
            name=file.filename or "dataset.bin",
            media_type=file.content_type or "application/octet-stream",
        ),
    )
    return DatasetVersionResponse.model_validate(created)


@router.get(
    "/datasets/{dataset_id}/versions",
    response_model=list[DatasetVersionResponse],
)
async def list_dataset_versions(
    dataset_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
) -> list[DatasetVersionResponse]:
    versions = await service.list_versions(actor_id, dataset_id)
    return [DatasetVersionResponse.model_validate(version) for version in versions]


@router.get("/dataset-versions/{version_id}/download")
async def download_dataset_version(
    version_id: UUID,
    actor_id: IdentityDependency,
    service: DatasetServiceDependency,
) -> StreamingResponse:
    _, chunks = await service.open_version(actor_id, version_id)
    return StreamingResponse(chunks, media_type="application/octet-stream")
