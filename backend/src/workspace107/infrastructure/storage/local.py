"""API adapter for Shared Resource blobs and Worker-installed Run output.

The independent Worker exclusively creates Run workspaces and installs Artifacts. This adapter
only writes content-addressed Shared Resource blobs and reads canonical logs/Artifact content.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path

from ...domain.enums import LogStream
from ...domain.errors import ObjectNotFound, ValidationFailed
from ...domain.ports.storage import ArtifactEntry

_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_CONTENT_HASH = re.compile(r"[0-9a-f]{64}")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._blobs = root / "blobs"
        self._runs = root / "runs"
        self._artifact_store = root / "artifact-store"
        self._ensure_private_directory(self._blobs, "Shared Resource blob store")

    # -- 内容寻址存储 ---------------------------------------------------

    def _blob_path(self, content_hash: str) -> Path:
        if not _CONTENT_HASH.fullmatch(content_hash):
            raise ValidationFailed("Shared Resource blob identity must be a SHA-256 digest")
        return self._blobs / content_hash[:2] / content_hash

    async def write_blob(self, data: bytes) -> str:
        content_hash = hashlib.sha256(data).hexdigest()
        target = self._blob_path(content_hash)
        await asyncio.to_thread(self._write_blob_sync, target, data)
        return content_hash

    async def read_blob(self, content_hash: str) -> bytes:
        target = self._blob_path(content_hash)
        return await asyncio.to_thread(self._read_blob_sync, target, content_hash)

    async def blob_exists(self, content_hash: str) -> bool:
        target = self._blob_path(content_hash)
        return await asyncio.to_thread(self._blob_exists_sync, target)

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

    @staticmethod
    def _ensure_private_directory(path: Path, label: str) -> None:
        if path.is_symlink():
            raise ValidationFailed(f"{label} cannot be a symbolic link")
        path.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=True)
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise ValidationFailed(f"{label} must be a service-owned directory")
        path.chmod(_PRIVATE_DIRECTORY_MODE)

    def _write_blob_sync(self, target: Path, data: bytes) -> None:
        self._ensure_private_directory(target.parent, "Shared Resource blob shard")
        if self._blob_exists_sync(target):
            return
        descriptor, temporary_name = tempfile.mkstemp(prefix=".workspace107-", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            os.replace(temporary, target)
            target.chmod(_PRIVATE_FILE_MODE)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _blob_exists_sync(target: Path) -> bool:
        if not target.exists() and not target.is_symlink():
            return False
        info = target.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != _PRIVATE_FILE_MODE
        ):
            raise ValidationFailed("Shared Resource blob must be a service-private regular file")
        return True

    def _read_blob_sync(self, target: Path, content_hash: str) -> bytes:
        if not self._blob_exists_sync(target):
            raise ObjectNotFound("文件内容", content_hash)
        return target.read_bytes()


def _read_tail(path: Path, max_bytes: int) -> tuple[str, bool]:
    if not path.exists():
        return "", False
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            return handle.read().decode("utf-8", errors="replace"), True
        return handle.read().decode("utf-8", errors="replace"), False
