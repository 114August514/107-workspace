"""Shared Resource blob content and installed Run-output query port.

Run workspace preparation and Artifact installation belong exclusively to ``RunWorkspacePort``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..enums import LogStream


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    """Artifact 内的一个文件条目。"""

    path: str
    size: int


class StoragePort(Protocol):
    # -- 内容寻址存储 ---------------------------------------------------

    async def write_blob(self, data: bytes) -> str:
        """写入内容，返回内容摘要。"""
        ...

    async def read_blob(self, content_hash: str) -> bytes: ...

    async def blob_exists(self, content_hash: str) -> bool: ...

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        """读取日志尾部，返回内容和是否被截断。"""
        ...

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]: ...

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes: ...
