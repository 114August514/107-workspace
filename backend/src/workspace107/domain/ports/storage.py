from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from workspace107.domain.models import ObjectMetadata, StoredObject


@runtime_checkable
class StoragePort(Protocol):
    async def put(self, chunks: AsyncIterator[bytes], metadata: ObjectMetadata) -> StoredObject: ...

    def open(self, storage_key: str) -> AsyncIterator[bytes]: ...

    async def delete_unreferenced(self, storage_key: str) -> None: ...
