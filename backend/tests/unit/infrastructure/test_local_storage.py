import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from workspace107.domain.errors import InvalidStorageKey, ResourceNotFound
from workspace107.domain.models import ObjectMetadata
from workspace107.infrastructure.storage.local import LocalStorage


async def chunks(data: bytes) -> AsyncIterator[bytes]:
    midpoint = len(data) // 2
    yield data[:midpoint]
    yield data[midpoint:]


async def broken_chunks() -> AsyncIterator[bytes]:
    yield b"partial"
    raise RuntimeError("stream failed")


async def read_all(source: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in source])


async def test_put_hashes_streams_and_deduplicates(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    metadata = ObjectMetadata(name="data.bin", media_type="application/octet-stream")

    first = await storage.put(chunks(b"dataset"), metadata)
    second = await storage.put(chunks(b"dataset"), metadata)

    digest = hashlib.sha256(b"dataset").hexdigest()
    assert first.sha256 == digest
    assert first.storage_key == f"sha256/{digest[:2]}/{digest}"
    assert first.size_bytes == 7
    assert first.created
    assert not second.created
    assert await read_all(storage.open(first.storage_key)) == b"dataset"


async def test_open_unknown_key_returns_not_found(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    digest = "a" * 64

    with pytest.raises(ResourceNotFound):
        await read_all(storage.open(f"sha256/aa/{digest}"))


@pytest.mark.parametrize(
    "key",
    ["../secret", "sha256/aa/../secret", "sha256/bb/" + "a" * 64, "sha256/AA/" + "a" * 64],
)
async def test_rejects_untrusted_storage_keys(tmp_path: Path, key: str) -> None:
    storage = LocalStorage(tmp_path)

    with pytest.raises(InvalidStorageKey):
        await read_all(storage.open(key))


async def test_failed_put_removes_temporary_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    with pytest.raises(RuntimeError, match="stream failed"):
        await storage.put(
            broken_chunks(),
            ObjectMetadata(name="broken.bin", media_type="application/octet-stream"),
        )

    assert list((tmp_path / ".tmp").iterdir()) == []


async def test_delete_unreferenced_is_idempotent(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    stored = await storage.put(
        chunks(b"delete me"),
        ObjectMetadata(name="delete.bin", media_type="application/octet-stream"),
    )

    await storage.delete_unreferenced(stored.storage_key)
    await storage.delete_unreferenced(stored.storage_key)

    with pytest.raises(ResourceNotFound):
        await read_all(storage.open(stored.storage_key))
