"""存储端口。

Project 文件、Run 工作目录、日志和 Artifact 的内容都在存储层，
数据库只保存元数据和内容摘要。

内容按摘要寻址（content-addressed），因此保存同一份内容的多个 Project
Version 不会重复占用空间，而且 ProjectVersion 的不可变性天然成立。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..enums import LogStream


@dataclass(frozen=True, slots=True)
class RunPaths:
    """一次 Run 在存储中的目录布局。"""

    root: Path
    work: Path
    """工作目录根，Project Version 的文件被materialize到这里。"""
    inputs: Path
    """输入内容的挂载根。其下的内容只读（GR-011）。"""
    logs: Path

    @property
    def stdout(self) -> Path:
        return self.logs / "stdout.log"

    @property
    def stderr(self) -> Path:
        return self.logs / "stderr.log"


@dataclass(frozen=True, slots=True)
class ArtifactContent:
    """收集 Artifact 后得到的内容事实。"""

    size: int
    file_count: int
    content_hash: str


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

    # -- Run 工作目录 ---------------------------------------------------

    def run_paths(self, run_id: str) -> RunPaths: ...

    async def prepare_run_directory(
        self,
        run_id: str,
        *,
        files: list[tuple[str, str]],
        inputs: list[tuple[str, str]],
    ) -> RunPaths:
        """准备 Run 工作目录。

        ``files``  是 ``(相对路径, 内容摘要)``，来自 Project Version。
        ``inputs`` 是 ``(访问路径, Artifact ID)``，内容以只读方式放置。
        """
        ...

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        """读取日志尾部，返回内容和是否被截断。"""
        ...

    async def cleanup_run_directory(self, run_id: str) -> None: ...

    # -- Artifact -------------------------------------------------------

    async def collect_artifact(
        self, run_id: str, artifact_id: str, source_path: str
    ) -> ArtifactContent | None:
        """把 Run 工作目录下的路径收集为 Artifact。

        路径不存在时返回 ``None``，由调用方按收集规则决定是否算失败。
        """
        ...

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]: ...

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes: ...

    async def delete_artifact_content(self, artifact_id: str) -> None:
        """删除 Artifact 的存储内容。

        只删内容，不删记录——历史 Run 仍要能看到标识、摘要和清理状态（GR-016）。
        """
        ...
