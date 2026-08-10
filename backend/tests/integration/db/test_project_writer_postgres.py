"""PostgreSQL production writer lock behavior; requires a disposable test database."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from workspace107.config import Settings
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.tables import Base
from workspace107.main import build_context, create_app
from workspace107.tools.seed import seed_catalog

POSTGRES_URL = os.environ.get("WORKSPACE107_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="WORKSPACE107_TEST_POSTGRES_URL is required for PostgreSQL lock coverage",
)


def _git(project_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", f"--git-dir={project_root / 'repository.git'}", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


async def test_req_m1_a_postgres_concurrent_save_has_one_parent_and_sequence(
    tmp_path: Path,
) -> None:
    assert POSTGRES_URL is not None
    settings = Settings(
        env="test",
        log_level="WARNING",
        database_url=POSTGRES_URL,
        storage_root=tmp_path / "storage",
        scheduler="mock",
        run_sync_interval_seconds=0,
    )
    context = build_context(settings)
    async with context.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with context.session_factory() as session:
        await seed_catalog(session)
        await session.commit()

    app = create_app(settings)
    app.state.context = context
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-User": "student"},
    ) as client:
        workspace_id = (await client.get("/api/v1/me")).json()["workspaces"][0]["id"]
        project = (
            await client.post(
                f"/api/v1/workspaces/{workspace_id}/projects",
                json={"name": "PostgreSQL Writer Lock"},
            )
        ).json()
        await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": "main.py", "content": "print(1)\n"},
        )

        first = await asyncio.gather(
            client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json={"message": "first-a"},
            ),
            client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json={"message": "first-b"},
            ),
        )
        assert sorted(response.status_code for response in first) == [201, 409]

        await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": "main.py", "content": "print(2)\n"},
        )
        second = await asyncio.gather(
            client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json={"message": "second-a"},
            ),
            client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json={"message": "second-b"},
            ),
        )
        assert sorted(response.status_code for response in second) == [201, 409]

    async with context.session_factory() as session:
        versions = (
            (
                await session.execute(
                    select(t.ProjectVersionRow)
                    .where(t.ProjectVersionRow.project_id == project["id"])
                    .order_by(t.ProjectVersionRow.sequence)
                )
            )
            .scalars()
            .all()
        )
    assert [version.sequence for version in versions] == [1, 2]
    assert len({version.commit_oid for version in versions}) == 2
    project_root = settings.storage_root / "projects" / project["id"]
    parent = _git(
        project_root,
        "show",
        "--no-patch",
        "--format=%P",
        versions[1].commit_oid,
    ).stdout.strip()
    assert parent == versions[0].commit_oid
    for version in versions:
        assert (
            _git(
                project_root,
                "show-ref",
                "--verify",
                f"refs/workspace107/versions/{version.id}",
            ).returncode
            == 0
        )
