"""HTTP Run submission commits only durable intent; Worker remains a separate process."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from workspace107.api.deps import AppContext, Services, build_services, get_services
from workspace107.config import Settings
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.tables import Base
from workspace107.main import build_context, create_app
from workspace107.tools.seed import seed_catalog


@pytest.fixture
async def run_api(
    tmp_path: Path,
) -> AsyncIterator[tuple[httpx.AsyncClient, AppContext, FastAPI]]:
    settings = Settings(
        env="test",
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        storage_root=tmp_path / "storage",
        scheduler="mock",
    )
    context = build_context(settings)
    async with context.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with context.session_factory() as session:
        await seed_catalog(session)
        await session.commit()

    app = create_app(settings)
    app.state.context = context
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-User": "student"},
    ) as client:
        yield client, context, app
    await context.engine.dispose()


async def _prepare_run(client: httpx.AsyncClient) -> tuple[str, str]:
    workspace_id = (await client.get("/api/v1/me")).json()["workspaces"][0]["id"]
    response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": "ev_python_312"},
    )
    assert response.status_code == 200
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": "Intent Contract Project"},
        )
    ).json()
    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('intent')\n"},
    )
    assert response.status_code == 200
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "intent contract"},
    )
    assert response.status_code == 201
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "Intent contract",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_variables": {},
            "input_bindings": [],
            "artifact_rules": [],
        },
    )
    assert response.status_code == 201
    return project["id"], response.json()["id"]


async def _row_counts(context: AppContext) -> tuple[int, int, int]:
    async with context.session_factory() as session:
        counts = []
        for table in (t.RunSnapshotRow, t.RunRow, t.RunExecutionIntentRow):
            counts.append(int(await session.scalar(select(func.count()).select_from(table))))
        return counts[0], counts[1], counts[2]


@pytest.mark.asyncio
async def test_post_run_commits_snapshot_queued_run_and_intent_without_worker(
    run_api: tuple[httpx.AsyncClient, AppContext, FastAPI],
) -> None:
    client, context, _app = run_api
    project_id, configuration_id = await _prepare_run(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id, "name": "Durable intent"},
    )

    assert response.status_code == 201
    submitted = response.json()
    assert submitted["status"] == "queued"
    assert submitted["scheduler_job_id"] is None
    async with context.session_factory() as session:
        run = await session.get(t.RunRow, submitted["id"])
        snapshot = await session.get(t.RunSnapshotRow, submitted["snapshot_id"])
        intent = await session.get(t.RunExecutionIntentRow, submitted["id"])
    assert run is not None and run.status == "queued" and run.scheduler_job_id is None
    assert snapshot is not None and snapshot.payload["project_version_id"]
    assert intent is not None and intent.attempt_no == 0
    assert not (context.settings.storage_root / "runs" / submitted["id"]).exists()


@pytest.mark.asyncio
async def test_post_run_outer_transaction_failure_leaves_no_snapshot_run_or_intent(
    run_api: tuple[httpx.AsyncClient, AppContext, FastAPI],
) -> None:
    client, context, app = run_api
    project_id, configuration_id = await _prepare_run(client)
    before = await _row_counts(context)

    async def fail_at_commit() -> AsyncIterator[Services]:
        session = context.session_factory()
        try:
            yield build_services(context, session)
            await session.rollback()
            raise RuntimeError("injected outer commit failure")
        finally:
            await session.close()

    app.dependency_overrides[get_services] = fail_at_commit
    try:
        with pytest.raises(RuntimeError, match="injected outer commit failure"):
            await client.post(
                f"/api/v1/projects/{project_id}/runs",
                json={"run_configuration_id": configuration_id, "name": "Rolled back intent"},
            )
    finally:
        app.dependency_overrides.clear()

    assert await _row_counts(context) == before
    runs_root = context.settings.storage_root / "runs"
    assert not runs_root.exists() or not any(runs_root.iterdir())
