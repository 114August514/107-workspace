"""真实 Git Project Working State 与不可变 Version 内容。"""

from __future__ import annotations

import asyncio
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


def _git(repository: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.stdout.strip()


async def _version(
    content: GitProjectContent,
    *,
    version_id: str,
    payload: bytes,
    parent: str | None,
) -> str:
    await content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py", payload, NOW)
    manifest = await content.commit_working(
        PROJECT_ID,
        REPOSITORY_IDENTITY,
        version_id=version_id,
        parent_commit_oid=parent,
        message=version_id,
        created_by="usr_alice",
        created_at=NOW,
    )
    return manifest.commit_oid


async def test_req_m1_a_version_ref_survives_branch_move_and_gc(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    first = await _version(content, version_id="pv_first", payload=b"print('v1')\n", parent=None)
    await _version(content, version_id="pv_second", payload=b"print('v2')\n", parent=first)
    repository = tmp_path / "projects" / PROJECT_ID

    assert FULL_OID.fullmatch(first)
    assert _git(repository, "rev-parse", "refs/workspace107/versions/pv_first") == first
    _git(repository, "update-ref", "-d", "refs/heads/main")
    _git(repository, "gc", "--prune=now")

    destination = tmp_path / "export"
    destination.mkdir()
    await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, first, destination)
    assert (destination / "src/main.py").read_bytes() == b"print('v1')\n"
    assert (
        await content.read_commit_file(PROJECT_ID, REPOSITORY_IDENTITY, first, "src/main.py")
        == b"print('v1')\n"
    )


@pytest.mark.parametrize("revision", ["HEAD", "main", "latest", "refs/heads/main", "deadbeef"])
async def test_req_m1_a_rejects_movable_or_abbreviated_revision(
    tmp_path: Path, revision: str
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    with pytest.raises(ValidationFailed, match="完整 commit OID"):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, revision)


async def test_req_m1_a_repository_identity_is_not_commit_author(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content, version_id="pv_identity", payload=b"print(1)\n", parent=None
    )

    with pytest.raises(ProjectContentIdentityMismatch, match="identity mismatch"):
        await content.manifest(PROJECT_ID, "repo_from_other_database", commit_oid)

    repository = tmp_path / "projects" / PROJECT_ID
    identity_file = repository / ".git" / "workspace107-project-identity"
    identity_file.unlink()
    identity_file.symlink_to(tmp_path / "forged-identity")
    with pytest.raises(ProjectContentIdentityMismatch, match="identity mismatch"):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, commit_oid)


async def test_req_m1_a_rejects_dot_git_symlink(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repository = root / PROJECT_ID
    repository.mkdir(parents=True)
    (repository / ".git").symlink_to(tmp_path / "outside-git")
    content = GitProjectContent(root)
    with pytest.raises(ProjectContentIdentityMismatch, match="metadata is a symlink"):
        await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)


async def test_req_m1_a_missing_tree_blob_fails_as_project_content_error(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(
        content, version_id="pv_missing", payload=b"print(1)\n", parent=None
    )
    repository = tmp_path / "projects" / PROJECT_ID
    blob_oid = _git(repository, "rev-parse", f"{commit_oid}:src/main.py")
    (repository / ".git" / "objects" / blob_oid[:2] / blob_oid[2:]).unlink()

    with pytest.raises(ProjectContentMissing):
        await content.manifest(PROJECT_ID, REPOSITORY_IDENTITY, commit_oid)


async def test_req_m1_a_concurrent_mutations_are_serialized(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)

    await asyncio.gather(
        content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "main.py", b"a" * 100_000, NOW),
        content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "main.py", b"b" * 100_000, NOW),
    )
    observed = await content.read_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "main.py")
    assert observed in {b"a" * 100_000, b"b" * 100_000}

    first = await content.commit_working(
        PROJECT_ID,
        REPOSITORY_IDENTITY,
        version_id="pv_concurrent_1",
        parent_commit_oid=None,
        message="first",
        created_by="usr_alice",
        created_at=NOW,
    )
    await content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "main.py", b"changed", NOW)
    saved = await asyncio.gather(
        content.commit_working(
            PROJECT_ID,
            REPOSITORY_IDENTITY,
            version_id="pv_concurrent_2a",
            parent_commit_oid=first.commit_oid,
            message="second a",
            created_by="usr_alice",
            created_at=NOW,
        ),
        content.commit_working(
            PROJECT_ID,
            REPOSITORY_IDENTITY,
            version_id="pv_concurrent_2b",
            parent_commit_oid=first.commit_oid,
            message="second b",
            created_by="usr_alice",
            created_at=NOW,
        ),
    )
    repository = tmp_path / "projects" / PROJECT_ID
    assert len({manifest.commit_oid for manifest in saved}) == 2
    for version_id, manifest in zip(("pv_concurrent_2a", "pv_concurrent_2b"), saved, strict=True):
        assert (
            _git(repository, "rev-parse", f"refs/workspace107/versions/{version_id}")
            == manifest.commit_oid
        )


async def test_req_m1_a_restore_preserves_unsaved_state_and_recovers_swap(
    tmp_path: Path,
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(content, version_id="pv_restore", payload=b"saved", parent=None)
    await content.write_working_file(
        PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py", b"unsaved", NOW
    )
    with pytest.raises(ProjectContentMissing):
        await content.restore_working(PROJECT_ID, REPOSITORY_IDENTITY, "f" * 40, NOW)
    assert (
        await content.read_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py")
        == b"unsaved"
    )

    root = tmp_path / "projects"
    repository = root / PROJECT_ID
    staging = root / f".restore-{PROJECT_ID}-staging"
    backup = root / f".restore-{PROJECT_ID}-backup"
    state = root / ".locks" / f"{PROJECT_ID}.restore"
    staging.mkdir()
    await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, commit_oid, staging)
    repository.replace(backup)
    state.write_text("backup\n", encoding="ascii")

    assert (
        await content.read_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py") == b"saved"
    )
    assert repository.is_dir()
    assert not backup.exists()
    assert not state.exists()


async def test_req_m1_a_export_is_all_or_nothing_and_rejects_symlink_escape(
    tmp_path: Path,
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    repository = tmp_path / "projects" / PROJECT_ID
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    (repository / "escape").symlink_to("../outside.txt")
    commit_env = {
        "GIT_AUTHOR_NAME": "usr_alice",
        "GIT_AUTHOR_EMAIL": "untrusted@example.invalid",
        "GIT_COMMITTER_NAME": "Workspace 107",
        "GIT_COMMITTER_EMAIL": "untrusted@example.invalid",
    }
    _git(repository, "add", "-A", "--", ".", env=commit_env)
    _git(repository, "commit", "-m", "malicious symlink", env=commit_env)
    commit_oid = _git(repository, "rev-parse", "HEAD")

    destination = tmp_path / "export"
    destination.mkdir()
    with pytest.raises(ValidationFailed, match="符号链接"):
        await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, commit_oid, destination)
    assert list(destination.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


async def test_req_m1_a_export_requires_caller_owned_empty_directory(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    commit_oid = await _version(content, version_id="pv_export", payload=b"print(1)\n", parent=None)
    destination = tmp_path / "export"
    destination.mkdir()
    (destination / "owned.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValidationFailed, match="空目录"):
        await content.export_commit(PROJECT_ID, REPOSITORY_IDENTITY, commit_oid, destination)
    assert (destination / "owned.txt").read_text(encoding="utf-8") == "keep"
