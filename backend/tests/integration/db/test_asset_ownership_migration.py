from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "e35a1d7c9b20"
ASSET_OWNERSHIP_REVISION = "c471ac39f002"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str, str]]:
    return {
        (str(row[3]), str(row[2]), str(row[6]).upper())
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def _asset_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "environments",
        "environment_versions",
        "shared_resources",
        "shared_resource_versions",
        "shared_resource_version_files",
    )
    return {
        table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _exact_references(connection: sqlite3.Connection) -> dict[str, object]:
    workspace_ref = connection.execute(
        "SELECT default_environment_version_id FROM workspaces WHERE id = 'ws_legacy'"
    ).fetchone()[0]
    project_ref = connection.execute(
        "SELECT environment_version_id FROM projects WHERE id = 'prj_legacy'"
    ).fetchone()[0]
    run_configuration = connection.execute(
        "SELECT environment_version_id, input_bindings FROM run_configurations "
        "WHERE id = 'rc_legacy'"
    ).fetchone()
    snapshot_payload = connection.execute(
        "SELECT payload FROM run_snapshots WHERE id = 'snap_legacy'"
    ).fetchone()[0]
    return {
        "workspace": workspace_ref,
        "project": project_ref,
        "run_configuration_environment": run_configuration[0],
        "run_configuration_bindings": json.loads(run_configuration[1]),
        "snapshot": json.loads(snapshot_payload),
    }


def _seed_predecessor(connection: sqlite3.Connection) -> dict[str, object]:
    now = "2026-08-18 17:07:00+00:00"
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO users (id, username, display_name, email, created_at) "
        "VALUES ('usr_legacy', 'legacy', 'Legacy User', NULL, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO workspaces "
        "(id, kind, name, description, owner_id, default_environment_version_id, created_at) "
        "VALUES ('ws_legacy', 'personal', 'Legacy Workspace', '', 'usr_legacy', "
        "'ev_legacy_exact', ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO projects "
        "(id, workspace_id, name, description, status, environment_version_id, "
        "default_run_configuration_id, created_by, created_at, updated_at) "
        "VALUES ('prj_legacy', 'ws_legacy', 'Legacy Project', '', 'active', "
        "'ev_legacy_exact', 'rc_legacy', 'usr_legacy', ?, ?)",
        (now, now),
    )
    input_bindings = [
        {
            "source_type": "shared_resource_version",
            "source_id": "shrv_legacy_exact",
            "target_path": "inputs/data",
        }
    ]
    connection.execute(
        "INSERT INTO run_configurations "
        "(id, project_id, name, description, working_directory, command, "
        "environment_version_id, environment_variables, input_bindings, compute_plan_id, "
        "compute_request, artifact_rules) VALUES "
        "('rc_legacy', 'prj_legacy', 'Legacy Config', '', '.', 'python train.py', "
        "'ev_legacy_exact', '{}', ?, 'plan_missing_but_not_fk', NULL, '[]')",
        (json.dumps(input_bindings),),
    )
    snapshot = {
        "environment_version_id": "ev_legacy_exact",
        "input_bindings": input_bindings,
    }
    connection.execute(
        "INSERT INTO run_snapshots (id, payload) VALUES ('snap_legacy', ?)",
        (json.dumps(snapshot),),
    )
    connection.execute(
        "INSERT INTO environments (id, name, description, owner_workspace_id) "
        "VALUES ('env_legacy', 'Legacy Environment', '', NULL)"
    )
    connection.execute(
        "INSERT INTO environment_versions "
        "(id, environment_id, version, description, image, setup_command, available) "
        "VALUES ('ev_legacy_exact', 'env_legacy', '1', '', 'legacy:image', '', 1)"
    )
    connection.execute(
        "INSERT INTO shared_resources "
        "(id, name, description, owner_workspace_id, created_at) "
        "VALUES ('shr_legacy', 'Legacy Resource', '', NULL, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO shared_resource_versions "
        "(id, shared_resource_id, sequence, description, created_by, created_at) "
        "VALUES ('shrv_legacy_exact', 'shr_legacy', 1, '', 'usr_legacy', ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO shared_resource_version_files "
        "(version_id, path, size, content_hash) VALUES "
        "('shrv_legacy_exact', 'data.txt', 4, ?)",
        ("a" * 64,),
    )
    connection.commit()
    return _exact_references(connection)


