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


def _git(repository: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.stdout.strip()


async def test_req_m1_a_version_is_full_immutable_commit(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project("prj_alpha")
    await content.write_working_file("prj_alpha", "src/main.py", b"print('v1')\n", NOW)

    first = await content.commit_working(
        "prj_alpha", parent_commit_oid=None, message="first", created_by="usr_alice", created_at=NOW
    )
    assert FULL_OID.fullmatch(first.commit_oid)
    assert _git(tmp_path / "projects" / "prj_alpha", "cat-file", "-t", first.commit_oid) == "commit"

    await content.write_working_file("prj_alpha", "src/main.py", b"print('v2')\n", NOW)
    second = await content.commit_working(
        "prj_alpha",
        parent_commit_oid=first.commit_oid,
        message="second",
        created_by="usr_alice",
        created_at=NOW,
    )
    assert second.commit_oid != first.commit_oid

    # 分支是可移动引用；旧 Version 仍只由完整 commit OID 决定。
    _git(tmp_path / "projects" / "prj_alpha", "update-ref", "refs/heads/main", second.commit_oid)
    destination = tmp_path / "export"
    destination.mkdir()
    await content.export_commit("prj_alpha", first.commit_oid, destination)
    assert (destination / "src/main.py").read_bytes() == b"print('v1')\n"
    assert (
        await content.read_commit_file("prj_alpha", first.commit_oid, "src/main.py")
        == b"print('v1')\n"
    )


@pytest.mark.parametrize("revision", ["HEAD", "main", "latest", "refs/heads/main", "deadbeef"])
async def test_req_m1_a_rejects_movable_or_abbreviated_revision(
    tmp_path: Path, revision: str
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project("prj_alpha")

    with pytest.raises(ValidationFailed, match="完整 commit OID"):
        await content.manifest("prj_alpha", revision)


async def test_req_m1_a_missing_object_and_identity_mismatch_fail_explicitly(
    tmp_path: Path,
) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project("prj_source")
    await content.write_working_file("prj_source", "main.py", b"print(1)\n", NOW)
    source = await content.commit_working(
        "prj_source",
        parent_commit_oid=None,
        message="source",
        created_by="usr_alice",
        created_at=NOW,
    )

    await content.initialize_project("prj_target")
    with pytest.raises(ProjectContentMissing, match="Git object"):
        await content.manifest("prj_target", source.commit_oid)

    target_repository = tmp_path / "projects" / "prj_target"
    _git(target_repository, "fetch", str(tmp_path / "projects" / "prj_source"), source.commit_oid)
    with pytest.raises(ProjectContentIdentityMismatch, match="prj_target"):
        await content.manifest("prj_target", source.commit_oid)


async def test_req_m1_a_missing_tree_blob_fails_as_project_content_error(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    repository = tmp_path / "projects" / "prj_alpha"
    await content.initialize_project("prj_alpha")
    await content.write_working_file("prj_alpha", "main.py", b"print(1)\n", NOW)
    version = await content.commit_working(
        "prj_alpha",
        parent_commit_oid=None,
        message="version",
        created_by="usr_alice",
        created_at=NOW,
    )
    blob_oid = _git(repository, "rev-parse", f"{version.commit_oid}:main.py")
    (repository / ".git" / "objects" / blob_oid[:2] / blob_oid[2:]).unlink()

    with pytest.raises(ProjectContentMissing, match=blob_oid):
        await content.manifest("prj_alpha", version.commit_oid)


async def test_req_m1_a_export_is_all_or_nothing_and_rejects_symlink_escape(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    project_id = "prj_alpha"
    repository = tmp_path / "projects" / project_id
    await content.initialize_project(project_id)
    (repository / "escape").symlink_to("../outside.txt")

    commit_env = {
        "GIT_AUTHOR_NAME": "usr_alice",
        "GIT_AUTHOR_EMAIL": f"{project_id}@projects.workspace107.invalid",
        "GIT_COMMITTER_NAME": "Workspace 107",
        "GIT_COMMITTER_EMAIL": f"{project_id}@projects.workspace107.invalid",
    }
    _git(repository, "add", "-A", "--", ".", env=commit_env)
    _git(repository, "commit", "-m", "malicious symlink", env=commit_env)
    commit_oid = _git(repository, "rev-parse", "HEAD")

    destination = tmp_path / "export"
    destination.mkdir()
    with pytest.raises(ValidationFailed, match="符号链接"):
        await content.export_commit(project_id, commit_oid, destination)

    assert list(destination.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


async def test_req_m1_a_export_requires_caller_owned_empty_directory(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project("prj_alpha")
    await content.write_working_file("prj_alpha", "main.py", b"print(1)\n", NOW)
    version = await content.commit_working(
        "prj_alpha",
        parent_commit_oid=None,
        message="version",
        created_by="usr_alice",
        created_at=NOW,
    )

    destination = tmp_path / "export"
    destination.mkdir()
    (destination / "owned.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValidationFailed, match="空目录"):
        await content.export_commit("prj_alpha", version.commit_oid, destination)

    assert (destination / "owned.txt").read_text(encoding="utf-8") == "keep"
