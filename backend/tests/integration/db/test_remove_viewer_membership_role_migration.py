from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "c471ac39f002"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def test_viewer_rows_are_revoked_without_privilege_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "viewer-role.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)
    command.upgrade(config, PREVIOUS_REVISION)

    connection = sqlite3.connect(database)
    now = "2026-08-22 00:00:00+00:00"
    connection.execute(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES ('usr_viewer', 'viewer-user', 'Viewer User', NULL, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
        "VALUES ('grp_viewer', 'Viewer Group', '', NULL, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO memberships (id, user_group_id, user_id, role, status, created_at) "
        "VALUES ('mbr_viewer', 'grp_viewer', 'usr_viewer', 'viewer', 'active', ?)",
        (now,),
    )
    connection.commit()
    connection.close()

    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT role, status FROM memberships WHERE id='mbr_viewer'"
    ).fetchone() == ("member", "removed")
    connection.close()

    command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT role, status FROM memberships WHERE id='mbr_viewer'"
    ).fetchone() == ("member", "removed")
    connection.close()
