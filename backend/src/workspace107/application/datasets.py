from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID

from workspace107.application.access import require_workspace_access
from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import ResourceArchived, ResourceConflict, ResourceNotFound
from workspace107.domain.models import (
    Dataset,
    DatasetVersion,
    NewDataset,
    NewDatasetVersion,
    ObjectMetadata,
    utc_now,
)
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory
from workspace107.domain.ports.storage import StoragePort


class DatasetService:
    def __init__(self, uow_factory: UnitOfWorkFactory, storage: StoragePort) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def create(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        name: str,
        slug: str,
        description: str = "",
    ) -> Dataset:
        async with self._uow_factory() as uow:
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=workspace_id,
                minimum=WorkspaceRole.MEMBER,
                active=True,
            )
            if await uow.datasets.get_by_slug(workspace_id, slug) is not None:
                raise ResourceConflict(f"dataset slug {slug!r} already exists")
            dataset = await uow.datasets.add(
                NewDataset(
                    workspace_id=workspace_id,
                    name=name,
                    slug=slug,
                    description=description,
                    created_by=actor_id,
                )
            )
            await uow.commit()
            return dataset

    async def list(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[Dataset, ...]:
        async with self._uow_factory() as uow:
            await require_workspace_access(uow, actor_id=actor_id, workspace_id=workspace_id)
            return await uow.datasets.list_for_workspace(workspace_id, limit=limit, offset=offset)

    async def get(self, actor_id: UUID, dataset_id: UUID) -> Dataset:
        async with self._uow_factory() as uow:
            dataset = await self._load(uow, dataset_id)
            await require_workspace_access(
                uow, actor_id=actor_id, workspace_id=dataset.workspace_id
            )
            return dataset

    async def archive(self, actor_id: UUID, dataset_id: UUID) -> Dataset:
        async with self._uow_factory() as uow:
            dataset = await self._load(uow, dataset_id)
            await require_workspace_access(
                uow,
                actor_id=actor_id,
                workspace_id=dataset.workspace_id,
                minimum=WorkspaceRole.MANAGER,
                active=True,
            )
            if dataset.archived_at is None:
                dataset = await uow.datasets.save(replace(dataset, archived_at=utc_now()))
                await uow.commit()
            return dataset

    async def create_version(
        self,
        *,
        actor_id: UUID,
        dataset_id: UUID,
        version: str,
        chunks: AsyncIterator[bytes],
        metadata: ObjectMetadata,
    ) -> DatasetVersion:
        async with self._uow_factory() as uow:
            await self._authorize_version_write(uow, actor_id, dataset_id, version)

        stored = await self._storage.put(chunks, metadata)
        try:
            async with self._uow_factory() as uow:
                await self._authorize_version_write(uow, actor_id, dataset_id, version)
                created = await uow.datasets.add_version(
                    NewDatasetVersion(
                        dataset_id=dataset_id,
                        version=version,
                        storage_key=stored.storage_key,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                        created_by=actor_id,
                    )
                )
                await uow.commit()
                return created
        except BaseException:
            if stored.created:
                async with self._uow_factory() as uow:
                    references = await uow.datasets.count_versions_by_storage_key(
                        stored.storage_key
                    )
                if references == 0:
                    await self._storage.delete_unreferenced(stored.storage_key)
            raise

    async def list_versions(self, actor_id: UUID, dataset_id: UUID) -> tuple[DatasetVersion, ...]:
        async with self._uow_factory() as uow:
            dataset = await self._load(uow, dataset_id)
            await require_workspace_access(
                uow, actor_id=actor_id, workspace_id=dataset.workspace_id
            )
            return await uow.datasets.list_versions(dataset_id)

    async def open_version(
        self, actor_id: UUID, version_id: UUID
    ) -> tuple[DatasetVersion, AsyncIterator[bytes]]:
        async with self._uow_factory() as uow:
            version = await uow.datasets.get_version(version_id)
            if version is None:
                raise ResourceNotFound(f"dataset version {version_id} not found")
            dataset = await self._load(uow, version.dataset_id)
            await require_workspace_access(
                uow, actor_id=actor_id, workspace_id=dataset.workspace_id
            )
        return version, self._storage.open(version.storage_key)

    async def _authorize_version_write(
        self, uow: UnitOfWork, actor_id: UUID, dataset_id: UUID, version: str
    ) -> None:
        dataset = await self._load(uow, dataset_id)
        await require_workspace_access(
            uow,
            actor_id=actor_id,
            workspace_id=dataset.workspace_id,
            minimum=WorkspaceRole.MEMBER,
            active=True,
        )
        if dataset.archived_at is not None:
            raise ResourceArchived(f"dataset {dataset.id} is archived")
        if await uow.datasets.get_version_by_name(dataset_id, version) is not None:
            raise ResourceConflict(f"dataset version {version!r} already exists")

    @staticmethod
    async def _load(uow: UnitOfWork, dataset_id: UUID) -> Dataset:
        dataset = await uow.datasets.get(dataset_id)
        if dataset is None:
            raise ResourceNotFound(f"dataset {dataset_id} not found")
        return dataset
