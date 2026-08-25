"""Single-writer POSIX Run workspace behavior."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import stat
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest

from workspace107.domain.ports.run_workspace import (
    ArtifactRunWorkspaceInput,
    RunWorkspaceConflict,
    RunWorkspaceIdentity,
    RunWorkspaceInputFile,
    SharedResourceRunWorkspaceInput,
    UnsafeRunWorkspacePath,
)
from workspace107.domain.ports.version_control import (
    ProjectVersionExportEvidence,
    ProjectVersionExportFile,
)
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace

COMMIT_OID = "1" * 40
TREE_OID = "2" * 40

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="Run workspace requires POSIX UID/GID and filesystem semantics"
)


class FakeExporter:
    def __init__(self, *, fail: bool = False, symlink_target: Path | None = None) -> None:
        self.calls = 0
        self.fail = fail
        self.symlink_target = symlink_target

    async def export(
        self, *, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        self.calls += 1
        assert project_version_id == "prjv_test"
        assert expected_commit_oid == COMMIT_OID
        assert list(target.iterdir()) == []  # noqa: ASYNC240
        data = b"print('prepared')\n"
        (target / "main.py").write_bytes(data)
        if self.symlink_target is not None:
            (target / "escape").symlink_to(self.symlink_target)
        if self.fail:
            raise RuntimeError("injected export failure")
        return ProjectVersionExportEvidence(
            commit_oid=COMMIT_OID,
            tree_oid=TREE_OID,
            manifest=(
                ProjectVersionExportFile(
                    path="main.py",
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                ),
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
    root.chmod(0o750)
    return root


def manager(root: Path, exporter: FakeExporter | None = None) -> PosixRunWorkspace:
    return PosixRunWorkspace(root, exporter or FakeExporter(), shared_gid=os.getegid())


@pytest.mark.asyncio
async def test_prepare_installs_complete_workspace_with_shared_permissions(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    exporter = FakeExporter()
    workspace = await manager(root, exporter).prepare(identity(), inputs=())

    assert exporter.calls == 1
    assert workspace.root.is_absolute()
    assert (workspace.work / "main.py").read_text() == "print('prepared')\n"
    assert list(workspace.inputs.iterdir()) == []
    marker = json.loads(workspace.identity_marker.read_text())
    assert marker == {
        "schema_version": 2,
        "state": "prepared",
        "run_id": "run_test",
        "snapshot_id": "snap_test",
        "project_version_id": "prjv_test",
        "commit_oid": COMMIT_OID,
        "input_fingerprint": hashlib.sha256(b"[]").hexdigest(),
        "tree_oid": TREE_OID,
        "manifest": [
            {
                "path": "main.py",
                "size": 18,
                "content_hash": hashlib.sha256(b"print('prepared')\n").hexdigest(),
            }
        ],
        "input_manifest": [],
    }
    expected = {
        workspace.root: 0o750,
        root / ".run-staging": 0o700,
        workspace.work: 0o2770,
        workspace.inputs: 0o2550,
        workspace.logs: 0o2770,
        workspace.artifact_staging: 0o2770,
        workspace.stdout: 0o660,
        workspace.stderr: 0o660,
        workspace.work / "main.py": 0o660,
        workspace.identity_marker: 0o400,
    }
    for path, mode in expected.items():
        info = path.stat()
        assert stat.S_IMODE(info.st_mode) == mode
        assert info.st_uid == os.geteuid()
        if path != workspace.identity_marker:
            assert info.st_gid == os.getegid()
    assert {entry.name for entry in (root / "runs").iterdir()} == {"run_test"}


@pytest.mark.asyncio
async def test_same_identity_preserves_logs_artifacts_and_work_without_reexport(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    exporter = FakeExporter()
    service = manager(root, exporter)
    workspace = await service.prepare(identity(), inputs=())
    workspace.stdout.write_text("existing log")
    (workspace.artifact_staging / "result.txt").write_text("result")
    (workspace.work / "main.py").write_text("locally changed")

    recovered = await service.prepare(identity(), inputs=())

    assert recovered == workspace
    assert json.loads(workspace.identity_marker.read_text())["schema_version"] == 2
    assert exporter.calls == 1
    assert workspace.stdout.read_text() == "existing log"
    assert (workspace.artifact_staging / "result.txt").read_text() == "result"
    assert (workspace.work / "main.py").read_text() == "locally changed"


@pytest.mark.asyncio
async def test_run_v1_marker_is_deliberately_rejected(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    service = manager(root)
    workspace = await service.prepare(identity(), inputs=())
    marker = json.loads(workspace.identity_marker.read_text())
    marker["schema_version"] = 1
    workspace.identity_marker.chmod(0o600)
    workspace.identity_marker.write_text(json.dumps(marker))
    workspace.identity_marker.chmod(0o400)

    with pytest.raises(
        RunWorkspaceConflict,
        match="Run identity marker schema version 1 is unsupported; expected 2",
    ):
        await service.prepare(identity(), inputs=())


@pytest.mark.asyncio
async def test_different_identity_never_reuses_prepared_workspace(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    service = manager(root)
    workspace = await service.prepare(identity(), inputs=())
    workspace.stdout.write_text("keep")

    with pytest.raises(RunWorkspaceConflict, match="prepared identity"):
        await service.prepare(identity(snapshot_id="snap_other"), inputs=())

    assert workspace.stdout.read_text() == "keep"


@pytest.mark.asyncio
async def test_interrupted_export_temp_is_owned_then_removed_and_reexported(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    with pytest.raises(RuntimeError, match="injected export failure"):
        await manager(root, FakeExporter(fail=True)).prepare(identity(), inputs=())
    temporary = next((root / ".run-staging").glob(".run_test.*.tmp"))
    marker_data = json.loads((temporary / ".workspace-identity.json").read_text())
    assert marker_data["state"] == "exporting"
    assert not (root / "runs" / "run_test").exists()

    exporter = FakeExporter()
    workspace = await manager(root, exporter).prepare(identity(), inputs=())

    assert exporter.calls == 1
    assert workspace.work.is_dir()
    assert not list((root / ".run-staging").glob(".run_test.*.tmp"))


@pytest.mark.asyncio
async def test_real_process_exit_during_export_is_recovered(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace
class KillingExporter:
    async def export(self, *, target, **kwargs):
        (target / 'partial.txt').write_text('partial')
        os.kill(os.getpid(), signal.SIGKILL)
asyncio.run(PosixRunWorkspace(
    Path({str(root)!r}), KillingExporter(), shared_gid=os.getegid()
).prepare(RunWorkspaceIdentity('run_test','snap_test','prjv_test',{"1" * 40!r}), inputs=()))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL
    assert list((root / ".run-staging").glob(".run_test.*.tmp"))

    workspace = await manager(root).prepare(identity(), inputs=())

    assert (workspace.work / "main.py").is_file()
    assert not list((root / ".run-staging").glob(".run_test.*.tmp"))


@pytest.mark.asyncio
async def test_real_process_exit_before_run_marker_cleans_owned_half_init(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace
class UnusedExporter:
    async def export(self, **kwargs): raise AssertionError('marker is first')
service = PosixRunWorkspace(
    Path({str(root)!r}), UnusedExporter(), shared_gid=os.getegid()
)
def kill_before_marker(*args, **kwargs): os.kill(os.getpid(), signal.SIGKILL)
service._write_json_marker = kill_before_marker
asyncio.run(service.prepare(
    RunWorkspaceIdentity('run_test','snap_test','prjv_test',{"1" * 40!r}), inputs=()))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL
    temporary = next((root / ".run-staging").glob(".run_test.*.tmp"))
    assert not (temporary / ".workspace-identity.json").exists()
    assert stat.S_IMODE(temporary.stat().st_mode) == 0o700

    workspace = await manager(root).prepare(identity(), inputs=())

    assert workspace.work.is_dir()
    assert not temporary.exists()


@pytest.mark.asyncio
async def test_setgid_execution_directories_inherit_shared_group_and_umask(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    workspace = await manager(root).prepare(identity(), inputs=())
    script = """