def _assert_owner_schema(connection: sqlite3.Connection) -> None:
    for table in ("environments", "shared_resources"):
        columns = _columns(connection, table)
        assert {"owner_user_id", "owner_user_group_id"} <= columns
        assert "owner_workspace_id" not in columns

    expected_fks = {
        ("owner_user_id", "users", "RESTRICT"),
        ("owner_user_group_id", "user_groups", "RESTRICT"),
    }
    assert expected_fks <= _foreign_keys(connection, "environments")
    assert expected_fks <= _foreign_keys(connection, "shared_resources")


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


def test_issue_39_asset_ownership_migration_is_destructive_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "asset-ownership.db"
    blob = tmp_path / "storage" / "blobs" / ("b" * 64)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"must survive database migration")
    monkeypatch.setenv("WORKSPACE107_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()
    config = _config(database)

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            exact_references = _seed_predecessor(connection)
            assert _asset_counts(connection) == {
                "environments": 1,
                "environment_versions": 1,
                "shared_resources": 1,
                "shared_resource_versions": 1,
                "shared_resource_version_files": 1,
            }

        command.upgrade(config, ASSET_OWNERSHIP_REVISION)
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            assert _asset_counts(connection) == {
                "environments": 0,
                "environment_versions": 0,
                "shared_resources": 0,
                "shared_resource_versions": 0,
                "shared_resource_version_files": 0,
            }
            _assert_owner_schema(connection)
            assert _exact_references(connection) == exact_references

            now = "2026-08-18 18:00:00+00:00"
            connection.execute(
                "INSERT INTO users (id, username, display_name, email, created_at) "
                "VALUES ('usr_asset_owner', 'asset-owner', 'Asset Owner', NULL, ?)",
                (now,),
            )
            connection.execute(
                "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
                "VALUES ('grp_asset_owner', 'Asset Group', '', NULL, ?)",
                (now,),
            )
            connection.execute(
                "INSERT INTO environments "
                "(id, name, description, owner_user_id, owner_user_group_id) "
                "VALUES ('env_new', 'New Environment', '', 'usr_asset_owner', NULL)"
            )
            connection.execute(
                "INSERT INTO shared_resources "
                "(id, name, description, owner_user_id, owner_user_group_id, created_at) "
                "VALUES ('shr_new', 'New Resource', '', NULL, 'grp_asset_owner', ?)",
                (now,),
            )
            for table, id_column, extra_columns, extra_values in (
                ("environments", "env", "", ()),
                ("shared_resources", "shr", ", created_at", (now,)),
            ):
                placeholders = ", ?" if extra_values else ""
                _assert_integrity_error(
                    connection,
                    f"INSERT INTO {table} "
                    f"(id, name, description, owner_user_id, owner_user_group_id{extra_columns}) "
                    f"VALUES ('{id_column}_both', 'Invalid', '', "
                    f"'usr_asset_owner', 'grp_asset_owner'{placeholders})",
                    extra_values,
                )
                _assert_integrity_error(
                    connection,
                    f"INSERT INTO {table} "
                    f"(id, name, description, owner_user_id, owner_user_group_id{extra_columns}) "
                    f"VALUES ('{id_column}_neither', 'Invalid', '', NULL, NULL{placeholders})",
                    extra_values,
                )
            _assert_integrity_error(connection, "DELETE FROM users WHERE id = 'usr_asset_owner'")
            _assert_integrity_error(
                connection, "DELETE FROM user_groups WHERE id = 'grp_asset_owner'"
            )
            connection.commit()

        assert blob.read_bytes() == b"must survive database migration"

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database) as connection:
            for table in ("environments", "shared_resources"):
                columns = _columns(connection, table)
                assert "owner_workspace_id" in columns
                assert {"owner_user_id", "owner_user_group_id"}.isdisjoint(columns)
            assert _asset_counts(connection) == {
                "environments": 0,
                "environment_versions": 0,
                "shared_resources": 0,
                "shared_resource_versions": 0,
                "shared_resource_version_files": 0,
            }
            assert _exact_references(connection) == exact_references

        command.upgrade(config, ASSET_OWNERSHIP_REVISION)
        with sqlite3.connect(database) as connection:
            _assert_owner_schema(connection)
            assert _asset_counts(connection) == {
                "environments": 0,
                "environment_versions": 0,
                "shared_resources": 0,
                "shared_resource_versions": 0,
                "shared_resource_version_files": 0,
            }
            assert _exact_references(connection) == exact_references
        assert blob.read_bytes() == b"must survive database migration"
    finally:
        get_settings.cache_clear()
