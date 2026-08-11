"""API 对 B 已安装日志与 Artifact 内容的查询端口。

Run workspace 准备和 Artifact 安装只属于 ``RunWorkspacePort``；本端口不能创建、
重建或覆盖执行内容。
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
    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        """读取日志尾部，返回内容和是否被截断。"""
        ...

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]: ...

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes: ...
