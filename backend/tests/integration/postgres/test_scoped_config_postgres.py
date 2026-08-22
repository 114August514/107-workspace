from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL"),
    reason="WORKSPACE107_TEST_POSTGRESQL_URL is not set",
)


def _url() -> str:
    return os.environ["WORKSPACE107_TEST_POSTGRESQL_URL"]


def _config(url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


async def _migrate(config: Config, revision: str, *, downgrade: bool = False) -> None:
    operation = command.downgrade if downgrade else command.upgrade
    await asyncio.to_thread(operation, config, revision)


async def _reset_to_e35(engine, config: Config) -> datetime:
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await _migrate(config, "e35a1d7c9b20")
    now = datetime(2026, 8, 21, tzinfo=UTC)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,created_at) VALUES ('u','u','U',:now)"
            ),
            {"now": now},
        )
        await connection.execute(
            text(
                "INSERT INTO workspaces VALUES ('w','personal','W','', 'u', NULL, :now), ('g','collaborative','G','', 'u', NULL, :now)"  # noqa: E501
            ),
            {"now": now},
        )
        await connection.execute(
            text("INSERT INTO user_groups VALUES ('g','G','',NULL,:now)"), {"now": now}
        )
        await connection.execute(
            text(
                "INSERT INTO memberships (id,user_group_id,user_id,role,status,created_at) VALUES ('m','g','u','owner','active',:now)"  # noqa: E501
            ),
            {"now": now},
        )
        await connection.execute(
            text(
                "INSERT INTO projects (id,workspace_id,name,description,status,created_by,created_at,updated_at) VALUES ('p','w','P','', 'active','u',:now,:now)"  # noqa: E501
            ),
            {"now": now},
        )
    return now


@pytest.mark.asyncio
async def test_postgresql_scoped_config_roundtrip() -> None:
    url = _url()
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    engine = create_async_engine(url)
    config = _config(url)
    try:
        now = await _reset_to_e35(engine, config)
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO workspace_variables VALUES ('w','LEVEL','x'), ('g','LEVEL','y')")
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_secrets VALUES ('w','TOKEN','secret-w',:now), ('g','TOKEN','secret-g',:now)"  # noqa: E501
                ),
                {"now": now},
            )
            snapshot_payload = (
                '{"project_id":"p","env":{"literals":{"A":"1"},'
                '"secret_refs":{"T":"TOKEN","U":"TOKEN"}}}'
            )
            await connection.execute(
                text("INSERT INTO run_snapshots (id,payload) VALUES ('s',CAST(:payload AS json))"),
                {"payload": snapshot_payload},
            )
            await connection.execute(
                text(
                    "INSERT INTO runs (id,project_id,workspace_id,snapshot_id,compute_plan_id,"
                    "project_version_id,project_version_label,name,status,failure_reason,"
                    "created_by,created_at,submitted_at) VALUES ('r','p','w','s','plan_cpu_quick',"
                    "'pv','v1','R','succeeded','', 'u',:now,:now)"
                ),
                {"now": now},
            )
        await _migrate(config, "head")
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        "SELECT scope_kind,scope_id,name FROM variables "
                        "ORDER BY scope_kind,scope_id"
                    )
                )
            ).all() == [("user", "u", "LEVEL"), ("user_group", "g", "LEVEL")]
            assert (
                await connection.execute(
                    text(
                        "SELECT scope_kind,scope_id,name FROM secrets ORDER BY scope_kind,scope_id"
                    )
                )
            ).all() == [("user", "u", "TOKEN"), ("user_group", "g", "TOKEN")]
            assert (
                await connection.execute(
                    text(
                        "SELECT jsonb_typeof(payload::jsonb), "
                        "payload::jsonb->'env'->'secret_refs'->>'T' FROM run_snapshots"
                    )
                )
            ).one() == ("object", "user:u:TOKEN")
            assert (
                await connection.execute(
                    text("SELECT run_id,value,value_digest FROM run_secret_redactions")
                )
            ).all() == [("r", "secret-w", hashlib.sha256(b"secret-w").hexdigest())]
            assert (
                await connection.execute(text("SELECT payload::text FROM run_snapshots"))
            ).scalar_one().find("secret-w") == -1
            constraints = (
                (
                    await connection.execute(
                        text(
                            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE conrelid='run_secret_redactions'::regclass"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert any("PRIMARY KEY (run_id, value_digest)" in value for value in constraints)
            assert any(
                "FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE" in value
                for value in constraints
            )
        await _migrate(config, "e35a1d7c9b20", downgrade=True)
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT payload::jsonb->'env'->'secret_refs'->>'T' FROM run_snapshots")
                )
            ).scalar_one() == "TOKEN"
        await _migrate(config, "head")
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        "SELECT jsonb_typeof(payload::jsonb), "
                        "payload::jsonb->'env'->'secret_refs'->>'T' FROM run_snapshots"
                    )
                )
            ).one() == ("object", "user:u:TOKEN")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_project_downgrade_refusal_preserves_data() -> None:
    url = _url()
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    engine = create_async_engine(url)
    config = _config(url)
    try:
        await _reset_to_e35(engine, config)
        await _migrate(config, "head")
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO variables VALUES ('project','p','LEVEL','x')")
            )
            await connection.execute(
                text("INSERT INTO run_snapshots (id,payload) VALUES ('s',CAST(:payload AS json))"),
                {"payload": '{"project_id":"p","env":{"secret_refs":{"T":"project:p:TOKEN"}}}'},
            )
        with pytest.raises(RuntimeError):
            await _migrate(config, "e35a1d7c9b20", downgrade=True)
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT value FROM variables WHERE scope_kind='project'")
                )
            ).scalar_one() == "x"
            assert (
                await connection.execute(
                    text(
                        "SELECT jsonb_typeof(payload::jsonb),payload::jsonb->'env'->'secret_refs'->>'T' FROM run_snapshots"  # noqa: E501
                    )
                )
            ).one() == ("object", "project:p:TOKEN")
            assert (
                await connection.execute(text("SELECT to_regclass('public.run_secret_redactions')"))
            ).scalar_one() == "run_secret_redactions"
    finally:
        await engine.dispose()
