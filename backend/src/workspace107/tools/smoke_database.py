"""Create and remove one disposable PostgreSQL database for the official smoke run."""

from __future__ import annotations

import asyncio
import os
import re
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

_NAME = re.compile(r"workspace107_smoke_[0-9a-f]{32}")
_ADMIN_URL_ENV = "WORKSPACE107_SMOKE_ADMIN_DATABASE_URL"
_DATABASE_NAME_ENV = "WORKSPACE107_SMOKE_DATABASE_NAME"


async def _manage(action: str, database_url: str, name: str) -> str | None:
    if action not in {"create", "drop"}:
        raise ValueError("action must be create or drop")
    if _NAME.fullmatch(name) is None:
        raise ValueError("Refusing to manage a database outside the workspace107_smoke namespace")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Smoke database administration requires PostgreSQL")

    admin_url = url.set(database="postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            if action == "create":
                await connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
                return url.set(database=name).render_as_string(hide_password=False)
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            await connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}"')
            return None
    finally:
        await engine.dispose()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m workspace107.tools.smoke_database create|drop")
    database_url = os.environ.get(_ADMIN_URL_ENV, "")
    name = os.environ.get(_DATABASE_NAME_ENV, "")
    if not database_url or not name:
        raise SystemExit(f"{_ADMIN_URL_ENV} and {_DATABASE_NAME_ENV} are required")
    result = asyncio.run(_manage(sys.argv[1], database_url, name))
    if result is not None:
        print(result)


if __name__ == "__main__":
    main()
