"""Run 终态输出到不可变 Artifact 目录的行为契约。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from workspace107.domain.ports.run_workspace import (
    RunArtifactEvidence,
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


class FakeExporter:
    async def export(
        self, *, project_version_id: str, expected_commit_oid: str, target: Path
    ) -> ProjectVersionExportEvidence:
        data = b"project\n"
        (target / "main.py").write_bytes(data)
        return ProjectVersionExportEvidence(
            commit_oid=expected_commit_oid,
            tree_oid=TREE_OID,
            manifest=(
                ProjectVersionExportFile(
                    path="main.py",
                    size=len(data),
                    content_hash=hashlib.sha256(data).hexdigest(),
                ),
            ),
        )


class SimulatedCrash(BaseException):
    pass


def identity() -> RunWorkspaceIdentity:
    return RunWorkspaceIdentity("run_artifact", "snap_artifact", "prjv_artifact", COMMIT_OID)


async def prepared_manager(tmp_path: Path) -> tuple[Path, PosixRunWorkspace]:
    root = tmp_path / "shared"
    root.mkdir(mode=0o750)
    manager = PosixRunWorkspace(root, FakeExporter())
    await manager.prepare(identity(), inputs=())
    return root, manager


def write_outputs(manager: PosixRunWorkspace) -> None:
    output = manager.paths_for(identity().run_id).work / "outputs"
    (output / "nested").mkdir(parents=True)
    (output / "a.txt").write_text("alpha", encoding="utf-8")
    (output / "nested" / "b.txt").write_text("beta", encoding="utf-8")


@pytest.mark.asyncio
async def test_collect_artifact_installs_once_and_same_digest_is_idempotent(tmp_path: Path) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)

    first = await manager.collect_artifact(
        identity(), artifact_id="art_stable", source_path="outputs"
    )
    second = await manager.collect_artifact(
        identity(), artifact_id="art_stable", source_path="outputs"
    )

    assert (
        first
        == second
        == RunArtifactEvidence(
            size=9,
            file_count=2,
            content_hash=first.content_hash,
        )
    )
    assert len(first.content_hash) == 64
    installed = root / "artifact-store" / "art_stable"
    assert (installed / "content" / "a.txt").read_text() == "alpha"
    assert (installed / "content" / "nested" / "b.txt").read_text() == "beta"
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == ("prepared")


@pytest.mark.asyncio
async def test_existing_artifact_different_digest_conflicts_without_overwrite(
    tmp_path: Path,
) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    await manager.collect_artifact(identity(), artifact_id="art_stable", source_path="outputs")
    source = manager.paths_for(identity().run_id).work / "outputs" / "a.txt"
    source.write_text("changed", encoding="utf-8")

    with pytest.raises(RunWorkspaceConflict, match="different content"):
        await manager.collect_artifact(identity(), artifact_id="art_stable", source_path="outputs")

    assert (root / "artifact-store" / "art_stable" / "content" / "a.txt").read_text() == ("alpha")


def test_real_threads_same_artifact_do_not_delete_or_overwrite_each_other(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    root.mkdir(mode=0o750)
    manager = PosixRunWorkspace(root, FakeExporter())
    asyncio.run(manager.prepare(identity(), inputs=()))
    write_outputs(manager)

    def collect() -> RunArtifactEvidence:
        return asyncio.run(
            manager.collect_artifact(
                identity(), artifact_id="art_concurrent", source_path="outputs"
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: collect(), range(2)))

    assert results[0] == results[1]
    assert (root / "artifact-store" / "art_concurrent" / "content" / "a.txt").read_text() == (
        "alpha"
    )


@pytest.mark.asyncio
async def test_artifact_rename_before_install_crash_recovers_owned_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    rename = Path.rename

    def crash_before_install(source: Path, target: Path) -> Path:
        if source.parent.name == ".staging" and source.name == "art_crash":
            raise SimulatedCrash("before artifact rename")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", crash_before_install)
    with pytest.raises(SimulatedCrash, match="before artifact rename"):
        await manager.collect_artifact(identity(), artifact_id="art_crash", source_path="outputs")
    monkeypatch.undo()

    recovered = await PosixRunWorkspace(root, FakeExporter()).collect_artifact(
        identity(), artifact_id="art_crash", source_path="outputs"
    )

    assert recovered.file_count == 2
    assert not (root / "artifact-store" / ".staging" / "art_crash").exists()


@pytest.mark.asyncio
async def test_artifact_rename_after_install_crash_recovers_without_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    write_marker = manager._write_artifact_marker

    def crash_before_prepared(path: Path, marker: dict[str, object]) -> None:
        if marker.get("state") == "prepared":
            raise SimulatedCrash("after artifact rename")
        write_marker(path, marker)

    monkeypatch.setattr(manager, "_write_artifact_marker", crash_before_prepared)
    with pytest.raises(SimulatedCrash, match="after artifact rename"):
        await manager.collect_artifact(identity(), artifact_id="art_crash", source_path="outputs")
    installed = root / "artifact-store" / "art_crash"
    assert installed.is_dir()
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == (
        "finalizing"
    )
    monkeypatch.undo()

    recovered = await PosixRunWorkspace(root, FakeExporter()).collect_artifact(
        identity(), artifact_id="art_crash", source_path="outputs"
    )

    assert recovered.file_count == 2
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == ("prepared")


@pytest.mark.asyncio
@pytest.mark.parametrize("source_path", ["/absolute", "../escape", "nested/../../escape"])
async def test_artifact_source_path_must_be_safe(tmp_path: Path, source_path: str) -> None:
    _, manager = await prepared_manager(tmp_path)

    with pytest.raises(UnsafeRunWorkspacePath):
        await manager.collect_artifact(
            identity(), artifact_id="art_invalid", source_path=source_path
        )


@pytest.mark.asyncio
async def test_artifact_source_rejects_symlinks_and_special_files(tmp_path: Path) -> None:
    _, manager = await prepared_manager(tmp_path)
    work = manager.paths_for(identity().run_id).work
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (work / "link").symlink_to(outside)

    with pytest.raises(UnsafeRunWorkspacePath, match=r"[Ss]ymbolic link"):
        await manager.collect_artifact(identity(), artifact_id="art_link", source_path="link")
    (work / "link").unlink()

    fifo = work / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(UnsafeRunWorkspacePath, match="regular file or directory"):
        await manager.collect_artifact(identity(), artifact_id="art_fifo", source_path="fifo")


@pytest.mark.asyncio
async def test_cancelled_lock_waiter_releases_fd_for_next_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    entered = threading.Event()
    release = threading.Event()
    copy_source = manager._copy_artifact_source

    def hold_copy(source: object, content: Path) -> None:
        entered.set()
        release.wait(timeout=5)
        copy_source(source, content)

    monkeypatch.setattr(manager, "_copy_artifact_source", hold_copy)
    holder = asyncio.create_task(
        manager.collect_artifact(identity(), artifact_id="art_cancel", source_path="outputs")
    )
    await asyncio.to_thread(entered.wait, 5)
    waiter = asyncio.create_task(
        manager.collect_artifact(identity(), artifact_id="art_cancel", source_path="outputs")
    )
    await asyncio.sleep(0.03)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    await holder

    third = await manager.collect_artifact(
        identity(), artifact_id="art_cancel", source_path="outputs"
    )
    assert third.file_count == 2


@pytest.mark.asyncio
async def test_finalizing_staging_installs_first_content_when_source_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    rename = Path.rename

    def crash_before_install(source: Path, target: Path) -> Path:
        if source.parent.name == ".staging" and source.name == "art_first":
            raise SimulatedCrash("before first install")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", crash_before_install)
    with pytest.raises(SimulatedCrash):
        await manager.collect_artifact(identity(), artifact_id="art_first", source_path="outputs")
    monkeypatch.undo()
    source = manager.paths_for(identity().run_id).work / "outputs" / "a.txt"
    source.write_text("second", encoding="utf-8")

    first = await PosixRunWorkspace(root, FakeExporter()).collect_artifact(
        identity(), artifact_id="art_first", source_path="outputs"
    )

    installed = root / "artifact-store" / "art_first" / "content" / "a.txt"
    assert first.size == 9
    assert installed.read_text() == "alpha"
    with pytest.raises(RunWorkspaceConflict, match="different content"):
        await manager.collect_artifact(identity(), artifact_id="art_first", source_path="outputs")


@pytest.mark.asyncio
async def test_descriptor_traversal_survives_ancestor_symlink_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, manager = await prepared_manager(tmp_path)
    work = manager.paths_for(identity().run_id).work
    ancestor = work / "ancestor"
    ancestor.mkdir()
    (ancestor / "result.txt").write_text("trusted")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "result.txt").write_text("outside")
    original_open = os.open
    swapped = False

    def swapping_open(
        path: str | bytes | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if path == "ancestor" and dir_fd is not None and not swapped:
            ancestor.rename(work / "held-ancestor")
            ancestor.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor

    monkeypatch.setattr(os, "open", swapping_open)
    await manager.collect_artifact(
        identity(), artifact_id="art_ancestor", source_path="ancestor/result.txt"
    )

    installed = manager._artifact_store / "art_ancestor" / "content" / "result.txt"
    assert swapped
    assert installed.read_text() == "trusted"


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
async def test_descriptor_copy_survives_final_file_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    _, manager = await prepared_manager(tmp_path)
    work = manager.paths_for(identity().run_id).work
    source = work / "result.txt"
    source.write_text("trusted")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    original_open = os.open
    swapped = False

    def swapping_open(
        path: str | bytes | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if path == "result.txt" and dir_fd is not None and not swapped:
            source.rename(work / "held-result.txt")
            if replacement == "symlink":
                source.symlink_to(outside)
            else:
                os.mkfifo(source)
            swapped = True
        return descriptor

    monkeypatch.setattr(os, "open", swapping_open)
    await manager.collect_artifact(
        identity(), artifact_id=f"art_{replacement}", source_path="result.txt"
    )

    installed = manager._artifact_store / f"art_{replacement}" / "content" / "result.txt"
    assert swapped
    assert installed.read_text() == "trusted"


@pytest.mark.asyncio
async def test_independent_process_flock_blocks_then_releases(tmp_path: Path) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    lock_path = root / "artifact-store" / ".locks" / "art_process.lock"
    script = """
