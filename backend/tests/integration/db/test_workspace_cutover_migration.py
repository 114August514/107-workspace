from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "a41b9c3e7d2f"
CUTOVER_REVISION = "f42a9c7e1d30"
NOW = "2026-08-25 00:00:00+00:00"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _seed_incompatible_state(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES ('usr_alice', 'alice', 'Alice', NULL, ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, default_environment_version_id, created_at) "
        "VALUES ('ws_alice', 'personal', 'Alice', '', 'usr_alice', NULL, ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO projects "
        "(id, workspace_id, owner_user_id, owner_user_group_id, name, description, status, "
        "visibility, environment_version_id, default_run_configuration_id, created_by, "
        "created_at, updated_at) VALUES ('prj_alice', 'ws_alice', 'usr_alice', NULL, "
        "'Project', '', 'active', 'owner_scope', NULL, NULL, 'usr_alice', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO notifications "
        "(id, recipient_id, type, title, body, workspace_id, target_type, target_id, mandatory, "
        "created_at, read_at) VALUES ('not_1', 'usr_alice', 'run_succeeded', 'Done', '', "
        "'ws_alice', 'project', 'prj_alice', 0, ?, NULL)",
        (NOW,),
    )
    connection.commit()


def _assert_current(connection: sqlite3.Connection) -> None:
    tables = _tables(connection)
    assert "workspaces" not in tables
    assert "legacy_personal_memberships" not in tables
    assert "user_group_migration_provenance" not in tables
    assert "workspace_id" not in _columns(connection, "projects")
    assert "workspace_id" not in _columns(connection, "runs")
    assert "workspace_id" not in _columns(connection, "artifacts")
    assert "workspace_id" not in _columns(connection, "activities")
    assert {"owner_user_id", "owner_user_group_id"} <= _columns(connection, "activities")
    assert "workspace_id" not in _columns(connection, "notifications")
    assert "source_workspace_id" not in _columns(connection, "fork_relations")
    assert {"source_owner_user_id", "source_owner_user_group_id"} <= _columns(
        connection, "fork_relations"
    )
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM projects").fetchone() == (0,)
    assert connection.execute("SELECT COUNT(*) FROM notifications").fetchone() == (0,)


def _assert_predecessor(connection: sqlite3.Connection) -> None:
    tables = _tables(connection)
    assert {"workspaces", "legacy_personal_memberships", "user_group_migration_provenance"} <= tables
    assert "workspace_id" in _columns(connection, "projects")
    assert "workspace_id" in _columns(connection, "runs")
    assert "workspace_id" in _columns(connection, "artifacts")
    assert "workspace_id" in _columns(connection, "activities")
    assert "workspace_id" in _columns(connection, "notifications")
    assert "source_workspace_id" in _columns(connection, "fork_relations")
    assert connection.execute("SELECT COUNT(*) FROM projects").fetchone() == (0,)


def test_issue_42_workspace_cutover_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "issue42-cutover.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _seed_incompatible_state(connection)

        command.upgrade(config, CUTOVER_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_current(connection)

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_predecessor(connection)

        command.upgrade(config, CUTOVER_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_current(connection)
    finally:
        get_settings.cache_clear()
