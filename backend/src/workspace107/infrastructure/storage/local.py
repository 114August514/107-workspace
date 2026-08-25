"""API adapter for Shared Resource blobs and Worker-installed Run output.

The independent Worker exclusively creates Run workspaces and installs Artifacts. This adapter
only writes content-addressed Shared Resource blobs and reads canonical logs/Artifact content.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from ...domain.enums import LogStream
from ...domain.errors import ObjectNotFound
from ...domain.ports.storage import ArtifactEntry


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._blobs = root / "blobs"
        self._runs = root / "runs"
        self._artifact_store = root / "artifact-store"
        self._blobs.mkdir(parents=True, exist_ok=True)

    # -- 内容寻址存储 ---------------------------------------------------

    def _blob_path(self, content_hash: str) -> Path:
        return self._blobs / content_hash[:2] / content_hash

    async def write_blob(self, data: bytes) -> str:
        content_hash = hashlib.sha256(data).hexdigest()
        target = self._blob_path(content_hash)
        if not target.exists():
            await asyncio.to_thread(_write_atomic, target, data)
        return content_hash

    async def read_blob(self, content_hash: str) -> bytes:
        target = self._blob_path(content_hash)
        if not target.exists():
            raise ObjectNotFound("文件内容", content_hash)
        return await asyncio.to_thread(target.read_bytes)

    async def blob_exists(self, content_hash: str) -> bool:
        return await asyncio.to_thread(self._blob_path(content_hash).exists)

    # -- Worker-installed output ---------------------------------------

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        logs = self._runs / run_id / "logs"
        target = logs / ("stdout.log" if stream is LogStream.STDOUT else "stderr.log")
        return await asyncio.to_thread(_read_tail, target, max_bytes)

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]:
        return await asyncio.to_thread(self._list_artifact_sync, artifact_id)

    def _list_artifact_sync(self, artifact_id: str) -> list[ArtifactEntry]:
        root = self._artifact_store / artifact_id / "content"
        if not root.exists():
            raise ObjectNotFound("Artifact 内容", artifact_id)
        return [
            ArtifactEntry(path=str(p.relative_to(root)), size=p.stat().st_size)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes:
        root = (self._artifact_store / artifact_id / "content").resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ObjectNotFound("Artifact 文件", path)
        return await asyncio.to_thread(target.read_bytes)


# --------------------------------------------------------------------------
# 文件系统辅助
# --------------------------------------------------------------------------


def _write_atomic(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)


def _read_tail(path: Path, max_bytes: int) -> tuple[str, bool]:
    if not path.exists():
        return "", False
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            return handle.read().decode("utf-8", errors="replace"), True
        return handle.read().decode("utf-8", errors="replace"), False
