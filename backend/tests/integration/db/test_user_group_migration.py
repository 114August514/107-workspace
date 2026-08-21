from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "a3f7c2e91b84"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _rows(connection: sqlite3.Connection, sql: str) -> list[tuple[object, ...]]:
    return list(connection.execute(sql).fetchall())


def test_user_group_migration_preserves_real_data_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)
    command.upgrade(config, PREVIOUS_REVISION)

    connection = sqlite3.connect(database)
    now = "2026-08-17 00:00:00+00:00"
    connection.executemany(
        "INSERT INTO users "
        "(id, username, display_name, email, created_at) VALUES (?, ?, ?, NULL, ?)",
        [
            ("usr_alice", "alice", "Alice", now),
            ("usr_bob", "bob", "Bob", now),
            ("usr_carol", "carol", "Carol", now),
        ],
    )
    connection.executemany(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, "
        "default_environment_version_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?)",
        [
            ("ws_personal", "personal", "Alice personal", "keep", "usr_alice", now),
            ("ws_collab", "collaborative", "Research Lab", "migrate", "usr_alice", now),
        ],
    )
    connection.executemany(
        "INSERT INTO memberships "
        "(id, workspace_id, user_id, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("mbr_personal", "ws_personal", "usr_alice", "owner", "active", now),
            ("mbr_alice", "ws_collab", "usr_alice", "member", "left", now),
            ("mbr_bob", "ws_collab", "usr_bob", "owner", "active", now),
        ],
    )
    connection.execute(
        "INSERT INTO projects "
        "(id, workspace_id, name, description, status, environment_version_id, "
        "default_run_configuration_id, created_by, created_at, updated_at) "
        "VALUES ('prj_personal', 'ws_personal', 'Keep me', '', 'active', "
        "NULL, NULL, 'usr_alice', ?, ?)",
        (now, now),
    )
    connection.executemany(
        "INSERT INTO workspace_variables (workspace_id, name, value) VALUES (?, ?, ?)",
        [("ws_personal", "LEVEL", "personal"), ("ws_collab", "LEVEL", "collab")],
    )
    connection.executemany(
        "INSERT INTO workspace_secrets (workspace_id, name, value, updated_at) VALUES (?, ?, ?, ?)",
        [
            ("ws_personal", "TOKEN", "personal-secret", now),
            ("ws_collab", "TOKEN", "collab-secret", now),
        ],
    )
    connection.execute(
        "INSERT INTO run_snapshots (id, payload) VALUES (?, ?)",
        (
            "snap_1",
            '{"project_id":"prj_personal","env":{"literals":{"A":"1"},"secret_refs":{"T":"TOKEN"}}}',
        ),
    )
    connection.commit()
    connection.close()

    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    assert _rows(connection, "SELECT id FROM user_groups ORDER BY id") == [("ws_collab",)]
    assert _rows(connection, "SELECT created_by_id FROM user_groups WHERE id='ws_collab'") == [
        (None,)
    ]
    assert _rows(
        connection,
        "SELECT user_id, role, status FROM memberships "
        "WHERE user_group_id='ws_collab' ORDER BY user_id",
    ) == [("usr_alice", "owner", "active"), ("usr_bob", "admin", "active")]
    assert _rows(connection, "SELECT id, kind FROM workspaces ORDER BY id") == [
        ("ws_collab", "collaborative"),
        ("ws_personal", "personal"),
    ]
    assert _rows(
        connection,
        "SELECT scope_kind, scope_id, name, value FROM variables ORDER BY scope_kind, scope_id",
    ) == [
        ("user", "usr_alice", "LEVEL", "personal"),
        ("user_group", "ws_collab", "LEVEL", "collab"),
    ]
    assert _rows(
        connection,
        "SELECT scope_kind, scope_id, name, value FROM secrets ORDER BY scope_kind, scope_id",
    ) == [
        ("user", "usr_alice", "TOKEN", "personal-secret"),
        ("user_group", "ws_collab", "TOKEN", "collab-secret"),
    ]
    snapshot_payload = connection.execute(
        "SELECT payload FROM run_snapshots WHERE id='snap_1'"
    ).fetchone()[0]
    assert "user:usr_alice:TOKEN" in str(snapshot_payload)
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='run_secret_redactions'"
    ).fetchone() == ("run_secret_redactions",)
    assert "personal-secret" not in str(snapshot_payload)
    assert _rows(connection, "SELECT id, workspace_id FROM projects") == [
        ("prj_personal", "ws_personal")
    ]
    assert _rows(
        connection,
        "SELECT id, workspace_id, user_id, role, status FROM legacy_personal_memberships",
    ) == [("mbr_personal", "ws_personal", "usr_alice", "owner", "active")]

    connection.execute("UPDATE user_groups SET name='Renamed Lab' WHERE id='ws_collab'")
    connection.execute(
        "UPDATE memberships SET role='admin' "
        "WHERE user_group_id='ws_collab' AND user_id='usr_alice'"
    )
    connection.execute(
        "UPDATE memberships SET role='owner' WHERE user_group_id='ws_collab' AND user_id='usr_bob'"
    )
    connection.execute(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, "
        "default_environment_version_id, created_at) "
        "VALUES ('grp_new', 'collaborative', 'New Group', '', "
        "'usr_bob', NULL, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO user_groups "
        "(id, name, description, created_by_id, created_at) "
        "VALUES ('grp_new', 'New Group', '', 'usr_carol', ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO memberships "
        "(id, user_group_id, user_id, role, status, created_at) VALUES "
        "('mbr_new_carol', 'grp_new', 'usr_carol', 'admin', 'active', ?), "
        "('mbr_new_bob', 'grp_new', 'usr_bob', 'owner', 'active', ?)",
        (now, now),
    )
    connection.commit()
    connection.close()

    command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    downgraded_snapshot = connection.execute(
        "SELECT payload FROM run_snapshots WHERE id='snap_1'"
    ).fetchone()[0]
    assert '"literals": {"A": "1"}' in str(downgraded_snapshot)
    assert '"secret_refs": {"T": "TOKEN"}' in str(downgraded_snapshot)
    assert _rows(
        connection,
        "SELECT id, name, owner_id FROM workspaces WHERE kind='collaborative' ORDER BY id",
    ) == [("grp_new", "New Group", "usr_bob"), ("ws_collab", "Renamed Lab", "usr_bob")]
    assert _rows(connection, "SELECT id, name FROM workspaces WHERE kind='personal'") == [
        ("ws_personal", "Alice personal")
    ]
    assert _rows(
        connection,
        "SELECT workspace_id, user_id, role, status FROM memberships "
        "ORDER BY workspace_id, user_id",
    ) == [
        ("grp_new", "usr_bob", "owner", "active"),
        ("grp_new", "usr_carol", "admin", "active"),
        ("ws_collab", "usr_alice", "admin", "active"),
        ("ws_collab", "usr_bob", "owner", "active"),
        ("ws_personal", "usr_alice", "owner", "active"),
    ]
    assert _rows(connection, "SELECT id, workspace_id FROM projects") == [
        ("prj_personal", "ws_personal")
    ]
    connection.close()

    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    assert _rows(connection, "SELECT id FROM user_groups ORDER BY id") == [
        ("grp_new",),
        ("ws_collab",),
    ]
    assert _rows(connection, "SELECT id, workspace_id FROM projects") == [
        ("prj_personal", "ws_personal")
    ]
    assert _rows(
        connection,
        "SELECT created_by_id FROM user_groups WHERE id='grp_new'",
    ) == [("usr_carol",)]
    assert _rows(
        connection,
        "SELECT id, workspace_id, user_id, role, status FROM legacy_personal_memberships",
    ) == [("mbr_personal", "ws_personal", "usr_alice", "owner", "active")]
    upgraded_snapshot = connection.execute(
        "SELECT payload FROM run_snapshots WHERE id='snap_1'"
    ).fetchone()[0]
    assert '"literals": {"A": "1"}' in str(upgraded_snapshot)
    assert '"secret_refs": {"T": "user:usr_alice:TOKEN"}' in str(upgraded_snapshot)
    connection.close()
