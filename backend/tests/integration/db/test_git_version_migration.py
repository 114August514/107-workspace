"""Git Project Version clean-cutover migration safety."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PREVIOUS_REVISION = "f42a9c7e1d30"


def _alembic(database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "WORKSPACE107_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
            "WORKSPACE107_STORAGE_ROOT": str(database.parent / "storage"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_git_version_migration_refuses_legacy_content_authority(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    assert _alembic(database, "upgrade", PREVIOUS_REVISION).returncode == 0
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO project_files (project_id, path, size, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("prj_legacy", "main.py", 1, "0" * 64, "2026-08-10 00:00:00"),
        )

    result = _alembic(database, "upgrade", "head")
    assert result.returncode != 0
    assert "Rebuild the database and project storage together" in result.stderr
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "project_files" in tables
        assert connection.execute("SELECT count(*) FROM project_files").fetchone() == (1,)


def test_git_version_migration_empty_up_down_up(tmp_path: Path) -> None:
    database = tmp_path / "empty.db"
    assert _alembic(database, "upgrade", "head").returncode == 0
    assert _alembic(database, "downgrade", PREVIOUS_REVISION).returncode == 0
    assert _alembic(database, "upgrade", "head").returncode == 0

    with sqlite3.connect(database) as connection:
        project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        version_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(project_versions)")
        }
        assert "repository_identity" in project_columns
        assert {
            "repository_identity",
            "commit_oid",
            "tree_oid",
            "file_count",
            "total_size",
        } <= version_columns
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "project_files" not in tables
        assert "project_version_files" not in tables