import os, pathlib, sys
os.umask(0o007)
work, logs, artifacts = map(pathlib.Path, sys.argv[1:])
(work / 'generated').mkdir()
(work / 'generated' / 'result.txt').write_text('result')
(logs / 'worker.log').write_text('log')
(artifacts / 'candidate.txt').write_text('artifact')
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        os.fspath(workspace.work),
        os.fspath(workspace.logs),
        os.fspath(workspace.artifact_staging),
    )
    assert await process.wait() == 0

    expected = {
        workspace.work / "generated": 0o2770,
        workspace.work / "generated" / "result.txt": 0o660,
        workspace.logs / "worker.log": 0o660,
        workspace.artifact_staging / "candidate.txt": 0o660,
    }
    for path, mode in expected.items():
        info = path.stat()
        assert info.st_gid == os.getegid()
        assert stat.S_IMODE(info.st_mode) == mode


@pytest.mark.skipif(
    getattr(os, "geteuid", lambda: -1)() != 0,
    reason="requires root to create distinct local service and compute identities",
)
def test_distinct_uids_share_execution_paths_but_not_service_control(
    tmp_path: Path,
) -> None:
    for probe_parent in (tmp_path.parent.parent, tmp_path.parent, tmp_path):
        probe_parent.chmod(0o755)
    service_uid, service_gid = 11001, 11001
    compute_uid, compute_gid = 12001, 12001
    shared_gid = 13001
    root = tmp_path / "shared"
    root.mkdir(mode=0o750)
    os.chown(root, service_uid, shared_gid)
    root.chmod(0o750)

    def run_as(uid: int, gid: int, action: Callable[[], None]) -> None:
        process_id = os.fork()
        if process_id == 0:
            try:
                os.setgroups([shared_gid])
                os.setgid(gid)
                os.setuid(uid)
                action()
            except BaseException:
                traceback.print_exc()
                os._exit(1)
            os._exit(0)
        _, status = os.waitpid(process_id, 0)
        assert os.waitstatus_to_exitcode(status) == 0

    run_as(
        service_uid,
        service_gid,
        lambda: asyncio.run(
            PosixRunWorkspace(root, FakeExporter(), shared_gid=shared_gid).prepare(
                identity(), inputs=()
            )
        ),
    )
    workspace = root / "runs" / "run_test"

    def exercise_compute_paths() -> None:
        os.umask(0o007)
        (workspace / "work" / "generated").mkdir()
        (workspace / "work" / "generated" / "result.txt").write_text("result")
        (workspace / "logs" / "compute.log").write_text("log")
        with (workspace / "logs" / "stdout.log").open("a") as output:
            output.write("stdout")
        with (workspace / "logs" / "stderr.log").open("a") as output:
            output.write("stderr")
        (workspace / "artifacts" / "candidate.txt").write_text("artifact")
        denied = (
            lambda: (workspace / "inputs" / "forbidden").write_text("no"),
            lambda: (workspace / ".workspace-identity.json").open("w"),
            lambda: list((root / "artifact-store").iterdir()),
            lambda: list((root / ".run-staging").iterdir()),
        )
        for action in denied:
            with pytest.raises(PermissionError):
                action()

    run_as(compute_uid, compute_gid, exercise_compute_paths)
    expected = {
        workspace / "work" / "generated": 0o2770,
        workspace / "work" / "generated" / "result.txt": 0o660,
        workspace / "logs" / "compute.log": 0o660,
        workspace / "artifacts" / "candidate.txt": 0o660,
    }
    for path, mode in expected.items():
        info = path.stat()
        assert info.st_uid == compute_uid
        assert info.st_gid == shared_gid
        assert stat.S_IMODE(info.st_mode) == mode


