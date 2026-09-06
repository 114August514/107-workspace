"""Environment objects can be created only in the actor's authorized owner scope."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_environment_owner_scope_and_empty_versions(client: httpx.AsyncClient) -> None:
    alice = {"X-User": "alice"}
    bob = {"X-User": "bob"}
    user = (await client.get("/api/v1/me", headers=alice)).json()["user"]
    group = (
        await client.post("/api/v1/user-groups", headers=alice, json={"name": "实验组"})
    ).json()
    for owner in (
        {"kind": "user", "id": user["id"]},
        {"kind": "user_group", "id": group["id"]},
    ):
        payload = {"owner": owner, "name": "  Python 实验  ", "description": "环境说明"}
        denied = await client.post("/api/v1/catalog/environments", headers=bob, json=payload)
        assert denied.status_code == 404
        created = await client.post("/api/v1/catalog/environments", headers=alice, json=payload)
        assert created.status_code == 201, created.text
        environment = created.json()
        assert environment["name"] == "Python 实验"
        assert environment["owner"]["id"] == owner["id"]
        assert environment["versions"] == []
        assert "environment.version.create" in environment["capabilities"]
        fetched = await client.get(
            f"/api/v1/catalog/environments/{environment['id']}", headers=alice
        )
        assert fetched.status_code == 200
        assert (
            await client.get(f"/api/v1/catalog/environments/{environment['id']}", headers=bob)
        ).status_code == 404

    invalid = await client.post(
        "/api/v1/catalog/environments",
        headers=alice,
        json={"owner": {"kind": "user", "id": user["id"]}, "name": "   "},
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_environment_creation_requires_active_group_membership(
    client: httpx.AsyncClient,
) -> None:
    alice = {"X-User": "alice"}
    bob = {"X-User": "bob"}
    await client.get("/api/v1/me", headers=bob)
    group = (
        await client.post("/api/v1/user-groups", headers=alice, json={"name": "成员环境"})
    ).json()
    payload = {"owner": {"kind": "user_group", "id": group["id"]}, "name": "成员创建"}
    invitation = await client.post(
        f"/api/v1/user-groups/{group['id']}/members",
        headers=alice,
        json={"username": "bob"},
    )
    assert invitation.status_code == 201
    assert (
        await client.post("/api/v1/catalog/environments", headers=bob, json=payload)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/user-groups/{group['id']}/invitation",
            headers=bob,
            json={"accept": True},
        )
    ).status_code == 204
    created = await client.post("/api/v1/catalog/environments", headers=bob, json=payload)
    assert created.status_code == 201, created.text
