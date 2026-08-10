"""以系统 Git CLI 实现每 Project repository 与不可变 commit 内容。"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO

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
_REPOSITORY_IDENTITY_FILE = "workspace107-project-identity"
_VERSION_REF_PREFIX = "refs/workspace107/versions"
_GIT_TIMEOUT_SECONDS = 30
_GIT_ENV_KEYS = ("HOME", "LANG", "LC_ALL", "PATH", "SYSTEMROOT", "TMPDIR")


@dataclass(frozen=True, slots=True)
class _TreeEntry:
    path: str
    mode: str
    object_oid: str
    size: int
    content_hash: str


class _GitFailure(ProjectContentMissing):
    """已去敏、可稳定映射的本地 Git 执行失败。"""


class GitProjectContent:
    """Project 内容的唯一事实来源：working tree 与完整 Git commit OID。"""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock_root = root / ".locks"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock_root.mkdir(parents=True, exist_ok=True)

    async def initialize_project(self, project_id: str, repository_identity: str) -> None:
        await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._initialize_sync,
            project_id,
            repository_identity,
        )

    async def list_working_files(
        self, project_id: str, repository_identity: str
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._list_working_sync,
            project_id,
            repository_identity,
        )

    async def read_working_file(
        self, project_id: str, repository_identity: str, path: str
    ) -> bytes:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._read_working_sync,
            project_id,
            repository_identity,
            path,
        )

    async def write_working_file(
        self,
        project_id: str,
        repository_identity: str,
        path: str,
        content: bytes,
        updated_at: datetime,
    ) -> ProjectFile:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._write_working_sync,
            project_id,
            repository_identity,
            path,
            content,
            updated_at,
        )

    async def delete_working_path(
        self, project_id: str, repository_identity: str, path: str
    ) -> int:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._delete_working_sync,
            project_id,
            repository_identity,
            path,
        )

    async def move_working_path(
        self,
        project_id: str,
        repository_identity: str,
        source: str,
        destination: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._move_working_sync,
            project_id,
            repository_identity,
            source,
            destination,
            updated_at,
        )

    async def working_changes(
        self,
        project_id: str,
        repository_identity: str,
        baseline_commit_oid: str | None,
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._working_changes_sync,
            project_id,
            repository_identity,
            baseline_commit_oid,
        )

    async def commit_working(
        self,
        project_id: str,
        repository_identity: str,
        *,
        version_id: str,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._commit_working_sync,
            project_id,
            repository_identity,
            version_id,
            parent_commit_oid,
            message,
            created_by,
            created_at,
        )

    async def manifest(
        self, project_id: str, repository_identity: str, commit_oid: str
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._manifest_sync,
            project_id,
            repository_identity,
            commit_oid,
        )

    async def read_commit_file(
        self, project_id: str, repository_identity: str, commit_oid: str, path: str
    ) -> bytes:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._read_commit_file_sync,
            project_id,
            repository_identity,
            commit_oid,
            path,
        )

    async def diff_commits(
        self,
        project_id: str,
        repository_identity: str,
        base_commit_oid: str,
        target_commit_oid: str,
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._diff_commits_sync,
            project_id,
            repository_identity,
            base_commit_oid,
            target_commit_oid,
        )

    async def restore_working(
        self,
        project_id: str,
        repository_identity: str,
        commit_oid: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._restore_working_sync,
            project_id,
            repository_identity,
            commit_oid,
            updated_at,
        )

    async def fork_commit(
        self,
        source_project_id: str,
        source_repository_identity: str,
        source_commit_oid: str,
        target_project_id: str,
        target_repository_identity: str,
        *,
        version_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._locked_call,
            (source_project_id, target_project_id),
            self._fork_commit_sync,
            source_project_id,
            source_repository_identity,
            source_commit_oid,
            target_project_id,
            target_repository_identity,
            version_id,
            message,
            created_by,
            created_at,
        )

    async def export_commit(
        self,
        project_id: str,
        repository_identity: str,
        commit_oid: str,
        destination: Path,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._locked_call,
            (project_id,),
            self._export_sync,
            project_id,
            repository_identity,
            commit_oid,
            destination,
        )

    def _locked_call(
        self, project_ids: tuple[str, ...], function: Callable[..., object], *args: object
    ) -> object:
        with self._project_locks(*project_ids):
            return function(*args)

    @contextmanager
    def _project_locks(self, *project_ids: str) -> Iterator[None]:
        with ExitStack() as stack:
            for project_id in sorted(set(project_ids)):
                self._repository_path(project_id)
                handle = stack.enter_context((self._lock_root / f"{project_id}.lock").open("a+b"))
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                stack.callback(fcntl.flock, handle.fileno(), fcntl.LOCK_UN)
            yield

    def _initialize_sync(self, project_id: str, repository_identity: str) -> None:
        repository = self._repository_path(project_id)
        if repository.exists():
            if repository.is_symlink() or not repository.is_dir():
                raise ProjectContentIdentityMismatch(
                    f"Project {project_id} repository identity mismatch"
                )
            git_directory = repository / ".git"
            if git_directory.is_symlink():
                raise ProjectContentIdentityMismatch(
                    f"Project {project_id} repository metadata is a symlink"
                )
            if git_directory.is_dir():
                self._verify_repository_identity(repository, project_id, repository_identity)
                return
            if any(repository.iterdir()):
                raise ConflictError(f"Project {project_id} 的内容目录已存在且不是 Git repository")
        else:
            repository.mkdir(parents=True)
        self._git(repository, "init", "--initial-branch=main")
        identity_file = repository / ".git" / _REPOSITORY_IDENTITY_FILE
        identity_file.write_text(repository_identity + "\n", encoding="utf-8")
        identity_file.chmod(0o600)

    def _repository_path(self, project_id: str) -> Path:
        if not _PROJECT_ID.fullmatch(project_id):
            raise ValidationFailed("Project identity 不合法")
        return self._root / project_id

    def _require_repository(self, project_id: str, repository_identity: str) -> Path:
        self._recover_restore(project_id)
        repository = self._repository_path(project_id)
        git_directory = repository / ".git"
        if repository.is_symlink() or git_directory.is_symlink() or not git_directory.is_dir():
            raise ProjectContentMissing(f"Project {project_id} 的 Git repository 不存在")
        self._verify_repository_identity(repository, project_id, repository_identity)
        return repository

    def _verify_repository_identity(
        self, repository: Path, project_id: str, repository_identity: str
    ) -> None:
        identity_file = repository / ".git" / _REPOSITORY_IDENTITY_FILE
        if (
            identity_file.is_symlink()
            or not identity_file.is_file()
            or identity_file.read_text(encoding="utf-8").rstrip("\n") != repository_identity
        ):
            raise ProjectContentIdentityMismatch(
                f"Project {project_id} repository identity mismatch"
            )

    def _assert_commit(self, project_id: str, repository_identity: str, commit_oid: str) -> Path:
        if not _FULL_COMMIT_OID.fullmatch(commit_oid):
            raise ValidationFailed(
                "Project Version 必须使用完整 commit OID，不接受 branch/HEAD/latest"
            )
        repository = self._require_repository(project_id, repository_identity)
        try:
            self._git(repository, "cat-file", "-e", f"{commit_oid}^{{commit}}")
        except _GitFailure as exc:
            raise ProjectContentMissing(
                f"Project {project_id} 的 Git object {commit_oid} 不存在"
            ) from exc
        return repository

    def _identity_email(self, project_id: str) -> str:
        return f"{project_id}@{_IDENTITY_DOMAIN}"

    def _list_working_sync(self, project_id: str, repository_identity: str) -> list[ProjectFile]:
        repository = self._require_repository(project_id, repository_identity)
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

    def _read_working_sync(self, project_id: str, repository_identity: str, path: str) -> bytes:
        repository = self._require_repository(project_id, repository_identity)
        target = self._safe_target(repository, path)
        if not target.is_file() or target.is_symlink():
            raise ObjectNotFound("文件", path)
        return target.read_bytes()

    def _write_working_sync(
        self,
        project_id: str,
        repository_identity: str,
        path: str,
        content: bytes,
        updated_at: datetime,
    ) -> ProjectFile:
        repository = self._require_repository(project_id, repository_identity)
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

    def _delete_working_sync(self, project_id: str, repository_identity: str, path: str) -> int:
        repository = self._require_repository(project_id, repository_identity)
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
        self,
        project_id: str,
        repository_identity: str,
        source: str,
        destination: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        repository = self._require_repository(project_id, repository_identity)
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
        self,
        project_id: str,
        repository_identity: str,
        baseline_commit_oid: str | None,
    ) -> list[tuple[str, ChangeKind]]:
        current = {
            entry.path: entry.content_hash
            for entry in self._list_working_sync(project_id, repository_identity)
        }
        baseline: dict[str, str] = {}
        if baseline_commit_oid is not None:
            baseline = {
                entry.path: entry.content_hash
                for entry in self._manifest_sync(
                    project_id, repository_identity, baseline_commit_oid
                ).files
            }
        return self._diff(baseline, current)

    def _commit_working_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        repository = self._require_repository(project_id, repository_identity)
        if not _PROJECT_ID.fullmatch(version_id):
            raise ValidationFailed("Project Version identity 不合法")
        if not self._working_paths(repository):
            raise ValidationFailed("Project 中没有文件，无法保存版本")
        if parent_commit_oid is not None:
            self._assert_commit(project_id, repository_identity, parent_commit_oid)

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
        version_ref = f"{_VERSION_REF_PREFIX}/{version_id}"
        zero_oid = "0" * len(commit_oid)
        self._git(repository, "update-ref", version_ref, commit_oid, zero_oid)
        current_main = self._try_ref(repository, "refs/heads/main")
        expected_main = current_main or zero_oid
        self._git(
            repository,
            "update-ref",
            "refs/heads/main",
            commit_oid,
            expected_main,
        )
        return self._manifest_sync(project_id, repository_identity, commit_oid)

    def _identity_name(self, created_by: str) -> str:
        return created_by.replace("\n", " ").replace("\r", " ") or "Workspace user"

    def _manifest_sync(
        self, project_id: str, repository_identity: str, commit_oid: str
    ) -> CommitManifest:
        repository = self._assert_commit(project_id, repository_identity, commit_oid)
        tree_oid = self._git_text(
            repository, "show", "--no-patch", "--format=%T", commit_oid
        ).strip()
        entries = self._tree_entries(repository, commit_oid)
        return CommitManifest(
            commit_oid=commit_oid,
            tree_oid=tree_oid,
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
            if raw_size == b"BAD":
                raise ProjectContentMissing(f"Git object {object_oid} 不存在")
            size = int(raw_size)
            content_hash, actual_size = self._hash_blob(repository, object_oid)
            if actual_size != size:
                raise ProjectContentMissing(f"Git object {object_oid} 的大小与 tree 不一致")
            entries.append(
                _TreeEntry(
                    path=relative,
                    mode=decoded_mode,
                    object_oid=object_oid,
                    size=size,
                    content_hash=content_hash,
                )
            )
        return sorted(entries, key=lambda entry: entry.path)

    def _read_commit_file_sync(
        self,
        project_id: str,
        repository_identity: str,
        commit_oid: str,
        path: str,
    ) -> bytes:
        repository = self._assert_commit(project_id, repository_identity, commit_oid)
        relative = self._safe_relative(path)
        entry = next(
            (item for item in self._tree_entries(repository, commit_oid) if item.path == relative),
            None,
        )
        if entry is None:
            raise ObjectNotFound("文件", relative)
        return self._read_blob(repository, entry.object_oid)

    def _diff_commits_sync(
        self,
        project_id: str,
        repository_identity: str,
        base_commit_oid: str,
        target_commit_oid: str,
    ) -> list[tuple[str, ChangeKind]]:
        base = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(project_id, repository_identity, base_commit_oid).files
        }
        target = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(
                project_id, repository_identity, target_commit_oid
            ).files
        }
        return self._diff(base, target)

    def _restore_working_sync(
        self,
        project_id: str,
        repository_identity: str,
        commit_oid: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        repository = self._require_repository(project_id, repository_identity)
        manifest = self._manifest_sync(project_id, repository_identity, commit_oid)
        entries = self._tree_entries(repository, commit_oid)
        staging, backup, state = self._restore_paths(project_id)
        state.write_text("exporting\n", encoding="ascii")
        staging.mkdir()
        try:
            self._materialize(repository, entries, manifest, staging)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            state.unlink(missing_ok=True)
            raise
        state.write_text("prepared\n", encoding="ascii")
        repository.replace(backup)
        state.write_text("backup\n", encoding="ascii")
        (backup / ".git").replace(staging / ".git")
        state.write_text("git_moved\n", encoding="ascii")
        staging.replace(repository)
        state.write_text("swapped\n", encoding="ascii")
        shutil.rmtree(backup)
        state.unlink()
        timestamp = updated_at.timestamp()
        for path in self._working_paths(repository):
            os.utime(path, (timestamp, timestamp))
        return self._list_working_sync(project_id, repository_identity)

    def _restore_paths(self, project_id: str) -> tuple[Path, Path, Path]:
        return (
            self._root / f".restore-{project_id}-staging",
            self._root / f".restore-{project_id}-backup",
            self._lock_root / f"{project_id}.restore",
        )

    def _recover_restore(self, project_id: str) -> None:
        repository = self._repository_path(project_id)
        staging, backup, state = self._restore_paths(project_id)
        if not state.exists():
            return
        if state.is_symlink() or not state.is_file():
            raise ProjectContentIdentityMismatch(f"Project {project_id} restore state is invalid")
        phase = state.read_text(encoding="ascii").strip()
        if phase in {"exporting", "prepared"} and repository.exists():
            shutil.rmtree(staging, ignore_errors=True)
            state.unlink()
            return
        if phase in {"prepared", "backup"}:
            if backup.is_dir() and (backup / ".git").is_dir() and staging.is_dir():
                (backup / ".git").replace(staging / ".git")
            phase = "git_moved"
            state.write_text(phase + "\n", encoding="ascii")
        if phase == "git_moved":
            if not repository.exists() and staging.is_dir() and (staging / ".git").is_dir():
                staging.replace(repository)
            phase = "swapped"
            state.write_text(phase + "\n", encoding="ascii")
        if phase == "swapped" and repository.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)
            state.unlink()
            return
        raise ProjectContentIdentityMismatch(
            f"Project {project_id} restore state cannot be recovered"
        )

    def _fork_commit_sync(
        self,
        source_project_id: str,
        source_repository_identity: str,
        source_commit_oid: str,
        target_project_id: str,
        target_repository_identity: str,
        version_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        self._initialize_sync(target_project_id, target_repository_identity)
        target_repository = self._require_repository(target_project_id, target_repository_identity)
        if any(item.name != ".git" for item in target_repository.iterdir()):
            raise ConflictError(f"目标 Project {target_project_id} Working State 不是空的")
        temporary = Path(
            tempfile.mkdtemp(prefix="workspace107-fork-", dir=target_repository.parent)
        )
        try:
            self._export_sync(
                source_project_id,
                source_repository_identity,
                source_commit_oid,
                temporary,
            )
            for item in temporary.iterdir():
                item.replace(target_repository / item.name)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return self._commit_working_sync(
            target_project_id,
            target_repository_identity,
            version_id,
            None,
            message,
            created_by,
            created_at,
        )

    def _export_sync(
        self,
        project_id: str,
        repository_identity: str,
        commit_oid: str,
        destination: Path,
    ) -> CommitManifest:
        if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
            raise ValidationFailed("Project Version 只能导出到调用方指定的现有空目录")
        repository = self._assert_commit(project_id, repository_identity, commit_oid)
        manifest = self._manifest_sync(project_id, repository_identity, commit_oid)
        entries = self._tree_entries(repository, commit_oid)
        return self._materialize(repository, entries, manifest, destination)

    def _materialize(
        self,
        repository: Path,
        entries: list[_TreeEntry],
        manifest: CommitManifest,
        destination: Path,
    ) -> CommitManifest:
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-workspace107-", dir=destination.parent)
        )
        try:
            for entry in entries:
                target = temporary.joinpath(*PurePosixPath(entry.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                actual_hash, actual_size = self._write_blob(repository, entry.object_oid, target)
                if actual_size != entry.size or actual_hash != entry.content_hash:
                    raise ProjectContentMissing(
                        f"Git object {entry.object_oid} 与 Project Version manifest 不一致"
                    )
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

    def _hash_blob(self, repository: Path, object_oid: str) -> tuple[str, int]:
        with tempfile.TemporaryFile() as temporary:
            self._stream_blob(repository, object_oid, temporary)
            temporary.seek(0)
            return self._hash_stream(temporary)

    def _write_blob(self, repository: Path, object_oid: str, target: Path) -> tuple[str, int]:
        with target.open("w+b") as handle:
            self._stream_blob(repository, object_oid, handle)
            handle.seek(0)
            return self._hash_stream(handle)

    def _stream_blob(self, repository: Path, object_oid: str, sink: BinaryIO) -> None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repository), "cat-file", "blob", object_oid],
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.DEVNULL,
                check=False,
                env=self._git_env(),
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise _GitFailure("Git executable is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise _GitFailure("Git command timed out") from exc
        if result.returncode != 0:
            raise _GitFailure("Git command failed: cat-file")

    def _hash_stream(self, source: BinaryIO) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        return digest.hexdigest(), size

    def _try_ref(self, repository: Path, reference: str) -> str | None:
        try:
            return self._git_text(repository, "rev-parse", "--verify", reference).strip()
        except _GitFailure:
            return None

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

    def _git_env(self, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        environment = {key: os.environ[key] for key in _GIT_ENV_KEYS if key in os.environ}
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        environment.update(extra_env or {})
        return environment

    def _git(
        self,
        repository: Path,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> bytes:
        try:
            result = subprocess.run(
                ["git", "-C", str(repository), *arguments],
                input=input_data,
                capture_output=True,
                check=False,
                env=self._git_env(extra_env),
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise _GitFailure("Git executable is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise _GitFailure("Git command timed out") from exc
        if result.returncode != 0:
            command = arguments[0] if arguments else "unknown"
            raise _GitFailure(f"Git command failed: {command}")
        return result.stdout