@pytest.mark.asyncio
async def test_wrong_identity_temp_is_not_deleted(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    failing = manager(root, FakeExporter(fail=True))
    with pytest.raises(RuntimeError):
        await failing.prepare(identity(snapshot_id="snap_other"), inputs=())
    temporary = next((root / ".run-staging").glob(".run_test.*.tmp"))

    with pytest.raises(RunWorkspaceConflict, match="prepared identity"):
        await manager(root).prepare(identity(), inputs=())

    assert temporary.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("run_id", ["/tmp/absolute", "../escape", "nested/run", r"nested\run"])
async def test_run_id_must_be_one_posix_segment(tmp_path: Path, run_id: str) -> None:
    unsafe = RunWorkspaceIdentity(run_id, "snap_test", "prjv_test", COMMIT_OID)
    with pytest.raises(UnsafeRunWorkspacePath):
        await manager(storage_root(tmp_path)).prepare(unsafe, inputs=())


@pytest.mark.asyncio
async def test_shared_resource_inputs_are_verified_read_only_and_bound_to_marker(
    tmp_path: Path,
) -> None:
    root = storage_root(tmp_path)
    data = b"immutable input"
    content_hash = hashlib.sha256(data).hexdigest()
    blob = root / "blobs" / content_hash[:2] / content_hash
    blob.parent.mkdir(parents=True)
    blob.write_bytes(data)
    inputs = (
        SharedResourceRunWorkspaceInput(
            version_id="shrv_1",
            access_path="/inputs/data",
            files=(
                RunWorkspaceInputFile(
                    source_path="train/value.txt",
                    target_path="value.txt",
                    size=len(data),
                    content_hash=content_hash,
                ),
            ),
        ),
    )

    service = manager(root)
    workspace = await service.prepare(identity(), inputs=inputs)
    materialized = workspace.inputs / "inputs/data/value.txt"
    marker = json.loads(workspace.identity_marker.read_text())

    assert materialized.read_bytes() == data
    assert stat.S_IMODE(materialized.stat().st_mode) == 0o440
    assert marker["input_manifest"] == [
        {
            "path": "inputs/data/value.txt",
            "size": len(data),
            "content_hash": content_hash,
        }
    ]
    with pytest.raises(RunWorkspaceConflict, match="input identity differs"):
        await service.prepare(
            identity(),
            inputs=(
                SharedResourceRunWorkspaceInput(
                    version_id="shrv_1",
                    access_path="/inputs/other",
                    files=inputs[0].files,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_installed_artifact_can_be_materialized_as_read_only_input(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    service = manager(root)
    source_identity = identity()
    source_workspace = await service.prepare(source_identity, inputs=())
    output = source_workspace.work / "output"
    output.mkdir()
    (output / "result.txt").write_text("artifact input")
    evidence = await service.collect_artifact(
        source_identity,
        artifact_id="art_input",
        source_path="output",
    )
    assert evidence is not None

    consumer_identity = RunWorkspaceIdentity(
        "run_consumer", "snap_consumer", "prjv_test", COMMIT_OID
    )
    consumer = await service.prepare(
        consumer_identity,
        inputs=(
            ArtifactRunWorkspaceInput(
                artifact_id="art_input",
                access_path="/inputs/prior",
                source_subpath="",
                content_hash=evidence.content_hash,
            ),
        ),
    )

    materialized = consumer.inputs / "inputs/prior/result.txt"
    assert materialized.read_text() == "artifact input"
    assert stat.S_IMODE(materialized.stat().st_mode) == 0o440


@pytest.mark.asyncio
async def test_existing_symlink_or_unmarked_directory_is_never_rebuilt(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    service = manager(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = root / "runs" / "run_test"
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic link"):
        await service.prepare(identity(), inputs=())
    target.unlink()
    target.mkdir(mode=0o750)
    target.chmod(0o750)
    os.chown(target, -1, os.getegid())
    sentinel = target / "keep"
    sentinel.write_text("keep")
    with pytest.raises(RunWorkspaceConflict, match="marker"):
        await service.prepare(identity(), inputs=())
    assert sentinel.read_text() == "keep"


@pytest.mark.asyncio
async def test_exported_symlink_is_rejected_without_final_workspace(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("outside")
    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic links"):
        await manager(root, FakeExporter(symlink_target=outside)).prepare(identity(), inputs=())
    assert not (root / "runs" / "run_test").exists()
    assert outside.read_text() == "outside"


@pytest.mark.asyncio
async def test_prepared_layout_permission_drift_is_rejected(tmp_path: Path) -> None:
    root = storage_root(tmp_path)
    service = manager(root)
    workspace = await service.prepare(identity(), inputs=())
    workspace.logs.chmod(0o777)
    with pytest.raises(UnsafeRunWorkspacePath, match="mode drifted"):
        await service.prepare(identity(), inputs=())


def test_storage_root_and_shared_gid_are_explicitly_validated(tmp_path: Path) -> None:
    with pytest.raises(UnsafeRunWorkspacePath, match="absolute"):
        PosixRunWorkspace(Path("relative"), FakeExporter(), shared_gid=os.getegid())
    root = tmp_path / "world"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    with pytest.raises(UnsafeRunWorkspacePath, match="world-writable"):
        PosixRunWorkspace(root, FakeExporter(), shared_gid=os.getegid())
    root.chmod(0o750)
    with pytest.raises(UnsafeRunWorkspacePath, match="non-negative"):
        PosixRunWorkspace(root, FakeExporter(), shared_gid=-1)
