from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from workspace107.infrastructure.db.repositories import SqlRepositories

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
) -> httpx.Response:
    return await client.post(
        f"/api/v1/user-groups/{group_id}/members",
        json={"username": username},
        headers=headers,
    )


async def _group_with_active_bob(client: httpx.AsyncClient, name: str) -> tuple[str, str]:
    await client.get("/api/v1/me", headers=BOB)
    group = await _create_group(client, ALICE, name)
    group_id = str(group["id"])
    assert (await _invite(client, group_id, "bob")).status_code == 201
    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/invitation",
            json={"accept": True},
            headers=BOB,
        )
    ).status_code == 204
    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    bob_id = next(member["user_id"] for member in members if member["username"] == "bob")
    return group_id, bob_id


async def _assert_exactly_one_active_owner(client: httpx.AsyncClient, group_id: str) -> None:
    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    assert (
        len(
            [
                member
                for member in members
                if member["role"] == "owner" and member["status"] == "active"
            ]
        )
        == 1
    )


@pytest.mark.asyncio
async def test_new_user_home_uses_direct_user_execution_context(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/me", headers=ALICE)

    assert response.status_code == 200
    body = response.json()
    assert body["user_groups"] == []
    assert body["personal_execution_context"]["owner"] == {
        "kind": "user",
        "id": body["user"]["id"],
        "display_name": body["user"]["display_name"],
    }
    assert "personal_resource_context_id" not in body
    assert "workspaces" not in body


@pytest.mark.asyncio
async def test_user_group_capabilities_are_governance_only_for_every_role(
    client: httpx.AsyncClient,
) -> None:
    for headers in (BOB, CAROL):
        await client.get("/api/v1/me", headers=headers)

    group = await _create_group(client, ALICE, "Capability Lab")
    group_id = str(group["id"])
    expected = {
        "owner": [
            "member.invite",
            "member.remove",
            "member.role.manage",
            "member.view",
            "ownership.transfer",
            "user_group.update",
            "user_group.view",
        ],
        "admin": [
            "member.invite",
            "member.remove",
            "member.view",
            "user_group.update",
            "user_group.view",
        ],
        "member": ["member.view", "user_group.view"],
    }
    assert group["capabilities"] == expected["owner"]

    for username, headers in (("bob", BOB), ("carol", CAROL)):
        assert (await _invite(client, group_id, username)).status_code == 201
        assert (
            await client.post(
                f"/api/v1/user-groups/{group_id}/invitation",
                json={"accept": True},
                headers=headers,
            )
        ).status_code == 204

    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    bob_id = next(member["user_id"] for member in members if member["username"] == "bob")
    assert (
        await client.patch(
            f"/api/v1/user-groups/{group_id}/members/{bob_id}",
            json={"role": "admin"},
            headers=ALICE,
        )
    ).status_code == 200

    for role, headers in (
        ("owner", ALICE),
        ("admin", BOB),
        ("member", CAROL),
    ):
        visible = (await client.get(f"/api/v1/user-groups/{group_id}", headers=headers)).json()
        assert visible["role"] == role
        assert visible["capabilities"] == expected[role]


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
    owners = [m for m in members if m["role"] == "owner" and m["status"] == "active"]
    assert [m["username"] for m in owners] == ["alice"]
    entitlements = (await client.get("/api/v1/me/entitlements", headers=ALICE)).json()
    assert entitlements == []


@pytest.mark.asyncio
async def test_invitation_accept_reject_and_cross_group_404(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await client.get("/api/v1/me", headers=BOB)
    group = await _create_group(client, ALICE, "Invite Lab")
    group_id = str(group["id"])

    invited = await _invite(client, group_id, "bob")
    assert invited.status_code == 201
    repos = SqlRepositories(session)
    alice = await repos.users.get_by_username("alice")
    bob = await repos.users.get_by_username("bob")
    assert alice is not None and bob is not None
    assert await repos.user_groups.get_for_active_member(group_id, bob.id) is None
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
    discovered = await repos.user_groups.get_for_active_member(group_id, bob.id)
    assert discovered is not None and discovered.id == group_id

    other = await _create_group(client, BOB, "Bob Only")
    assert (
        await client.get(f"/api/v1/user-groups/{other['id']}", headers=ALICE)
    ).status_code == 404
    assert await repos.user_groups.get_for_active_member(str(other["id"]), alice.id) is None


@pytest.mark.asyncio
async def test_owner_changes_roles_and_admin_cannot(
    client: httpx.AsyncClient,
) -> None:
    for headers in (BOB, CAROL):
        await client.get("/api/v1/me", headers=headers)
    group_id, bob_id = await _group_with_active_bob(client, "Role Change Lab")
    assert (await _invite(client, group_id, "carol")).status_code == 201
    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/invitation",
            json={"accept": True},
            headers=CAROL,
        )
    ).status_code == 204
    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    carol_id = next(member["user_id"] for member in members if member["username"] == "carol")

    assert (
        await client.patch(
            f"/api/v1/user-groups/{group_id}/members/{bob_id}",
            json={"role": "admin"},
            headers=ALICE,
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/user-groups/{group_id}/members/{carol_id}",
            json={"role": "admin"},
            headers=BOB,
        )
    ).status_code == 403

    promoted = await client.patch(
        f"/api/v1/user-groups/{group_id}/members/{carol_id}",
        json={"role": "admin"},
        headers=ALICE,
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    demoted = await client.patch(
        f"/api/v1/user-groups/{group_id}/members/{carol_id}",
        json={"role": "member"},
        headers=ALICE,
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "member"


@pytest.mark.asyncio
async def test_admin_governs_only_ordinary_members(client: httpx.AsyncClient) -> None:
    for headers in (BOB, CAROL, DAVE):
        await client.get("/api/v1/me", headers=headers)
    group_id, bob_id = await _group_with_active_bob(client, "Admin Governance Lab")
    assert (await _invite(client, group_id, "carol")).status_code == 201
    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/invitation",
            json={"accept": True},
            headers=CAROL,
        )
    ).status_code == 204
    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=ALICE)).json()
    alice_id = next(member["user_id"] for member in members if member["username"] == "alice")
    carol_id = next(member["user_id"] for member in members if member["username"] == "carol")
    assert (
        await client.patch(
            f"/api/v1/user-groups/{group_id}/members/{bob_id}",
            json={"role": "admin"},
            headers=ALICE,
        )
    ).status_code == 200

    admin_members = (
        await client.get(f"/api/v1/user-groups/{group_id}/members", headers=BOB)
    ).json()
    assert (
        next(member for member in admin_members if member["user_id"] == alice_id)["capabilities"]
        == []
    )
    assert (
        next(member for member in admin_members if member["user_id"] == bob_id)["capabilities"]
        == []
    )
    assert next(member for member in admin_members if member["user_id"] == carol_id)[
        "capabilities"
    ] == ["member.remove"]

    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/members",
            json={"username": "dave", "role": "admin"},
            headers=BOB,
        )
    ).status_code == 422
    invited = await _invite(client, group_id, "dave", headers=BOB)
    assert invited.status_code == 201
    assert invited.json()["role"] == "member"
    assert (await _invite(client, group_id, "dave", headers=CAROL)).status_code == 403

    assert (
        await client.delete(f"/api/v1/user-groups/{group_id}/members/{bob_id}", headers=BOB)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/user-groups/{group_id}/members/{alice_id}", headers=BOB)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/user-groups/{group_id}/members/{carol_id}", headers=BOB)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/user-groups/{group_id}/members/{bob_id}", headers=ALICE)
    ).status_code == 204


