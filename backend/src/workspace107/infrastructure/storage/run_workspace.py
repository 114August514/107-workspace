"""POSIX 文件系统上的可恢复 Run workspace。

该组件只拥有 Run 目录选择、prepared identity、路径安全和最小目录布局。
Project Version 内容由注入的 ``ProjectVersionExporter`` 导出；调度、Run 状态和
Input Binding 均不属于这里。
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from ...domain.ports.run_workspace import (
    RunWorkspace,
    RunWorkspaceConflict,
    RunWorkspaceIdentity,
    UnsafeRunWorkspacePath,
)
from ...domain.ports.version_control import (
    ProjectVersionExporter,
    ProjectVersionExportEvidence,
    ProjectVersionExportFile,
)

_DIRECTORY_MODE = 0o750
_CONTROL_DIRECTORY_MODE = 0o700
_LOG_MODE = 0o640
_MARKER_MODE = 0o440
_LOCK_MODE = 0o600
_MARKER_NAME = ".workspace-identity.json"
_STAGING_NAME = ".work-staging"
_MARKER_SCHEMA_VERSION = 1
_CLAIM_SCHEMA_VERSION = 1
_HASH_CHUNK_BYTES = 1024 * 1024
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_MARKER_TEMP_NAME = re.compile(rf"\A\.{re.escape(_MARKER_NAME)}\.[0-9a-f]{{32}}\.tmp\Z")
_StateAction = Literal["prepared", "export", "finalize"]


class PosixRunWorkspace:
    """在 Worker 与计算节点共同挂载的绝对 POSIX 根上准备 Run。"""

    def __init__(self, root: Path, exporter: ProjectVersionExporter) -> None:
        if os.name != "posix":
            raise UnsafeRunWorkspacePath("Run workspace requires a POSIX filesystem")
        if not root.is_absolute():
            raise UnsafeRunWorkspacePath("Run workspace root must be absolute")
        if root.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace root cannot be a symbolic link")
        try:
            canonical_root = root.resolve(strict=True)
        except (FileNotFoundError, RuntimeError) as exc:
            raise UnsafeRunWorkspacePath(
                "Run workspace root must be an existing directory"
            ) from exc

        self._owner_uid = os.geteuid()
        self._owner_gid = os.getegid()
        self._validate_storage_root(canonical_root)
        self._root = canonical_root
        self._exporter = exporter

        self._runs = canonical_root / "runs"
        self._locks = self._runs / ".locks"
        self._claims = self._runs / ".claims"
        self._ensure_owned_directory(self._runs, _DIRECTORY_MODE, label="runs")
        self._ensure_owned_directory(self._locks, _CONTROL_DIRECTORY_MODE, label="locks")
        self._ensure_owned_directory(self._claims, _CONTROL_DIRECTORY_MODE, label="claims")

    def paths_for(self, run_id: str) -> RunWorkspace:
        self._validate_identifier("run_id", run_id)
        root = self._runs / run_id
        return RunWorkspace(
            root=root,
            work=root / "work",
            inputs=root / "inputs",
            logs=root / "logs",
            artifact_staging=root / "artifacts",
            identity_marker=root / _MARKER_NAME,
        )

    async def prepare(
        self,
        identity: RunWorkspaceIdentity,
        *,
        inputs: tuple[()] = (),
    ) -> RunWorkspace:
        """准备新 workspace，或恢复完全相同 identity 的中断状态。"""
        if inputs:
            raise ValueError("M1 Run workspace only accepts explicit empty inputs")
        self._validate_identity(identity)
        workspace = self.paths_for(identity.run_id)
        lock_descriptor = await asyncio.to_thread(self._acquire_run_lock, identity.run_id)
        try:
            action, evidence = await asyncio.to_thread(
                self._inspect_or_initialize, workspace, identity
            )
            if action == "prepared":
                return workspace
            if action == "finalize":
                assert evidence is not None
                await asyncio.to_thread(self._finish_finalizing, workspace, identity, evidence)
                return workspace
            return await self._export_and_prepare(workspace, identity)
        finally:
            await asyncio.to_thread(self._release_run_lock, lock_descriptor)

    def _inspect_or_initialize(
        self, workspace: RunWorkspace, identity: RunWorkspaceIdentity
    ) -> tuple[_StateAction, ProjectVersionExportEvidence | None]:
        root_exists = os.path.lexists(workspace.root)
        claim_path = self._claim_path(identity.run_id)
        claim_exists = os.path.lexists(claim_path)

        if root_exists and workspace.root.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace root is a symbolic link")
        if root_exists and not claim_exists:
            raise RunWorkspaceConflict("Existing Run directory has no ownership claim")
        if claim_exists:
            self._require_same_identity(self._read_claim(claim_path), identity)
        else:
            self._install_claim(claim_path, identity)

        if not root_exists:
            workspace.root.mkdir(mode=_DIRECTORY_MODE)
            workspace.root.chmod(_DIRECTORY_MODE)
            self._fsync_directory(self._runs)
            self._complete_initial_layout(workspace)
            self._write_marker(workspace.identity_marker, self._marker(identity, state="preparing"))
            return "export", None

        self._validate_workspace_root(workspace.root)
        self._remove_marker_temporaries(workspace.root)
        if not os.path.lexists(workspace.identity_marker):
            self._complete_initial_layout(workspace)
            self._write_marker(workspace.identity_marker, self._marker(identity, state="preparing"))
            return "export", None

        marker = self._read_marker(workspace.identity_marker)
        self._require_same_identity(marker, identity)
        state = marker.get("state")
        if state == "prepared":
            self._validate_prepared_layout(workspace)
            return "prepared", None
        if state == "preparing":
            self._validate_preparing_layout(workspace)
            return "export", None
        if state == "exporting":
            self._validate_staging_marker(marker)
            self._validate_exporting_layout(workspace)
            self._remove_recorded_staging(workspace)
            self._write_marker(workspace.identity_marker, self._marker(identity, state="preparing"))
            return "export", None
        if state == "finalizing":
            self._validate_staging_marker(marker)
            evidence = self._evidence_from_marker(marker)
            self._validate_finalizing_layout(workspace)
            return "finalize", evidence
        raise RunWorkspaceConflict(f"Run {identity.run_id} has unknown workspace marker state")

    def _complete_initial_layout(self, workspace: RunWorkspace) -> None:
        allowed = {"inputs", "logs", "artifacts", _MARKER_NAME}
        self._reject_unknown_entries(workspace.root, allowed)
        for directory, label in (
            (workspace.inputs, "inputs"),
            (workspace.logs, "logs"),
            (workspace.artifact_staging, "artifact staging"),
        ):
            self._ensure_owned_directory(directory, _DIRECTORY_MODE, label=label)
        for log, label in ((workspace.stdout, "stdout"), (workspace.stderr, "stderr")):
            self._ensure_owned_file(log, _LOG_MODE, label=label)
        self._fsync_directory(workspace.root)

    async def _export_and_prepare(
        self, workspace: RunWorkspace, identity: RunWorkspaceIdentity
    ) -> RunWorkspace:
        exporting = self._marker(identity, state="exporting")
        exporting["staging"] = _STAGING_NAME
        await asyncio.to_thread(self._write_marker, workspace.identity_marker, exporting)
        staging = workspace.root / _STAGING_NAME
        await asyncio.to_thread(self._create_staging, staging, workspace.root)
        try:
            evidence = await self._exporter.export(
                project_version_id=identity.project_version_id,
                expected_commit_oid=identity.commit_oid,
                target=staging,
            )
            await asyncio.to_thread(self._prepare_finalizing, staging, identity, evidence)
            finalizing = self._marker(identity, state="finalizing", evidence=evidence)
            finalizing["staging"] = _STAGING_NAME
            await asyncio.to_thread(self._write_marker, workspace.identity_marker, finalizing)
            await asyncio.to_thread(self._finish_finalizing, workspace, identity, evidence)
            return workspace
        except Exception:
            await asyncio.to_thread(self._recover_failed_export, workspace, identity)
            raise

    def _prepare_finalizing(
        self,
        staging: Path,
        identity: RunWorkspaceIdentity,
        evidence: ProjectVersionExportEvidence,
    ) -> None:
        self._validate_evidence(staging, identity, evidence)
        self._fsync_tree(staging)

    def _finish_finalizing(
        self,
        workspace: RunWorkspace,
        identity: RunWorkspaceIdentity,
        evidence: ProjectVersionExportEvidence,
    ) -> None:
        staging = workspace.root / _STAGING_NAME
        staging_exists = os.path.lexists(staging)
        work_exists = os.path.lexists(workspace.work)
        if staging_exists and work_exists:
            raise RunWorkspaceConflict("Finalizing Run has both staging and work directories")
        if staging_exists:
            self._validate_owned_path(
                staging, expected_mode=_DIRECTORY_MODE, kind="directory", label="work staging"
            )
            self._validate_evidence(staging, identity, evidence)
            staging.rename(workspace.work)
            self._fsync_directory(workspace.root)
        elif work_exists:
            self._validate_owned_path(
                workspace.work,
                expected_mode=_DIRECTORY_MODE,
                kind="directory",
                label="work",
            )
            self._validate_evidence(workspace.work, identity, evidence)
        else:
            raise RunWorkspaceConflict("Finalizing Run has neither staging nor work directory")

        self._write_marker(
            workspace.identity_marker,
            self._marker(identity, state="prepared", evidence=evidence),
        )
        self._validate_prepared_layout(workspace)

    def _recover_failed_export(
        self, workspace: RunWorkspace, identity: RunWorkspaceIdentity
    ) -> None:
        marker = self._read_marker(workspace.identity_marker)
        self._require_same_identity(marker, identity)
        if marker.get("state") not in {"exporting", "finalizing"}:
            return
        self._validate_staging_marker(marker)
        staging = workspace.root / _STAGING_NAME
        if os.path.lexists(staging):
            self._remove_recorded_staging(workspace)
        if not os.path.lexists(workspace.work):
            self._write_marker(workspace.identity_marker, self._marker(identity, state="preparing"))

    def _create_staging(self, staging: Path, workspace_root: Path) -> None:
        if os.path.lexists(staging):
            raise RunWorkspaceConflict("Recorded work staging already exists")
        staging.mkdir(mode=_DIRECTORY_MODE)
        staging.chmod(_DIRECTORY_MODE)
        self._fsync_directory(workspace_root)

    def _remove_recorded_staging(self, workspace: RunWorkspace) -> None:
        staging = workspace.root / _STAGING_NAME
        self._validate_owned_path(
            staging, expected_mode=_DIRECTORY_MODE, kind="directory", label="work staging"
        )
        shutil.rmtree(staging)
        self._fsync_directory(workspace.root)

    def _validate_preparing_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        self._reject_unknown_entries(workspace.root, {"inputs", "logs", "artifacts", _MARKER_NAME})

    def _validate_exporting_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        self._reject_unknown_entries(
            workspace.root,
            {"inputs", "logs", "artifacts", _MARKER_NAME, _STAGING_NAME},
        )
        staging = workspace.root / _STAGING_NAME
        if os.path.lexists(staging):
            self._validate_owned_path(
                staging, expected_mode=_DIRECTORY_MODE, kind="directory", label="work staging"
            )

    def _validate_finalizing_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        self._reject_unknown_entries(
            workspace.root,
            {"inputs", "logs", "artifacts", "work", _MARKER_NAME, _STAGING_NAME},
        )
        staging = workspace.root / _STAGING_NAME
        if os.path.lexists(staging):
            self._validate_owned_path(
                staging, expected_mode=_DIRECTORY_MODE, kind="directory", label="work staging"
            )
        if os.path.lexists(workspace.work):
            self._validate_owned_path(
                workspace.work,
                expected_mode=_DIRECTORY_MODE,
                kind="directory",
                label="work",
            )

    def _validate_prepared_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        self._reject_unknown_entries(
            workspace.root, {"inputs", "logs", "artifacts", "work", _MARKER_NAME}
        )
        self._validate_owned_path(
            workspace.work,
            expected_mode=_DIRECTORY_MODE,
            kind="directory",
            label="work",
        )
        for root in (workspace.work, workspace.inputs, workspace.artifact_staging):
            self._validate_symlink_escapes(root)

    def _validate_common_layout(self, workspace: RunWorkspace) -> None:
        self._validate_workspace_root(workspace.root)
        for path, label in (
            (workspace.inputs, "inputs"),
            (workspace.logs, "logs"),
            (workspace.artifact_staging, "artifact staging"),
        ):
            self._validate_owned_path(
                path, expected_mode=_DIRECTORY_MODE, kind="directory", label=label
            )
        for path, label in ((workspace.stdout, "stdout"), (workspace.stderr, "stderr")):
            self._validate_owned_path(path, expected_mode=_LOG_MODE, kind="file", label=label)
        self._validate_owned_path(
            workspace.identity_marker,
            expected_mode=_MARKER_MODE,
            kind="file",
            label="identity marker",
        )

    def _validate_evidence(
        self,
        root: Path,
        identity: RunWorkspaceIdentity,
        evidence: ProjectVersionExportEvidence,
    ) -> None:
        if evidence.commit_oid != identity.commit_oid:
            raise RunWorkspaceConflict(
                "Project Version exporter returned a commit different from prepared identity"
            )
        if not _OID.fullmatch(evidence.tree_oid):
            raise RunWorkspaceConflict("Project Version exporter returned an invalid tree OID")
        paths = [entry.path for entry in evidence.manifest]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise RunWorkspaceConflict(
                "Project Version export manifest must be unique and path-sorted"
            )
        for entry in evidence.manifest:
            self._validate_manifest_entry(entry)
        self._reject_export_symlinks(root)
        actual = tuple(self._manifest_from_directory(root))
        if actual != evidence.manifest:
            raise RunWorkspaceConflict(
                "Project Version export evidence does not match exported bytes"
            )

    def _manifest_from_directory(self, root: Path) -> list[ProjectVersionExportFile]:
        manifest: list[ProjectVersionExportFile] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            mode = path.lstat().st_mode
            if mode & stat.S_IWOTH:
                raise UnsafeRunWorkspacePath(
                    f"Exported path is world-writable: {path.relative_to(root).as_posix()}"
                )
            if not path.is_file():
                continue
            size, content_hash = self._hash_file(path)
            manifest.append(
                ProjectVersionExportFile(
                    path=path.relative_to(root).as_posix(),
                    size=size,
                    content_hash=content_hash,
                )
            )
        return manifest

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(_HASH_CHUNK_BYTES):
                size += len(chunk)
                digest.update(chunk)
        return size, digest.hexdigest()

    @staticmethod
    def _reject_export_symlinks(root: Path) -> None:
        for path in root.rglob("*"):
            if path.is_symlink():
                raise UnsafeRunWorkspacePath(
                    f"M1 Project Version exports cannot contain symbolic links: {path}"
                )

    @staticmethod
    def _validate_symlink_escapes(root: Path) -> None:
        for path in root.rglob("*"):
            if not path.is_symlink():
                continue
            try:
                resolved = path.resolve(strict=True)
            except (FileNotFoundError, RuntimeError) as exc:
                raise UnsafeRunWorkspacePath(
                    f"Unsafe symbolic link in Run workspace: {path}"
                ) from exc
            if not resolved.is_relative_to(root):
                raise UnsafeRunWorkspacePath(f"Symbolic link escapes Run workspace: {path}")

    def _acquire_run_lock(self, run_id: str) -> int:
        import fcntl

        path = self._locks / f"{run_id}.lock"
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, _LOCK_MODE)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._validate_descriptor(
                descriptor, expected_mode=_LOCK_MODE, label="Run workspace lock"
            )
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @staticmethod
    def _release_run_lock(descriptor: int) -> None:
        import fcntl

        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def _install_claim(self, path: Path, identity: RunWorkspaceIdentity) -> None:
        marker = {
            "schema_version": _CLAIM_SCHEMA_VERSION,
            "run_id": identity.run_id,
            "snapshot_id": identity.snapshot_id,
            "project_version_id": identity.project_version_id,
            "commit_oid": identity.commit_oid,
        }
        temporary = self._claims / f".{identity.run_id}.{uuid.uuid4().hex}.claim.tmp"
        self._write_new_json_file(temporary, marker, _MARKER_MODE)
        try:
            if os.path.lexists(path):
                self._require_same_identity(self._read_claim(path), identity)
                return
            temporary.rename(path)
            self._fsync_directory(self._claims)
        finally:
            if os.path.lexists(temporary):
                temporary.unlink()

    def _read_claim(self, path: Path) -> dict[str, Any]:
        self._validate_owned_path(
            path, expected_mode=_MARKER_MODE, kind="file", label="Run ownership claim"
        )
        marker = self._read_json(path, label="Run ownership claim")
        if marker.get("schema_version") != _CLAIM_SCHEMA_VERSION:
            raise RunWorkspaceConflict("Run ownership claim has an unsupported schema")
        return marker

    def _claim_path(self, run_id: str) -> Path:
        return self._claims / f"{run_id}.json"

    def _read_marker(self, path: Path) -> dict[str, Any]:
        self._validate_owned_path(
            path, expected_mode=_MARKER_MODE, kind="file", label="identity marker"
        )
        marker = self._read_json(path, label="Run identity marker")
        if marker.get("schema_version") != _MARKER_SCHEMA_VERSION:
            raise RunWorkspaceConflict("Run identity marker has an unsupported schema")
        return marker

    def _write_marker(self, path: Path, marker: dict[str, Any]) -> None:
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        self._write_new_json_file(temporary, marker, _MARKER_MODE)
        try:
            temporary.replace(path)
            self._fsync_directory(path.parent)
        finally:
            if os.path.lexists(temporary):
                temporary.unlink()

    @staticmethod
    def _write_new_json_file(path: Path, marker: dict[str, Any], mode: int) -> None:
        data = (json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n").encode()
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(descriptor)
            raise

    @staticmethod
    def _read_json(path: Path, *, label: str) -> dict[str, Any]:
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunWorkspaceConflict(f"{label} is invalid") from exc
        if not isinstance(marker, dict):
            raise RunWorkspaceConflict(f"{label} must be a JSON object")
        return marker

    def _remove_marker_temporaries(self, root: Path) -> None:
        removed = False
        for path in root.iterdir():
            if not _MARKER_TEMP_NAME.fullmatch(path.name):
                continue
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise UnsafeRunWorkspacePath(
                    "Run workspace identity marker temporary is not a regular file"
                )
            if info.st_uid != self._owner_uid or info.st_gid != self._owner_gid:
                raise UnsafeRunWorkspacePath(
                    "Run workspace identity marker temporary ownership drifted"
                )
            mode = stat.S_IMODE(info.st_mode)
            if mode not in {0o600, _MARKER_MODE}:
                raise UnsafeRunWorkspacePath(
                    f"Run workspace identity marker temporary mode drifted: {mode:#o}"
                )
            path.unlink()
            removed = True
        if removed:
            self._fsync_directory(root)

    def _ensure_owned_directory(self, path: Path, mode: int, *, label: str) -> None:
        if os.path.lexists(path):
            self._validate_owned_path(path, expected_mode=mode, kind="directory", label=label)
            return
        path.mkdir(mode=mode)
        path.chmod(mode)
        self._fsync_directory(path.parent)
        self._validate_owned_path(path, expected_mode=mode, kind="directory", label=label)

    def _ensure_owned_file(self, path: Path, mode: int, *, label: str) -> None:
        if not os.path.lexists(path):
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                mode,
            )
            try:
                os.fchmod(descriptor, mode)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._fsync_directory(path.parent)
        self._validate_owned_path(path, expected_mode=mode, kind="file", label=label)

    def _validate_storage_root(self, path: Path) -> None:
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise UnsafeRunWorkspacePath("Run workspace root must be a directory")
        if info.st_uid != self._owner_uid or info.st_gid != self._owner_gid:
            raise UnsafeRunWorkspacePath(
                "Run workspace root ownership differs from process identity"
            )
        if stat.S_IMODE(info.st_mode) & stat.S_IWOTH:
            raise UnsafeRunWorkspacePath("Run workspace root cannot be world-writable")
        if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
            raise UnsafeRunWorkspacePath(
                "Run workspace root must be readable, writable, and searchable"
            )

    def _validate_workspace_root(self, path: Path) -> None:
        resolved = self._resolve_inside(path, self._runs, label="Run workspace")
        if resolved != path:
            raise UnsafeRunWorkspacePath("Run workspace path is not canonical")
        self._validate_owned_path(
            path, expected_mode=_DIRECTORY_MODE, kind="directory", label="workspace root"
        )

    def _validate_owned_path(
        self,
        path: Path,
        *,
        expected_mode: int,
        kind: Literal["file", "directory"],
        label: str,
    ) -> None:
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise RunWorkspaceConflict(f"Run workspace {label} is missing") from exc
        if stat.S_ISLNK(info.st_mode):
            raise UnsafeRunWorkspacePath(f"Run workspace {label} is a symbolic link")
        expected_kind = stat.S_ISREG if kind == "file" else stat.S_ISDIR
        if not expected_kind(info.st_mode):
            raise RunWorkspaceConflict(f"Run workspace {label} is not a {kind}")
        if info.st_uid != self._owner_uid or info.st_gid != self._owner_gid:
            raise UnsafeRunWorkspacePath(f"Run workspace {label} ownership drifted")
        actual_mode = stat.S_IMODE(info.st_mode)
        if actual_mode != expected_mode:
            raise UnsafeRunWorkspacePath(
                f"Run workspace {label} mode drifted: {actual_mode:#o} != {expected_mode:#o}"
            )

    def _validate_descriptor(self, descriptor: int, *, expected_mode: int, label: str) -> None:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise UnsafeRunWorkspacePath(f"{label} is not a regular file")
        if info.st_uid != self._owner_uid or info.st_gid != self._owner_gid:
            raise UnsafeRunWorkspacePath(f"{label} ownership drifted")
        if stat.S_IMODE(info.st_mode) != expected_mode:
            raise UnsafeRunWorkspacePath(f"{label} mode drifted")

    @staticmethod
    def _reject_unknown_entries(root: Path, allowed: set[str]) -> None:
        unknown = sorted(path.name for path in root.iterdir() if path.name not in allowed)
        if unknown:
            raise RunWorkspaceConflict(
                f"Run workspace has unowned root entries: {', '.join(unknown)}"
            )

    @staticmethod
    def _validate_staging_marker(marker: dict[str, Any]) -> None:
        if marker.get("staging") != _STAGING_NAME:
            raise RunWorkspaceConflict("Run marker does not own the expected staging directory")

    @staticmethod
    def _validate_manifest_entry(entry: ProjectVersionExportFile) -> None:
        PosixRunWorkspace._validate_relative_path("manifest path", entry.path)
        if entry.size < 0:
            raise RunWorkspaceConflict("Project Version export manifest has a negative file size")
        if not re.fullmatch(r"[0-9a-f]{64}", entry.content_hash):
            raise RunWorkspaceConflict(
                "Project Version export manifest has an invalid content hash"
            )

    @staticmethod
    def _validate_identity(identity: RunWorkspaceIdentity) -> None:
        PosixRunWorkspace._validate_identifier("run_id", identity.run_id)
        PosixRunWorkspace._validate_identifier("snapshot_id", identity.snapshot_id)
        PosixRunWorkspace._validate_identifier("project_version_id", identity.project_version_id)
        if not _OID.fullmatch(identity.commit_oid):
            raise UnsafeRunWorkspacePath("commit_oid must be a full lowercase Git object ID")

    @staticmethod
    def _validate_identifier(label: str, value: str) -> None:
        if (
            not value
            or "\\" in value
            or PurePosixPath(value).is_absolute()
            or len(PurePosixPath(value).parts) != 1
            or value in {".", ".."}
        ):
            raise UnsafeRunWorkspacePath(f"{label} must be one relative POSIX path segment")

    @staticmethod
    def _validate_relative_path(label: str, value: str) -> None:
        path = PurePosixPath(value)
        if not value or "\\" in value or path.is_absolute() or ".." in path.parts:
            raise UnsafeRunWorkspacePath(f"{label} must be a safe relative POSIX path")

    @staticmethod
    def _marker(
        identity: RunWorkspaceIdentity,
        *,
        state: str,
        evidence: ProjectVersionExportEvidence | None = None,
    ) -> dict[str, Any]:
        marker: dict[str, Any] = {
            "schema_version": _MARKER_SCHEMA_VERSION,
            "state": state,
            "run_id": identity.run_id,
            "snapshot_id": identity.snapshot_id,
            "project_version_id": identity.project_version_id,
            "commit_oid": identity.commit_oid,
        }
        if evidence is not None:
            marker["tree_oid"] = evidence.tree_oid
            marker["manifest"] = [
                {
                    "path": entry.path,
                    "size": entry.size,
                    "content_hash": entry.content_hash,
                }
                for entry in evidence.manifest
            ]
        return marker

    @staticmethod
    def _evidence_from_marker(marker: dict[str, Any]) -> ProjectVersionExportEvidence:
        tree_oid = marker.get("tree_oid")
        raw_manifest = marker.get("manifest")
        if not isinstance(tree_oid, str) or not isinstance(raw_manifest, list):
            raise RunWorkspaceConflict("Finalizing marker has no export evidence")
        entries: list[ProjectVersionExportFile] = []
        for raw in raw_manifest:
            if not isinstance(raw, dict):
                raise RunWorkspaceConflict("Finalizing marker manifest is invalid")
            path = raw.get("path")
            size = raw.get("size")
            content_hash = raw.get("content_hash")
            if (
                not isinstance(path, str)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or not isinstance(content_hash, str)
            ):
                raise RunWorkspaceConflict("Finalizing marker manifest entry is invalid")
            entries.append(
                ProjectVersionExportFile(path=path, size=size, content_hash=content_hash)
            )
        commit_oid = marker.get("commit_oid")
        if not isinstance(commit_oid, str):
            raise RunWorkspaceConflict("Finalizing marker commit OID is invalid")
        return ProjectVersionExportEvidence(
            commit_oid=commit_oid,
            tree_oid=tree_oid,
            manifest=tuple(entries),
        )

    @staticmethod
    def _require_same_identity(marker: dict[str, Any], identity: RunWorkspaceIdentity) -> None:
        expected = {
            "run_id": identity.run_id,
            "snapshot_id": identity.snapshot_id,
            "project_version_id": identity.project_version_id,
            "commit_oid": identity.commit_oid,
        }
        actual = {name: marker.get(name) for name in expected}
        if actual != expected:
            raise RunWorkspaceConflict(
                f"Run {identity.run_id} workspace prepared identity differs from requested identity"
            )

    @staticmethod
    def _resolve_inside(path: Path, root: Path, *, label: str) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, RuntimeError) as exc:
            raise UnsafeRunWorkspacePath(f"{label} cannot be resolved safely") from exc
        if not resolved.is_relative_to(root):
            raise UnsafeRunWorkspacePath(f"{label} escapes configured storage root")
        return resolved

    @staticmethod
    def _fsync_tree(root: Path) -> None:
        directories = [root]
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            elif path.is_dir() and not path.is_symlink():
                directories.append(path)
        for directory in reversed(directories):
            PosixRunWorkspace._fsync_directory(directory)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
