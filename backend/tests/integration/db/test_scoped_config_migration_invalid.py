from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from workspace107.config import get_settings

PREVIOUS_REVISION = "a3f7c2e91b84"
CONFIG_BASE_REVISION = "e35a1d7c9b20"


def _config(database: Path) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    url = f"sqlite+aiosqlite:///{database}"
    config.set_main_option("sqlalchemy.url", url)
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    get_settings.cache_clear()
    return config


def _base(database: Path) -> tuple[Config, sqlite3.Connection, str]:
    config = _config(database)
    command.upgrade(config, CONFIG_BASE_REVISION)
    connection = sqlite3.connect(database)
    now = "2026-08-21 00:00:00+00:00"
    connection.execute(
        "INSERT INTO users (id,username,display_name,email,created_at) VALUES ('u','u','U',NULL,?)",
        (now,),
    )
    return config, connection, now


def test_scoped_config_upgrade_rejects_orphan_workspace(tmp_path: Path) -> None:
    config, connection, _ = _base(tmp_path / "orphan.db")
    connection.execute("INSERT INTO workspace_variables VALUES ('missing','LEVEL','x')")
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError, match="orphan Workspace config"):
        command.upgrade(config, "head")


def test_scoped_config_upgrade_rejects_group_without_active_owner(tmp_path: Path) -> None:
    config, connection, now = _base(tmp_path / "owner.db")
    connection.execute(
        "INSERT INTO workspaces VALUES ('g','collaborative','G','', 'u', NULL, ?)", (now,)
    )
    connection.execute("INSERT INTO user_groups VALUES ('g','G','',NULL,?)", (now,))
    connection.execute("INSERT INTO workspace_variables VALUES ('g','LEVEL','x')")
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError, match="active owner"):
        command.upgrade(config, "head")


def test_project_scope_downgrade_refuses_and_preserves_scoped_data(tmp_path: Path) -> None:
    database = tmp_path / "project.db"
    config = _config(database)
    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO variables VALUES ('project','p','LEVEL','x')")
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError, match="Project-scoped"):
        command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT scope_kind,scope_id,name,value FROM variables"
    ).fetchall() == [("project", "p", "LEVEL", "x")]
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='variables'"
    ).fetchone() == ("variables",)
    connection.close()


def test_successful_downgrade_restores_legacy_fk_shape(tmp_path: Path) -> None:
    database = tmp_path / "shape.db"
    config, connection, now = _base(database)
    connection.execute(
        "INSERT INTO workspaces VALUES ('p','personal','P','', 'u', NULL, ?)", (now,)
    )
    connection.execute("INSERT INTO workspace_variables VALUES ('p','LEVEL','x')")
    connection.commit()
    connection.close()
    command.upgrade(config, "head")
    command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    cols = {row[1] for row in connection.execute("PRAGMA table_info(workspace_variables)")}
    fks = connection.execute("PRAGMA foreign_key_list(workspace_variables)").fetchall()
    assert cols == {"workspace_id", "name", "value"}
    assert any(row[2] == "workspaces" and row[3] == "workspace_id" for row in fks)
    assert connection.execute(
        "SELECT workspace_id,name,value FROM workspace_variables"
    ).fetchall() == [("p", "LEVEL", "x")]
    connection.close()


def test_downgrade_rejects_project_exact_snapshot_ref_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "project-snapshot.db"
    config = _config(database)
    command.upgrade(config, CONFIG_BASE_REVISION)
    connection = sqlite3.connect(database)
    now = "2026-08-21 00:00:00+00:00"
    connection.execute(
        "INSERT INTO users (id,username,display_name,email,created_at) VALUES ('u','u','U',NULL,?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO workspaces VALUES ('w','personal','W','', 'u', NULL, ?)", (now,)
    )
    connection.execute(
        "INSERT INTO projects (id,workspace_id,name,description,status,"
        "environment_version_id,default_run_configuration_id,created_by,created_at,updated_at) "
        "VALUES ('p','w','P','', 'active',NULL,NULL,'u',?,?)",
        (now, now),
    )
    connection.commit()
    connection.close()
    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO run_snapshots (id,payload) VALUES ('s',?)",
        ('{"project_id":"p","env":{"secret_refs":{"T":"project:p:TOKEN"}}}',),
    )
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError):
        command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    assert (
        "project:p:TOKEN"
        in connection.execute("SELECT payload FROM run_snapshots WHERE id='s'").fetchone()[0]
    )
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='variables'"
    ).fetchone() == ("variables",)
    connection.close()


def test_downgrade_rejects_non_owner_user_snapshot_ref(tmp_path: Path) -> None:
    database = tmp_path / "user-snapshot.db"
    config = _config(database)
    command.upgrade(config, CONFIG_BASE_REVISION)
    connection = sqlite3.connect(database)
    now = "2026-08-21 00:00:00+00:00"
    connection.executemany(
        "INSERT INTO users (id,username,display_name,email,created_at) VALUES (?, ?, ?, NULL, ?)",
        [("owner", "owner", "Owner", now), ("other", "other", "Other", now)],
    )
    connection.execute(
        "INSERT INTO workspaces VALUES ('g','collaborative','G','', 'owner', NULL, ?)", (now,)
    )
    connection.execute("INSERT INTO user_groups VALUES ('g','G','',NULL,?)", (now,))
    connection.execute(
        "INSERT INTO memberships (id,user_group_id,user_id,role,status,created_at) "
        "VALUES ('m','g','owner','owner','active',?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO projects (id,workspace_id,name,description,status,"
        "environment_version_id,default_run_configuration_id,created_by,created_at,updated_at) "
        "VALUES ('p','g','P','', 'active',NULL,NULL,'owner',?,?)",
        (now, now),
    )
    connection.commit()
    connection.close()
    command.upgrade(config, "head")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO run_snapshots (id,payload) VALUES ('s',?)",
        ('{"project_id":"p","env":{"secret_refs":{"T":"user:other:TOKEN"}}}',),
    )
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError):
        command.downgrade(config, PREVIOUS_REVISION)
    connection = sqlite3.connect(database)
    assert (
        "user:other:TOKEN"
        in connection.execute("SELECT payload FROM run_snapshots WHERE id='s'").fetchone()[0]
    )
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='secrets'"
    ).fetchone() == ("secrets",)
    connection.close()
