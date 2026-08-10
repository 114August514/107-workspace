"""Git Project Version clean-cutover migration safety behavior。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PREVIOUS_REVISION = "b48640074b91"


def _alembic(database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "WORKSPACE107_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
        "WORKSPACE107_STORAGE_ROOT": str(database.parent / "storage"),
    }
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_git_version_migration_aborts_on_legacy_project_graph(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    assert _alembic(database, "upgrade", PREVIOUS_REVISION).returncode == 0
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                id, workspace_id, name, description, status,
                environment_version_id, default_run_configuration_id,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "prj_legacy",
                "ws_legacy",
                "legacy",
                "",
                "active",
                None,
                None,
                "usr_legacy",
                "2026-08-10 00:00:00",
                "2026-08-10 00:00:00",
            ),
        )

    result = _alembic(database, "upgrade", "head")
    assert result.returncode != 0
    assert "Rebuild the database and project storage together" in result.stderr
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        assert "repository_identity" not in columns
        assert connection.execute("SELECT count(*) FROM projects").fetchone() == (1,)


def test_git_version_downgrade_aborts_on_git_backed_project(tmp_path: Path) -> None:
    database = tmp_path / "git-backed.db"
    assert _alembic(database, "upgrade", "head").returncode == 0
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                id, workspace_id, name, repository_identity, description, status,
                environment_version_id, default_run_configuration_id,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "prj_git",
                "ws_git",
                "git",
                "repo_git",
                "",
                "active",
                None,
                None,
                "usr_git",
                "2026-08-10 00:00:00",
                "2026-08-10 00:00:00",
            ),
        )

    result = _alembic(database, "downgrade", "-1")
    assert result.returncode != 0
    assert "Rebuild the database and project storage together" in result.stderr
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        assert "repository_identity" in columns


def test_git_version_migration_empty_up_down_up(tmp_path: Path) -> None:
    database = tmp_path / "empty.db"
    assert _alembic(database, "upgrade", "head").returncode == 0
    assert _alembic(database, "downgrade", "-1").returncode == 0
    assert _alembic(database, "upgrade", "head").returncode == 0

    with sqlite3.connect(database) as connection:
        project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        version_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(project_versions)")
        }
        assert "repository_identity" in project_columns
        assert {"commit_oid", "file_count", "total_size"} <= version_columns
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "project_files" not in tables
        assert "project_version_files" not in tables
