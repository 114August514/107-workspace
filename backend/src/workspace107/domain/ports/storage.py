"""存储端口。

Project 文件、Run 工作目录、日志和 Artifact 的内容都在存储层，
数据库只保存元数据和内容摘要。

内容按摘要寻址（content-addressed），因此保存同一份内容的多个 Project
Version 不会重复占用空间，而且 ProjectVersion 的不可变性天然成立。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..enums import InputSourceType, LogStream


@dataclass(frozen=True, slots=True)
class RunPaths:
    """一次 Run 在存储中的目录布局。"""

    root: Path
    work: Path
    """工作目录根，Project Version 的文件被materialize到这里。"""
    inputs: Path
    """输入内容的挂载根。其下的内容只读（GR-404）。"""
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


@dataclass(frozen=True, slots=True)
class RunInput:
    """一次 Run 的一个输入绑定，按来源类型决定如何物化。

    设计稿 §3.1.3 把 InputBinding 定义为对 Content Version 的统一引用，
    storage 端也用同一种结构表达——artifact 和 shared_resource_version
    只是 Content Version 的两种来源，物化方式不同，但都暴露在同一
    ``access_path`` 下、都只读（GR-404）。

    ``files`` 仅对 ``shared_resource_version`` 有意义：把版本的
    ``(path, content_hash)`` 列表物化到 ``access_path`` 下，复用 Project
    Version 已在用的 blob 池。``artifact`` 路径则按 ``artifact_id`` 找到
    已经收集好的目录直接复制。

    ``source_subpath`` 非空时只物化该子路径下的内容并剥掉前缀映射到 ``access_path``
    下（设计稿 §3.1.3 的可选 Source Subpath）；空串表示物化整份内容。子路径已在
    ``InputBinding`` 层规范化，storage 端直接按规范值匹配。
    """

    source_type: InputSourceType
    source_id: str
    access_path: str
    files: tuple[tuple[str, str], ...] = ()
    """``(relative_path, content_hash)``，仅 shared_resource_version 使用。"""
    source_subpath: str = ""
    """规范化后的子路径，空串表示物化整份内容；两种来源都用。"""


class StoragePort(Protocol):
    # -- 内容寻址存储 ---------------------------------------------------

    async def write_blob(self, data: bytes) -> str:
        """写入内容，返回内容摘要。"""
        ...

    async def write_blob_file(self, path: Path) -> str:
        """Stream a local file into CAS without loading the whole image into memory."""
        ...

    async def read_blob(self, content_hash: str) -> bytes: ...

    async def blob_exists(self, content_hash: str) -> bool: ...

    async def resolve_blob_path(self, content_hash: str) -> Path:
        """Return a scheduler-visible CAS path after rechecking the exact digest."""
        ...

    # -- Run 工作目录 ---------------------------------------------------

    def run_paths(self, run_id: str) -> RunPaths: ...

    async def prepare_run_directory(
        self,
        run_id: str,
        *,
        files: list[tuple[str, str]],
        inputs: list[RunInput],
    ) -> RunPaths:
        """准备 Run 工作目录。

        ``files``  是 ``(相对路径, 内容摘要)``，来自 Project Version。
        ``inputs`` 是 :class:`RunInput` 列表，按来源类型物化到 ``access_path``，
        内容只读（GR-404）。
        """
        ...

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        """读取日志尾部，返回内容和是否被截断。"""
        ...

    async def iter_log(
        self, run_id: str, stream: LogStream, *, chunk_size: int
    ) -> AsyncIterator[bytes]:
        """以小块读取完整日志，不把文件一次性载入应用内存。"""
        ...

    async def iter_artifact_file(
        self, artifact_id: str, path: str, *, chunk_size: int
    ) -> AsyncIterator[bytes]:
        """以小块读取 Artifact 文件。"""
        ...

    async def iter_artifact_archive(
        self, artifact_id: str, *, chunk_size: int
    ) -> AsyncIterator[bytes]:
        """以小块读取 Artifact 的完整归档。"""
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
        """删除 Artifact 的存储内容。"""
        ...
