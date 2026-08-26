from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "f42a9c7e1d30"
DEFAULT_REVISION = "e45a1c2d3f40"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def test_user_group_default_environment_migration_round_trips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)
    command.upgrade(config, PREVIOUS_REVISION)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        now = "2026-08-26 00:00:00+00:00"
        connection.execute(
            "INSERT INTO users (id, username, display_name, email, created_at) "
            "VALUES ('usr_owner', 'owner', 'Owner', NULL, ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
            "VALUES ('grp_lab', 'Lab', '', 'usr_owner', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO environments "
            "(id, name, description, owner_user_id, owner_user_group_id) "
            "VALUES ('env_python', 'Python', '', NULL, 'grp_lab')"
        )
        connection.execute(
            "INSERT INTO environment_versions "
            "(id, environment_id, version, description, image, setup_command, available) "
            "VALUES ('envv_python', 'env_python', '3.12', '', 'python:3.12', '', 1)"
        )

    command.upgrade(config, DEFAULT_REVISION)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert "default_environment_version_id" in _columns(connection, "user_groups")
        connection.execute(
            "UPDATE user_groups SET default_environment_version_id='envv_python' WHERE id='grp_lab'"
        )
        assert connection.execute(
            "SELECT default_environment_version_id FROM user_groups WHERE id='grp_lab'"
        ).fetchone() == ("envv_python",)

    command.downgrade(config, PREVIOUS_REVISION)
    with sqlite3.connect(database) as connection:
        assert "default_environment_version_id" not in _columns(connection, "user_groups")

    command.upgrade(config, DEFAULT_REVISION)
    with sqlite3.connect(database) as connection:
        assert "default_environment_version_id" in _columns(connection, "user_groups")
