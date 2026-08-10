"""POSIX Run workspace 的 prepared identity 与恢复语义。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
from pathlib import Path

import pytest

from workspace107.domain.ports.run_workspace import (
    RunWorkspaceConflict,
    RunWorkspaceIdentity,
    UnsafeRunWorkspacePath,
)
from workspace107.domain.ports.version_control import (
    ProjectVersionExportEvidence,
    ProjectVersionExportFile,
)
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace

COMMIT_OID = "1" * 40
TREE_OID = "2" * 40


class SimulatedCrash(BaseException):
    pass


class FakeExporter:
    def __init__(self, *, symlink_target: Path | None = None, fail_first: bool = False) -> None:
        self.calls = 0
        self.symlink_target = symlink_target
        self.fail_first = fail_first

    async def export(
        self, *, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        return await asyncio.to_thread(
            self._export_sync, project_version_id, expected_commit_oid, target
        )

    def _export_sync(
        self, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        self.calls += 1
        assert project_version_id == "prjv_test"
        assert expected_commit_oid == COMMIT_OID
        assert target.is_absolute()
        assert list(target.iterdir()) == []
        content = b"print('prepared')\n"
        (target / "main.py").write_bytes(content)
        if self.fail_first and self.calls == 1:
            raise RuntimeError("injected export failure")
        if self.symlink_target is not None:
            (target / "escape").symlink_to(self.symlink_target)
        return ProjectVersionExportEvidence(
            commit_oid=COMMIT_OID,
            tree_oid=TREE_OID,
            manifest=(
                ProjectVersionExportFile(
                    path="main.py",
                    size=len(content),
                    content_hash=hashlib.sha256(content).hexdigest(),
                ),
            ),
        )


class SlowExporter(FakeExporter):
    async def export(
        self, *, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        await asyncio.sleep(0.05)
        return await super().export(
            project_version_id=project_version_id,
            expected_commit_oid=expected_commit_oid,
            target=target,
        )


class InternalSymlinkExporter(FakeExporter):
    async def export(
        self, *, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        evidence = await super().export(
            project_version_id=project_version_id,
            expected_commit_oid=expected_commit_oid,
            target=target,
        )
        (target / "alias.py").symlink_to("main.py")
        main = evidence.manifest[0]
        return ProjectVersionExportEvidence(
            commit_oid=evidence.commit_oid,
            tree_oid=evidence.tree_oid,
            manifest=(
                ProjectVersionExportFile(
                    path="alias.py",
                    size=main.size,
                    content_hash=main.content_hash,
                ),
                main,
            ),
        )


def identity(*, snapshot_id: str = "snap_test") -> RunWorkspaceIdentity:
    return RunWorkspaceIdentity(
        run_id="run_test",
        snapshot_id=snapshot_id,
        project_version_id="prjv_test",
        commit_oid=COMMIT_OID,
    )


def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "shared"
    root.mkdir(mode=0o750)
    return root


@pytest.mark.asyncio
async def test_prepare_exports_to_empty_work_and_writes_evidence_marker(tmp_path: Path) -> None:
    exporter = FakeExporter()
    manager = PosixRunWorkspace(storage_root(tmp_path), exporter)

    workspace = await manager.prepare(identity(), inputs=())

    assert exporter.calls == 1
    assert all(
        path.is_absolute()
        for path in (
            workspace.root,
            workspace.work,
            workspace.inputs,
            workspace.logs,
            workspace.stdout,
            workspace.stderr,
            workspace.artifact_staging,
            workspace.identity_marker,
        )
    )
    assert (workspace.work / "main.py").read_text(encoding="utf-8") == "print('prepared')\n"
    assert list(workspace.inputs.iterdir()) == []
    assert workspace.stdout.is_file()
    assert workspace.stderr.is_file()
    assert workspace.artifact_staging.is_dir()

    marker = json.loads(workspace.identity_marker.read_text(encoding="utf-8"))
    assert marker == {
        "schema_version": 1,
        "state": "prepared",
        "run_id": "run_test",
        "snapshot_id": "snap_test",
        "project_version_id": "prjv_test",
        "commit_oid": COMMIT_OID,
        "tree_oid": TREE_OID,
        "manifest": [
            {
                "path": "main.py",
                "size": 18,
                "content_hash": hashlib.sha256(b"print('prepared')\n").hexdigest(),
            }
        ],
    }
    for path in (
        workspace.root,
        workspace.work,
        workspace.inputs,
        workspace.logs,
        workspace.stdout,
        workspace.stderr,
        workspace.artifact_staging,
        workspace.identity_marker,
    ):
        assert path.stat().st_mode & 0o002 == 0


@pytest.mark.asyncio
async def test_same_identity_recovers_after_export_failure_without_false_success(
    tmp_path: Path,
) -> None:
    exporter = FakeExporter(fail_first=True)
    manager = PosixRunWorkspace(storage_root(tmp_path), exporter)

    with pytest.raises(RuntimeError, match="injected export failure"):
        await manager.prepare(identity(), inputs=())

    workspace = manager.paths_for("run_test")
    marker = json.loads(workspace.identity_marker.read_text(encoding="utf-8"))
    assert marker["state"] == "preparing"
    assert not workspace.work.exists()
    workspace.stdout.write_text("preserved across recovery", encoding="utf-8")

    recovered = await manager.prepare(identity(), inputs=())

    assert recovered == workspace
    assert exporter.calls == 2
    assert workspace.stdout.read_text(encoding="utf-8") == "preserved across recovery"
    assert json.loads(workspace.identity_marker.read_text(encoding="utf-8"))["state"] == (
        "prepared"
    )


@pytest.mark.asyncio
async def test_same_identity_retry_preserves_workspace_logs_and_artifacts(tmp_path: Path) -> None:
    exporter = FakeExporter()
    manager = PosixRunWorkspace(storage_root(tmp_path), exporter)
    workspace = await manager.prepare(identity(), inputs=())
    workspace.stdout.write_text("existing log\n", encoding="utf-8")
    artifact = workspace.artifact_staging / "result.txt"
    artifact.write_text("existing result\n", encoding="utf-8")
    (workspace.work / "main.py").write_text("locally changed\n", encoding="utf-8")

    recovered = await manager.prepare(identity(), inputs=())

    assert recovered == workspace
    assert exporter.calls == 1
    assert workspace.stdout.read_text(encoding="utf-8") == "existing log\n"
    assert artifact.read_text(encoding="utf-8") == "existing result\n"
    assert (workspace.work / "main.py").read_text(encoding="utf-8") == "locally changed\n"


@pytest.mark.asyncio
async def test_different_identity_cannot_reuse_existing_run_workspace(tmp_path: Path) -> None:
    exporter = FakeExporter()
    manager = PosixRunWorkspace(storage_root(tmp_path), exporter)
    workspace = await manager.prepare(identity(), inputs=())
    workspace.stdout.write_text("keep me", encoding="utf-8")

    with pytest.raises(RunWorkspaceConflict, match="prepared identity"):
        await manager.prepare(identity(snapshot_id="snap_other"), inputs=())

    assert exporter.calls == 1
    assert workspace.stdout.read_text(encoding="utf-8") == "keep me"
    assert json.loads(workspace.identity_marker.read_text(encoding="utf-8"))["snapshot_id"] == (
        "snap_test"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("run_id", ["/tmp/absolute", "../escape", "nested/run", r"nested\\run"])
async def test_run_id_must_be_one_posix_path_segment(tmp_path: Path, run_id: str) -> None:
    manager = PosixRunWorkspace(storage_root(tmp_path), FakeExporter())
    unsafe = RunWorkspaceIdentity(
        run_id=run_id,
        snapshot_id="snap_test",
        project_version_id="prjv_test",
        commit_oid=COMMIT_OID,
    )

    with pytest.raises(UnsafeRunWorkspacePath):
        await manager.prepare(unsafe, inputs=())


@pytest.mark.asyncio
async def test_existing_symlink_workspace_is_rejected_without_writing_outside(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    runs = root / "runs"
    runs.mkdir()
    runs.chmod(0o750)
    (runs / "run_test").symlink_to(outside, target_is_directory=True)
    manager = PosixRunWorkspace(root, FakeExporter())

    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic link"):
        await manager.prepare(identity(), inputs=())

    assert list(outside.iterdir()) == []


@pytest.mark.asyncio
async def test_exporter_symlink_escape_is_rejected_without_prepared_marker(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    manager = PosixRunWorkspace(root, FakeExporter(symlink_target=outside))

    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic links"):
        await manager.prepare(identity(), inputs=())

    workspace = manager.paths_for("run_test")
    marker = json.loads(workspace.identity_marker.read_text(encoding="utf-8"))
    assert marker["state"] == "preparing"
    assert outside.read_text(encoding="utf-8") == "outside"


@pytest.mark.asyncio
async def test_unmarked_existing_directory_is_never_deleted_or_rebuilt(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    existing = root / "runs" / "run_test"
    existing.mkdir(parents=True)
    (root / "runs").chmod(0o750)
    sentinel = existing / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    manager = PosixRunWorkspace(root, FakeExporter())

    with pytest.raises(RunWorkspaceConflict, match="ownership claim"):
        await manager.prepare(identity(), inputs=())

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_storage_root_must_be_absolute_posix_and_not_world_writable(tmp_path: Path) -> None:
    with pytest.raises(UnsafeRunWorkspacePath, match="absolute"):
        PosixRunWorkspace(Path("relative-storage"), FakeExporter())

    root = tmp_path / "world-writable"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    with pytest.raises(UnsafeRunWorkspacePath, match="world-writable"):
        PosixRunWorkspace(root, FakeExporter())


@pytest.mark.asyncio
async def test_two_independent_processes_read_the_same_prepared_marker(tmp_path: Path) -> None:
    manager = PosixRunWorkspace(storage_root(tmp_path), FakeExporter())
    workspace = await manager.prepare(identity(), inputs=())
    script = (
        "import json, pathlib, sys; "
        "print(json.dumps(json.loads(pathlib.Path(sys.argv[1]).read_text()), sort_keys=True))"
    )

    async def read_marker() -> str:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            os.fspath(workspace.identity_marker),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        return stdout.decode().strip()

    outputs = [await read_marker(), await read_marker()]

    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["commit_oid"] == COMMIT_OID


@pytest.mark.asyncio
async def test_initialization_crash_before_preparing_marker_recovers_from_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = storage_root(tmp_path)
    manager = PosixRunWorkspace(root, FakeExporter())
    write_marker = manager._write_marker

    def crash_before_marker(path: Path, marker: dict[str, object]) -> None:
        if marker.get("state") == "preparing":
            raise RuntimeError("crash before preparing marker")
        write_marker(path, marker)

    monkeypatch.setattr(manager, "_write_marker", crash_before_marker)
    with pytest.raises(RuntimeError, match="crash before preparing marker"):
        await manager.prepare(identity(), inputs=())
    monkeypatch.undo()

    exporter = FakeExporter()
    workspace = await PosixRunWorkspace(root, exporter).prepare(identity(), inputs=())

    assert exporter.calls == 1
    assert json.loads(workspace.identity_marker.read_text())["state"] == "prepared"


@pytest.mark.asyncio
async def test_marker_tmp_crash_before_fchmod_is_cleaned_and_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = storage_root(tmp_path)
    manager = PosixRunWorkspace(root, FakeExporter())

    def crash_with_created_tmp(path: Path, marker: dict[str, object]) -> None:
        temporary = path.parent / f".{path.name}.{'a' * 32}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        raise SimulatedCrash("crash before marker fchmod")

    monkeypatch.setattr(manager, "_write_marker", crash_with_created_tmp)
    with pytest.raises(SimulatedCrash, match="crash before marker fchmod"):
        await manager.prepare(identity(), inputs=())
    monkeypatch.undo()

    workspace = manager.paths_for("run_test")
    temporary = workspace.root / f".{workspace.identity_marker.name}.{'a' * 32}.tmp"
    assert temporary.stat().st_mode & 0o777 == 0o600

    recovered = await PosixRunWorkspace(root, FakeExporter()).prepare(identity(), inputs=())

    assert not temporary.exists()
    assert json.loads(recovered.identity_marker.read_text())["state"] == "prepared"


@pytest.mark.asyncio
async def test_finalizing_crash_before_work_rename_is_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = storage_root(tmp_path)
    manager = PosixRunWorkspace(root, FakeExporter())
    rename = Path.rename

    def crash_install(source: Path, target: Path) -> Path:
        if source.name == ".work-staging" and Path(target).name == "work":
            raise SimulatedCrash("crash before work rename")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", crash_install)
    with pytest.raises(SimulatedCrash, match="crash before work rename"):
        await manager.prepare(identity(), inputs=())
    workspace = manager.paths_for("run_test")
    finalizing = json.loads(workspace.identity_marker.read_text())
    assert finalizing["state"] == "finalizing"
    assert finalizing["staging"] == ".work-staging"
    monkeypatch.undo()

    recovered = await PosixRunWorkspace(root, FakeExporter()).prepare(identity(), inputs=())

    assert recovered.work.is_dir()
    assert json.loads(recovered.identity_marker.read_text())["state"] == "prepared"


@pytest.mark.asyncio
async def test_finalizing_crash_after_work_rename_is_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = storage_root(tmp_path)
    manager = PosixRunWorkspace(root, FakeExporter())
    write_marker = manager._write_marker

    def crash_before_prepared(path: Path, marker: dict[str, object]) -> None:
        if marker.get("state") == "prepared":
            raise RuntimeError("crash before prepared marker")
        write_marker(path, marker)

    monkeypatch.setattr(manager, "_write_marker", crash_before_prepared)
    with pytest.raises(RuntimeError, match="crash before prepared marker"):
        await manager.prepare(identity(), inputs=())
    workspace = manager.paths_for("run_test")
    assert workspace.work.is_dir()
    assert json.loads(workspace.identity_marker.read_text())["state"] == "finalizing"
    monkeypatch.undo()

    recovered = await PosixRunWorkspace(root, FakeExporter()).prepare(identity(), inputs=())

    assert (recovered.work / "main.py").is_file()
    assert json.loads(recovered.identity_marker.read_text())["state"] == "prepared"


@pytest.mark.asyncio
async def test_concurrent_same_identity_prepares_once_and_both_callers_recover(
    tmp_path: Path,
) -> None:
    exporter = SlowExporter()
    manager = PosixRunWorkspace(storage_root(tmp_path), exporter)

    first, second = await asyncio.gather(
        manager.prepare(identity(), inputs=()),
        manager.prepare(identity(), inputs=()),
    )

    assert first == second
    assert exporter.calls == 1


@pytest.mark.asyncio
async def test_sigkill_staging_is_marker_owned_and_same_identity_recovers(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace

class KillingExporter:
    async def export(self, *, project_version_id, expected_commit_oid, target):
        (target / 'partial.txt').write_text('partial')
        os.kill(os.getpid(), signal.SIGKILL)

asyncio.run(PosixRunWorkspace(Path({str(root)!r}), KillingExporter()).prepare(
    RunWorkspaceIdentity('run_test', 'snap_test', 'prjv_test', {"1" * 40!r}), inputs=()
))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL

    manager = PosixRunWorkspace(root, FakeExporter())
    workspace = manager.paths_for("run_test")
    interrupted = json.loads(workspace.identity_marker.read_text())
    assert interrupted["state"] == "exporting"
    assert interrupted["staging"] == ".work-staging"

    recovered = await manager.prepare(identity(), inputs=())

    assert json.loads(recovered.identity_marker.read_text())["state"] == "prepared"
    assert not (recovered.root / ".work-staging").exists()


@pytest.mark.asyncio
async def test_exported_internal_symlink_is_rejected_for_m1(tmp_path: Path) -> None:
    manager = PosixRunWorkspace(storage_root(tmp_path), InternalSymlinkExporter())

    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic links"):
        await manager.prepare(identity(), inputs=())


@pytest.mark.asyncio
async def test_permission_drift_is_rejected_during_recovery(tmp_path: Path) -> None:
    manager = PosixRunWorkspace(storage_root(tmp_path), FakeExporter())
    workspace = await manager.prepare(identity(), inputs=())
    workspace.logs.chmod(0o777)

    with pytest.raises(UnsafeRunWorkspacePath, match="mode"):
        await manager.prepare(identity(), inputs=())
