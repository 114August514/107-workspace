from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS = "f42a9c7e1d30"
REVISION = "e46a1b2c3d4e"
NOW = "2026-08-29 00:00:00+00:00"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def test_environment_cutover_preserves_unrelated_history_and_round_trips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "environment-publication.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)
    command.upgrade(config, PREVIOUS)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO users (id, username, display_name, email, created_at) "
            "VALUES ('usr_history', 'history', 'History', NULL, ?)",
            (NOW,),
        )
        connection.execute(
            "INSERT INTO environments "
            "(id, name, description, owner_user_id, owner_user_group_id) "
            "VALUES ('env_old', 'old', '', 'usr_history', NULL)"
        )
        connection.execute(
            "INSERT INTO environment_versions "
            "(id, environment_id, version, description, image, setup_command, available) "
            "VALUES ('ev_old', 'env_old', '1', '', 'legacy', '', 1)"
        )
        connection.execute(
            "INSERT INTO activities "
            "(id, owner_user_id, owner_user_group_id, project_id, actor_id, actor_name, "
            "action, target_type, target_id, target_name, detail, created_at) "
            "VALUES ('act_keep', 'usr_history', NULL, NULL, 'usr_history', 'History', "
            "'project_created', 'project', 'unrelated', 'Unrelated', '', ?)",
            (NOW,),
        )
        connection.execute(
            "INSERT INTO notifications "
            "(id, recipient_id, type, title, body, target_type, target_id, mandatory, "
            "created_at, read_at) VALUES "
            "('ntf_keep', 'usr_history', 'run_succeeded', 'Unrelated', '', NULL, NULL, 0, ?, NULL)",
            (NOW,),
        )
        connection.commit()

    command.upgrade(config, REVISION)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id FROM activities").fetchall() == [("act_keep",)]
        assert connection.execute("SELECT id FROM notifications").fetchall() == [("ntf_keep",)]
        assert connection.execute("SELECT COUNT(*) FROM environment_versions").fetchone() == (0,)

    command.downgrade(config, PREVIOUS)
    command.upgrade(config, REVISION)
    get_settings.cache_clear()
