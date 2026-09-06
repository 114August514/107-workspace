from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "d71f3a9c2b4e"
CURRENT_REVISION = "e8a1c4d2f6b9"
NOW = "2026-09-04 00:00:00+00:00"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _seed_entitlement(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO users (id, username, display_name, email, created_at) "
            "VALUES ('usr_alice', 'alice', 'Alice', NULL, ?)",
            (NOW,),
        )
        connection.execute(
            "INSERT INTO compute_plans ("
            "id, code, name, description, default_nodes, default_cpus, default_memory_mb, "
            "default_gpus, default_time_limit_minutes, max_nodes, max_cpus, max_memory_mb, "
            "max_gpus, max_time_limit_minutes, cluster, account, partition, qos"
            ") VALUES ("
            "'plan_cpu', 'cpu', 'CPU', '', 1, 1, 1024, 0, 10, 1, 4, 4096, 0, 60, "
            "'cluster', 'account', 'partition', 'qos'"
            ")"
        )
        connection.execute(
            "INSERT INTO resource_entitlements "
            "(id, user_id, compute_plan_id, max_concurrent_runs, expires_at) "
            "VALUES ('ent_alice', 'usr_alice', 'plan_cpu', 7, NULL)"
        )
        connection.commit()


def _columns(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        return {
            str(row[1]) for row in connection.execute("PRAGMA table_info(resource_entitlements)")
        }


def _entitlement(database: Path) -> tuple[str, str, str, int | None]:
    with sqlite3.connect(database) as connection:
        has_concurrency = "max_concurrent_runs" in _columns(database)
        columns = "id, user_id, compute_plan_id"
        if has_concurrency:
            columns += ", max_concurrent_runs"
        row = connection.execute(
            f"SELECT {columns} FROM resource_entitlements WHERE id='ent_alice'"
        ).fetchone()
    assert row is not None
    if has_concurrency:
        return str(row[0]), str(row[1]), str(row[2]), int(row[3])
    return str(row[0]), str(row[1]), str(row[2]), None


def test_issue_49_migration_round_trips_nonempty_entitlements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "remove-entitlement-concurrency.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        _seed_entitlement(database)

        command.upgrade(config, CURRENT_REVISION)
        assert _entitlement(database) == ("ent_alice", "usr_alice", "plan_cpu", None)

        command.downgrade(config, PREVIOUS_REVISION)
        assert _entitlement(database) == ("ent_alice", "usr_alice", "plan_cpu", 1)

        command.upgrade(config, CURRENT_REVISION)
        assert _entitlement(database) == ("ent_alice", "usr_alice", "plan_cpu", None)
    finally:
        get_settings.cache_clear()
