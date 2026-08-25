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
_FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
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
    content_hash: str = ""


class _GitFailure(ProjectContentMissing):
    """已去敏、可稳定映射的本地 Git 执行失败。"""


class GitProjectContent:
    """Git 是内容事实；正式 Version 由 immutable ref 与完整 commit OID 共同标识。"""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    async def initialize_project(self, project_id: str, repository_identity: str) -> None:
        await asyncio.to_thread(self._initialize_sync, project_id, repository_identity)

    async def list_working_files(
        self, project_id: str, repository_identity: str
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(self._list_working_sync, project_id, repository_identity)

    async def read_working_file(
        self, project_id: str, repository_identity: str, path: str
    ) -> bytes:
        return await asyncio.to_thread(
            self._read_working_sync, project_id, repository_identity, path
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
            self._delete_working_sync, project_id, repository_identity, path
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
        baseline_version_id: str | None,
        baseline_commit_oid: str | None,
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(
            self._working_changes_sync,
            project_id,
            repository_identity,
            baseline_version_id,
            baseline_commit_oid,
        )

    async def commit_working(
        self,
        project_id: str,
        repository_identity: str,
        *,
        version_id: str,
        parent_version_id: str | None,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._commit_working_sync,
            project_id,
            repository_identity,
            version_id,
            parent_version_id,
            parent_commit_oid,
            message,
            created_by,
            created_at,
        )

    async def manifest(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._manifest_sync,
            project_id,
            repository_identity,
            version_id,
            commit_oid,
        )

    async def read_commit_file(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        path: str,
    ) -> bytes:
        return await asyncio.to_thread(
            self._read_commit_file_sync,
            project_id,
            repository_identity,
            version_id,
            commit_oid,
            path,
        )

    async def diff_commits(
        self,
        project_id: str,
        repository_identity: str,
        base_version_id: str,
        base_commit_oid: str,
        target_version_id: str,
        target_commit_oid: str,
    ) -> list[tuple[str, ChangeKind]]:
        return await asyncio.to_thread(
            self._diff_commits_sync,
            project_id,
            repository_identity,
            base_version_id,
            base_commit_oid,
            target_version_id,
            target_commit_oid,
        )

    async def restore_working(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        return await asyncio.to_thread(
            self._restore_working_sync,
            project_id,
            repository_identity,
            version_id,
            commit_oid,
            updated_at,
        )

    async def fork_commit(
        self,
        source_project_id: str,
        source_repository_identity: str,
        source_version_id: str,
        source_commit_oid: str,
        target_project_id: str,
        target_repository_identity: str,
        *,
        version_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
        expected_source_tree_oid: str,
        expected_source_file_count: int,
        expected_source_total_size: int,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._fork_commit_sync,
            source_project_id,
            source_repository_identity,
            source_version_id,
            source_commit_oid,
            target_project_id,
            target_repository_identity,
            version_id,
            message,
            created_by,
            created_at,
            expected_source_tree_oid,
            expected_source_file_count,
            expected_source_total_size,
        )

    async def export_commit(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        destination: Path,
        *,
        expected_tree_oid: str | None = None,
        expected_file_count: int | None = None,
        expected_total_size: int | None = None,
    ) -> CommitManifest:
        return await asyncio.to_thread(
            self._export_sync,
            project_id,
            repository_identity,
            version_id,
            commit_oid,
            destination,
            expected_tree_oid,
            expected_file_count,
            expected_total_size,
        )

    def _initialize_sync(self, project_id: str, repository_identity: str) -> None:
        project_root = self._project_root(project_id)
        if project_root.exists():
            self._require_repository(project_id, repository_identity)
            return
        project_root.mkdir()
        work_tree = self._work_tree(project_root)
        git_directory = self._git_directory(project_root)
        work_tree.mkdir()
        try:
            self._run_git(
                "init",
                "--initial-branch=main",
                f"--separate-git-dir={git_directory}",
                str(work_tree),
            )
            (work_tree / ".git").unlink()
            identity_file = git_directory / _REPOSITORY_IDENTITY_FILE
            identity_file.write_text(repository_identity + "\n", encoding="utf-8")
            identity_file.chmod(0o600)
        except Exception:
            shutil.rmtree(project_root, ignore_errors=True)
            raise

    def _project_root(self, project_id: str) -> Path:
        if not _PROJECT_ID.fullmatch(project_id):
            raise ValidationFailed("Project identity 不合法")
        return self._root / project_id

    @staticmethod
    def _git_directory(project_root: Path) -> Path:
        return project_root / "repository.git"

    @staticmethod
    def _work_tree(project_root: Path) -> Path:
        return project_root / "work"

    def _require_repository(self, project_id: str, repository_identity: str) -> Path:
        project_root = self._project_root(project_id)
        self._recover_restore(project_root, project_id)
        git_directory = self._git_directory(project_root)
        work_tree = self._work_tree(project_root)
        if (
            project_root.is_symlink()
            or git_directory.is_symlink()
            or work_tree.is_symlink()
            or not git_directory.is_dir()
            or not work_tree.is_dir()
        ):
            raise ProjectContentMissing(f"Project {project_id} 的 Git repository 不存在")
        identity_file = git_directory / _REPOSITORY_IDENTITY_FILE
        if (
            identity_file.is_symlink()
            or not identity_file.is_file()
            or identity_file.read_text(encoding="utf-8").rstrip("\n") != repository_identity
        ):
            raise ProjectContentIdentityMismatch(
                f"Project {project_id} repository identity mismatch"
            )
        return project_root

    def _assert_version_ref(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
    ) -> Path:
        if not _PROJECT_ID.fullmatch(version_id):
            raise ValidationFailed("Project Version identity 不合法")
        if not _FULL_OID.fullmatch(commit_oid):
            raise ValidationFailed(
                "Project Version 必须使用完整 commit OID，不接受 branch/HEAD/latest"
            )
        project_root = self._require_repository(project_id, repository_identity)
        if self._try_ref(project_root, self._version_ref(version_id)) != commit_oid:
            raise ProjectContentIdentityMismatch(
                f"Project Version {version_id} immutable ref identity mismatch"
            )
        try:
            self._git(project_root, "cat-file", "-e", f"{commit_oid}^{{commit}}")
        except _GitFailure as exc:
            raise ProjectContentMissing(f"Git commit {commit_oid} 不存在") from exc
        return project_root

    @staticmethod
    def _version_ref(version_id: str) -> str:
        return f"{_VERSION_REF_PREFIX}/{version_id}"

    def _list_working_sync(self, project_id: str, repository_identity: str) -> list[ProjectFile]:
        project_root = self._require_repository(project_id, repository_identity)
        work_tree = self._work_tree(project_root)
        result: list[ProjectFile] = []
        for path in self._working_paths(work_tree):
            data = path.read_bytes()
            result.append(
                ProjectFile(
                    project_id=project_id,
                    path=path.relative_to(work_tree).as_posix(),
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                    updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                )
            )
        return result

    def _working_paths(self, work_tree: Path) -> list[Path]:
        paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(work_tree, followlinks=False):
            current = Path(dirpath)
            for name in list(dirnames):
                candidate = current / name
                if candidate.is_symlink():
                    relative = candidate.relative_to(work_tree)
                    raise ValidationFailed(
                        f"Project Working State 包含不支持的符号链接：{relative}"
                    )
            for name in filenames:
                candidate = current / name
                relative = candidate.relative_to(work_tree).as_posix()
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
        return sorted(paths, key=lambda item: item.relative_to(work_tree).as_posix())

    def _read_working_sync(self, project_id: str, repository_identity: str, path: str) -> bytes:
        project_root = self._require_repository(project_id, repository_identity)
        target = self._safe_target(self._work_tree(project_root), path)
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
        project_root = self._require_repository(project_id, repository_identity)
        work_tree = self._work_tree(project_root)
        relative = self._safe_relative(path)
        target = self._safe_target(work_tree, relative, allow_missing=True)
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
        project_root = self._require_repository(project_id, repository_identity)
        target = self._safe_target(self._work_tree(project_root), path)
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
        project_root = self._require_repository(project_id, repository_identity)
        work_tree = self._work_tree(project_root)
        source_path = self._safe_target(work_tree, source)
        destination_path = self._safe_target(work_tree, destination, allow_missing=True)
        if not source_path.exists() or source_path.is_symlink():
            raise ObjectNotFound("文件或目录", source)
        if destination_path.exists():
            raise ConflictError(f"目标路径 {destination} 已存在")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(destination_path)
        timestamp = updated_at.timestamp()
        candidates = (
            [destination_path] if destination_path.is_file() else self._working_paths(work_tree)
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
                    path=candidate.relative_to(work_tree).as_posix(),
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
        baseline_version_id: str | None,
        baseline_commit_oid: str | None,
    ) -> list[tuple[str, ChangeKind]]:
        current = {
            entry.path: entry.content_hash
            for entry in self._list_working_sync(project_id, repository_identity)
        }
        if (baseline_version_id is None) != (baseline_commit_oid is None):
            raise ProjectContentIdentityMismatch("Project Version baseline identity 不完整")
        baseline: dict[str, str] = {}
        if baseline_version_id is not None and baseline_commit_oid is not None:
            baseline = {
                entry.path: entry.content_hash
                for entry in self._manifest_sync(
                    project_id,
                    repository_identity,
                    baseline_version_id,
                    baseline_commit_oid,
                ).files
            }
        return self._diff(baseline, current)

    def _commit_working_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        parent_version_id: str | None,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest:
        project_root = self._require_repository(project_id, repository_identity)
        if not _PROJECT_ID.fullmatch(version_id):
            raise ValidationFailed("Project Version identity 不合法")
        if not self._working_paths(self._work_tree(project_root)):
            raise ValidationFailed("Project 中没有文件，无法保存版本")
        if (parent_version_id is None) != (parent_commit_oid is None):
            raise ProjectContentIdentityMismatch("Project Version parent identity 不完整")
        if parent_version_id is not None and parent_commit_oid is not None:
            self._assert_version_ref(
                project_id,
                repository_identity,
                parent_version_id,
                parent_commit_oid,
            )
        self._git(project_root, "add", "-A", "-f", "--", ".")
        # Windows Git commonly uses ``core.checkStat=minimal``. A same-size replacement with the
        # same caller-supplied mtime can therefore look clean in the index even though its bytes
        # changed. The first add preserves normal new/deleted-file semantics; renormalize then
        # forces Git's own clean/hash pipeline over every tracked working-tree file.
        self._git(project_root, "add", "--renormalize", "-f", "--", ".")
        tree_oid = self._git_text(project_root, "write-tree").strip()
        if parent_commit_oid is not None:
            parent_tree = self._git_text(
                project_root, "show", "--no-patch", "--format=%T", parent_commit_oid
            ).strip()
            if tree_oid == parent_tree:
                raise ConflictError("当前内容与最近一个版本相同，没有需要保存的变更")
        identity_email = f"{project_id}@{_IDENTITY_DOMAIN}"
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
            project_root,
            *arguments,
            input_data=(message.strip() or "保存版本").encode("utf-8") + b"\n",
            extra_env=git_env,
        ).strip()
        self._git(
            project_root,
            "update-ref",
            self._version_ref(version_id),
            commit_oid,
            "0" * len(commit_oid),
        )
        return self._manifest_for_commit(project_root, commit_oid)

    @staticmethod
    def _identity_name(created_by: str) -> str:
        return created_by.replace("\n", " ").replace("\r", " ") or "Workspace user"

    def _manifest_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
    ) -> CommitManifest:
        project_root = self._assert_version_ref(
            project_id, repository_identity, version_id, commit_oid
        )
        return self._manifest_for_commit(project_root, commit_oid)

    def _manifest_for_commit(self, project_root: Path, commit_oid: str) -> CommitManifest:
        tree_oid = self._git_text(
            project_root, "show", "--no-patch", "--format=%T", commit_oid
        ).strip()
        entries = self._tree_entries(project_root, commit_oid, hash_blobs=True)
        return CommitManifest(
            commit_oid=commit_oid,
            tree_oid=tree_oid,
            files=tuple(
                ProjectVersionFile(entry.path, entry.size, entry.content_hash) for entry in entries
            ),
        )

    def _tree_entries(
        self, project_root: Path, revision: str, *, hash_blobs: bool
    ) -> list[_TreeEntry]:
        try:
            payload = self._git(project_root, "ls-tree", "-r", "-z", "-l", "--full-tree", revision)
        except _GitFailure as exc:
            raise ProjectContentMissing(f"Git revision {revision} 的 tree 不存在") from exc
        entries = [
            self._parse_tree_entry(project_root, raw, hash_blob=hash_blobs)
            for raw in payload.split(b"\0")
            if raw
        ]
        return sorted(entries, key=lambda entry: entry.path)

    def _parse_tree_entry(
        self, project_root: Path, raw_entry: bytes, *, hash_blob: bool
    ) -> _TreeEntry:
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
        content_hash = ""
        if hash_blob:
            content_hash, actual_size = self._hash_blob(project_root, object_oid)
            if actual_size != size:
                raise ProjectContentMissing(f"Git object {object_oid} 的大小与 tree 不一致")
        return _TreeEntry(relative, decoded_mode, object_oid, size, content_hash)

    def _read_commit_file_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        path: str,
    ) -> bytes:
        project_root = self._assert_version_ref(
            project_id, repository_identity, version_id, commit_oid
        )
        relative = self._safe_relative(path)
        payload = self._git(
            project_root,
            "ls-tree",
            "-z",
            "-l",
            "--full-tree",
            commit_oid,
            "--",
            f":(literal){relative}",
        )
        raw_entries = [entry for entry in payload.split(b"\0") if entry]
        if len(raw_entries) != 1:
            raise ObjectNotFound("文件", relative)
        entry = self._parse_tree_entry(project_root, raw_entries[0], hash_blob=False)
        if entry.path != relative:
            raise ObjectNotFound("文件", relative)
        data = self._read_blob(project_root, entry.object_oid)
        if len(data) != entry.size:
            raise ProjectContentMissing(f"Git object {entry.object_oid} 大小不一致")
        return data

    def _diff_commits_sync(
        self,
        project_id: str,
        repository_identity: str,
        base_version_id: str,
        base_commit_oid: str,
        target_version_id: str,
        target_commit_oid: str,
    ) -> list[tuple[str, ChangeKind]]:
        base = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(
                project_id, repository_identity, base_version_id, base_commit_oid
            ).files
        }
        target = {
            entry.path: entry.content_hash
            for entry in self._manifest_sync(
                project_id, repository_identity, target_version_id, target_commit_oid
            ).files
        }
        return self._diff(base, target)

    def _restore_working_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        updated_at: datetime,
    ) -> list[ProjectFile]:
        project_root = self._assert_version_ref(
            project_id, repository_identity, version_id, commit_oid
        )
        work_tree = self._work_tree(project_root)
        staging, backup, state = self._restore_paths(project_root)
        if staging.exists() or backup.exists() or state.exists():
            raise ProjectContentIdentityMismatch(
                f"Project {project_id} restore ownership state is not clean"
            )
        staging.mkdir()
        try:
            self._export_tree(project_root, commit_oid, staging)
            self._write_restore_state(state, "prepared")
            work_tree.replace(backup)
            self._write_restore_state(state, "backup")
            staging.replace(work_tree)
            self._write_restore_state(state, "swapped")
            shutil.rmtree(backup)
            state.unlink()
        except Exception:
            self._recover_restore(project_root, project_id)
            raise
        timestamp = updated_at.timestamp()
        for path in self._working_paths(work_tree):
            os.utime(path, (timestamp, timestamp))
        return self._list_working_sync(project_id, repository_identity)

    @staticmethod
    def _restore_paths(project_root: Path) -> tuple[Path, Path, Path]:
        return (
            project_root / "restore-staging",
            project_root / "restore-backup",
            project_root / "restore.state",
        )

    def _recover_restore(self, project_root: Path, project_id: str) -> None:
        staging, backup, state = self._restore_paths(project_root)
        work_tree = self._work_tree(project_root)
        for owned in (staging, backup, state):
            if owned.is_symlink():
                raise ProjectContentIdentityMismatch(
                    f"Project {project_id} restore ownership path is a symlink"
                )
        if not state.exists():
            if backup.exists():
                raise ProjectContentIdentityMismatch(
                    f"Project {project_id} restore backup has no state"
                )
            if staging.exists():
                shutil.rmtree(staging)
            return
        if not state.is_file():
            raise ProjectContentIdentityMismatch(f"Project {project_id} restore state is invalid")
        phase = state.read_text(encoding="ascii").strip()
        if phase == "prepared" and work_tree.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
            state.unlink()
            return
        if phase in {"prepared", "backup"}:
            if not work_tree.exists() and staging.is_dir() and backup.is_dir():
                staging.replace(work_tree)
            if work_tree.is_dir() and backup.is_dir():
                phase = "swapped"
        if phase == "swapped" and work_tree.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)
            state.unlink(missing_ok=True)
            return
        raise ProjectContentIdentityMismatch(
            f"Project {project_id} restore state cannot be recovered"
        )

    @staticmethod
    def _write_restore_state(state: Path, phase: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="restore-state-", suffix=".tmp", dir=state.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(phase + "\n")
            os.replace(temporary, state)
        finally:
            temporary.unlink(missing_ok=True)

    def _fork_commit_sync(
        self,
        source_project_id: str,
        source_repository_identity: str,
        source_version_id: str,
        source_commit_oid: str,
        target_project_id: str,
        target_repository_identity: str,
        version_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
        expected_source_tree_oid: str,
        expected_source_file_count: int,
        expected_source_total_size: int,
    ) -> CommitManifest:
        source_root = self._assert_version_ref(
            source_project_id,
            source_repository_identity,
            source_version_id,
            source_commit_oid,
        )
        self._initialize_sync(target_project_id, target_repository_identity)
        target_root = self._require_repository(target_project_id, target_repository_identity)
        target_work = self._work_tree(target_root)
        if any(target_work.iterdir()):
            raise ConflictError(f"目标 Project {target_project_id} Working State 不是空的")
        self._export_tree(
            source_root,
            source_commit_oid,
            target_work,
            expected_tree_oid=expected_source_tree_oid,
            expected_file_count=expected_source_file_count,
            expected_total_size=expected_source_total_size,
        )
        return self._commit_working_sync(
            target_project_id,
            target_repository_identity,
            version_id,
            None,
            None,
            message,
            created_by,
            created_at,
        )

    def _export_sync(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        destination: Path,
        expected_tree_oid: str | None,
        expected_file_count: int | None,
        expected_total_size: int | None,
    ) -> CommitManifest:
        if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
            raise ValidationFailed("Project Version 只能导出到调用方指定的现有空目录")
        project_root = self._assert_version_ref(
            project_id, repository_identity, version_id, commit_oid
        )
        return self._export_tree(
            project_root,
            commit_oid,
            destination,
            expected_tree_oid=expected_tree_oid,
            expected_file_count=expected_file_count,
            expected_total_size=expected_total_size,
        )

    def _export_tree(
        self,
        project_root: Path,
        commit_oid: str,
        destination: Path,
        *,
        expected_tree_oid: str | None = None,
        expected_file_count: int | None = None,
        expected_total_size: int | None = None,
    ) -> CommitManifest:
        tree_oid = self._git_text(
            project_root, "show", "--no-patch", "--format=%T", commit_oid
        ).strip()
        entries = self._tree_entries(project_root, commit_oid, hash_blobs=False)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-workspace107-", dir=destination.parent)
        )
        files: list[ProjectVersionFile] = []
        try:
            for entry in entries:
                target = temporary.joinpath(*PurePosixPath(entry.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                content_hash, actual_size = self._write_blob(project_root, entry.object_oid, target)
                if actual_size != entry.size:
                    raise ProjectContentMissing(
                        f"Git object {entry.object_oid} 的大小与 tree 不一致"
                    )
                target.chmod(0o755 if entry.mode == "100755" else 0o644)
                files.append(ProjectVersionFile(entry.path, actual_size, content_hash))
            if (
                (expected_tree_oid is not None and tree_oid != expected_tree_oid)
                or (expected_file_count is not None and len(files) != expected_file_count)
                or (
                    expected_total_size is not None
                    and sum(entry.size for entry in files) != expected_total_size
                )
            ):
                raise ProjectContentIdentityMismatch(
                    "Project Version Git export 与持久化 evidence 不一致"
                )
            destination.rmdir()
            try:
                os.replace(temporary, destination)
            except Exception:
                destination.mkdir(exist_ok=True)
                raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        return CommitManifest(commit_oid=commit_oid, tree_oid=tree_oid, files=tuple(files))

    def _read_blob(self, project_root: Path, object_oid: str) -> bytes:
        try:
            return self._git(project_root, "cat-file", "blob", object_oid)
        except _GitFailure as exc:
            raise ProjectContentMissing(f"Git object {object_oid} 不存在") from exc

    def _hash_blob(self, project_root: Path, object_oid: str) -> tuple[str, int]:
        return self._stream_hash_blob(project_root, object_oid, None)

    def _write_blob(self, project_root: Path, object_oid: str, target: Path) -> tuple[str, int]:
        with target.open("wb") as sink:
            return self._stream_hash_blob(project_root, object_oid, sink)

    def _stream_hash_blob(
        self, project_root: Path, object_oid: str, sink: BinaryIO | None
    ) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        try:
            process = subprocess.Popen(
                [
                    "git",
                    f"--git-dir={self._git_directory(project_root)}",
                    f"--work-tree={self._work_tree(project_root)}",
                    "cat-file",
                    "blob",
                    object_oid,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self._git_env(),
            )
        except FileNotFoundError as exc:
            raise _GitFailure("Git executable is unavailable") from exc
        assert process.stdout is not None
        try:
            while chunk := process.stdout.read(1024 * 1024):
                if sink is not None:
                    sink.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            return_code = process.wait(timeout=_GIT_TIMEOUT_SECONDS)
        except Exception:
            process.kill()
            process.wait()
            raise
        finally:
            process.stdout.close()
        if return_code != 0:
            raise _GitFailure("Git command failed: cat-file")
        return digest.hexdigest(), size

    def _try_ref(self, project_root: Path, reference: str) -> str | None:
        try:
            return self._git_text(project_root, "rev-parse", "--verify", reference).strip()
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

    def _safe_target(self, work_tree: Path, path: str, *, allow_missing: bool = False) -> Path:
        relative = self._safe_relative(path)
        target = work_tree.joinpath(*PurePosixPath(relative).parts)
        current = work_tree
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    raise ValidationFailed(f"Project 路径 {path!r} 穿过符号链接")
            elif not allow_missing:
                break
        return target

    @staticmethod
    def _diff(left: dict[str, str], right: dict[str, str]) -> list[tuple[str, ChangeKind]]:
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
        project_root: Path,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> str:
        return self._git(
            project_root,
            *arguments,
            input_data=input_data,
            extra_env=extra_env,
        ).decode("utf-8")

    def _git(
        self,
        project_root: Path,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> bytes:
        return self._run_git(
            f"--git-dir={self._git_directory(project_root)}",
            f"--work-tree={self._work_tree(project_root)}",
            *arguments,
            input_data=input_data,
            extra_env=extra_env,
        )

    def _run_git(
        self,
        *arguments: str,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> bytes:
        try:
            result = subprocess.run(
                ["git", *arguments],
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
            command = next((item for item in arguments if not item.startswith("--")), "unknown")
            raise _GitFailure(f"Git command failed: {command}")
        return result.stdout

    @staticmethod
    def _git_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
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