@pytest.mark.asyncio
async def test_owner_role_only_changes_through_atomic_transfer(client: httpx.AsyncClient) -> None:
    for headers in (BOB, CAROL, DAVE):
        await client.get("/api/v1/me", headers=headers)
    group = await _create_group(client, ALICE, "Transfer Lab")
    group_id = str(group["id"])

    assert (
        await client.post(
            f"/api/v1/user-groups/{group_id}/members",
            json={"username": "bob", "role": "owner"},
            headers=ALICE,
        )
    ).status_code == 422
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
    assert sorted(r.status_code for r in results) == [204, 403]

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
    assert (
        await client.post(f"/api/v1/user-groups/{group_id}/leave", headers=ALICE)
    ).status_code == 204

    members = (await client.get(f"/api/v1/user-groups/{group_id}/members", headers=BOB)).json()
    assert [(m["username"], m["role"], m["status"]) for m in members] == [
        ("bob", "owner", "active")
    ]


@pytest.mark.asyncio
async def test_concurrent_transfer_and_remove_preserve_an_active_owner(
    client: httpx.AsyncClient,
) -> None:
    group_id, bob_id = await _group_with_active_bob(client, "Transfer Remove Lab")

    transfer, remove = await asyncio.gather(
        client.post(f"/api/v1/user-groups/{group_id}/transfer-ownership/{bob_id}", headers=ALICE),
        client.delete(f"/api/v1/user-groups/{group_id}/members/{bob_id}", headers=ALICE),
    )

    assert (transfer.status_code, remove.status_code) in {(204, 403), (404, 204)}
    await _assert_exactly_one_active_owner(client, group_id)


@pytest.mark.asyncio
async def test_concurrent_transfer_and_target_leave_preserve_an_active_owner(
    client: httpx.AsyncClient,
) -> None:
    group_id, bob_id = await _group_with_active_bob(client, "Transfer Leave Lab")

    transfer, leave = await asyncio.gather(
        client.post(f"/api/v1/user-groups/{group_id}/transfer-ownership/{bob_id}", headers=ALICE),
        client.post(f"/api/v1/user-groups/{group_id}/leave", headers=BOB),
    )

    assert (transfer.status_code, leave.status_code) in {(204, 403), (404, 204)}
    await _assert_exactly_one_active_owner(client, group_id)


@pytest.mark.asyncio
async def test_concurrent_transfer_and_role_change_preserve_an_active_owner(
    client: httpx.AsyncClient,
) -> None:
    group_id, bob_id = await _group_with_active_bob(client, "Transfer Role Lab")

    transfer, role_change = await asyncio.gather(
        client.post(f"/api/v1/user-groups/{group_id}/transfer-ownership/{bob_id}", headers=ALICE),
        client.patch(
            f"/api/v1/user-groups/{group_id}/members/{bob_id}",
            json={"role": "admin"},
            headers=ALICE,
        ),
    )

    assert (transfer.status_code, role_change.status_code) in {(204, 403), (204, 200)}
    await _assert_exactly_one_active_owner(client, group_id)
