"""本地文件系统存储。

目录布局::

    <storage_root>/
    ├── blobs/<前两位>/<摘要>          按内容寻址的文件内容
    ├── runs/<run_id>/
    │   ├── work/                     Project Version 的文件
    │   ├── inputs/                   只读输入（GR-011）
    │   └── logs/{stdout,stderr}.log
    └── artifacts/<artifact_id>/      收集到的运行产物

内容按摘要寻址，因此多个 Project Version 引用同一份内容不会重复占用空间，
ProjectVersion 的不可变性也天然成立——内容变了摘要就变了。

真实集群部署时会把这里换成共享文件系统或对象存储的实现，
上层通过 ``StoragePort`` 使用，不需要改动。
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
from pathlib import Path

from ...domain.enums import LogStream
from ...domain.errors import ObjectNotFound
from ...domain.ports.storage import ArtifactContent, ArtifactEntry, RunPaths

READONLY_DIR = 0o555
READONLY_FILE = 0o444


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._blobs = root / "blobs"
        self._runs = root / "runs"
        self._artifacts = root / "artifacts"
        for path in (self._blobs, self._runs, self._artifacts):
            path.mkdir(parents=True, exist_ok=True)

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

    # -- Run 工作目录 ---------------------------------------------------

    def run_paths(self, run_id: str) -> RunPaths:
        root = self._runs / run_id
        return RunPaths(root=root, work=root / "work", inputs=root / "inputs", logs=root / "logs")

    async def prepare_run_directory(
        self,
        run_id: str,
        *,
        files: list[tuple[str, str]],
        inputs: list[tuple[str, str]],
    ) -> RunPaths:
        paths = self.run_paths(run_id)
        await asyncio.to_thread(self._prepare_sync, paths, files, inputs)
        return paths

    def _prepare_sync(
        self,
        paths: RunPaths,
        files: list[tuple[str, str]],
        inputs: list[tuple[str, str]],
    ) -> None:
        if paths.root.exists():
            _force_rmtree(paths.root)
        for directory in (paths.work, paths.inputs, paths.logs):
            directory.mkdir(parents=True, exist_ok=True)

        for relative_path, content_hash in files:
            target = paths.work / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._blob_path(content_hash), target)

        for access_path, artifact_id in inputs:
            # 访问路径是运行环境中的绝对路径；本机执行时挂到 Run 的 inputs 根下。
            target = paths.inputs / access_path.lstrip("/")
            source = self._artifacts / artifact_id
            if not source.exists():
                raise FileNotFoundError(f"输入 Artifact {artifact_id} 的内容不存在")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)

        # 输入默认只读：Run 不得原地修改输入对象（GR-011）。
        if inputs:
            _make_readonly(paths.inputs)

        paths.stdout.touch()
        paths.stderr.touch()

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        paths = self.run_paths(run_id)
        target = paths.stdout if stream is LogStream.STDOUT else paths.stderr
        return await asyncio.to_thread(_read_tail, target, max_bytes)

    async def cleanup_run_directory(self, run_id: str) -> None:
        await asyncio.to_thread(_force_rmtree, self.run_paths(run_id).root)

    # -- Artifact -------------------------------------------------------

    async def collect_artifact(
        self, run_id: str, artifact_id: str, source_path: str
    ) -> ArtifactContent | None:
        return await asyncio.to_thread(self._collect_sync, run_id, artifact_id, source_path)

    def _collect_sync(
        self, run_id: str, artifact_id: str, source_path: str
    ) -> ArtifactContent | None:
        source = self.run_paths(run_id).work / source_path
        if not source.exists():
            return None

        target = self._artifacts / artifact_id
        if target.exists():
            _force_rmtree(target)
        target.mkdir(parents=True)

        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(source, target / source.name)

        digest = hashlib.sha256()
        size = 0
        count = 0
        for path in sorted(p for p in target.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(target)).encode())
            data = path.read_bytes()
            digest.update(data)
            size += len(data)
            count += 1

        return ArtifactContent(size=size, file_count=count, content_hash=digest.hexdigest())

    async def list_artifact_files(self, artifact_id: str) -> list[ArtifactEntry]:
        return await asyncio.to_thread(self._list_artifact_sync, artifact_id)

    def _list_artifact_sync(self, artifact_id: str) -> list[ArtifactEntry]:
        root = self._artifacts / artifact_id
        if not root.exists():
            raise ObjectNotFound("Artifact 内容", artifact_id)
        return [
            ArtifactEntry(path=str(p.relative_to(root)), size=p.stat().st_size)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]

    async def read_artifact_file(self, artifact_id: str, path: str) -> bytes:
        root = (self._artifacts / artifact_id).resolve()
        target = (root / path).resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            raise ObjectNotFound("Artifact 文件", path)
        return await asyncio.to_thread(target.read_bytes)

    async def delete_artifact_content(self, artifact_id: str) -> None:
        await asyncio.to_thread(_force_rmtree, self._artifacts / artifact_id)


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


def _make_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(READONLY_FILE if path.is_file() else READONLY_DIR)
    root.chmod(READONLY_DIR)


def _force_rmtree(root: Path) -> None:
    """删除目录树，先恢复只读目录的写权限。"""
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o755)
        for name in dirnames + filenames:
            with contextlib.suppress(FileNotFoundError):  # 并发删除时忽略
                os.chmod(Path(dirpath) / name, 0o644 if name in filenames else 0o755)
    shutil.rmtree(root, ignore_errors=True)
