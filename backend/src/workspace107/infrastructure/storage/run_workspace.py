"""Single-writer POSIX Run workspace and immutable Artifact installation.

M1 has exactly one active Worker. This component therefore uses owned staging plus
same-filesystem rename without filesystem writer coordination or a general
power-loss durability protocol.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from ...domain.ports.run_workspace import (
    ArtifactRunWorkspaceInput,
    RunArtifactEvidence,
    RunWorkspace,
    RunWorkspaceConflict,
    RunWorkspaceIdentity,
    RunWorkspaceInput,
    RunWorkspaceInputFile,
    SharedResourceRunWorkspaceInput,
    UnsafeRunWorkspacePath,
)
from ...domain.ports.version_control import (
    ProjectVersionExporter,
    ProjectVersionExportEvidence,
    ProjectVersionExportFile,
)

_RUN_ROOT_MODE = 0o750
_SHARED_DIRECTORY_MODE = 0o2770
_INPUT_DIRECTORY_MODE = 0o2550
_INPUT_FILE_MODE = 0o440
_SHARED_FILE_MODE = 0o660
_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_PRIVATE_MARKER_MODE = 0o400
_MARKER_NAME = ".workspace-identity.json"
_ARTIFACT_MARKER_NAME = ".artifact-identity.json"
_RUN_MARKER_SCHEMA_VERSION = 2
_ARTIFACT_MARKER_SCHEMA_VERSION = 1
_HASH_CHUNK_BYTES = 1024 * 1024
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


@dataclass(frozen=True, slots=True)
class _OpenSource:
    descriptor: int
    is_directory: bool
    name: str


class PosixRunWorkspace:
    """Prepare workspaces for one active service Worker on one POSIX Shared FS."""

    def __init__(
        self,
        root: Path,
        exporter: ProjectVersionExporter,
        *,
        shared_gid: int,
    ) -> None:
        if os.name != "posix":
            raise UnsafeRunWorkspacePath("Run workspace requires POSIX")
        if not root.is_absolute():
            raise UnsafeRunWorkspacePath("Run workspace root must be absolute")
        if root.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace root cannot be a symbolic link")
        try:
            canonical = root.resolve(strict=True)
        except (FileNotFoundError, RuntimeError) as exc:
            raise UnsafeRunWorkspacePath("Run workspace root must exist") from exc
        if shared_gid < 0:
            raise UnsafeRunWorkspacePath("shared_gid must be a non-negative POSIX GID")

        self._owner_uid = os.geteuid()
        self._owner_gid = os.getegid()
        self._shared_gid = shared_gid
        self._validate_storage_root(canonical)
        self._root = canonical
        self._exporter = exporter
        self._blobs = canonical / "blobs"
        self._runs = canonical / "runs"
        self._run_staging = canonical / ".run-staging"
        self._artifact_store = canonical / "artifact-store"
        self._artifact_staging = self._artifact_store / ".staging"
        self._ensure_directory(self._runs, mode=_RUN_ROOT_MODE, gid=shared_gid, label="runs")
        self._ensure_directory(
            self._run_staging,
            mode=_PRIVATE_DIRECTORY_MODE,
            gid=self._owner_gid,
            label="Run staging",
        )
        self._ensure_directory(
            self._artifact_store,
            mode=_PRIVATE_DIRECTORY_MODE,
            gid=self._owner_gid,
            label="artifact store",
        )
        self._ensure_directory(
            self._artifact_staging,
            mode=_PRIVATE_DIRECTORY_MODE,
            gid=self._owner_gid,
            label="artifact staging",
        )

    def paths_for(self, run_id: str) -> RunWorkspace:
        self._validate_segment("run_id", run_id)
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
        inputs: tuple[RunWorkspaceInput, ...] = (),
    ) -> RunWorkspace:
        """Atomically install a complete workspace, or return the same prepared one."""
        self._validate_identity(identity)
        input_fingerprint = self._input_fingerprint(inputs)
        workspace = self.paths_for(identity.run_id)
        if self._path_exists(workspace.root):
            self._validate_prepared_workspace(workspace, identity, inputs)
            return workspace

        self._cleanup_run_temporaries(identity, input_fingerprint)
        temporary = self._run_staging / f".{identity.run_id}.{uuid.uuid4().hex}.tmp"
        temporary.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
        temporary.chmod(_PRIVATE_DIRECTORY_MODE)
        try:
            temp_workspace = self._workspace_at(temporary)
            self._write_json_marker(
                temp_workspace.identity_marker,
                self._run_marker(
                    identity,
                    state="exporting",
                    input_fingerprint=input_fingerprint,
                ),
                mode=_PRIVATE_FILE_MODE,
            )
            self._create_shared_layout(temp_workspace)
            evidence = await self._exporter.export(
                project_version_id=identity.project_version_id,
                expected_commit_oid=identity.commit_oid,
                target=temp_workspace.work,
            )
            self._validate_export(temp_workspace.work, identity, evidence)
            self._normalize_work_permissions(temp_workspace.work)
            self._materialize_inputs(temp_workspace.inputs, inputs)
            self._normalize_input_permissions(temp_workspace.inputs)
            input_evidence = self._manifest_from_directory(temp_workspace.inputs)
            self._write_json_marker(
                temp_workspace.identity_marker,
                self._run_marker(
                    identity,
                    state="prepared",
                    evidence=evidence,
                    input_fingerprint=input_fingerprint,
                    input_evidence=input_evidence,
                ),
                mode=_PRIVATE_MARKER_MODE,
            )
            os.chown(temporary, -1, self._shared_gid)
            temporary.chmod(_RUN_ROOT_MODE)
            temporary.rename(workspace.root)
        except BaseException:
            # The owned temp intentionally remains evidence of an interrupted operation.
            raise

        self._validate_prepared_workspace(workspace, identity, inputs)
        return workspace

    async def collect_artifact(
        self,
        identity: RunWorkspaceIdentity,
        *,
        artifact_id: str,
        source_path: str,
    ) -> RunArtifactEvidence | None:
        """Install one immutable Artifact under the single-active-Worker contract."""
        self._validate_identity(identity)
        self._validate_segment("artifact_id", artifact_id)
        self._validate_relative_path("artifact source", source_path, allow_dot=False)
        workspace = self.paths_for(identity.run_id)
        self._validate_prepared_workspace(workspace, identity)
        installed = self._artifact_store / artifact_id
        staging = self._artifact_staging / artifact_id

        recovered = self._recover_finalizing(
            staging=staging,
            installed=installed,
            identity=identity,
            artifact_id=artifact_id,
            source_path=source_path,
        )
        if recovered is not None:
            return recovered

        if self._path_exists(staging):
            self._validate_private_tree_root(staging, label="Artifact copying staging")
            marker_path = staging / _ARTIFACT_MARKER_NAME
            if not self._path_exists(marker_path):
                shutil.rmtree(staging)
            else:
                marker = self._read_artifact_marker(staging)
                self._require_artifact_identity(marker, identity, artifact_id, source_path)
                if marker.get("state") != "copying":
                    raise RunWorkspaceConflict("Artifact staging has an invalid state")
                shutil.rmtree(staging)

        source = self._open_artifact_source(workspace.work, source_path)
        if source is None:
            return None
        try:
            staging.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
            staging.chmod(_PRIVATE_DIRECTORY_MODE)
            self._write_json_marker(
                staging / _ARTIFACT_MARKER_NAME,
                self._artifact_marker(identity, artifact_id, source_path, state="copying"),
                mode=_PRIVATE_FILE_MODE,
            )
            content = staging / "content"
            content.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
            content.chmod(_PRIVATE_DIRECTORY_MODE)
            self._copy_source(source, content)
            evidence = self._evidence_from_directory(content)
            self._write_json_marker(
                staging / _ARTIFACT_MARKER_NAME,
                self._artifact_marker(
                    identity,
                    artifact_id,
                    source_path,
                    state="finalizing",
                    evidence=evidence,
                ),
                mode=_PRIVATE_MARKER_MODE,
            )
        finally:
            os.close(source.descriptor)

        staging.rename(installed)
        self._write_json_marker(
            installed / _ARTIFACT_MARKER_NAME,
            self._artifact_marker(
                identity,
                artifact_id,
                source_path,
                state="installed",
                evidence=evidence,
            ),
            mode=_PRIVATE_MARKER_MODE,
        )
        return evidence

    def _recover_finalizing(
        self,
        *,
        staging: Path,
        installed: Path,
        identity: RunWorkspaceIdentity,
        artifact_id: str,
        source_path: str,
    ) -> RunArtifactEvidence | None:
        if os.path.lexists(installed):
            marker = self._read_artifact_marker(installed)
            self._require_artifact_identity(marker, identity, artifact_id, source_path)
            if marker.get("state") == "installed":
                return self._require_durable_artifact_evidence(installed, marker)
            if marker.get("state") != "finalizing":
                raise RunWorkspaceConflict("Installed Artifact has an invalid state")
            evidence = self._require_durable_artifact_evidence(installed, marker)
            if os.path.lexists(staging):
                raise RunWorkspaceConflict(
                    "Finalizing Artifact has both installed and staging directories"
                )
            self._write_json_marker(
                installed / _ARTIFACT_MARKER_NAME,
                self._artifact_marker(
                    identity,
                    artifact_id,
                    source_path,
                    state="installed",
                    evidence=evidence,
                ),
                mode=_PRIVATE_MARKER_MODE,
            )
            return evidence

        if not os.path.lexists(staging):
            return None
        if not os.path.lexists(staging / _ARTIFACT_MARKER_NAME):
            return None
        marker = self._read_artifact_marker(staging)
        self._require_artifact_identity(marker, identity, artifact_id, source_path)
        if marker.get("state") != "finalizing":
            return None
        evidence = self._require_durable_artifact_evidence(staging, marker)
        staging.rename(installed)
        self._write_json_marker(
            installed / _ARTIFACT_MARKER_NAME,
            self._artifact_marker(
                identity,
                artifact_id,
                source_path,
                state="installed",
                evidence=evidence,
            ),
            mode=_PRIVATE_MARKER_MODE,
        )
        return evidence

    def _require_durable_artifact_evidence(
        self, root: Path, marker: dict[str, Any]
    ) -> RunArtifactEvidence:
        self._validate_private_tree_root(root, label="Artifact")
        evidence = self._artifact_evidence_from_marker(marker)
        actual = self._evidence_from_directory(root / "content")
        if actual != evidence:
            raise RunWorkspaceConflict("Artifact content differs from durable evidence")
        return evidence

    def _cleanup_run_temporaries(
        self, identity: RunWorkspaceIdentity, input_fingerprint: str
    ) -> None:
        pattern = re.compile(rf"\A\.{re.escape(identity.run_id)}\.[0-9a-f]{{32}}\.tmp\Z")
        for candidate in self._run_staging.iterdir():
            if not pattern.fullmatch(candidate.name):
                continue
            info = candidate.lstat()
            private_half_init = (
                stat.S_ISDIR(info.st_mode)
                and info.st_uid == self._owner_uid
                and info.st_gid == self._owner_gid
                and stat.S_IMODE(info.st_mode) == _PRIVATE_DIRECTORY_MODE
            )
            ready_to_install = (
                stat.S_ISDIR(info.st_mode)
                and info.st_uid == self._owner_uid
                and info.st_gid == self._shared_gid
                and stat.S_IMODE(info.st_mode) == _RUN_ROOT_MODE
            )
            if not (private_half_init or ready_to_install):
                raise RunWorkspaceConflict("Run staging ownership or mode drifted")
            marker_path = candidate / _MARKER_NAME
            if not self._path_exists(marker_path):
                if not private_half_init:
                    raise RunWorkspaceConflict("Run staging marker is missing")
                shutil.rmtree(candidate)
                continue
            marker = self._read_run_marker(marker_path, label="Run staging marker")
            self._require_same_identity(marker, identity)
            self._require_input_fingerprint(marker, input_fingerprint)
            if marker.get("state") not in {"exporting", "prepared"}:
                raise RunWorkspaceConflict("Run staging has an invalid state")
            shutil.rmtree(candidate)

    def _create_shared_layout(self, workspace: RunWorkspace) -> None:
        self._create_directory(workspace.work, _SHARED_DIRECTORY_MODE, self._shared_gid)
        self._create_directory(workspace.inputs, _PRIVATE_DIRECTORY_MODE, self._owner_gid)
        self._create_directory(workspace.logs, _SHARED_DIRECTORY_MODE, self._shared_gid)
        self._create_directory(workspace.artifact_staging, _SHARED_DIRECTORY_MODE, self._shared_gid)
        self._create_file(workspace.stdout, _SHARED_FILE_MODE, self._shared_gid)
        self._create_file(workspace.stderr, _SHARED_FILE_MODE, self._shared_gid)

    def _validate_prepared_workspace(
        self,
        workspace: RunWorkspace,
        identity: RunWorkspaceIdentity,
        inputs: tuple[RunWorkspaceInput, ...] | None = None,
    ) -> None:
        if workspace.root.is_symlink():
            raise UnsafeRunWorkspacePath("Run workspace root is a symbolic link")
        self._validate_path(
            workspace.root,
            kind="directory",
            mode=_RUN_ROOT_MODE,
            uid=self._owner_uid,
            gid=self._shared_gid,
            label="workspace root",
        )
        marker = self._read_run_marker(workspace.identity_marker, label="Run identity marker")
        self._require_same_identity(marker, identity)
        if marker.get("state") != "prepared":
            raise RunWorkspaceConflict("Run workspace is not prepared")
        self._export_evidence_from_marker(marker)
        if inputs is not None:
            self._require_input_fingerprint(marker, self._input_fingerprint(inputs))
        expected_input_evidence = self._input_evidence_from_marker(marker)
        actual_input_evidence = self._manifest_from_directory(workspace.inputs)
        if actual_input_evidence != expected_input_evidence:
            raise RunWorkspaceConflict("Run input content differs from prepared evidence")
        expected = {
            "work",
            "inputs",
            "logs",
            "artifacts",
            _MARKER_NAME,
        }
        actual = {entry.name for entry in workspace.root.iterdir()}
        if actual != expected and actual != expected | {"job.sh"}:
            raise RunWorkspaceConflict("Run workspace root layout drifted")
        for path, mode, label in (
            (workspace.work, _SHARED_DIRECTORY_MODE, "work"),
            (workspace.inputs, _INPUT_DIRECTORY_MODE, "inputs"),
            (workspace.logs, _SHARED_DIRECTORY_MODE, "logs"),
            (workspace.artifact_staging, _SHARED_DIRECTORY_MODE, "artifact staging"),
        ):
            self._validate_path(
                path,
                kind="directory",
                mode=mode,
                uid=self._owner_uid,
                gid=self._shared_gid,
                label=label,
            )
        self._validate_input_permissions(workspace.inputs)
        for path, label in ((workspace.stdout, "stdout"), (workspace.stderr, "stderr")):
            self._validate_path(
                path,
                kind="file",
                mode=_SHARED_FILE_MODE,
                uid=self._owner_uid,
                gid=self._shared_gid,
                label=label,
            )
        job_script = workspace.root / "job.sh"
        if self._path_exists(job_script):
            self._validate_path(
                job_script,
                kind="file",
                mode=_SHARED_FILE_MODE,
                uid=self._owner_uid,
                gid=self._shared_gid,
                label="job script",
            )
        self._validate_path(
            workspace.identity_marker,
            kind="file",
            mode=_PRIVATE_MARKER_MODE,
            uid=self._owner_uid,
            gid=None,
            label="identity marker",
        )

    def _validate_export(
        self,
        work: Path,
        identity: RunWorkspaceIdentity,
        evidence: ProjectVersionExportEvidence,
    ) -> None:
        if evidence.commit_oid != identity.commit_oid or not _OID.fullmatch(evidence.commit_oid):
            raise RunWorkspaceConflict("Exporter returned a different commit identity")
        if not _OID.fullmatch(evidence.tree_oid):
            raise RunWorkspaceConflict("Exporter returned an invalid tree identity")
        actual = self._manifest_from_directory(work)
        expected = tuple(sorted(evidence.manifest, key=lambda entry: entry.path))
        if actual != expected:
            raise RunWorkspaceConflict("Exported content differs from exporter evidence")

    def _manifest_from_directory(self, root: Path) -> tuple[ProjectVersionExportFile, ...]:
        entries: list[ProjectVersionExportFile] = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise UnsafeRunWorkspacePath("Exported work cannot contain symbolic links")
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise UnsafeRunWorkspacePath("Exported work contains a special file")
            size, digest = self._hash_file(path)
            entries.append(
                ProjectVersionExportFile(path=relative.as_posix(), size=size, content_hash=digest)
            )
        return tuple(entries)

    def _normalize_work_permissions(self, root: Path) -> None:
        for path in [root, *sorted(root.rglob("*"))]:
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                mode = _SHARED_DIRECTORY_MODE
            elif stat.S_ISREG(info.st_mode):
                mode = 0o770 if stat.S_IMODE(info.st_mode) & 0o111 else _SHARED_FILE_MODE
            else:
                raise UnsafeRunWorkspacePath("Exported work contains an unsafe file type")
            os.chown(path, -1, self._shared_gid)
            path.chmod(mode)

    def _materialize_inputs(self, root: Path, inputs: tuple[RunWorkspaceInput, ...]) -> None:
        for item in inputs:
            target = self._input_access_target(root, item.access_path)
            self._ensure_input_directory(root, target)
            if isinstance(item, SharedResourceRunWorkspaceInput):
                for entry in item.files:
                    self._copy_blob_input(root, target, entry)
            elif isinstance(item, ArtifactRunWorkspaceInput):
                self._copy_artifact_input(root, target, item)
            else:
                raise RunWorkspaceConflict("Run input descriptor type is unsupported")

    def _copy_blob_input(self, root: Path, target_root: Path, entry: RunWorkspaceInputFile) -> None:
        self._validate_relative_path("input target", entry.target_path, allow_dot=False)
        target = target_root.joinpath(*PurePosixPath(entry.target_path).parts)
        self._require_input_containment(root, target)
        descriptor = self._open_blob(entry.content_hash)
        try:
            size, digest = self._hash_descriptor(descriptor)
            if size != entry.size or digest != entry.content_hash:
                raise RunWorkspaceConflict(
                    f"Shared Resource blob evidence differs for {entry.source_path}"
                )
            self._copy_input_descriptor(root, descriptor, target)
        finally:
            os.close(descriptor)

    def _copy_artifact_input(
        self, root: Path, target: Path, item: ArtifactRunWorkspaceInput
    ) -> None:
        self._validate_segment("artifact_id", item.artifact_id)
        installed = self._artifact_store / item.artifact_id
        marker = self._read_artifact_marker(installed)
        if marker.get("state") != "installed" or marker.get("artifact_id") != item.artifact_id:
            raise RunWorkspaceConflict(f"Artifact {item.artifact_id} is not canonically installed")
        evidence = self._require_durable_artifact_evidence(installed, marker)
        if evidence.content_hash != item.content_hash:
            raise RunWorkspaceConflict(f"Artifact {item.artifact_id} content identity differs")

        content = installed / "content"
        if item.source_subpath:
            self._validate_relative_path(
                "artifact input subpath", item.source_subpath, allow_dot=False
            )
            source = self._open_artifact_source(content, item.source_subpath)
        else:
            descriptor = os.open(content, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            source = _OpenSource(descriptor, True, content.name)
        if source is None:
            raise RunWorkspaceConflict(
                f"Artifact {item.artifact_id} input subpath {item.source_subpath!r} is unavailable"
            )
        try:
            if source.is_directory:
                self._walk_source(
                    source.descriptor,
                    lambda path, descriptor: self._copy_input_descriptor(
                        root, descriptor, target / path
                    ),
                )
            else:
                self._copy_input_descriptor(root, source.descriptor, target / source.name)
        finally:
            os.close(source.descriptor)

    def _open_blob(self, content_hash: str) -> int:
        if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
            raise RunWorkspaceConflict("Shared Resource blob identity is invalid")
        current = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for index, part in enumerate(("blobs", content_hash[:2], content_hash)):
                flags = os.O_RDONLY | os.O_NOFOLLOW
                if index < 2:
                    flags |= os.O_DIRECTORY
                following = os.open(part, flags, dir_fd=current)
                os.close(current)
                current = following
            if not stat.S_ISREG(os.fstat(current).st_mode):
                raise UnsafeRunWorkspacePath("Shared Resource blob is not a regular file")
            return current
        except OSError as exc:
            os.close(current)
            if exc.errno in {errno.ENOENT, errno.ELOOP, errno.ENOTDIR}:
                raise RunWorkspaceConflict(
                    f"Shared Resource blob {content_hash} is unavailable"
                ) from exc
            raise
        except BaseException:
            os.close(current)
            raise

    def _copy_input_descriptor(self, root: Path, descriptor: int, target: Path) -> None:
        self._require_input_containment(root, target)
        self._ensure_input_directory(root, target.parent)
        if os.path.lexists(target):
            raise RunWorkspaceConflict(f"Run input path collision at {target.relative_to(root)}")
        os.lseek(descriptor, 0, os.SEEK_SET)
        target_descriptor = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, _PRIVATE_FILE_MODE
        )
        try:
            os.fchmod(target_descriptor, _PRIVATE_FILE_MODE)
            while chunk := os.read(descriptor, _HASH_CHUNK_BYTES):
                view = memoryview(chunk)
                while view:
                    written = os.write(target_descriptor, view)
                    view = view[written:]
        finally:
            os.close(target_descriptor)

    def _ensure_input_directory(self, root: Path, target: Path) -> None:
        self._require_input_containment(root, target)
        relative = target.relative_to(root)
        current = root
        for part in relative.parts:
            current /= part
            if os.path.lexists(current):
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    raise UnsafeRunWorkspacePath("Run input ancestor is not a safe directory")
                continue
            current.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
            current.chmod(_PRIVATE_DIRECTORY_MODE)

    def _input_access_target(self, root: Path, access_path: str) -> Path:
        candidate = PurePosixPath(access_path)
        if (
            not access_path
            or not candidate.is_absolute()
            or "\\" in access_path
            or any(part == ".." for part in candidate.parts)
        ):
            raise UnsafeRunWorkspacePath("input access_path must be a safe absolute POSIX path")
        target = root.joinpath(*candidate.parts[1:])
        self._require_input_containment(root, target)
        return target

    @staticmethod
    def _require_input_containment(root: Path, target: Path) -> None:
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise UnsafeRunWorkspacePath("Run input path escaped its private staging root") from exc

    def _normalize_input_permissions(self, root: Path) -> None:
        paths = [*sorted(root.rglob("*"), reverse=True), root]
        for path in paths:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise UnsafeRunWorkspacePath("Run inputs cannot contain symbolic links")
            if stat.S_ISDIR(info.st_mode):
                mode = _INPUT_DIRECTORY_MODE
            elif stat.S_ISREG(info.st_mode):
                mode = _INPUT_FILE_MODE
            else:
                raise UnsafeRunWorkspacePath("Run inputs contain a special file")
            os.chown(path, -1, self._shared_gid)
            path.chmod(mode)

    def _validate_input_permissions(self, root: Path) -> None:
        for path in [root, *sorted(root.rglob("*"))]:
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                mode = _INPUT_DIRECTORY_MODE
                kind: Literal["file", "directory"] = "directory"
            elif stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                mode = _INPUT_FILE_MODE
                kind = "file"
            else:
                raise UnsafeRunWorkspacePath("Run inputs contain an unsafe file type")
            self._validate_path(
                path,
                kind=kind,
                mode=mode,
                uid=self._owner_uid,
                gid=self._shared_gid,
                label="Run input",
            )

    @staticmethod
    def _input_fingerprint(inputs: tuple[RunWorkspaceInput, ...]) -> str:
        payload: list[dict[str, Any]] = []
        for item in inputs:
            if isinstance(item, SharedResourceRunWorkspaceInput):
                payload.append(
                    {
                        "source_type": "shared_resource_version",
                        "source_id": item.version_id,
                        "access_path": item.access_path,
                        "files": [
                            {
                                "source_path": entry.source_path,
                                "target_path": entry.target_path,
                                "size": entry.size,
                                "content_hash": entry.content_hash,
                            }
                            for entry in item.files
                        ],
                    }
                )
            elif isinstance(item, ArtifactRunWorkspaceInput):
                payload.append(
                    {
                        "source_type": "artifact",
                        "source_id": item.artifact_id,
                        "access_path": item.access_path,
                        "source_subpath": item.source_subpath,
                        "content_hash": item.content_hash,
                    }
                )
            else:  # pragma: no cover - the closed port type prevents this
                raise RunWorkspaceConflict("Run input descriptor type is unsupported")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _open_artifact_source(self, work: Path, source_path: str) -> _OpenSource | None:
        parts = PurePosixPath(source_path).parts
        directory_flag = os.O_DIRECTORY
        nofollow = os.O_NOFOLLOW
        current = os.open(work, os.O_RDONLY | directory_flag | nofollow)
        try:
            for index, part in enumerate(parts):
                flags = os.O_RDONLY | os.O_NONBLOCK | nofollow
                if index < len(parts) - 1:
                    flags |= directory_flag
                following = os.open(part, flags, dir_fd=current)
                os.close(current)
                current = following
            info = os.fstat(current)
            if stat.S_ISDIR(info.st_mode):
                return _OpenSource(current, True, parts[-1])
            if stat.S_ISREG(info.st_mode):
                return _OpenSource(current, False, parts[-1])
            raise UnsafeRunWorkspacePath("Artifact source must be a regular file or directory")
        except OSError as exc:
            os.close(current)
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise UnsafeRunWorkspacePath(
                    "Artifact source contains a symbolic link or non-directory ancestor"
                ) from exc
            if exc.errno == errno.ENOENT:
                return None
            raise
        except BaseException:
            os.close(current)
            raise

    def _copy_source(self, source: _OpenSource, content: Path) -> None:
        if source.is_directory:
            self._walk_source(
                source.descriptor,
                lambda path, descriptor: self._copy_open_file(descriptor, content / path),
            )
            return
        self._copy_open_file(source.descriptor, content / source.name)

    def _walk_source(self, descriptor: int, visit: Any, prefix: Path = Path()) -> None:
        nofollow = os.O_NOFOLLOW
        for name in sorted(os.listdir(descriptor)):
            relative = prefix / name
            try:
                child = os.open(
                    name,
                    os.O_RDONLY | os.O_NONBLOCK | nofollow,
                    dir_fd=descriptor,
                )
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise UnsafeRunWorkspacePath(
                        "Artifact source contains a symbolic link"
                    ) from exc
                raise
            try:
                info = os.fstat(child)
                if stat.S_ISREG(info.st_mode):
                    visit(relative, child)
                elif stat.S_ISDIR(info.st_mode):
                    self._walk_source(child, visit, relative)
                else:
                    raise UnsafeRunWorkspacePath("Artifact source contains a special file")
            finally:
                os.close(child)

    def _copy_open_file(self, descriptor: int, target: Path) -> None:
        target.parent.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=True)
        for parent in target.parents:
            if parent == self._artifact_staging:
                break
            if parent.exists():
                parent.chmod(_PRIVATE_DIRECTORY_MODE)
        os.lseek(descriptor, 0, os.SEEK_SET)
        target_descriptor = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _PRIVATE_FILE_MODE
        )
        try:
            os.fchmod(target_descriptor, _PRIVATE_FILE_MODE)
            while chunk := os.read(descriptor, _HASH_CHUNK_BYTES):
                view = memoryview(chunk)
                while view:
                    written = os.write(target_descriptor, view)
                    view = view[written:]
        finally:
            os.close(target_descriptor)

    def _evidence_from_directory(self, content: Path) -> RunArtifactEvidence:
        self._validate_path(
            content,
            kind="directory",
            mode=_PRIVATE_DIRECTORY_MODE,
            uid=self._owner_uid,
            gid=self._owner_gid,
            label="Artifact content",
        )
        entries = self._manifest_from_directory(content)
        for path in content.rglob("*"):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                expected_mode = _PRIVATE_DIRECTORY_MODE
            elif stat.S_ISREG(info.st_mode):
                expected_mode = _PRIVATE_FILE_MODE
            else:
                raise RunWorkspaceConflict("Artifact contains an unsafe file type")
            if info.st_uid != self._owner_uid or info.st_gid != self._owner_gid:
                raise UnsafeRunWorkspacePath("Artifact content ownership drifted")
            if stat.S_IMODE(info.st_mode) != expected_mode:
                raise UnsafeRunWorkspacePath("Artifact content mode drifted")
        return self._artifact_evidence(entries)

    @staticmethod
    def _artifact_evidence(entries: tuple[ProjectVersionExportFile, ...]) -> RunArtifactEvidence:
        ordered = tuple(sorted(entries, key=lambda entry: entry.path))
        payload = [
            {
                "path": entry.path,
                "size": entry.size,
                "content_hash": entry.content_hash,
            }
            for entry in ordered
        ]
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return RunArtifactEvidence(
            size=sum(entry.size for entry in ordered),
            file_count=len(ordered),
            content_hash=digest,
        )

    def _run_marker(
        self,
        identity: RunWorkspaceIdentity,
        *,
        state: Literal["exporting", "prepared"],
        input_fingerprint: str,
        evidence: ProjectVersionExportEvidence | None = None,
        input_evidence: tuple[ProjectVersionExportFile, ...] = (),
    ) -> dict[str, Any]:
        marker: dict[str, Any] = {
            "schema_version": _RUN_MARKER_SCHEMA_VERSION,
            "state": state,
            **self._identity_fields(identity),
            "input_fingerprint": input_fingerprint,
        }
        if evidence is not None:
            marker["tree_oid"] = evidence.tree_oid
            marker["manifest"] = [
                {
                    "path": entry.path,
                    "size": entry.size,
                    "content_hash": entry.content_hash,
                }
                for entry in sorted(evidence.manifest, key=lambda item: item.path)
            ]
            marker["input_manifest"] = [
                {
                    "path": entry.path,
                    "size": entry.size,
                    "content_hash": entry.content_hash,
                }
                for entry in sorted(input_evidence, key=lambda item: item.path)
            ]
        return marker

    def _artifact_marker(
        self,
        identity: RunWorkspaceIdentity,
        artifact_id: str,
        source_path: str,
        *,
        state: Literal["copying", "finalizing", "installed"],
        evidence: RunArtifactEvidence | None = None,
    ) -> dict[str, Any]:
        marker: dict[str, Any] = {
            "schema_version": _ARTIFACT_MARKER_SCHEMA_VERSION,
            "state": state,
            **self._identity_fields(identity),
            "artifact_id": artifact_id,
            "source_path": source_path,
        }
        if evidence is not None:
            marker["evidence"] = {
                "size": evidence.size,
                "file_count": evidence.file_count,
                "content_hash": evidence.content_hash,
            }
        return marker

    @staticmethod
    def _identity_fields(identity: RunWorkspaceIdentity) -> dict[str, str]:
        return {
            "run_id": identity.run_id,
            "snapshot_id": identity.snapshot_id,
            "project_version_id": identity.project_version_id,
            "commit_oid": identity.commit_oid,
        }

    def _require_same_identity(
        self, marker: dict[str, Any], identity: RunWorkspaceIdentity
    ) -> None:
        if any(marker.get(key) != value for key, value in self._identity_fields(identity).items()):
            raise RunWorkspaceConflict("Run workspace prepared identity differs")

    @staticmethod
    def _require_input_fingerprint(marker: dict[str, Any], expected: str) -> None:
        actual = marker.get("input_fingerprint")
        if not isinstance(actual, str) or not re.fullmatch(r"[0-9a-f]{64}", actual):
            raise RunWorkspaceConflict("Run input fingerprint is invalid")
        if actual != expected:
            raise RunWorkspaceConflict("Run workspace input identity differs")

    def _require_artifact_identity(
        self,
        marker: dict[str, Any],
        identity: RunWorkspaceIdentity,
        artifact_id: str,
        source_path: str,
    ) -> None:
        self._require_same_identity(marker, identity)
        if marker.get("artifact_id") != artifact_id or marker.get("source_path") != source_path:
            raise RunWorkspaceConflict("Artifact identity differs")

    def _export_evidence_from_marker(self, marker: dict[str, Any]) -> ProjectVersionExportEvidence:
        try:
            manifest = tuple(
                ProjectVersionExportFile(
                    path=entry["path"],
                    size=entry["size"],
                    content_hash=entry["content_hash"],
                )
                for entry in marker["manifest"]
            )
            evidence = ProjectVersionExportEvidence(
                commit_oid=marker["commit_oid"],
                tree_oid=marker["tree_oid"],
                manifest=manifest,
            )
        except (KeyError, TypeError) as exc:
            raise RunWorkspaceConflict("Run marker evidence is invalid") from exc
        if not _OID.fullmatch(evidence.commit_oid) or not _OID.fullmatch(evidence.tree_oid):
            raise RunWorkspaceConflict("Run marker evidence is invalid")
        return evidence

    def _input_evidence_from_marker(
        self, marker: dict[str, Any]
    ) -> tuple[ProjectVersionExportFile, ...]:
        try:
            evidence = tuple(
                ProjectVersionExportFile(
                    path=entry["path"],
                    size=entry["size"],
                    content_hash=entry["content_hash"],
                )
                for entry in marker["input_manifest"]
            )
        except (KeyError, TypeError) as exc:
            raise RunWorkspaceConflict("Run input marker evidence is invalid") from exc
        for entry in evidence:
            if (
                not isinstance(entry.path, str)
                or not isinstance(entry.size, int)
                or entry.size < 0
                or not isinstance(entry.content_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry.content_hash)
            ):
                raise RunWorkspaceConflict("Run input marker evidence is invalid")
            self._validate_relative_path("Run input marker path", entry.path, allow_dot=False)
        return tuple(sorted(evidence, key=lambda entry: entry.path))

    @staticmethod
    def _artifact_evidence_from_marker(marker: dict[str, Any]) -> RunArtifactEvidence:
        try:
            raw = marker["evidence"]
            evidence = RunArtifactEvidence(
                size=raw["size"],
                file_count=raw["file_count"],
                content_hash=raw["content_hash"],
            )
        except (KeyError, TypeError) as exc:
            raise RunWorkspaceConflict("Artifact marker evidence is invalid") from exc
        if (
            not isinstance(evidence.size, int)
            or evidence.size < 0
            or not isinstance(evidence.file_count, int)
            or evidence.file_count < 0
            or not isinstance(evidence.content_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", evidence.content_hash)
        ):
            raise RunWorkspaceConflict("Artifact marker evidence is invalid")
        return evidence

    def _read_run_marker(self, path: Path, *, label: str) -> dict[str, Any]:
        return self._read_marker(
            path,
            label=label,
            marker_kind="Run",
            expected_schema_version=_RUN_MARKER_SCHEMA_VERSION,
        )

    def _read_artifact_marker(self, root: Path) -> dict[str, Any]:
        self._validate_private_tree_root(root, label="Artifact")
        return self._read_marker(
            root / _ARTIFACT_MARKER_NAME,
            label="Artifact identity marker",
            marker_kind="Artifact",
            expected_schema_version=_ARTIFACT_MARKER_SCHEMA_VERSION,
        )

    def _validate_private_tree_root(self, path: Path, *, label: str) -> None:
        self._validate_path(
            path,
            kind="directory",
            mode=_PRIVATE_DIRECTORY_MODE,
            uid=self._owner_uid,
            gid=self._owner_gid,
            label=label,
        )

    def _write_json_marker(self, path: Path, marker: dict[str, Any], *, mode: int) -> None:
        for temporary in path.parent.glob(f".{path.name}.*.tmp"):
            if re.fullmatch(rf"\.{re.escape(path.name)}\.[0-9a-f]{{32}}\.tmp", temporary.name):
                info = temporary.lstat()
                if (
                    not stat.S_ISREG(info.st_mode)
                    or stat.S_ISLNK(info.st_mode)
                    or info.st_uid != self._owner_uid
                    or info.st_gid != self._owner_gid
                    or stat.S_IMODE(info.st_mode) not in {_PRIVATE_FILE_MODE, _PRIVATE_MARKER_MODE}
                ):
                    raise UnsafeRunWorkspacePath("marker temporary ownership drifted")
                temporary.unlink()
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _PRIVATE_FILE_MODE)
        try:
            payload = json.dumps(marker, sort_keys=True, separators=(",", ":")).encode()
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fchmod(descriptor, mode)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)

    def _read_marker(
        self,
        path: Path,
        *,
        label: str,
        marker_kind: Literal["Run", "Artifact"],
        expected_schema_version: int,
    ) -> dict[str, Any]:
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise RunWorkspaceConflict(f"{label} is missing") from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise UnsafeRunWorkspacePath(f"{label} is not a regular file")
        if info.st_uid != self._owner_uid:
            raise UnsafeRunWorkspacePath(f"{label} ownership drifted")
        if stat.S_IMODE(info.st_mode) not in {
            _PRIVATE_FILE_MODE,
            _PRIVATE_MARKER_MODE,
        }:
            raise UnsafeRunWorkspacePath(f"{label} mode drifted")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RunWorkspaceConflict(f"{label} is invalid") from exc
        if not isinstance(value, dict):
            raise RunWorkspaceConflict(f"{label} schema is invalid")
        actual_schema_version = value.get("schema_version")
        if actual_schema_version != expected_schema_version:
            raise RunWorkspaceConflict(
                f"{marker_kind} identity marker schema version "
                f"{actual_schema_version!r} is unsupported; expected {expected_schema_version}"
            )
        required_kind_fields = (
            {"run_id", "snapshot_id", "project_version_id", "commit_oid", "input_fingerprint"}
            if marker_kind == "Run"
            else {
                "run_id",
                "snapshot_id",
                "project_version_id",
                "commit_oid",
                "artifact_id",
                "source_path",
            }
        )
        if not required_kind_fields <= value.keys():
            raise RunWorkspaceConflict(f"{marker_kind} identity marker kind is invalid")
        return value

    def _ensure_directory(self, path: Path, *, mode: int, gid: int, label: str) -> None:
        if not os.path.lexists(path):
            path.mkdir(mode=mode)
            path.chmod(mode)
            os.chown(path, -1, gid)
        self._validate_path(
            path,
            kind="directory",
            mode=mode,
            uid=self._owner_uid,
            gid=gid,
            label=label,
        )

    def _create_directory(self, path: Path, mode: int, gid: int) -> None:
        path.mkdir(mode=mode)
        os.chown(path, -1, gid)
        path.chmod(mode)

    def _create_file(self, path: Path, mode: int, gid: int) -> None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            os.fchmod(descriptor, mode)
            os.fchown(descriptor, -1, gid)
        finally:
            os.close(descriptor)

    def _validate_path(
        self,
        path: Path,
        *,
        kind: Literal["file", "directory"],
        mode: int,
        uid: int,
        gid: int | None,
        label: str,
    ) -> None:
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise RunWorkspaceConflict(f"{label} is missing") from exc
        expected = stat.S_ISREG if kind == "file" else stat.S_ISDIR
        if stat.S_ISLNK(info.st_mode):
            raise UnsafeRunWorkspacePath(f"{label} is a symbolic link")
        if not expected(info.st_mode):
            raise RunWorkspaceConflict(f"{label} is not a {kind}")
        if info.st_uid != uid or (gid is not None and info.st_gid != gid):
            raise UnsafeRunWorkspacePath(f"{label} ownership drifted")
        actual_mode = stat.S_IMODE(info.st_mode)
        if actual_mode != mode:
            raise UnsafeRunWorkspacePath(f"{label} mode drifted: {actual_mode:#o} != {mode:#o}")

    def _validate_storage_root(self, root: Path) -> None:
        info = root.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise UnsafeRunWorkspacePath("Run workspace root must be a directory")
        if info.st_uid != self._owner_uid or info.st_gid != self._shared_gid:
            raise UnsafeRunWorkspacePath(
                "Run workspace root must be owned by the service UID and shared GID"
            )
        actual_mode = stat.S_IMODE(info.st_mode)
        if actual_mode & stat.S_IWOTH:
            raise UnsafeRunWorkspacePath("Run workspace root cannot be world-writable")
        if actual_mode != _RUN_ROOT_MODE:
            raise UnsafeRunWorkspacePath(
                f"Run workspace root mode drifted: {actual_mode:#o} != {_RUN_ROOT_MODE:#o}"
            )

    @staticmethod
    def _workspace_at(root: Path) -> RunWorkspace:
        return RunWorkspace(
            root=root,
            work=root / "work",
            inputs=root / "inputs",
            logs=root / "logs",
            artifact_staging=root / "artifacts",
            identity_marker=root / _MARKER_NAME,
        )

    @staticmethod
    def _path_exists(path: Path) -> bool:
        return os.path.lexists(path)

    @staticmethod
    def _validate_segment(label: str, value: str) -> None:
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or PurePosixPath(value).is_absolute()
        ):
            raise UnsafeRunWorkspacePath(f"{label} must be one POSIX path segment")

    @classmethod
    def _validate_identity(cls, identity: RunWorkspaceIdentity) -> None:
        cls._validate_segment("run_id", identity.run_id)
        cls._validate_segment("snapshot_id", identity.snapshot_id)
        cls._validate_segment("project_version_id", identity.project_version_id)
        if not _OID.fullmatch(identity.commit_oid):
            raise UnsafeRunWorkspacePath("commit_oid must be a full lowercase Git object ID")

    @staticmethod
    def _validate_relative_path(label: str, value: str, *, allow_dot: bool) -> None:
        path = PurePosixPath(value)
        if (
            not value
            or not path.parts
            or path.is_absolute()
            or "\\" in value
            or any(part == ".." for part in path.parts)
            or (not allow_dot and path.parts == (".",))
        ):
            raise UnsafeRunWorkspacePath(f"{label} must be a safe relative POSIX path")

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            return PosixRunWorkspace._hash_descriptor(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _hash_descriptor(descriptor: int) -> tuple[int, str]:
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, _HASH_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
        return size, digest.hexdigest()
