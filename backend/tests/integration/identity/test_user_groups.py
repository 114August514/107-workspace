from __future__ import annotations

import asyncio

import httpx
import pytest

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}
CAROL = {"X-User": "carol"}
DAVE = {"X-User": "dave"}


async def _create_group(
    client: httpx.AsyncClient, headers: dict[str, str], name: str
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/user-groups", json={"name": name, "description": "test"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _invite(
    client: httpx.AsyncClient,
    group_id: str,
    username: str,
    *,
    headers: dict[str, str] = ALICE,
    role: str = "member",
) -> httpx.Response:
    return await client.post(
        f"/api/v1/user-groups/{group_id}/members",
        json={"username": username, "role": role},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_new_user_does_not_create_personal_workspace(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me", headers=ALICE)

    assert response.status_code == 200
    body = response.json()
    assert body["user_groups"] == []
    assert "workspaces" not in body


@pytest.mark.asyncio
async def test_group_creation_has_exactly_one_active_owner(client: httpx.AsyncClient) -> None:
    group = await _create_group(client, ALICE, "Alice Lab")

    assert group["created_by_id"] is not None
    assert group["role"] == "owner"
    members = (await client.get(f"/api/v1/user-groups/{group['id']}/members", headers=ALICE)).json()
    updated = await client.patch(
        f"/api/v1/user-groups/{group['id']}",
        json={"name": "Renamed Lab", "description": "new description"},
        headers=ALICE,
    )
    assert updated.status_code == 200
    legacy = (await client.get(f"/api/v1/workspaces/{group['id']}", headers=ALICE)).json()
    assert (legacy["name"], legacy["owner_id"]) == ("Renamed Lab", group["created_by_id"])
    owners = [m for m in members if m["role"] == "owner" and m["status"] == "active"]
    assert [m["username"] for m in owners] == ["alice"]


@pytest.mark.asyncio
async def test_invitation_accept_reject_and_cross_group_404(client: httpx.AsyncClient) -> None:
    await client.get("/api/v1/me", headers=BOB)
    group = await _create_group(client, ALICE, "Invite Lab")
    group_id = str(group["id"])

    invited = await _invite(client, group_id, "bob")
    assert invited.status_code == 201
    assert (await client.get(f"/api/v1/user-groups/{group_id}", headers=BOB)).status_code == 404

    rejected = await client.post(
        f"/api/v1/user-groups/{group_id}/invitation", json={"accept": False}, headers=BOB
    )
    assert rejected.status_code == 204
    assert (await client.get(f"/api/v1/user-groups/{group_id}", headers=BOB)).status_code == 404

    assert (await _invite(client, group_id, "bob")).status_code == 201
    accepted = await client.post(
        f"/api/v1/user-groups/{group_id}/invitation", json={"accept": True}, headers=BOB
    )
    assert accepted.status_code == 204
    assert (await client.get(f"/api/v1/user-groups/{group_id}", headers=BOB)).status_code == 200

    other = await _create_group(client, BOB, "Bob Only")
    assert (
        await client.get(f"/api/v1/user-groups/{other['id']}", headers=ALICE)
    ).status_code == 404


@pytest.mark.asyncio
async def test_owner_role_only_changes_through_atomic_transfer(client: httpx.AsyncClient) -> None:
    for headers in (BOB, CAROL, DAVE):
        await client.get("/api/v1/me", headers=headers)
    group = await _create_group(client, ALICE, "Transfer Lab")
    group_id = str(group["id"])

    assert (await _invite(client, group_id, "bob", role="owner")).status_code == 409
    assert (await _invite(client, group_id, "bob")).status_code == 201
    assert (await _invite(client, group_id, "carol")).status_code == 201
    for headers in (BOB, CAROL):
        assert (
            await client.post(
                f"/api/v1/user-groups/{group_id}/invitation",
                json={"accept": True},
                headers=headers,
            )
        ).status_code == 204

    direct_owner = await client.patch(
        f"/api/v1/user-groups/{group_id}/members/usr_missing",
        json={"role": "owner"},
        headers=ALICE,
    )
    assert direct_owner.status_code == 409

    # A failed transfer cannot leave the group ownerless.
    missing = await client.post(
        f"/api/v1/user-groups/{group_id}/transfer-ownership/usr_missing", headers=ALICE
    )
    assert missing.status_code == 404

    # Competing transfers serialize; only one can commit from the original owner.
    results = await asyncio.gather(
        client.post(
            f"/api/v1/user-groups/{group_id}/transfer-ownership/"
            + next(
                m["user_id"]
                for m in (
                    await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)
                ).json()
                if m["username"] == "bob"
            ),
            headers=ALICE,
        ),
        client.post(
            f"/api/v1/user-groups/{group_id}/transfer-ownership/"
            + next(
                m["user_id"]
                for m in (
                    await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)
                ).json()
                if m["username"] == "carol"
            ),
            headers=ALICE,
        ),
    )
    assert sorted(r.status_code for r in results) == [204, 409]

    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    owners = [m for m in members if m["role"] == "owner" and m["status"] == "active"]
    assert len(owners) == 1


@pytest.mark.asyncio
async def test_owner_cannot_leave_or_be_removed_then_former_owner_can_leave(
    client: httpx.AsyncClient,
) -> None:
    await client.get("/api/v1/me", headers=BOB)
    group = await _create_group(client, ALICE, "Leave Lab")
    group_id = str(group["id"])
    assert (await _invite(client, group_id, "bob")).status_code == 201
    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/invitation", json={"accept": True}, headers=BOB
        )
    ).status_code == 204

    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    alice_id = next(m["user_id"] for m in members if m["username"] == "alice")
    bob_id = next(m["user_id"] for m in members if m["username"] == "bob")

    assert (
        await client.post(f"/api/v1/user-groups/{group_id}/leave", headers=ALICE)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/user-groups/{group_id}/members/{alice_id}", headers=ALICE)
    ).status_code == 409

    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/transfer-ownership/{bob_id}", headers=ALICE
        )
    ).status_code == 204
    legacy = (await client.get(f"/api/v1/workspaces/{group_id}", headers=BOB)).json()
    assert legacy["owner_id"] == bob_id
    assert (
        await client.post(f"/api/v1/user-groups/{group_id}/leave", headers=ALICE)
    ).status_code == 204

    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=BOB)).json()
    assert [(m["username"], m["role"], m["status"]) for m in members] == [
        ("bob", "owner", "active")
    ]
