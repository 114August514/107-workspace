from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "4d7a2f91c3e5"
PROJECT_OWNERSHIP_REVISION = "f36a1b2c3d4e"

NOW = "2026-08-23 00:00:00+00:00"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _rows(connection: sqlite3.Connection, sql: str) -> list[tuple[object, ...]]:
    return list(connection.execute(sql).fetchall())


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str, str]]:
    return {
        (str(row[3]), str(row[2]), str(row[6]).upper())
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def _assert_integrity_error(
    connection: sqlite3.Connection, sql: str, parameters: tuple[object, ...] = ()
) -> None:
    connection.execute("SAVEPOINT expected_integrity_error")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, parameters)
    finally:
        connection.execute("ROLLBACK TO expected_integrity_error")
        connection.execute("RELEASE expected_integrity_error")


def _seed_predecessor(connection: sqlite3.Connection) -> None:
    """Seed the last pre-#36 schema: projects anchored to workspaces, no owner."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executemany(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES (?, ?, ?, NULL, ?)",
        [("usr_alice", "alice", "Alice", NOW), ("usr_bob", "bob", "Bob", NOW)],
    )
    connection.executemany(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, default_environment_version_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?)",
        [
            ("ws_personal", "personal", "Alice personal", "", "usr_alice", NOW),
            ("ws_collab", "collaborative", "Research Lab", "", "usr_alice", NOW),
        ],
    )
    # 现实不变量：collaborative anchor 与 User Group 同 id。
    connection.execute(
        "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
        "VALUES ('ws_collab', 'Research Lab', '', NULL, ?)",
        (NOW,),
    )
    connection.executemany(
        "INSERT INTO projects "
        "(id, workspace_id, name, description, status, environment_version_id, "
        "default_run_configuration_id, created_by, created_at, updated_at) "
        "VALUES (?, ?, ?, '', 'active', NULL, NULL, ?, ?, ?)",
        [
            ("prj_personal", "ws_personal", "Personal project", "usr_alice", NOW, NOW),
            ("prj_group", "ws_collab", "Group project", "usr_bob", NOW, NOW),
        ],
    )
    connection.commit()


def _assert_owner_schema(connection: sqlite3.Connection) -> None:
    assert {"owner_user_id", "owner_user_group_id", "visibility"} <= _columns(
        connection, "projects"
    )
    assert {
        ("owner_user_id", "users", "RESTRICT"),
        ("owner_user_group_id", "user_groups", "RESTRICT"),
    } <= _foreign_keys(connection, "projects")


def _assert_backfill(connection: sqlite3.Connection) -> None:
    # 归属权威：personal 锚点 → User owner，collaborative 锚点 → UserGroup owner。
    assert _rows(
        connection,
        "SELECT id, owner_user_id, owner_user_group_id, visibility FROM projects "
        "WHERE id != 'prj_public' ORDER BY id",
    ) == [
        ("prj_group", None, "ws_collab", "owner_scope"),
        ("prj_personal", "usr_alice", None, "owner_scope"),
    ]
    # 兼容锚点保留：#37-#42 迁移窗口内子域仍按 workspace_id 关联。
    assert _rows(
        connection, "SELECT id, workspace_id FROM projects WHERE id != 'prj_public' ORDER BY id"
    ) == [("prj_group", "ws_collab"), ("prj_personal", "ws_personal")]


def test_issue_36_project_ownership_migration_backfills_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "project-ownership.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _seed_predecessor(connection)

        command.upgrade(config, PROJECT_OWNERSHIP_REVISION)
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            _assert_owner_schema(connection)
            _assert_backfill(connection)

            # 新写入路径：显式 owner + PUBLIC visibility。
            connection.execute(
                "INSERT INTO projects "
                "(id, workspace_id, owner_user_id, owner_user_group_id, name, description, "
                "status, visibility, environment_version_id, "
                "default_run_configuration_id, created_by, created_at, updated_at) "
                "VALUES ('prj_public', 'ws_personal', 'usr_alice', NULL, 'Public', '', "
                "'active', 'public', NULL, NULL, 'usr_alice', ?, ?)",
                (NOW, NOW),
            )
            assert _rows(
                connection,
                "SELECT owner_user_id, owner_user_group_id, visibility FROM projects "
                "WHERE id = 'prj_public'",
            ) == [("usr_alice", None, "public")]

            # 恰好一个 owner；owner 不可被删除。
            _assert_integrity_error(
                connection,
                "INSERT INTO projects "
                "(id, workspace_id, owner_user_id, owner_user_group_id, name, status, "
                "visibility, created_by, created_at, updated_at) "
                "VALUES ('prj_both', 'ws_personal', 'usr_alice', 'ws_collab', "
                "'Invalid', 'active', 'owner_scope', 'usr_alice', ?, ?)",
                (NOW, NOW),
            )
            _assert_integrity_error(
                connection,
                "INSERT INTO projects "
                "(id, workspace_id, owner_user_id, owner_user_group_id, name, status, "
                "visibility, created_by, created_at, updated_at) "
                "VALUES ('prj_neither', 'ws_personal', NULL, NULL, "
                "'Invalid', 'active', 'owner_scope', 'usr_alice', ?, ?)",
                (NOW, NOW),
            )
            _assert_integrity_error(connection, "DELETE FROM users WHERE id = 'usr_alice'")
            _assert_integrity_error(connection, "DELETE FROM user_groups WHERE id = 'ws_collab'")
            connection.commit()

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            columns = _columns(connection, "projects")
            assert {"owner_user_id", "owner_user_group_id", "visibility"}.isdisjoint(columns)
            # 行数据保留；owner 与 visibility 是本次新增语义，降级即丢（产品未上线）。
            assert _rows(connection, "SELECT id, workspace_id FROM projects ORDER BY id") == [
                ("prj_group", "ws_collab"),
                ("prj_personal", "ws_personal"),
                ("prj_public", "ws_personal"),
            ]

        command.upgrade(config, PROJECT_OWNERSHIP_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_owner_schema(connection)
            # 重新升级后按锚点重新推导 owner。
            assert _rows(
                connection,
                "SELECT id, owner_user_id, owner_user_group_id, visibility FROM projects "
                "ORDER BY id",
            ) == [
                ("prj_group", None, "ws_collab", "owner_scope"),
                ("prj_personal", "usr_alice", None, "owner_scope"),
                ("prj_public", "usr_alice", None, "owner_scope"),
            ]
    finally:
        get_settings.cache_clear()
