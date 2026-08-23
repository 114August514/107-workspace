from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL"), reason="URL missing"
)


def _config(url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


async def _migrate(config: Config, revision: str, downgrade: bool = False) -> None:
    await asyncio.to_thread(command.downgrade if downgrade else command.upgrade, config, revision)


@pytest.mark.asyncio
async def test_postgresql_scoped_config_structural_roundtrip() -> None:
    url = os.environ["WORKSPACE107_TEST_POSTGRESQL_URL"]
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    engine = create_async_engine(url)
    try:
        config = _config(url)
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        await _migrate(config, "head")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO variables VALUES "
                    "('user','u','A','1'), ('user_group','g','A','2'), ('project','p','A','3')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO secrets VALUES "
                    "('user','u','S','1',CURRENT_TIMESTAMP), "
                    "('user_group','g','S','2',CURRENT_TIMESTAMP), "
                    "('project','p','S','3',CURRENT_TIMESTAMP)"
                )
            )
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM variables"))
            ).scalar_one() == 3
            assert (
                await connection.execute(text("SELECT count(*) FROM secrets"))
            ).scalar_one() == 3
        await _migrate(config, "c471ac39f002", downgrade=True)
        await _migrate(config, "head")
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM variables"))
            ).scalar_one() == 0
            assert (
                await connection.execute(text("SELECT count(*) FROM secrets"))
            ).scalar_one() == 0
            assert (
                await connection.execute(text("SELECT to_regclass('public.variables')"))
            ).scalar_one() == "variables"
    finally:
        await engine.dispose()
