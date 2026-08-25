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

EXECUTION_TABLES = (
    "idempotency_keys",
    "run_secret_redactions",
    "run_events",
    "artifacts",
    "runs",
    "run_snapshots",
    "run_configurations",
)


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _table_info(connection: sqlite3.Connection, table: str) -> dict[str, tuple[int, int]]:
    return {
        str(row[1]): (int(row[3]), int(row[5]))
        for row in connection.execute(f"PRAGMA table_info({table})")
    }


def _foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str]]:
    return {
        (str(row[3]), str(row[2]))
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def _seed_project(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executemany(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES (?, ?, ?, NULL, ?)",
        [("usr_alice", "alice", "Alice", NOW), ("usr_bob", "bob", "Bob", NOW)],
    )
    connection.execute(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, default_environment_version_id, created_at) "
        "VALUES ('ws_lab', 'personal', 'Lab', '', 'usr_alice', NULL, ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO projects "
        "(id, workspace_id, owner_user_id, owner_user_group_id, name, description, status, "
        "visibility, environment_version_id, default_run_configuration_id, created_by, "
        "created_at, updated_at) VALUES ('prj_lab', 'ws_lab', 'usr_alice', NULL, "
        "'Lab project', '', 'active', 'owner_scope', NULL, NULL, 'usr_alice', ?, ?)",
        (NOW, NOW),
    )


def _seed_execution_state(connection: sqlite3.Connection, identity_column: str) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO run_configurations "
        "(id, project_id, name, description, working_directory, command, environment_version_id, "
        "environment_variables, input_bindings, compute_plan_id, compute_request, artifact_rules) "
        "VALUES ('cfg_1', 'prj_lab', 'config', '', '.', 'true', 'env_v1', '{}', '[]', "
        "'plan_1', NULL, '[]')"
    )
    connection.execute(
        "UPDATE projects SET default_run_configuration_id = 'cfg_1' WHERE id = 'prj_lab'"
    )
    connection.execute("INSERT INTO run_snapshots (id, payload) VALUES ('snap_1', '{}')")
    run_identity_column = (
        "created_by" if identity_column == "workspace_id" else "initiated_by_user_id"
    )
    connection.execute(
        "INSERT INTO runs "
        "(id, project_id, workspace_id, snapshot_id, compute_plan_id, project_version_id, "
        "project_version_label, source_run_configuration_id, source_run_id, name, status, "
        f"failure_reason, {run_identity_column}, created_at) "
        "VALUES ('run_1', 'prj_lab', 'ws_lab', 'snap_1', 'plan_1', 'pv_1', 'v1', "
        "'cfg_1', NULL, 'run', 'succeeded', '', 'usr_alice', ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO run_secret_redactions (run_id, value_digest, value) "
        "VALUES ('run_1', 'digest', 'secret')"
    )
    connection.execute(
        "INSERT INTO run_events (id, run_id, type, message, created_at) "
        "VALUES ('event_1', 'run_1', 'created', '', ?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO artifacts "
        "(id, run_id, project_id, workspace_id, name, source_path, size, file_count, "
        "content_hash, status, description, created_at, cleaned_at) "
        "VALUES ('artifact_1', 'run_1', 'prj_lab', 'ws_lab', 'output', 'output', 1, 1, "
        "'hash', 'available', '', ?, NULL)",
        (NOW,),
    )
    connection.execute(
        f"INSERT INTO idempotency_keys ({identity_column}, key, endpoint, run_id, created_at) "
        "VALUES (?, 'seed-key', 'create_run', 'run_1', ?)",
        (("ws_lab" if identity_column == "workspace_id" else "usr_alice"), NOW),
    )
    connection.commit()


def _assert_state_cleared(connection: sqlite3.Connection) -> None:
    for table in EXECUTION_TABLES:
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
    assert connection.execute(
        "SELECT COUNT(*) FROM projects WHERE default_run_configuration_id IS NOT NULL"
    ).fetchone() == (0,)
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (2,)
    assert connection.execute("SELECT COUNT(*) FROM workspaces").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM projects").fetchone() == (1,)


def _assert_current_schema(connection: sqlite3.Connection) -> None:
    runs = _table_info(connection, "runs")
    assert "initiated_by_user_id" in runs
    assert "created_by" not in runs
    assert _table_info(connection, "run_configurations")["environment_version_id"][0] == 1

    idempotency = _table_info(connection, "idempotency_keys")
    assert set(idempotency) == {
        "initiated_by_user_id",
        "key",
        "endpoint",
        "run_id",
        "created_at",
    }
    assert [name for name, (_, order) in idempotency.items() if order] == [
        "initiated_by_user_id",
        "key",
    ]
    assert ("initiated_by_user_id", "users") in _foreign_keys(connection, "idempotency_keys")


def _assert_predecessor_schema(connection: sqlite3.Connection) -> None:
    runs = _table_info(connection, "runs")
    assert "created_by" in runs
    assert "initiated_by_user_id" not in runs
    assert _table_info(connection, "run_configurations")["environment_version_id"][0] == 0

    idempotency = _table_info(connection, "idempotency_keys")
    assert set(idempotency) == {"workspace_id", "key", "endpoint", "run_id", "created_at"}
    assert [name for name, (_, order) in idempotency.items() if order] == [
        "workspace_id",
        "key",
    ]
    assert ("workspace_id", "workspaces") in _foreign_keys(connection, "idempotency_keys")


def test_issue_41_migration_is_a_destructive_schema_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "run-initiated-by.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _seed_project(connection)
            _seed_execution_state(connection, "workspace_id")

        command.upgrade(config, RUN_INITIATED_BY_REVISION)
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            _assert_current_schema(connection)
            _assert_state_cleared(connection)

            _seed_execution_state(connection, "initiated_by_user_id")
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO idempotency_keys "
                    "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                    "VALUES ('usr_alice', 'seed-key', 'create_run', NULL, ?)",
                    (NOW,),
                )
            connection.execute(
                "INSERT INTO idempotency_keys "
                "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                "VALUES ('usr_bob', 'seed-key', 'create_run', NULL, ?)",
                (NOW,),
            )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO idempotency_keys "
                    "(initiated_by_user_id, key, endpoint, run_id, created_at) "
                    "VALUES ('usr_missing', 'other-key', 'create_run', NULL, ?)",
                    (NOW,),
                )
            connection.commit()

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_predecessor_schema(connection)
            _assert_state_cleared(connection)

        command.upgrade(config, RUN_INITIATED_BY_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_current_schema(connection)
            _assert_state_cleared(connection)
    finally:
        get_settings.cache_clear()
