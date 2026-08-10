"""以系统 Git CLI 实现每 Project repository 与不可变 commit 内容。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from ..domain.enums import ChangeKind
from ..domain.errors import (
    ConflictError,
    ObjectNotFound,
    ProjectContentIdentityMismatch,
    ProjectContentMissing,
    ValidationFailed,
)
from ..domain.models import ProjectFile, ProjectVersionFile
from ..domain.ports.project_content import CommitManifest

_PROJECT_ID = re.compile(r"[A-Za-z0-9_-]+")
_FULL_COMMIT_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_IDENTITY_DOMAIN = "projects.workspace107.invalid"


@dataclass(frozen=True, slots=True)
class _TreeEntry:
    path: str
    mode: str
    object_oid: str
    size: int
    content_hash: str


class _GitFailure(RuntimeError):
    pass


class GitProjectContent:
    """Project 内容的唯一事实来源：working tree 与完整 Git commit OID。"""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    async def initialize_project(self, project_id: str) -> None:
        await asyncio.to_thread(self._initialize_sync, project_id)

    async def list_working_files(self, project_id: str) -> list[ProjectFile]:
        return await asyncio.to_thread(self._list_working_sync, project_id)

    async def read_working_file(self, project_id: str, path: str) -> bytes:
        return await asyncio.to_thread(self._read_working_sync, project_id, path)

    async def write_working_file(
        self, project_id: str, path: str, content: bytes, updated_at: datetime
    ) -> ProjectFile:
        return await asyncio.to_thread(
            self._write_working_sync, project_id, path, content, updated_at
        )

    async def delete_working_path(self, project_id: str, path: str) -> int:
        return await asyncio.to_thread(self._delete_working_sync, project_id, path)

    async def move_working_path(
        self, project_id: str, source: str, destination: str, updated_at: datetime
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._move_working_sync, project_id, source, destination, updated_at
        )

    async def working_changes(
        self, project_id: str, baseline_commit_oid: str | None
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(self._working_changes_sync, project_id, baseline_commit_oid)

    async def commit_working(
        self,
        project_id: str,
        *,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._commit_working_sync,
            project_id,
            parent_commit_oid,
            message,
            created_by,
            created_at,
        )

    async def manifest(self, project_id: str, commit_oid: str) -> CommitManifest:
        return await asyncio.to_thread(self._manifest_sync, project_id, commit_oid)

    async def read_commit_file(self, project_id: str, commit_oid: str, path: str) -> bytes:
        return await asyncio.to_thread(self._read_commit_file_sync, project_id, commit_oid, path)

    async def diff_commits(
        self, project_id: str, base_commit_oid: str, target_commit_oid: str
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(
            self._diff_commits_sync, project_id, base_commit_oid, target_commit_oid
        )

    async def restore_working(
        self, project_id: str, commit_oid: str, updated_at: datetime
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._restore_working_sync, project_id, commit_oid, updated_at
        )

    async def fork_commit(
        self,
        source_project_id: str,
        source_commit_oid: str,
        target_project_id: str,
        *,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._fork_commit_sync,
            source_project_id,
            source_commit_oid,
            target_project_id,
            message,
            created_by,
            created_at,
        )

    async def export_commit(
        self, project_id: str, commit_oid: str, destination: Path
    ) -> CommitManifest:
        return await asyncio.to_thread(self._export_sync, project_id, commit_oid, destination)

    def _initialize_sync(self, project_id: str) -> None:
        repository = self._repository_path(project_id)
        if repository.exists():
            if repository.is_symlink() or not repository.is_dir():
                raise ProjectContentIdentityMismatch(
                    f"Project {project_id} repository identity mismatch"
                )
            if (repository / ".git").is_dir():
                return
            if any(repository.iterdir()):
                raise ConflictError(f"Project {project_id} 的内容目录已存在且不是 Git repository")
        else:
            repository.mkdir(parents=True)
        self._git(repository, "init", "--initial-branch=main")

    def _repository_path(self, project_id: str) -> Path:
        if not _PROJECT_ID.fullmatch(project_id):
            raise ValidationFailed("Project identity 不合法")
        return self._root / project_id

    def _require_repository(self, project_id: str) -> Path:
        repository = self._repository_path(project_id)
        if repository.is_symlink() or not (repository / ".git").is_dir():
            raise ProjectContentMissing(f"Project {project_id} 的 Git repository 不存在")
        return repository

    def _assert_commit(self, project_id: str, commit_oid: str) -> Path:
        if not _FULL_COMMIT_OID.fullmatch(commit_oid):
            raise ValidationFailed(
                "Project Version 必须使用完整 commit OID，不接受 branch/HEAD/latest"
            )
        repository = self._require_repository(project_id)
        try:
            self._git(repository, "cat-file", "-e", f"{commit_oid}^{{commit}}")
        except _GitFailure as exc:
            raise ProjectContentMissing(
                f"Project {project_id} 的 Git object {commit_oid} 不存在"
            ) from exc
        author_email = self._git_text(
            repository, "show", "--no-patch", "--format=%ae", commit_oid
        ).strip()
        if author_email != self._identity_email(project_id):
            raise ProjectContentIdentityMismatch(
                f"commit {commit_oid} 与 Project {project_id} identity mismatch"
            )
        return repository

    def _identity_email(self, project_id: str) -> str:
        return f"{project_id}@{_IDENTITY_DOMAIN}"

    def _list_working_sync(self, project_id: str) -> list[ProjectFile]:
        repository = self._require_repository(project_id)
        result: list[ProjectFile] = []
        for path in self._working_paths(repository):
            data = path.read_bytes()
            result.append(
                ProjectFile(
                    project_id=project_id,
                    path=path.relative_to(repository).as_posix(),
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                    updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                )
            )
        return result

    def _working_paths(self, repository: Path) -> list[Path]:
        paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(repository, followlinks=False):
            current = Path(dirpath)
            if current == repository:
                dirnames[:] = [name for name in dirnames if name != ".git"]
            for name in list(dirnames):
                candidate = current / name
                if candidate.is_symlink():
                    relative = candidate.relative_to(repository)
                    raise ValidationFailed(
                        f"Project Working State 包含不支持的符号链接：{relative}"
                    )
            for name in filenames:
                candidate = current / name
                relative = candidate.relative_to(repository).as_posix()
                self._safe_relative(relative)
                mode = candidate.lstat().st_mode
                if stat.S_ISLNK(mode):
                    raise ValidationFailed(
                        f"Project Working State 包含不支持的符号链接：{relative}"
                    )
                if not stat.S_ISREG(mode):
                    raise ValidationFailed(
                        f"Project Working State 包含不支持的文件类型：{relative}"
                    )
                paths.append(candidate)
        return sorted(paths, key=lambda item: item.relative_to(repository).as_posix())

    def _read_working_sync(self, project_id: str, path: str) -> bytes:
        repository = self._require_repository(project_id)
        target = self._safe_target(repository, path)
        if not target.is_file() or target.is_symlink():
            raise ObjectNotFound("文件", path)
        return target.read_bytes()

    def _write_working_sync(
        self, project_id: str, path: str, content: bytes, updated_at: datetime
    ) -> ProjectFile:
        repository = self._require_repository(project_id)
        relative = self._safe_relative(path)
        target = self._safe_target(repository, relative, allow_missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".workspace107-", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        timestamp = updated_at.timestamp()
        os.utime(target, (timestamp, timestamp))
        return ProjectFile(
            project_id=project_id,
            path=relative,
            size=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            updated_at=updated_at,
        )

    def _delete_working_sync(self, project_id: str, path: str) -> int:
        repository = self._require_repository(project_id)
        target = self._safe_target(repository, path)
        if not target.exists() or target.is_symlink():
            raise ObjectNotFound("文件或目录", path)
        if target.is_file():
            target.unlink()
            return 1
        count = sum(1 for item in target.rglob("*") if item.is_file() and not item.is_symlink())
        shutil.rmtree(target)
        return count

    def _move_working_sync(
        self, project_id: str, source: str, destination: str, updated_at: datetime
    ) -> list[ProjectFile]:
        repository = self._require_repository(project_id)
        source_path = self._safe_target(repository, source)
        destination_path = self._safe_target(repository, destination, allow_missing=True)
        if not source_path.exists() or source_path.is_symlink():
            raise ObjectNotFound("文件或目录", source)
        if destination_path.exists():
            raise ConflictError(f"目标路径 {destination} 已存在")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(destination_path)
        timestamp = updated_at.timestamp()
        candidates = (
            [destination_path] if destination_path.is_file() else self._working_paths(repository)
        )
        moved: list[ProjectFile] = []
        for candidate in candidates:
            if candidate != destination_path and not candidate.is_relative_to(destination_path):
                continue
            data = candidate.read_bytes()
            os.utime(candidate, (timestamp, timestamp))
            moved.append(
                ProjectFile(
                    project_id=project_id,
                    path=candidate.relative_to(repository).as_posix(),
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                    updated_at=updated_at,
                )
            )
        return sorted(moved, key=lambda item: item.path)

    def _working_changes_sync(
        self, project_id: str, baseline_commit_oid: str | None
    ) -> list[tuple[str, ChangeKind]]:
        current = {entry.path: entry.content_hash for entry in self._list_working_sync(project_id)}
        baseline: dict[str, str] = {}
        if baseline_commit_oid is not None:
            baseline = {
                entry.path: entry.content_hash
                for entry in self._manifest_sync(project_id, baseline_commit_oid).files
            }
        return self._diff(baseline, current)

    def _commit_working_sync(
        self,
        project_id: str,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        repository = self._require_repository(project_id)
        if not self._working_paths(repository):
            raise ValidationFailed("Project 中没有文件，无法保存版本")
        if parent_commit_oid is not None:
            self._assert_commit(project_id, parent_commit_oid)

        self._git(repository, "add", "-A", "-f", "--", ".")
        tree_oid = self._git_text(repository, "write-tree").strip()
        if parent_commit_oid is not None:
            parent_tree = self._git_text(
                repository, "show", "--no-patch", "--format=%T", parent_commit_oid
            ).strip()
            if tree_oid == parent_tree:
                raise ConflictError("当前内容与最近一个版本相同，没有需要保存的变更")

        identity_email = self._identity_email(project_id)
        git_env = {
            "GIT_AUTHOR_NAME": self._identity_name(created_by),
            "GIT_AUTHOR_EMAIL": identity_email,
            "GIT_AUTHOR_DATE": created_at.isoformat(),
            "GIT_COMMITTER_NAME": "Workspace 107",
            "GIT_COMMITTER_EMAIL": identity_email,
            "GIT_COMMITTER_DATE": created_at.isoformat(),
        }
        arguments = ["commit-tree", tree_oid]
        if parent_commit_oid is not None:
            arguments.extend(["-p", parent_commit_oid])
        commit_oid = self._git_text(
            repository,
            *arguments,
            input_data=(message.strip() or "保存版本").encode("utf-8") + b"\n",
            extra_env=git_env,
        ).strip()
        self._git(repository, "update-ref", "refs/heads/main", commit_oid)
        return self._manifest_sync(project_id, commit_oid)

    def _identity_name(self, created_by: str) -> str:
        return created_by.replace("\n", " ").replace("\r", " ") or "Workspace user"

    def _manifest_sync(self, project_id: str, commit_oid: str) -> CommitManifest:
        repository = self._assert_commit(project_id, commit_oid)
        entries = self._tree_entries(repository, commit_oid)
        return CommitManifest(
            commit_oid=commit_oid,
            files=tuple(
                ProjectVersionFile(entry.path, entry.size, entry.content_hash) for entry in entries
            ),
        )

    def _tree_entries(self, repository: Path, commit_oid: str) -> list[_TreeEntry]:
        try:
            payload = self._git(repository, "ls-tree", "-r", "-z", "-l", "--full-tree", commit_oid)
        except _GitFailure as exc:
            raise ProjectContentMissing(f"Git commit {commit_oid} 的 tree 不存在") from exc
        entries: list[_TreeEntry] = []
        for raw_entry in payload.split(b"\0"):
            if not raw_entry:
                continue
            metadata, raw_path = raw_entry.split(b"\t", 1)
            mode, object_type, raw_oid, raw_size = metadata.split()
            try:
                path = raw_path.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationFailed("Project Version 包含非 UTF-8 路径") from exc
            relative = self._safe_relative(path)
            decoded_mode = mode.decode("ascii")
            if decoded_mode == "120000":
                raise ValidationFailed(f"Project Version 包含不支持的符号链接：{relative}")
            if object_type != b"blob" or decoded_mode not in {"100644", "100755"}:
                raise ValidationFailed(f"Project Version 包含不支持的 Git tree entry：{relative}")
            object_oid = raw_oid.decode("ascii")
            data = self._read_blob(repository, object_oid)
            size = int(raw_size)
            if len(data) != size:
                raise ProjectContentMissing(f"Git object {object_oid} 的大小与 tree 不一致")
            entries.append(
                _TreeEntry(
                    path=relative,
                    mode=decoded_mode,
                    object_oid=object_oid,
                    size=size,
                    content_hash=hashlib.sha256(data).hexdigest(),
                )
            )
        return sorted(entries, key=lambda entry: entry.path)

    def _read_commit_file_sync(self, project_id: str, commit_oid: str, path: str) -> bytes:
        repository = self._assert_commit(project_id, commit_oid)
        relative = self._safe_relative(path)
        entry = next(
            (item for item in self._tree_entries(repository, commit_oid) if item.path == relative),
            None,
        )
        if entry is None:
            raise ObjectNotFound("文件", relative)
        return self._read_blob(repository, entry.object_oid)

    def _diff_commits_sync(
        self, project_id: str, base_commit_oid: str, target_commit_oid: str
    ) -> list[tuple[str, ChangeKind]]:
        base = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(project_id, base_commit_oid).files
        }
        target = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(project_id, target_commit_oid).files
        }
        return self._diff(base, target)

    def _restore_working_sync(
        self, project_id: str, commit_oid: str, updated_at: datetime
    ) -> list[ProjectFile]:
        repository = self._require_repository(project_id)
        temporary = Path(tempfile.mkdtemp(prefix="workspace107-restore-", dir=repository.parent))
        try:
            self._export_sync(project_id, commit_oid, temporary)
            for item in repository.iterdir():
                if item.name == ".git":
                    continue
                shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
            for item in temporary.iterdir():
                item.replace(repository / item.name)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        timestamp = updated_at.timestamp()
        for path in self._working_paths(repository):
            os.utime(path, (timestamp, timestamp))
        return self._list_working_sync(project_id)

    def _fork_commit_sync(
        self,
        source_project_id: str,
        source_commit_oid: str,
        target_project_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        self._initialize_sync(target_project_id)
        target_repository = self._require_repository(target_project_id)
        if any(item.name != ".git" for item in target_repository.iterdir()):
            raise ConflictError(f"目标 Project {target_project_id} Working State 不是空的")
        temporary = Path(
            tempfile.mkdtemp(prefix="workspace107-fork-", dir=target_repository.parent)
        )
        try:
            self._export_sync(source_project_id, source_commit_oid, temporary)
            for item in temporary.iterdir():
                item.replace(target_repository / item.name)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return self._commit_working_sync(target_project_id, None, message, created_by, created_at)

    def _export_sync(self, project_id: str, commit_oid: str, destination: Path) -> CommitManifest:
        if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
            raise ValidationFailed("Project Version 只能导出到调用方指定的现有空目录")
        repository = self._assert_commit(project_id, commit_oid)
        entries = self._tree_entries(repository, commit_oid)
        manifest = CommitManifest(
            commit_oid=commit_oid,
            files=tuple(
                ProjectVersionFile(item.path, item.size, item.content_hash) for item in entries
            ),
        )
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-workspace107-", dir=destination.parent)
        )
        try:
            for entry in entries:
                target = temporary.joinpath(*PurePosixPath(entry.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                data = self._read_blob(repository, entry.object_oid)
                if (
                    len(data) != entry.size
                    or hashlib.sha256(data).hexdigest() != entry.content_hash
                ):
                    raise ProjectContentMissing(
                        f"Git object {entry.object_oid} 与 Project Version manifest 不一致"
                    )
                target.write_bytes(data)
                target.chmod(0o755 if entry.mode == "100755" else 0o644)
            destination.rmdir()
            try:
                os.replace(temporary, destination)
            except Exception:
                destination.mkdir(exist_ok=True)
                raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        return manifest

    def _read_blob(self, repository: Path, object_oid: str) -> bytes:
        try:
            return self._git(repository, "cat-file", "blob", object_oid)
        except _GitFailure as exc:
            raise ProjectContentMissing(f"Git object {object_oid} 不存在") from exc

    def _safe_relative(self, path: str) -> str:
        candidate = PurePosixPath(path)
        if (
            not path
            or candidate.is_absolute()
            or any(part in {"", ".", "..", ".git"} for part in candidate.parts)
        ):
            raise ValidationFailed(f"Project 路径 {path!r} 越出了 repository 或命中保留路径")
        normalized = candidate.as_posix()
        if normalized != path:
            raise ValidationFailed(f"Project 路径 {path!r} 不是规范相对路径")
        return normalized

    def _safe_target(self, repository: Path, path: str, *, allow_missing: bool = False) -> Path:
        relative = self._safe_relative(path)
        target = repository.joinpath(*PurePosixPath(relative).parts)
        current = repository
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    raise ValidationFailed(f"Project 路径 {path!r} 穿过符号链接")
            elif not allow_missing:
                break
        return target

    def _diff(self, left: dict[str, str], right: dict[str, str]) -> list[tuple[str, ChangeKind]]:
        changes: list[tuple[str, ChangeKind]] = []
        for path in sorted(set(left) | set(right)):
            if path not in left:
                changes.append((path, ChangeKind.ADDED))
            elif path not in right:
                changes.append((path, ChangeKind.REMOVED))
            elif left[path] != right[path]:
                changes.append((path, ChangeKind.MODIFIED))
        return changes

    def _git_text(
        self,
        repository: Path,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> str:
        return self._git(repository, *arguments, input_data=input_data, extra_env=extra_env).decode(
            "utf-8"
        )

    def _git(
        self,
        repository: Path,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> bytes:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            input=input_data,
            capture_output=True,
            check=False,
            env={**os.environ, **(extra_env or {})},
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise _GitFailure(detail or f"git {' '.join(arguments)} failed")
        return result.stdout
