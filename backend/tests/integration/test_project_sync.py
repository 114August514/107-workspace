"""Issue #95：rsync 暂存区应用到 Project Working State。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from workspace107.config import Settings

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    storage = tmp_path / "storage"
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        storage_root=storage,
        scheduler="mock",
        auth_mode="dev",
        run_sync_interval_seconds=0,
        project_sync_ssh_target="workspace107@login.example.edu",
        project_sync_remote_root=str(storage / "project-sync"),
    )


async def _create_project(client: httpx.AsyncClient) -> str:
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    response = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice["id"]}, "name": "同步测试"},
        headers=ALICE,
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _write(client: httpx.AsyncClient, project_id: str, path: str, content: str) -> None:
    response = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": path, "content": content},
        headers=ALICE,
    )
    assert response.status_code == 200, response.text


def _populate_staging(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "replace.txt").write_text("new", encoding="utf-8")
    (staging / "src").mkdir()
    (staging / "src" / "main.py").write_text("print('sync')\n", encoding="utf-8")


def _write_reserved_marker(staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    (staging / ".gitkeep").write_text("not a marker", encoding="utf-8")


def _replace_marker_with_symlink(staging: Path) -> None:
    (staging / ".gitkeep").unlink()
    (staging / "link").symlink_to("outside")


@pytest.mark.asyncio
async def test_prepare_and_apply_sync_reuses_staging_without_deleting_project_extras(
    client: httpx.AsyncClient,
) -> None:
    project_id = await _create_project(client)
    await _write(client, project_id, "keep.txt", "remote only")
    await _write(client, project_id, "replace.txt", "old")
    version = await client.post(
        f"/api/v1/projects/{project_id}/versions", json={"message": "baseline"}, headers=ALICE
    )
    assert version.status_code == 201

    prepared = await client.post(f"/api/v1/projects/{project_id}/sync", headers=ALICE)
    assert prepared.status_code == 200, prepared.text
    target = prepared.json()
    assert target["ssh_target"] == "workspace107@login.example.edu"
    staging = Path(target["remote_path"])
    await asyncio.to_thread(_populate_staging, staging)

    applied = await client.post(f"/api/v1/projects/{project_id}/sync/apply", headers=ALICE)
    assert applied.status_code == 200, applied.text
    assert applied.json() == {"scanned_files": 2, "changed_files": 2}

    listing = await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)
    assert [entry["path"] for entry in listing.json()] == [
        "keep.txt",
        "replace.txt",
        "src/main.py",
    ]
    content = await client.get(
        f"/api/v1/projects/{project_id}/files/content",
        params={"path": "replace.txt"},
        headers=ALICE,
    )
    assert content.json()["content"] == "new"

    repeated_prepare = await client.post(f"/api/v1/projects/{project_id}/sync", headers=ALICE)
    assert repeated_prepare.json()["remote_path"] == target["remote_path"]
    repeated_apply = await client.post(f"/api/v1/projects/{project_id}/sync/apply", headers=ALICE)
    assert repeated_apply.json() == {"scanned_files": 2, "changed_files": 0}
    versions = await client.get(f"/api/v1/projects/{project_id}/versions", headers=ALICE)
    assert versions.json()["total"] == 1


@pytest.mark.asyncio
async def test_sync_rechecks_authority_and_rejects_unsafe_staging_content(
    client: httpx.AsyncClient,
) -> None:
    project_id = await _create_project(client)
    hidden = await client.post(f"/api/v1/projects/{project_id}/sync", headers=BOB)
    assert hidden.status_code == 404

    prepared = await client.post(f"/api/v1/projects/{project_id}/sync", headers=ALICE)
    staging = Path(prepared.json()["remote_path"])
    await asyncio.to_thread(_write_reserved_marker, staging)
    rejected = await client.post(f"/api/v1/projects/{project_id}/sync/apply", headers=ALICE)
    assert rejected.status_code == 422
    assert "保留" in rejected.json()["message"]

    await asyncio.to_thread(_replace_marker_with_symlink, staging)
    rejected_link = await client.post(f"/api/v1/projects/{project_id}/sync/apply", headers=ALICE)
    assert rejected_link.status_code == 422
    assert "符号链接" in rejected_link.json()["message"]
