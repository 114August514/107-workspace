"""Issue #55: Shared Resource availability and USE Grant boundary presentation.

Discovery covers owner scope plus resources reachable through a valid USE Grant
issued under the resource's current Owner.  Availability tells the acting User
why they can (or cannot) use a resource: owner scope, personal User Grant, or
UserGroup Grant with active membership.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _get_user_id(client: httpx.AsyncClient, headers: dict) -> str:
    response = await client.get("/api/v1/me", headers=headers)
    response.raise_for_status()
    return str(response.json()["user"]["id"])


async def _create_group(
    client: httpx.AsyncClient, name: str, *, headers: dict | None = None
) -> str:
    response = await client.post(
        "/api/v1/user-groups", json={"name": name}, headers=headers or ALICE
    )
    response.raise_for_status()
    return str(response.json()["id"])


async def _create_resource_with_version(
    client: httpx.AsyncClient, *, owner: dict, name: str
) -> tuple[str, str]:
    """Create a Shared Resource + Version. Returns (resource_id, version_id)."""
    response = await client.post(
        "/api/v1/shared-resources",
        json={"owner": owner, "name": name},
        headers=ALICE,
    )
    response.raise_for_status()
    resource_id = str(response.json()["id"])
    response = await client.post(
        f"/api/v1/shared-resources/{resource_id}/versions",
        data={"description": "v1"},
        files={"files": ("data.txt", b"data", "text/plain")},
        headers=ALICE,
    )
    response.raise_for_status()
    return resource_id, str(response.json()["id"])


async def _grant(
    client: httpx.AsyncClient,
    *,
    target_kind: str,
    target_id: str,
    grantee: dict,
    grantor: dict | None = None,
) -> str:
    payload: dict = {"target_kind": target_kind, "target_id": target_id, "grantee": grantee}
    if grantor is not None:
        payload["grantor"] = grantor
    response = await client.post("/api/v1/grants", json=payload, headers=ALICE)
    response.raise_for_status()
    return str(response.json()["id"])


def _availability_in_list(body: list[dict], resource_id: str) -> dict | None:
    for entry in body:
        if entry["id"] == resource_id:
            return entry["availability"]
    return None


async def test_owner_scope_availability_in_list_and_detail(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """User-owned and UserGroup-owned resources show source=owner with no grants."""
    alice_id = await _get_user_id(client, ALICE)
    group_a = await _create_group(client, "Availability Owner Group")
    user_resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user", "id": alice_id}, name="user owned"
    )
    group_resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_a}, name="group owned"
    )

    listing = await client.get("/api/v1/shared-resources", headers=ALICE)
    listing.raise_for_status()
    for resource_id in (user_resource_id, group_resource_id):
        availability = _availability_in_list(listing.json(), resource_id)
        assert availability is not None
        assert availability == {"usable": True, "source": "owner", "grants": []}

    detail = await client.get(f"/api/v1/shared-resources/{group_resource_id}", headers=ALICE)
    detail.raise_for_status()
    body = detail.json()
    assert body["owner"]["kind"] == "user_group"
    assert body["owner"]["display_name"] == "Availability Owner Group"
    assert body["availability"] == {"usable": True, "source": "owner", "grants": []}


async def test_unrelated_user_neither_discovers_nor_uses(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Without owner scope or Grant the resource is absent and detail 404s."""
    alice_id = await _get_user_id(client, ALICE)
    resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user", "id": alice_id}, name="alice only"
    )

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    assert _availability_in_list(listing.json(), resource_id) is None

    detail = await client.get(f"/api/v1/shared-resources/{resource_id}", headers=BOB)
    assert detail.status_code == 404


async def test_user_grant_availability_with_summary(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """A personal USE Grant makes the resource discoverable with source=user_grant."""
    bob_id = await _get_user_id(client, BOB)
    group_b = await _create_group(client, "User Grant Owner Group")
    resource_id, version_id = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_b}, name="granted resource"
    )
    grant_id = await _grant(
        client,
        target_kind="shared_resource",
        target_id=resource_id,
        grantee={"kind": "user", "id": bob_id},
    )

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    availability = _availability_in_list(listing.json(), resource_id)
    assert availability is not None
    assert availability["usable"] is True
    assert availability["source"] == "user_grant"
    assert [summary["id"] for summary in availability["grants"]] == [grant_id]
    assert availability["grants"][0]["grantee"]["id"] == bob_id
    assert availability["grants"][0]["target_all"] is False

    detail = await client.get(f"/api/v1/shared-resources/{resource_id}", headers=BOB)
    detail.raise_for_status()
    assert detail.json()["availability"]["source"] == "user_grant"
    assert [version["id"] for version in detail.json()["versions"]] == [version_id]

    # USE Grant authorizes use, never management.
    patch = await client.patch(
        f"/api/v1/shared-resources/{resource_id}",
        json={"name": "bob edit"},
        headers=BOB,
    )
    assert patch.status_code == 403
    publish = await client.post(
        f"/api/v1/shared-resources/{resource_id}/versions",
        data={"description": "bob version"},
        files={"files": ("x.txt", b"x", "text/plain")},
        headers=BOB,
    )
    assert publish.status_code == 403

    # Owner still sees owner scope, not the grant issued to Bob.
    owner_listing = await client.get("/api/v1/shared-resources", headers=ALICE)
    owner_listing.raise_for_status()
    assert _availability_in_list(owner_listing.json(), resource_id) == {
        "usable": True,
        "source": "owner",
        "grants": [],
    }


