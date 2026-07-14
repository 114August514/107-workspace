import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def application_tables(database: Path) -> set[str]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'alembic_version'"
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_migration_upgrade_downgrade_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend_root = Path(__file__).resolve().parents[3]
    database = tmp_path / "workspace107.db"
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    monkeypatch.delenv("WORKSPACE107_DATABASE_URL", raising=False)

    command.upgrade(config, "head")
    assert len(application_tables(database)) == 12

    command.downgrade(config, "base")
    assert application_tables(database) == set()

    command.upgrade(config, "head")
    assert len(application_tables(database)) == 12
