"""Single-writer immutable Artifact installation behavior."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import stat
import sys
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


def identity() -> RunWorkspaceIdentity:
    return RunWorkspaceIdentity("run_artifact", "snap_artifact", "prjv_artifact", COMMIT_OID)


async def prepared_manager(tmp_path: Path) -> tuple[Path, PosixRunWorkspace]:
    root = tmp_path / "shared"
    root.mkdir(mode=0o750)
    root.chmod(0o750)
    service = PosixRunWorkspace(root, FakeExporter(), shared_gid=os.getegid())
    await service.prepare(identity(), inputs=())
    return root, service


def write_outputs(service: PosixRunWorkspace) -> Path:
    output = service.paths_for(identity().run_id).work / "outputs"
    (output / "nested").mkdir(parents=True)
    (output / "a.txt").write_text("alpha")
    (output / "nested" / "b.txt").write_text("beta")
    return output


@pytest.mark.asyncio
async def test_install_is_idempotent_for_same_digest_and_private_from_compute(
    tmp_path: Path,
) -> None:
    root, service = await prepared_manager(tmp_path)
    write_outputs(service)

    first = await service.collect_artifact(
        identity(), artifact_id="art_stable", source_path="outputs"
    )
    second = await service.collect_artifact(
        identity(), artifact_id="art_stable", source_path="outputs"
    )

    assert first == second
    assert first.size == 9
    assert first.file_count == 2
    installed = root / "artifact-store" / "art_stable"
    assert (installed / "content" / "a.txt").read_text() == "alpha"
    assert (installed / "content" / "nested" / "b.txt").read_text() == "beta"
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == ("installed")
    assert stat.S_IMODE((root / "artifact-store").stat().st_mode) == 0o700
    assert stat.S_IMODE(installed.stat().st_mode) == 0o700
    assert stat.S_IMODE((installed / "content" / "a.txt").stat().st_mode) == 0o600
    assert stat.S_IMODE((installed / ".artifact-identity.json").stat().st_mode) == 0o400
    assert {entry.name for entry in (root / "artifact-store").iterdir()} == {
        ".staging",
        "art_stable",
    }


@pytest.mark.asyncio
async def test_different_digest_or_source_identity_never_overwrites(
    tmp_path: Path,
) -> None:
    root, service = await prepared_manager(tmp_path)
    output = write_outputs(service)
    await service.collect_artifact(identity(), artifact_id="art_stable", source_path="outputs")
    (output / "a.txt").write_text("changed")

    with pytest.raises(RunWorkspaceConflict, match="different content"):
        await service.collect_artifact(identity(), artifact_id="art_stable", source_path="outputs")
    with pytest.raises(RunWorkspaceConflict, match="Artifact identity differs"):
        await service.collect_artifact(
            identity(), artifact_id="art_stable", source_path="outputs/a.txt"
        )

    installed = root / "artifact-store" / "art_stable" / "content" / "a.txt"
    assert installed.read_text() == "alpha"


@pytest.mark.asyncio
async def test_real_process_exit_during_copying_discards_partial_and_retries(
    tmp_path: Path,
) -> None:
    root, service = await prepared_manager(tmp_path)
    write_outputs(service)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace
class UnusedExporter:
    async def export(self, **kwargs): raise AssertionError('prepared')
service = PosixRunWorkspace(Path({str(root)!r}), UnusedExporter(), shared_gid=os.getegid())
def kill_copy(source, content):
    (content / 'partial.txt').write_text('partial')
    os.kill(os.getpid(), signal.SIGKILL)
service._copy_source = kill_copy
asyncio.run(service.collect_artifact(
    RunWorkspaceIdentity('run_artifact','snap_artifact','prjv_artifact',{"1" * 40!r}),
    artifact_id='art_copy', source_path='outputs'))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL
    staging = root / "artifact-store" / ".staging" / "art_copy"
    assert json.loads((staging / ".artifact-identity.json").read_text())["state"] == ("copying")

    recovered = await service.collect_artifact(
        identity(), artifact_id="art_copy", source_path="outputs"
    )

    assert recovered.file_count == 2
    assert not staging.exists()
    assert not (root / "artifact-store" / "art_copy" / "content" / "partial.txt").exists()


@pytest.mark.asyncio
async def test_real_process_exit_at_finalizing_recovers_first_evidence_without_source(
    tmp_path: Path,
) -> None:
    root, service = await prepared_manager(tmp_path)
    output = write_outputs(service)
    script = f"""
import asyncio, os, signal
from pathlib import Path
from workspace107.domain.ports.run_workspace import RunWorkspaceIdentity
from workspace107.infrastructure.storage.run_workspace import PosixRunWorkspace
class UnusedExporter:
    async def export(self, **kwargs): raise AssertionError('prepared')
