from __future__ import annotations

import pytest

from tests.helpers import ensure_user_group

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


@pytest.mark.asyncio
async def test_user_owned_project_is_not_visible_to_other_users(client) -> None:
    await client.get("/api/v1/me", headers=ALICE)
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    created = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice["id"]}, "name": "Alice Project"},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["owner"]["kind"] == "user"
    assert project["visibility"] == "owner_scope"
    assert (await client.get(f"/api/v1/projects/{project['id']}", headers=BOB)).status_code == 404


@pytest.mark.asyncio
async def test_public_project_exposes_metadata_and_versions_but_not_working_state(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    created = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Public Project"},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    updated = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"visibility": "public"},
        headers=ALICE,
    )
    assert updated.status_code == 200, updated.text
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "README.md", "content": "public"},
        headers=ALICE,
    )
    version = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "public version"},
        headers=ALICE,
    )
    assert version.status_code == 201, version.text

    metadata = await client.get(f"/api/v1/projects/{project['id']}", headers=BOB)
    assert metadata.status_code == 200
    assert metadata.json()["environment_version_id"] is None
    assert metadata.json()["default_run_configuration_id"] is None
    versions = await client.get(f"/api/v1/projects/{project['id']}/versions", headers=BOB)
    assert versions.status_code == 200
    assert len(versions.json()["items"]) == 1
    assert (
        await client.get(f"/api/v1/projects/{project['id']}/files", headers=BOB)
    ).status_code == 404


@pytest.mark.asyncio
async def test_discoverable_project_listing_includes_public_projects(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    project = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Discoverable"},
        headers=ALICE,
    )
    project_id = project.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"visibility": "public"},
            headers=ALICE,
        )
    ).status_code == 200
    listing = await client.get("/api/v1/projects", headers=BOB)
    assert listing.status_code == 200
    assert any(item["id"] == project_id for item in listing.json()["items"])


@pytest.mark.asyncio
async def test_public_version_can_be_forked_to_requesting_user_owner(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    source = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Fork Source"},
        headers=ALICE,
    )
    source_id = source.json()["id"]
    await client.patch(
        f"/api/v1/projects/{source_id}",
        json={"visibility": "public"},
        headers=ALICE,
    )
    await client.put(
        f"/api/v1/projects/{source_id}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=ALICE,
    )
    configuration = await client.post(
        f"/api/v1/projects/{source_id}/run-configurations",
        json={
            "name": "private config",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
        },
        headers=ALICE,
    )
    assert configuration.status_code == 201, configuration.text
    version = await client.post(
        f"/api/v1/projects/{source_id}/versions",
        json={"message": "forkable"},
        headers=ALICE,
    )
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]
    forked = await client.post(
        f"/api/v1/versions/{version.json()['id']}/fork",
        json={
            "target_owner": {"kind": "user", "id": bob["id"]},
            "name": "Bob Fork",
        },
        headers=BOB,
    )
    assert forked.status_code == 201, forked.text
    assert forked.json()["owner"]["id"] == bob["id"]
    copied = await client.get(
        f"/api/v1/projects/{forked.json()['id']}/run-configurations", headers=BOB
    )
    assert copied.status_code == 200
    assert copied.json() == []
