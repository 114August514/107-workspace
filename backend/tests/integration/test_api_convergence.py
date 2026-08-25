"""Issue #42 current Home, Activity, and Notification contracts."""

from __future__ import annotations

import pytest

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


@pytest.mark.asyncio
async def test_home_uses_user_owner_execution_context_without_workspace(client) -> None:
    response = await client.get("/api/v1/me", headers=ALICE)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "user",
        "user_groups",
        "personal_execution_context",
        "recent_projects",
        "recent_runs",
    }
    assert body["personal_execution_context"] == {
        "owner": {
            "kind": "user",
            "id": body["user"]["id"],
            "display_name": body["user"]["display_name"],
        },
        "entitlements": [],
    }
    assert "personal_resource_context_id" not in body


@pytest.mark.asyncio
async def test_user_group_activity_requires_current_membership(client) -> None:
    await client.get("/api/v1/me", headers=BOB)
    group = await client.post(
        "/api/v1/user-groups",
        json={"name": "Current authority"},
        headers=ALICE,
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    own = await client.get(f"/api/v1/user-groups/{group_id}/activities", headers=ALICE)
    assert own.status_code == 200
    assert own.json()["items"][0]["owner"] == {
        "kind": "user_group",
        "id": group_id,
    }

    denied = await client.get(f"/api/v1/user-groups/{group_id}/activities", headers=BOB)
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_notification_is_recipient_only_and_uses_current_target(client) -> None:
    bob = await client.get("/api/v1/me", headers=BOB)
    assert bob.status_code == 200
    bob_id = bob.json()["user"]["id"]
    group = await client.post(
        "/api/v1/user-groups",
        json={"name": "Notify current target"},
        headers=ALICE,
    )
    assert group.status_code == 201
    group_id = group.json()["id"]
    invited = await client.post(
        f"/api/v1/user-groups/{group_id}/members",
        json={"username": "bob"},
        headers=ALICE,
    )
    assert invited.status_code == 201

    mine = await client.get("/api/v1/notifications", headers=BOB)
    assert mine.status_code == 200
    notification = mine.json()["items"][0]
    assert notification["target_type"] == "user_group"
    assert notification["target_id"] == group_id
    assert "workspace_id" not in notification

    alice = await client.get("/api/v1/notifications", headers=ALICE)
    assert alice.status_code == 200
    assert all(item["id"] != notification["id"] for item in alice.json()["items"])

    # Recipient scoping applies to updates too: another user cannot mark Bob's notification read.
    hidden = await client.post(
        f"/api/v1/notifications/{notification['id']}/read",
        headers=ALICE,
    )
    assert hidden.status_code == 204
    still_unread = await client.get("/api/v1/notifications/unread-count", headers=BOB)
    assert still_unread.json()["unread"] == 1
    assert bob_id == invited.json()["user_id"]