import fcntl, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
print('locked', flush=True)
sys.stdin.readline()
fcntl.flock(fd, fcntl.LOCK_UN)
os.close(fd)
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        os.fspath(lock_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    assert process.stdout is not None
    assert await process.stdout.readline() == b"locked\n"
    pending = asyncio.create_task(
        manager.collect_artifact(identity(), artifact_id="art_process", source_path="outputs")
    )
    await asyncio.sleep(0.03)
    assert not pending.done()
    assert process.stdin is not None
    process.stdin.write(b"release\n")
    await process.stdin.drain()
    await process.wait()
    assert (await pending).file_count == 2


@pytest.mark.asyncio
async def test_sigkill_copying_process_leaves_owned_staging_for_recovery(
    tmp_path: Path,
) -> None:
    root, manager = await prepared_manager(tmp_path)
    write_outputs(manager)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.domain.ports.version_control import ProjectVersionExportEvidence
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace
class UnusedExporter:
    async def export(self, **kwargs):
        raise AssertionError('workspace already prepared')
manager = PosixRunWorkspace(Path({str(root)!r}), UnusedExporter())
def kill_copy(source, content):
    (content / 'partial.txt').write_text('partial')
    os.kill(os.getpid(), signal.SIGKILL)
manager._copy_artifact_source = kill_copy
asyncio.run(manager.collect_artifact(
    RunWorkspaceIdentity('run_artifact','snap_artifact','prjv_artifact',{"1" * 40!r}),
    artifact_id='art_sigkill', source_path='outputs'))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL

    recovered = await manager.collect_artifact(
        identity(), artifact_id="art_sigkill", source_path="outputs"
    )
    assert recovered.file_count == 2
    assert not (root / "artifact-store" / ".staging" / "art_sigkill").exists()
