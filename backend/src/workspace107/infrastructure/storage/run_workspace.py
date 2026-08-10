"""POSIX 文件系统上的 Run workspace。

该组件只拥有 Run 目录选择、prepared identity、路径安全和最小目录布局。
Project Version 内容由注入的 ``ProjectVersionExporter`` 导出；调度、Run 状态和
Input Binding 均不属于这里。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

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
_LOG_MODE = 0o640
_MARKER_MODE = 0o440
_MARKER_NAME = ".workspace-identity.json"
_MARKER_SCHEMA_VERSION = 1
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class PosixRunWorkspace:
    """在一个可由 Worker 与计算节点共同挂载的绝对 POSIX 根上准备 Run。"""

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
        self._validate_writable_directory(canonical_root, label="Run workspace root")

        runs = canonical_root / "runs"
        if os.path.lexists(runs) and runs.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace runs directory cannot be a symbolic link")
        runs.mkdir(mode=_DIRECTORY_MODE, exist_ok=True)
        canonical_runs = runs.resolve(strict=True)
        if canonical_runs.parent != canonical_root:
            raise UnsafeRunWorkspacePath("Run workspace runs directory escapes storage root")
        self._validate_writable_directory(canonical_runs, label="Run workspace runs directory")

        self._root = canonical_root
        self._runs = canonical_runs
        self._exporter = exporter

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
        """准备新 workspace，或无副作用地恢复完全相同的 prepared identity。"""
        if inputs:
            raise ValueError("M1 Run workspace only accepts explicit empty inputs")
        self._validate_identity(identity)
        workspace = self.paths_for(identity.run_id)
        should_export = await asyncio.to_thread(self._claim_or_recover, workspace, identity)
        if not should_export:
            return workspace
        return await self._export_and_prepare(workspace, identity)

    def _claim_or_recover(self, workspace: RunWorkspace, identity: RunWorkspaceIdentity) -> bool:
        if os.path.lexists(workspace.root):
            return self._recover_existing(workspace, identity)
        try:
            workspace.root.mkdir(mode=_DIRECTORY_MODE)
        except FileExistsError:
            return self._recover_existing(workspace, identity)
        workspace.root.chmod(_DIRECTORY_MODE)
        self._create_layout(workspace)
        self._write_marker(workspace.identity_marker, self._marker(identity, state="preparing"))
        return True

    def _recover_existing(self, workspace: RunWorkspace, identity: RunWorkspaceIdentity) -> bool:
        if workspace.root.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace root is a symbolic link")
        resolved = self._resolve_inside(workspace.root, self._runs, label="Run workspace")
        if resolved != workspace.root:
            raise UnsafeRunWorkspacePath("Run workspace path is not canonical")
        marker = self._read_marker(workspace.identity_marker)
        self._require_same_identity(marker, identity)
        state = marker.get("state")
        if state == "prepared":
            self._validate_prepared_layout(workspace)
            return False
        if state == "preparing":
            self._validate_preparing_layout(workspace)
            return True
        raise RunWorkspaceConflict(f"Run {identity.run_id} has unknown workspace marker state")

    def _create_layout(self, workspace: RunWorkspace) -> None:
        for directory in (workspace.inputs, workspace.logs, workspace.artifact_staging):
            directory.mkdir(mode=_DIRECTORY_MODE)
            directory.chmod(_DIRECTORY_MODE)
        for log in (workspace.stdout, workspace.stderr):
            log.touch(mode=_LOG_MODE, exist_ok=False)
            log.chmod(_LOG_MODE)

    async def _export_and_prepare(
        self, workspace: RunWorkspace, identity: RunWorkspaceIdentity
    ) -> RunWorkspace:
        staging = await asyncio.to_thread(self._create_staging, workspace)
        try:
            evidence = await self._exporter.export(
                project_version_id=identity.project_version_id,
                expected_commit_oid=identity.commit_oid,
                target=staging,
            )
            await asyncio.to_thread(self._finalize_export, workspace, staging, identity, evidence)
            return workspace
        finally:
            await asyncio.to_thread(self._remove_staging, staging)

    @staticmethod
    def _create_staging(workspace: RunWorkspace) -> Path:
        staging = workspace.root / f".work-{uuid.uuid4().hex}.tmp"
        staging.mkdir(mode=_DIRECTORY_MODE)
        staging.chmod(_DIRECTORY_MODE)
        return staging

    def _finalize_export(
        self,
        workspace: RunWorkspace,
        staging: Path,
        identity: RunWorkspaceIdentity,
        evidence: ProjectVersionExportEvidence,
    ) -> None:
        self._validate_evidence(staging, identity, evidence)
        if os.path.lexists(workspace.work):
            raise RunWorkspaceConflict(
                f"Run {identity.run_id} work directory already exists without prepared marker"
            )
        staging.rename(workspace.work)
        self._write_marker(
            workspace.identity_marker,
            self._marker(identity, state="prepared", evidence=evidence),
        )
        self._validate_prepared_layout(workspace)

    @staticmethod
    def _remove_staging(staging: Path) -> None:
        if os.path.lexists(staging):
            shutil.rmtree(staging)

    def _validate_preparing_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        if os.path.lexists(workspace.work):
            raise RunWorkspaceConflict(
                f"Run {workspace.root.name} has work content without a prepared identity"
            )

    def _validate_prepared_layout(self, workspace: RunWorkspace) -> None:
        self._validate_common_layout(workspace)
        self._require_real_directory(workspace.work, label="work")
        for root in (workspace.work, workspace.inputs, workspace.artifact_staging):
            self._validate_symlinks_inside(root)

    def _validate_common_layout(self, workspace: RunWorkspace) -> None:
        for path, label in (
            (workspace.root, "root"),
            (workspace.inputs, "inputs"),
            (workspace.logs, "logs"),
            (workspace.artifact_staging, "artifact staging"),
        ):
            self._require_real_directory(path, label=label)
        for path, label in ((workspace.stdout, "stdout"), (workspace.stderr, "stderr")):
            if path.is_symlink() or not path.is_file():
                raise RunWorkspaceConflict(f"Run workspace {label} path is not a regular file")

    def _validate_evidence(
        self,
        staging: Path,
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

        self._validate_symlinks_inside(staging)
        actual = tuple(self._manifest_from_directory(staging))
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
            data = path.read_bytes()
            manifest.append(
                ProjectVersionExportFile(
                    path=path.relative_to(root).as_posix(),
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                )
            )
        return manifest

    def _validate_symlinks_inside(self, root: Path) -> None:
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
    def _validate_writable_directory(path: Path, *, label: str) -> None:
        if not path.is_dir():
            raise UnsafeRunWorkspacePath(f"{label} must be a directory")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & stat.S_IWOTH:
            raise UnsafeRunWorkspacePath(f"{label} cannot be world-writable")
        if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
            raise UnsafeRunWorkspacePath(f"{label} must be readable, writable, and searchable")

    @staticmethod
    def _require_real_directory(path: Path, *, label: str) -> None:
        if path.is_symlink() or not path.is_dir():
            raise RunWorkspaceConflict(f"Run workspace {label} path is not a real directory")

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
    def _write_marker(path: Path, marker: dict[str, Any]) -> None:
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        data = (json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n").encode()
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            path.chmod(_MARKER_MODE)
        finally:
            if os.path.lexists(temporary):
                temporary.unlink()

    @staticmethod
    def _read_marker(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise RunWorkspaceConflict("Existing Run directory has no safe identity marker")
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunWorkspaceConflict(
                "Existing Run directory has an invalid identity marker"
            ) from exc
        if not isinstance(marker, dict) or marker.get("schema_version") != _MARKER_SCHEMA_VERSION:
            raise RunWorkspaceConflict("Existing Run directory has an unsupported identity marker")
        return marker

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
