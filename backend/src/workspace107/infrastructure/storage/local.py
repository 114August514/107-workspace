import asyncio
import hashlib
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from workspace107.domain.errors import InvalidStorageKey, ResourceNotFound
from workspace107.domain.models import ObjectMetadata, StoredObject

_KEY_PATTERN = re.compile(r"sha256/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})")
_READ_SIZE = 64 * 1024


def _flush_and_close(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())
    handle.close()


def _install(temp_path: Path, target: Path) -> bool:
    try:
        os.link(temp_path, target)
        return True
    except FileExistsError:
        return False
    finally:
        temp_path.unlink(missing_ok=True)


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._temporary_root = self._root / ".tmp"
        self._temporary_root.mkdir(parents=True, exist_ok=True)
        (self._root / "sha256").mkdir(parents=True, exist_ok=True)

    async def put(self, chunks: AsyncIterator[bytes], metadata: ObjectMetadata) -> StoredObject:
        del metadata
        temp_path = self._temporary_root / uuid4().hex
        digest = hashlib.sha256()
        size_bytes = 0
        handle = temp_path.open("xb")
        try:
            async for chunk in chunks:
                digest.update(chunk)
                size_bytes += len(chunk)
                await asyncio.to_thread(handle.write, chunk)
            await asyncio.to_thread(_flush_and_close, handle)
            handle = None

            hex_digest = digest.hexdigest()
            storage_key = f"sha256/{hex_digest[:2]}/{hex_digest}"
            target = self._storage_path(storage_key)
            await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
            created = await asyncio.to_thread(_install, temp_path, target)
            return StoredObject(
                storage_key=storage_key,
                size_bytes=size_bytes,
                sha256=hex_digest,
                created=created,
            )
        finally:
            if handle is not None:
                await asyncio.to_thread(handle.close)
            await asyncio.to_thread(temp_path.unlink, missing_ok=True)

    def open(self, storage_key: str) -> AsyncIterator[bytes]:
        path = self._storage_path(storage_key)

        async def stream() -> AsyncIterator[bytes]:
            if not path.is_file():
                raise ResourceNotFound(f"stored object {storage_key!r} not found")
            handle = await asyncio.to_thread(path.open, "rb")
            try:
                while chunk := await asyncio.to_thread(handle.read, _READ_SIZE):
                    yield chunk
            finally:
                await asyncio.to_thread(handle.close)

        return stream()

    async def delete_unreferenced(self, storage_key: str) -> None:
        path = self._storage_path(storage_key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    def _storage_path(self, storage_key: str) -> Path:
        match = _KEY_PATTERN.fullmatch(storage_key)
        if match is None or match.group("prefix") != match.group("digest")[:2]:
            raise InvalidStorageKey(storage_key)
        path = (self._root / storage_key).resolve()
        if not path.is_relative_to(self._root):
            raise InvalidStorageKey(storage_key)
        return path
