"""Project API 对真实 Git Working State 与 commit Version 的集成行为。"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from workspace107.api.deps import AppContext
from workspace107.config import Settings
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.tables import Base
from workspace107.main import build_context, create_app
from workspace107.tools.seed import seed_catalog

FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


@pytest.fixture
async def git_api(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, AppContext]]:
    settings = Settings(
        env="test",
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        storage_root=tmp_path / "storage",
        scheduler="mock",
        run_sync_interval_seconds=0,
    )
    context = build_context(settings)
    async with context.engine.begin() as connection:
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
        yield client, context
    await context.engine.dispose()


async def test_req_m1_a_project_api_version_restore_fork_and_run_use_exact_commit(
    git_api: tuple[httpx.AsyncClient, AppContext], tmp_path: Path
) -> None:
    client, context = git_api
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "Git Project"}
    )
    assert project_response.status_code == 201
    project = project_response.json()

    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('v1')\n"},
    )
    v1_response = await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "first"}
    )
    assert v1_response.status_code == 201
    v1 = v1_response.json()
    async with context.session_factory() as session:
        row = (
            await session.execute(
                select(t.ProjectVersionRow).where(t.ProjectVersionRow.id == v1["id"])
            )
        ).scalar_one()
        assert FULL_OID.fullmatch(row.commit_oid)
        v1_oid = row.commit_oid

    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('v2')\n"},
    )
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "added.txt", "content": "new"},
    )
    v2 = (
        await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "second"})
    ).json()

    listing = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert [item["id"] for item in listing["items"]] == [v2["id"], v1["id"]]
    detail = (await client.get(f"/api/v1/versions/{v1['id']}")).json()
    assert detail["files"] == [
        {
            "path": "main.py",
            "size": len("print('v1')\n"),
            "content_hash": hashlib.sha256(b"print('v1')\n").hexdigest(),
        }
    ]
    assert "commit_oid" not in detail
    old_content = (
        await client.get(f"/api/v1/versions/{v1['id']}/files/content", params={"path": "main.py"})
    ).json()
    assert old_content["content"] == "print('v1')\n"

    diff = (await client.get(f"/api/v1/versions/{v2['id']}/diff", params={"base": v1["id"]})).json()
    assert diff == [
        {"path": "added.txt", "change": "added"},
        {"path": "main.py", "change": "modified"},
    ]

    restored = await client.post(f"/api/v1/versions/{v1['id']}/restore")
    assert restored.status_code == 200
    assert [item["path"] for item in restored.json()] == ["main.py"]
    forked = (
        await client.post(
            f"/api/v1/versions/{v1['id']}/fork",
            json={"target_workspace_id": workspace_id, "name": "Forked Git Project"},
        )
    ).json()
    fork_content = (
        await client.get(
            f"/api/v1/projects/{forked['id']}/files/content", params={"path": "main.py"}
        )
    ).json()
    assert fork_content["content"] == "print('v1')\n"

    export = tmp_path / "caller-export"
    export.mkdir()
    await context.project_content.export_commit(project["id"], v1_oid, export)
    assert (export / "main.py").read_bytes() == b"print('v1')\n"

    await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": "ev_python_312"},
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "exact version",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
            },
        )
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "raise RuntimeError('working state')\n"},
    )
    run_response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "run_configuration_id": configuration["id"],
            "project_version_id": v1["id"],
        },
    )
    assert run_response.status_code == 201, run_response.text
    run = run_response.json()
    run_file = context.settings.storage_root / "runs" / run["id"] / "work" / "main.py"
    assert run_file.read_bytes() == b"print('v1')\n"

    for _ in range(20):
        await asyncio.sleep(0.05)
        await client.post("/api/v1/runs/sync")
        detail = (await client.get(f"/api/v1/runs/{run['id']}")).json()
        if detail["run"]["status"] in {"succeeded", "failed", "submit_failed"}:
            break
    assert detail["run"]["status"] == "succeeded"
