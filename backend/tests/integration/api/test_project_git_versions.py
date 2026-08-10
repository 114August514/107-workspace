"""Project API 对真实 Git Working State 与 commit Version 的集成行为。"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from workspace107.api.deps import AppContext, Services, build_services, get_services
from workspace107.config import Settings
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.tables import Base
from workspace107.infrastructure.project_version_exporter import GitProjectVersionExporter
from workspace107.main import build_context, create_app
from workspace107.tools.seed import seed_catalog

FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _git(project_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", f"--git-dir={project_root / 'repository.git'}", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
async def git_api(
    tmp_path: Path,
) -> AsyncIterator[tuple[httpx.AsyncClient, AppContext, FastAPI]]:
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
        yield client, context, app
    await context.engine.dispose()


async def test_req_m1_a_project_api_version_restore_fork_and_export_exact_commit(
    git_api: tuple[httpx.AsyncClient, AppContext, FastAPI], tmp_path: Path
) -> None:
    client, context, _app = git_api
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
        assert row.repository_identity
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
    exporter = GitProjectVersionExporter(context.session_factory, context.project_content)
    evidence = await exporter.export(
        project_version_id=v1["id"],
        expected_commit_oid=v1_oid,
        target=export,
    )
    assert evidence.commit_oid == v1_oid
    assert FULL_OID.fullmatch(evidence.tree_oid)
    assert [entry.path for entry in evidence.manifest] == ["main.py"]
    assert (export / "main.py").read_bytes() == b"print('v1')\n"


async def test_req_m1_a_outer_commit_failure_leaves_only_invisible_orphan_ref(
    git_api: tuple[httpx.AsyncClient, AppContext, FastAPI],
) -> None:
    client, context, app = git_api
    workspace_id = (await client.get("/api/v1/me")).json()["workspaces"][0]["id"]
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": "Orphan Ref Project"},
        )
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('orphan')\n"},
    )

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
                f"/api/v1/projects/{project['id']}/versions",
                json={"message": "orphan"},
            )
    finally:
        app.dependency_overrides.clear()

    listing = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert listing["items"] == []
    project_root = context.settings.storage_root / "projects" / project["id"]
    orphan_refs = _git(
        project_root,
        "for-each-ref",
        "--format=%(refname)",
        "refs/workspace107/versions",
    ).stdout.splitlines()
    assert len(orphan_refs) == 1

    saved = await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "retry"}
    )
    assert saved.status_code == 201
    async with context.session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(t.ProjectVersionRow).where(
                        t.ProjectVersionRow.project_id == project["id"]
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert (
        rows[0].repository_identity
        == project_root.joinpath("repository.git", "workspace107-project-identity")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert (
        _git(
            project_root,
            "show-ref",
            "--verify",
            f"refs/workspace107/versions/{rows[0].id}",
        ).returncode
        == 0
    )