service = PosixRunWorkspace(Path({str(root)!r}), UnusedExporter(), shared_gid=os.getegid())
rename = Path.rename
def kill_finalizing(source, target):
    if source.parent.name == '.staging' and source.name == 'art_final':
        os.kill(os.getpid(), signal.SIGKILL)
    return rename(source, target)
Path.rename = kill_finalizing
asyncio.run(service.collect_artifact(
    RunWorkspaceIdentity('run_artifact','snap_artifact','prjv_artifact',{"1" * 40!r}),
    artifact_id='art_final', source_path='outputs'))
"""
    process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
    assert await process.wait() == -signal.SIGKILL
    staging = root / "artifact-store" / ".staging" / "art_final"
    marker = json.loads((staging / ".artifact-identity.json").read_text())
    assert marker["state"] == "finalizing"
    original = marker["evidence"]
    shutil_target = output
    for child in sorted(shutil_target.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    shutil_target.rmdir()

    recovered = await service.collect_artifact(
        identity(), artifact_id="art_final", source_path="outputs"
    )

    assert recovered == RunArtifactEvidence(**original)
    assert (root / "artifact-store" / "art_final" / "content" / "a.txt").read_text() == ("alpha")


@pytest.mark.asyncio
async def test_exit_after_install_rename_recovers_without_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, service = await prepared_manager(tmp_path)
    output = write_outputs(service)
    write_marker = service._write_json_marker

    def stop_before_installed(path: Path, marker: dict[str, object], *, mode: int) -> None:
        if marker.get("state") == "installed":
            raise RuntimeError("stop after install rename")
        write_marker(path, marker, mode=mode)

    monkeypatch.setattr(service, "_write_json_marker", stop_before_installed)
    with pytest.raises(RuntimeError, match="after install rename"):
        await service.collect_artifact(identity(), artifact_id="art_renamed", source_path="outputs")
    monkeypatch.undo()
    installed = root / "artifact-store" / "art_renamed"
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == (
        "finalizing"
    )
    for child in sorted(output.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    output.rmdir()

    recovered = await service.collect_artifact(
        identity(), artifact_id="art_renamed", source_path="outputs"
    )

    assert recovered.file_count == 2
    assert json.loads((installed / ".artifact-identity.json").read_text())["state"] == ("installed")


@pytest.mark.asyncio
@pytest.mark.parametrize("source_path", ["/absolute", "../escape", "nested/../../escape", "."])
async def test_artifact_source_path_must_be_safe(tmp_path: Path, source_path: str) -> None:
    _, service = await prepared_manager(tmp_path)
    with pytest.raises(UnsafeRunWorkspacePath):
        await service.collect_artifact(
            identity(), artifact_id="art_invalid", source_path=source_path
        )


@pytest.mark.asyncio
async def test_source_rejects_symlink_fifo_and_nested_symlink(tmp_path: Path) -> None:
    _, service = await prepared_manager(tmp_path)
    work = service.paths_for(identity().run_id).work
    outside = tmp_path / "outside"
    outside.write_text("outside")
    (work / "link").symlink_to(outside)
    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic link"):
        await service.collect_artifact(identity(), artifact_id="art_link", source_path="link")
    fifo = work / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(UnsafeRunWorkspacePath, match="regular file or directory"):
        await service.collect_artifact(identity(), artifact_id="art_fifo", source_path="fifo")
    tree = work / "tree"
    tree.mkdir()
    (tree / "link").symlink_to(outside)
    with pytest.raises(UnsafeRunWorkspacePath, match="symbolic link"):
        await service.collect_artifact(identity(), artifact_id="art_nested", source_path="tree")


@pytest.mark.asyncio
async def test_descriptor_traversal_uses_opened_ancestor_after_symlink_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = await prepared_manager(tmp_path)
    work = service.paths_for(identity().run_id).work
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
    await service.collect_artifact(
        identity(), artifact_id="art_ancestor", source_path="ancestor/result.txt"
    )
    installed = service._artifact_store / "art_ancestor" / "content" / "result.txt"
    assert swapped
    assert installed.read_text() == "trusted"


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
async def test_descriptor_copy_uses_opened_file_after_final_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    _, service = await prepared_manager(tmp_path)
    work = service.paths_for(identity().run_id).work
    source = work / "result.txt"
    source.write_text("trusted")
    outside = tmp_path / "outside"
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
            source.rename(work / "held-result")
            source.symlink_to(outside) if replacement == "symlink" else os.mkfifo(source)
            swapped = True
        return descriptor

    monkeypatch.setattr(os, "open", swapping_open)
    await service.collect_artifact(
        identity(), artifact_id=f"art_{replacement}", source_path="result.txt"
    )
    installed = service._artifact_store / f"art_{replacement}" / "content" / "result.txt"
    assert swapped
    assert installed.read_text() == "trusted"
