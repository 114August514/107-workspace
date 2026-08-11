"""API 对 B 已安装日志与 Artifact 内容的查询适配器。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from ...domain.enums import LogStream
from ...domain.errors import ObjectNotFound
from ...domain.ports.storage import ArtifactEntry


class LocalStorage:
    """只读 B 的 canonical Shared FS 布局，不创建或重建执行内容。"""

    def __init__(self, root: Path) -> None:
        self._runs = root / "runs"
        self._artifact_store = root / "artifact-store"

    async def read_log(
        self,
        run_id: str,
        stream: LogStream,
        *,
        max_bytes: int,
    ) -> tuple[str, bool]:
        logs = self._runs / run_id / "logs"
        target = logs / ("stdout.log" if stream is LogStream.STDOUT else "stderr.log")
        return await asyncio.to_thread(_read_tail, target, max_bytes)

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]:
        return await asyncio.to_thread(self._list_artifact_sync, artifact_id)

    def _list_artifact_sync(self, artifact_id: str) -> list[ArtifactEntry]:
        root = self._artifact_store / artifact_id / "content"
        if not root.is_dir():
            raise ObjectNotFound("Artifact 内容", artifact_id)
        return [
            ArtifactEntry(path=path.relative_to(root).as_posix(), size=path.stat().st_size)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes:
        root = (self._artifact_store / artifact_id / "content").resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ObjectNotFound("Artifact 文件", path)
        return await asyncio.to_thread(target.read_bytes)


def _read_tail(path: Path, max_bytes: int) -> tuple[str, bool]:
    if not path.exists():
        return "", False
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            return handle.read().decode("utf-8", errors="replace"), True
        return handle.read().decode("utf-8", errors="replace"), False
