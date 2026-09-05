"""Project latest-Version language statistics."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from workspace107.config import Settings

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def create_project(
    client: httpx.AsyncClient, name: str, *, visibility: str = "owner_scope"
) -> str:
    user = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    response = await client.post(
        "/api/v1/projects",
        json={
            "owner": {"kind": "user", "id": user["id"]},
            "name": name,
            "visibility": visibility,
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def write_file(
    client: httpx.AsyncClient, project_id: str, path: str, content: str
) -> None:
    response = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": path, "content": content},
        headers=ALICE,
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_languages_use_latest_version_not_working_state_and_clean_temporary_files(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    project_id = await create_project(client, "语言统计", visibility="public")

    empty = await client.get(f"/api/v1/projects/{project_id}/languages", headers=BOB)
    assert empty.status_code == 200
    assert empty.json() == {"languages": [], "total_code_lines": 0}

    await write_file(client, project_id, "main.py", "def answer():\n    return 42\n")
    await write_file(client, project_id, "web.js", "console.log('saved');\n")
    saved = await client.post(
        f"/api/v1/projects/{project_id}/versions",
        json={"message": "可统计版本"},
        headers=ALICE,
    )
    assert saved.status_code == 201, saved.text

    await write_file(client, project_id, "draft.rs", "fn main() {}\n")
    response = await client.get(f"/api/v1/projects/{project_id}/languages", headers=BOB)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_code_lines"] == 3
    assert [(entry["name"], entry["code_lines"]) for entry in body["languages"]] == [
        ("Python", 2),
        ("JavaScript", 1),
    ]
    assert sum(entry["percentage"] for entry in body["languages"]) == pytest.approx(100)
    assert not any((settings.storage_root / "temporary").iterdir())


@pytest.mark.asyncio
async def test_languages_hide_owner_scope_project_from_other_users(
    client: httpx.AsyncClient,
) -> None:
    project_id = await create_project(client, "私有语言统计")

    response = await client.get(f"/api/v1/projects/{project_id}/languages", headers=BOB)

    assert response.status_code == 404
