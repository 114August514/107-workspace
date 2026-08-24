from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "f36a1b2c3d4e"
RUN_INITIATED_BY_REVISION = "a41b9c3e7d2f"

NOW = "2026-08-24 00:00:00+00:00"


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


def _foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str]]:
    return {
        (str(row[3]), str(row[2]))
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
    """Seed pre-#41 schema: runs.created_by + nullable config env + workspace idempotency."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executemany(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES (?, ?, ?, NULL, ?)",
        [("usr_alice", "alice", "Alice", NOW), ("usr_bob", "bob", "Bob", NOW)],
    )
    connection.execute(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, default_environment_version_id, created_at) "
        "VALUES ('ws_lab', 'collaborative', 'Lab', '', 'usr_alice', NULL, ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
        "VALUES ('ws_lab', 'Lab', '', NULL, ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO projects "
        "(id, workspace_id, owner_user_id, owner_user_group_id, name, description, status, "
        "visibility, environment_version_id, default_run_configuration_id, "
        "created_by, created_at, updated_at) "
        "VALUES ('prj_lab', 'ws_lab', NULL, 'ws_lab', 'Lab project', '', 'active', "
        "'owner_scope', NULL, NULL, 'usr_alice', ?, ?)",
        (NOW, NOW),
    )
    connection.execute("INSERT INTO run_snapshots (id, payload) VALUES ('snap_1', '{}')")
    connection.executemany(
        "INSERT INTO run_configurations "
        "(id, project_id, name, description, working_directory, command, environment_version_id, "
        "environment_variables, input_bindings, compute_plan_id, compute_request, artifact_rules) "
        "VALUES (?, ?, ?, '', '.', 'echo ok', ?, '{}', '[]', 'plan_cpu_quick', NULL, '[]')",
        [
            ("cfg_exact", "prj_lab", "exact env", "ev_demo_python_312_2026"),
            ("cfg_legacy", "prj_lab", "null env", None),
        ],
    )
    connection.execute(
        "INSERT INTO runs "
        "(id, project_id, workspace_id, snapshot_id, compute_plan_id, project_version_id, "
        "project_version_label, source_run_configuration_id, source_run_id, name, status, "
        "failure_reason, created_by, created_at) "
        "VALUES ('run_1', 'prj_lab', 'ws_lab', 'snap_1', 'plan_cpu_quick', 'pv_1', 'v1', "
        "'cfg_exact', NULL, 'first run', 'succeeded', '', 'usr_alice', ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO idempotency_keys (workspace_id, key, endpoint, run_id, created_at) "
        "VALUES ('ws_lab', 'seed-key', 'create_run', 'run_1', ?)",
        (NOW,),
    )
    connection.commit()


def _assert_initiated_by_schema(connection: sqlite3.Connection) -> None:
    assert "initiated_by_user_id" in _columns(connection, "runs")
    assert "created_by" not in _columns(connection, "runs")
    assert ("initiated_by_user_id", "users") in _foreign_keys(connection, "idempotency_keys")
    assert "workspace_id" not in _columns(connection, "idempotency_keys")


def _assert_initiated_by_data(connection: sqlite3.Connection) -> None:
    # created_by 的既有值就是发起人：rename 即 backfill（GR-307）。
    assert _rows(connection, "SELECT id, initiated_by_user_id FROM runs") == [
        ("run_1", "usr_alice")
    ]
    # 运行方案必须精确引用 Environment Version：历史 NULL 行显式删除。
    assert _rows(
        connection, "SELECT id, environment_version_id FROM run_configurations ORDER BY id"
    ) == [("cfg_exact", "ev_demo_python_312_2026")]
    # 幂等作用域收敛到发起 User：旧 workspace 登记被丢弃。
    assert _rows(connection, "SELECT * FROM idempotency_keys") == []


def test_issue_41_run_initiated_by_user_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "run-initiated-by.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _seed_predecessor(connection)

        command.upgrade(config, RUN_INITIATED_BY_REVISION)
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            _assert_initiated_by_schema(connection)
            _assert_initiated_by_data(connection)

            # NOT NULL：运行方案不能再不指定 Environment Version。
            _assert_integrity_error(
                connection,
                "INSERT INTO run_configurations "
                "(id, project_id, name, working_directory, command, environment_version_id, "
                "environment_variables, input_bindings, compute_plan_id, artifact_rules) "
                "VALUES ('cfg_new', 'prj_lab', 'no env', '.', 'echo ok', NULL, '{}', '[]', "
                "'plan_cpu_quick', '[]')",
            )

            # 幂等键按 (initiated_by_user_id, key) 唯一；不同 User 可复用同一个 key。
            connection.execute(
                "INSERT INTO idempotency_keys "
                "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                "VALUES ('usr_alice', 'k1', 'create_run', NULL, ?)",
                (NOW,),
            )
            _assert_integrity_error(
                connection,
                "INSERT INTO idempotency_keys "
                "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                "VALUES ('usr_alice', 'k1', 'create_run', NULL, ?)",
                (NOW,),
            )
            connection.execute(
                "INSERT INTO idempotency_keys "
                "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                "VALUES ('usr_bob', 'k1', 'create_run', NULL, ?)",
                (NOW,),
            )
            assert _rows(
                connection,
                "SELECT initiated_by_user_id, key FROM idempotency_keys ORDER BY key",
            ) == [("usr_alice", "k1"), ("usr_bob", "k1")]
            # 登记引用的发起人不可删除。
            _assert_integrity_error(connection, "DELETE FROM users WHERE id = 'usr_bob'")
            connection.commit()

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            assert "created_by" in _columns(connection, "runs")
            assert "initiated_by_user_id" not in _columns(connection, "runs")
            assert ("workspace_id", "workspaces") in _foreign_keys(connection, "idempotency_keys")
            # downgrade 保留行数据；幂等登记是结构变化的一部分，不恢复。
            assert _rows(connection, "SELECT id, created_by FROM runs") == [("run_1", "usr_alice")]
            assert _rows(
                connection,
                "SELECT id, environment_version_id FROM run_configurations",
            ) == [("cfg_exact", "ev_demo_python_312_2026")]

        command.upgrade(config, RUN_INITIATED_BY_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_initiated_by_schema(connection)
            _assert_initiated_by_data(connection)
    finally:
        get_settings.cache_clear()
