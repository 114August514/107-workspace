"""Grants table migration (Issue #40)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "c471ac39f002"
GRANTS_REVISION = "1f61cd1dc3ac"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _indexes(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA index_list({table})")}


def _index_columns(connection: sqlite3.Connection, table: str, index: str) -> list[str]:
    return [str(row[2]) for row in connection.execute(f"PRAGMA index_info({index})")]


def _unique_constraints(connection: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of unique index names (sqlite implements UNIQUE constraints as indexes)."""
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA index_list({table})")
        if int(row[2]) == 1  # origin == "u" (unique constraint)
    }


def _foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str, str]]:
    return {
        (str(row[3]), str(row[2]), str(row[6]).upper())
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def test_grants_migration_creates_table_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upgrade creates the grants table; downgrade drops it."""
    database = tmp_path / "grants.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()

    config = _config(database)

    # Upgrade to the previous revision (before grants).
    command.upgrade(config, PREVIOUS_REVISION)

    with sqlite3.connect(str(database)) as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='grants'"
        ).fetchone()
        assert table_exists is None

    # Upgrade to the grants revision.
    command.upgrade(config, GRANTS_REVISION)

    with sqlite3.connect(str(database)) as conn:
        # Table exists with expected columns.
        expected_columns = {
            "id",
            "grantee_kind",
            "grantee_id",
            "target_kind",
            "target_id",
            "action",
            "granted_by_id",
            "created_at",
        }
        assert expected_columns <= _columns(conn, "grants")

        # Foreign key: granted_by_id → users.id (RESTRICT).
        fks = _foreign_keys(conn, "grants")
        assert ("granted_by_id", "users", "RESTRICT") in fks

        # Unique constraint over (grantee_kind, grantee_id, target_kind, target_id, action).
        # SQLite names these sqlite_autoindex_*; verify by column set instead of name.
        unique_index_names = _unique_constraints(conn, "grants")
        unique_col_sets: list[list[str]] = []
        for idx_name in unique_index_names:
            unique_col_sets.append(_index_columns(conn, "grants", idx_name))
        assert sorted(["grantee_kind", "grantee_id", "target_kind", "target_id", "action"]) in (
            sorted(cols) for cols in unique_col_sets
        )

        # Indexes: ix_grants_target, ix_grants_grantee.
        indexes = _indexes(conn, "grants")
        assert "ix_grants_target" in indexes
        assert "ix_grants_grantee" in indexes

    # Downgrade back to previous revision.
    command.downgrade(config, PREVIOUS_REVISION)

    with sqlite3.connect(str(database)) as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='grants'"
        ).fetchone()
        assert table_exists is None

    get_settings.cache_clear()