async def test_user_group_grant_requires_active_membership(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """A UserGroup grantee surfaces source=user_group_grant only while the
    acting User keeps active membership; after removal the resource is gone."""
    from workspace107.infrastructure.db.tables import MembershipRow

    bob_id = await _get_user_id(client, BOB)
    group_a = await _create_group(client, "Grantee Group A", headers=BOB)
    group_b = await _create_group(client, "Grantor Group B")
    resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_b}, name="group granted"
    )
    await _grant(
        client,
        target_kind="shared_resource",
        target_id=resource_id,
        grantee={"kind": "user_group", "id": group_a},
    )

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    availability = _availability_in_list(listing.json(), resource_id)
    assert availability is not None
    assert availability["usable"] is True
    assert availability["source"] == "user_group_grant"
    assert availability["grants"][0]["grantee"] == {
        "kind": "user_group",
        "id": group_a,
        "display_name": "Grantee Group A",
    }

    # Bob loses membership in the grantee group: the grant no longer reaches him.
    membership = (
        await session.execute(
            select(MembershipRow).where(
                MembershipRow.user_group_id == group_a,
                MembershipRow.user_id == bob_id,
            )
        )
    ).scalar_one()
    membership.status = "removed"
    await session.commit()

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    assert _availability_in_list(listing.json(), resource_id) is None
    detail = await client.get(f"/api/v1/shared-resources/{resource_id}", headers=BOB)
    assert detail.status_code == 404


async def test_all_grant_summary_marks_target_all(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """An ALL grant covers the resource and is summarized with target_all=true."""
    bob_id = await _get_user_id(client, BOB)
    group_b = await _create_group(client, "ALL Grantor Group")
    resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_b}, name="all granted"
    )
    await _grant(
        client,
        target_kind="all",
        target_id="",
        grantee={"kind": "user", "id": bob_id},
        grantor={"kind": "user_group", "id": group_b},
    )

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    availability = _availability_in_list(listing.json(), resource_id)
    assert availability is not None
    assert availability["source"] == "user_grant"
    assert availability["grants"][0]["target_all"] is True


async def test_revoked_grant_removes_availability_on_reload(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """After Grant revocation a reload no longer shows the resource as usable."""
    bob_id = await _get_user_id(client, BOB)
    group_b = await _create_group(client, "Revoke Grantor Group")
    resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_b}, name="revoked later"
    )
    grant_id = await _grant(
        client,
        target_kind="shared_resource",
        target_id=resource_id,
        grantee={"kind": "user", "id": bob_id},
    )
    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    assert _availability_in_list(listing.json(), resource_id) is not None

    revoke = await client.delete(f"/api/v1/grants/{grant_id}", headers=ALICE)
    assert revoke.status_code == 204

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    assert _availability_in_list(listing.json(), resource_id) is None
    detail = await client.get(f"/api/v1/shared-resources/{resource_id}", headers=BOB)
    assert detail.status_code == 404


async def test_grant_from_previous_owner_no_longer_surfaces(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """After Ownership transfer, Grants issued under the old Owner stop matching
    (GR-408), so the resource leaves the grantee's discovery on reload."""
    from workspace107.infrastructure.db.tables import SharedResourceRow

    bob_id = await _get_user_id(client, BOB)
    group_b = await _create_group(client, "Transfer Grantor Group")
    group_c = await _create_group(client, "Transfer New Owner Group")
    resource_id, _ = await _create_resource_with_version(
        client, owner={"kind": "user_group", "id": group_b}, name="transferred"
    )
    await _grant(
        client,
        target_kind="shared_resource",
        target_id=resource_id,
        grantee={"kind": "user", "id": bob_id},
    )
    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    assert _availability_in_list(listing.json(), resource_id) is not None

    resource_row = (
        await session.execute(select(SharedResourceRow).where(SharedResourceRow.id == resource_id))
    ).scalar_one()
    resource_row.owner_user_group_id = group_c
    resource_row.owner_user_id = None
    await session.commit()

    listing = await client.get("/api/v1/shared-resources", headers=BOB)
    listing.raise_for_status()
    assert _availability_in_list(listing.json(), resource_id) is None
