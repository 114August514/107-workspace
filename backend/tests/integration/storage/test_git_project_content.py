"""Git-backed Project Working State and immutable commit identity."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from workspace107.infrastructure.project_git import GitProjectContent

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
PROJECT_ID = "prj_alpha"
REPOSITORY_IDENTITY = "repo_alpha"


def _git(project_root: Path, *args: str) -> str:
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
        env=os.environ,
    )
    return result.stdout.strip()


async def _commit(
    content: GitProjectContent,
    version_id: str,
    payload: bytes,
    parent: tuple[str, str] | None = None,
):
    await content.write_working_file(PROJECT_ID, REPOSITORY_IDENTITY, "src/main.py", payload, NOW)
    return await content.commit_working(
        PROJECT_ID,
        REPOSITORY_IDENTITY,
        version_id=version_id,
        parent_version_id=parent[0] if parent else None,
        parent_commit_oid=parent[1] if parent else None,
        message=version_id,
        created_by="usr_alice",
        created_at=NOW,
    )


async def test_git_version_ref_pins_full_immutable_commit(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    first = await _commit(content, "pv_first", b"print('v1')\n")
    second = await _commit(content, "pv_second", b"print('v2')\n", ("pv_first", first.commit_oid))
    project_root = tmp_path / "projects" / PROJECT_ID

    assert FULL_OID.fullmatch(first.commit_oid)
    assert FULL_OID.fullmatch(first.tree_oid)
    assert (
        _git(project_root, "rev-parse", "refs/workspace107/versions/pv_first") == first.commit_oid
    )
    assert (
        _git(project_root, "rev-parse", "refs/workspace107/versions/pv_second") == second.commit_oid
    )

    export = tmp_path / "export"
    export.mkdir()
    evidence = await content.export_commit(
        PROJECT_ID,
        REPOSITORY_IDENTITY,
        "pv_first",
        first.commit_oid,
        export,
        expected_tree_oid=first.tree_oid,
        expected_file_count=first.file_count,
        expected_total_size=first.total_size,
    )
    assert evidence.commit_oid == first.commit_oid
    assert evidence.tree_oid == first.tree_oid
    assert (export / "src/main.py").read_bytes() == b"print('v1')\n"


async def test_commit_rehashes_same_size_same_mtime(tmp_path: Path) -> None:
    content = GitProjectContent(tmp_path / "projects")
    await content.initialize_project(PROJECT_ID, REPOSITORY_IDENTITY)
    project_root = tmp_path / "projects" / PROJECT_ID
    _git(project_root, "config", "core.checkStat", "minimal")

    first = await _commit(content, "pv_first", b"print('v1')\n")
    second = await _commit(content, "pv_second", b"print('v2')\n", ("pv_first", first.commit_oid))

    assert second.commit_oid != first.commit_oid
    assert second.tree_oid != first.tree_oid
    assert (
        await content.read_commit_file(
            PROJECT_ID,
            REPOSITORY_IDENTITY,
            "pv_second",
            second.commit_oid,
            "src/main.py",
        )
        == b"print('v2')\n"
    )
