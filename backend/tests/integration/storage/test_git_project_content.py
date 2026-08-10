"""真实 Git Project Working State 与不可变 Version 内容。"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workspace107.domain.errors import (
    ProjectContentIdentityMismatch,
    ProjectContentMissing,
    ValidationFailed,
)
from workspace107.infrastructure.project_git import GitProjectContent

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
PROJECT_ID = "prj_alpha"
REPOSITORY_IDENTITY = "repo_alpha"


def _git(project_root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        [
            "git",
            f"--git-dir={project_root / 'repository.git'}",
            f"--work-tree={project_root / 'work'}",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.stdout.strip()


def _git_returncode(project_root: Path, *args: str) -> int:
    return subprocess.run(
        ["git", f"--git-dir={project_root / 'repository.git'}", *args],
        check=False,
        capture_output=True,
    ).returncode


async def _version(
    content: GitProjectContent,
    *,
    version_id: str,
    payload: bytes,
    parent_version_id: str | None,
    parent_commit_oid: str | None,
) -> str:
    await content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py", payload, NOW)
    manifest = await content.commit_working(
        PROJECT_ID,
        REPOSITORY_IDENTITY,
        version_id=version_id,
        parent_version_id=parent_version_id,
        parent_commit_oid=parent_commit_oid,
        message=version_id,
        created_by="usr_alice",
        created_at=NOW,
    )
    return manifest.commit_oid


async def test_req_m1_a_immutable_ref_survives_branch_changes_and_gc(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    first = await _version(
        content,
        version_id="pv_first",
        payload=b"print('v1')\n",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    second = await _version(
        content,
        version_id="pv_second",
        payload=b"print('v2')\n",
        parent_version_id="pv_first",
        parent_commit_oid=first,
    )
    project_root = tmp_path / "projects" / PROJECT_ID

    assert FULL_OID.fullmatch(first)
    assert _git(project_root, "rev-parse", "refs/workspace107/versions/pv_first") == first
    assert _git(project_root, "rev-parse", "refs/workspace107/versions/pv_second") == second
    assert _git_returncode(project_root, "show-ref", "--verify", "refs/heads/main") != 0
    _git(project_root, "gc", "--prune=now")

    destination = tmp_path / "export"
    destination.mkdir()
    await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, "pv_first", first, destination)
    assert (destination / "src/main.py").read_bytes() == b"print('v1')\n"
    assert (
        await content.read_commit_file(
            PROJECT_ID, REPOSITORY_IDENTITY, "pv_first", first, "src/main.py"
        )
        == b"print('v1')\n"
    )


@pytest.mark.parametrize("revision", ["HEAD", "main", "latest", "refs/heads/main", "deadbeef"])
async def test_req_m1_a_rejects_movable_or_abbreviated_revision(
    tmp_path: Path, revision: str
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    with pytest.raises(ValidationFailed, match="完整 commit OID"):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, "pv_missing", revision)


async def test_req_m1_a_repository_and_ref_identity_are_verified(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_identity",
        payload=b"print(1)\n",
        parent_version_id=None,
        parent_commit_oid=None,
    )

    with pytest.raises(ProjectContentIdentityMismatch, match="identity mismatch"):
        await content.manifest(PROJECT_ID, "repo_from_other_database", "pv_identity", commit_oid)
    with pytest.raises(ProjectContentIdentityMismatch, match="immutable ref"):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, "pv_other", commit_oid)

    identity_file = (
        tmp_path / "projects" / PROJECT_ID / "repository.git" / "workspace107-project-identity"
    )
    identity_file.unlink()
    identity_file.symlink_to(tmp_path / "forged-identity")
    with pytest.raises(ProjectContentIdentityMismatch, match="identity mismatch"):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, "pv_identity", commit_oid)


async def test_req_m1_a_rejects_git_directory_symlink(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    project_root = root / PROJECT_ID
    project_root.mkdir(parents=True)
    (project_root / "work").mkdir()
    (project_root / "repository.git").symlink_to(tmp_path / "outside-git")
    content = GitProjectContent(root)
    with pytest.raises(ProjectContentMissing):
        await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)


async def test_req_m1_a_missing_tree_blob_fails_explicitly(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_missing",
        payload=b"print(1)\n",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    project_root = tmp_path / "projects" / PROJECT_ID
    blob_oid = _git(project_root, "rev-parse", f"{commit_oid}:src/main.py")
    (project_root / "repository.git" / "objects" / blob_oid[:2] / blob_oid[2:]).unlink()

    with pytest.raises(ProjectContentMissing):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, "pv_missing", commit_oid)


async def test_req_m1_a_single_file_read_does_not_scan_entire_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_target",
        payload=b"target",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    monkeypatch.setattr(
        content,
        "_tree_entries",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("full tree scan")),
    )
    assert (
        await content.read_commit_file(
            PROJECT_ID,
            REPOSITORY_IDENTITY,
            "pv_target",
            commit_oid,
            "src/main.py",
        )
        == b"target"
    )


async def test_req_m1_a_restore_recovers_process_interruption(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_restore",
        payload=b"saved",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    await content.write_working_file(
        PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py", b"unsaved", NOW
    )
    with pytest.raises(ProjectContentIdentityMismatch):
        await content.restore_working(
            PROJECT_ID,
            REPOSITORY_IDENTITY,
            "pv_wrong",
            commit_oid,
            NOW,
        )
    assert (
        await content.read_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py")
        == b"unsaved"
    )

    project_root = tmp_path / "projects" / PROJECT_ID
    work = project_root / "work"
    staging = project_root / "restore-staging"
    backup = project_root / "restore-backup"
    state = project_root / "restore.state"
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, "pv_restore", commit_oid, prepared)
    prepared.replace(staging)
    work.replace(backup)
    state.write_text("backup\n", encoding="ascii")

    assert (
        await content.read_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py") == b"saved"
    )
    assert work.is_dir()
    assert not backup.exists()
    assert not staging.exists()
    assert not state.exists()


async def test_req_m1_a_export_is_one_tree_walk_and_rejects_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_export",
        payload=b"print(1)\n",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    calls = 0
    original = content._tree_entries

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(content, "_tree_entries", counted)
    destination = tmp_path / "export"
    destination.mkdir()
    evidence = await content.export_commit(
        PROJECT_ID, REPOSITORY_IDENTITY, "pv_export", commit_oid, destination
    )
    assert calls == 1
    assert evidence.files[0].content_hash
    assert (destination / "src/main.py").read_bytes() == b"print(1)\n"

    project_root = tmp_path / "projects" / PROJECT_ID
    work = project_root / "work"
    (work / "escape").symlink_to("../../outside.txt")
    commit_env = {
        "GIT_AUTHOR_NAME": "usr_alice",
        "GIT_AUTHOR_EMAIL": "untrusted@example.invalid",
        "GIT_COMMITTER_NAME": "Workspace 107",
        "GIT_COMMITTER_EMAIL": "untrusted@example.invalid",
    }
    _git(project_root, "add", "-A", "--", ".", env=commit_env)
    tree_oid = _git(project_root, "write-tree", env=commit_env)
    malicious = _git(project_root, "commit-tree", tree_oid, "-m", "symlink", env=commit_env)
    _git(
        project_root,
        "update-ref",
        "refs/workspace107/versions/pv_symlink",
        malicious,
        "0" * len(malicious),
    )
    rejected = tmp_path / "rejected"
    rejected.mkdir()
    with pytest.raises(ValidationFailed, match="符号链接"):
        await content.export_commit(
            PROJECT_ID, REPOSITORY_IDENTITY, "pv_symlink", malicious, rejected
        )
    assert list(rejected.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


async def test_req_m1_a_export_requires_caller_owned_empty_directory(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content,
        version_id="pv_nonempty",
        payload=b"print(1)\n",
        parent_version_id=None,
        parent_commit_oid=None,
    )
    destination = tmp_path / "export"
    destination.mkdir()
    (destination / "owned.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValidationFailed, match="空目录"):
        await content.export_commit(
            PROJECT_ID, REPOSITORY_IDENTITY, "pv_nonempty", commit_oid, destination
        )
    assert (destination / "owned.txt").read_text(encoding="utf-8") == "keep"
