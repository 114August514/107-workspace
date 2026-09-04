"""本地文件系统存储。

目录布局::

    <storage_root>/
    ├── blobs/<前两位>/<摘要>          按内容寻址的文件内容
    ├── runs/<run_id>/
    │   ├── work/                     Project Version 的文件
    │   ├── inputs/                   只读输入（GR-404）
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
import stat
import tempfile
import zipfile
from pathlib import Path

from ...domain.enums import InputSourceType, LogStream
from ...domain.errors import ObjectNotFound, ValidationFailed
from ...domain.ports.storage import (
    ArtifactContent,
    ArtifactEntry,
    ProjectSyncEntry,
    RunInput,
    RunPaths,
)

READONLY_DIR = 0o555
READONLY_FILE = 0o444


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._blobs = root / "blobs"
        self._runs = root / "runs"
        self._artifacts = root / "artifacts"
        self._project_sync = root / "project-sync"
        for path in (self._blobs, self._runs, self._artifacts, self._project_sync):
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

    # -- Project 本地同步暂存区 ---------------------------------------

    def _project_sync_key(self, project_id: str, actor_id: str) -> str:
        actor_key = hashlib.sha256(actor_id.encode()).hexdigest()[:32]
        return f"{project_id}/{actor_key}"

    def _project_sync_path(self, project_id: str, actor_id: str) -> Path:
        return self._project_sync / self._project_sync_key(project_id, actor_id)

    async def prepare_project_sync(self, project_id: str, actor_id: str) -> str:
        target = self._project_sync_path(project_id, actor_id)
        await asyncio.to_thread(target.mkdir, parents=True, exist_ok=True)
        return self._project_sync_key(project_id, actor_id)

    async def list_project_sync_files(
        self, project_id: str, actor_id: str
    ) -> list[ProjectSyncEntry]:
        root = self._project_sync_path(project_id, actor_id)
        return await asyncio.to_thread(_scan_project_sync, root)

    async def read_project_sync_file(self, project_id: str, actor_id: str, path: str) -> bytes:
        root = self._project_sync_path(project_id, actor_id).resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file() or target.is_symlink():
            raise ValidationFailed(f"同步暂存区中的路径「{path}」不是可读取的普通文件")
        return await asyncio.to_thread(target.read_bytes)

    async def resolve_blob_path(self, content_hash: str) -> Path:
        target = self._blob_path(content_hash)
        if not await asyncio.to_thread(target.is_file):
            raise ObjectNotFound("文件内容", content_hash)
        actual = await asyncio.to_thread(_file_sha256, target)
        if actual != content_hash:
            raise ValidationFailed("CAS 文件内容与 Environment SIF 摘要不一致")
        return target.resolve()

    # -- Run 工作目录 ---------------------------------------------------

    def run_paths(self, run_id: str) -> RunPaths:
        root = self._runs / run_id
        return RunPaths(root=root, work=root / "work", inputs=root / "inputs", logs=root / "logs")

    async def prepare_run_directory(
        self,
        run_id: str,
        *,
        files: list[tuple[str, str]],
        inputs: list[RunInput],
    ) -> RunPaths:
        paths = self.run_paths(run_id)
        await asyncio.to_thread(self._prepare_sync, paths, files, inputs)
        return paths

    def _prepare_sync(
        self,
        paths: RunPaths,
        files: list[tuple[str, str]],
        inputs: list[RunInput],
    ) -> None:
        if paths.root.exists():
            _force_rmtree(paths.root)
        for directory in (paths.work, paths.inputs, paths.logs):
            directory.mkdir(parents=True, exist_ok=True)

        for relative_path, content_hash in files:
            target = paths.work / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._blob_path(content_hash), target)

        for entry in inputs:
            # 访问路径是运行环境中的绝对路径；本机执行时挂到 Run 的 inputs 根下。
            target = paths.inputs / entry.access_path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            sub = entry.source_subpath
            if entry.source_type is InputSourceType.ARTIFACT:
                source = self._artifacts / entry.source_id
                if not source.exists():
                    raise FileNotFoundError(f"输入 Artifact {entry.source_id} 的内容不存在")
                if not sub:
                    shutil.copytree(source, target)
                else:
                    # 子路径只取产物目录的一部分。sub 已在 InputBinding 规范化，
                    # 再用 resolve 二次确认不逃出产物根（防御性，不依赖单层校验）。
                    subtree = (source / sub).resolve()
                    if not str(subtree).startswith(str(source.resolve())):
                        raise FileNotFoundError(
                            f"输入 {entry.access_path} 引用的子路径 {sub!r} 越出了 Artifact 根目录"
                        )
                    if not subtree.exists():
                        raise FileNotFoundError(
                            f"输入 {entry.access_path} 引用的子路径 {sub!r} 不存在"
                        )
                    if subtree.is_dir():
                        shutil.copytree(subtree, target)
                    else:
                        # 子路径指向单个文件：物化到 target/<basename>，不能 copytree。
                        shutil.copyfile(subtree, target / subtree.name)
            elif entry.source_type is InputSourceType.SHARED_RESOURCE_VERSION:
                # Shared Resource Version 没有专门的存储目录——内容存在 blob 池里，
                # 这里按版本的 (path, content_hash) 列表从 blob 物化到 access_path 下。
                # sub 非空时只物化落在该子路径下的文件，并剥掉子路径前缀。
                for relative_path, content_hash in entry.files:
                    if sub and relative_path == sub:
                        # 子路径正好命名一个文件：保留 basename，落到 target/<basename>。
                        # 不能剥到空串——那会落到 target 目录本身导致 copyfile 进目录。
                        stripped = relative_path
                    elif sub and relative_path.startswith(sub + "/"):
                        # 子路径是一个目录：剥掉前缀，其下的文件原样落到 target 下。
                        stripped = relative_path[len(sub) + 1 :]
                    elif sub:
                        # 不在子路径下：跳过。用 "sub/" 边界前缀而非裸 startswith，
                        # 避免 sub="train" 误纳 "training/..."。
                        continue
                    else:
                        stripped = relative_path
                    file_target = target / stripped
                    file_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self._blob_path(content_hash), file_target)
            else:  # pragma: no cover - 枚举封闭，未来加新来源类型时这里会显式失败
                raise FileNotFoundError(f"未知输入来源类型 {entry.source_type!r}")

        # 输入默认只读：Run 不得原地修改输入对象（GR-404）。
        if inputs:
            _make_readonly(paths.inputs)

        paths.stdout.touch()
        paths.stderr.touch()

    async def read_log(self, run_id: str, stream: LogStream, *, max_bytes: int) -> tuple[str, bool]:
        paths = self.run_paths(run_id)
        target = paths.stdout if stream is LogStream.STDOUT else paths.stderr
        return await asyncio.to_thread(_read_tail, target, max_bytes)

    async def iter_log(self, run_id: str, stream: LogStream, *, chunk_size: int):
        paths = self.run_paths(run_id)
        target = paths.stdout if stream is LogStream.STDOUT else paths.stderr
        async for chunk in _read_chunks(target, chunk_size):
            yield chunk

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
        if root not in target.parents or not target.is_file():
            raise ObjectNotFound("Artifact 文件", path)
        return await asyncio.to_thread(target.read_bytes)

    async def iter_artifact_file(self, artifact_id: str, path: str, *, chunk_size: int):
        root = (self._artifacts / artifact_id).resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file():
            raise ObjectNotFound("Artifact 文件", path)
        async for chunk in _read_chunks(target, chunk_size):
            yield chunk

    async def iter_artifact_archive(self, artifact_id: str, *, chunk_size: int):
        root = (self._artifacts / artifact_id).resolve()
        if not root.is_dir():
            raise ObjectNotFound("Artifact 内容", artifact_id)
        temporary = await asyncio.to_thread(_create_archive, root)
        try:
            async for chunk in _read_chunks(temporary, chunk_size):
                yield chunk
        finally:
            with contextlib.suppress(FileNotFoundError):
                await asyncio.to_thread(temporary.unlink)

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


def _scan_project_sync(root: Path) -> list[ProjectSyncEntry]:
    if not root.is_dir():
        raise ValidationFailed("Project 同步暂存区尚未准备")

    entries: list[ProjectSyncEntry] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in dirnames:
            candidate = parent / name
            mode = candidate.lstat().st_mode
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISLNK(mode):
                raise ValidationFailed(f"同步暂存区不接受符号链接「{relative}」")
        for name in filenames:
            candidate = parent / name
            mode = candidate.lstat().st_mode
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISLNK(mode):
                raise ValidationFailed(f"同步暂存区不接受符号链接「{relative}」")
            if not stat.S_ISREG(mode):
                raise ValidationFailed(f"同步暂存区只接受普通文件「{relative}」")
            entries.append(ProjectSyncEntry(path=relative, size=candidate.stat().st_size))
    return sorted(entries, key=lambda entry: entry.path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _read_chunks(path: Path, chunk_size: int):
    if not await asyncio.to_thread(path.is_file):
        return
    handle = await asyncio.to_thread(path.open, "rb")
    try:
        while True:
            chunk = await asyncio.to_thread(handle.read, chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        await asyncio.to_thread(handle.close)


def _create_archive(root: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix="workspace107-artifact-", suffix=".zip", delete=False
    ) as handle:
        archive = Path(handle.name)
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(root.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    bundle.write(path, path.relative_to(root).as_posix())
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    return archive


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
