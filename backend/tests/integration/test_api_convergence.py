"""Issue #42 current Home, Activity, and Notification contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from workspace107.infrastructure.db.tables import RunRow, RunSnapshotRow

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
async def test_inaccessible_group_notifications_are_recipient_only_and_non_linking(client) -> None:
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
    assert notification["target_type"] is None
    assert notification["target_id"] is None
    assert "workspace_id" not in notification
    accepted = await client.post(
        f"/api/v1/user-groups/{group_id}/invitation",
        json={"accept": True},
        headers=BOB,
    )
    assert accepted.status_code == 204
    removed = await client.delete(f"/api/v1/user-groups/{group_id}/members/{bob_id}", headers=ALICE)
    assert removed.status_code == 204
    after_removal = await client.get("/api/v1/notifications", headers=BOB)
    removal = next(
        item for item in after_removal.json()["items"] if item["type"] == "member_removed"
    )
    assert removal["target_type"] is None
    assert removal["target_id"] is None

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
    assert still_unread.json()["unread"] == 2
    assert bob_id == invited.json()["user_id"]


@pytest.mark.asyncio
async def test_home_recent_runs_only_contains_runs_initiated_by_current_user(
    client, session
) -> None:
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]
    group = (
        await client.post("/api/v1/user-groups", json={"name": "Shared Runs"}, headers=ALICE)
    ).json()
    await client.post(
        f"/api/v1/user-groups/{group['id']}/members",
        json={"username": "bob"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/user-groups/{group['id']}/invitation",
        json={"accept": True},
        headers=BOB,
    )
    project = (
        await client.post(
            "/api/v1/projects",
            json={
                "owner": {"kind": "user_group", "id": group["id"]},
                "name": "Shared Project",
            },
            headers=ALICE,
        )
    ).json()
    now = datetime.now(UTC)
    for suffix, initiator in (("alice", alice["id"]), ("bob", bob["id"])):
        snapshot_id = f"snap_{suffix}"
        session.add(RunSnapshotRow(id=snapshot_id, payload={}))
        await session.flush()
        session.add(
            RunRow(
                id=f"run_{suffix}",
                project_id=project["id"],
                snapshot_id=snapshot_id,
                compute_plan_id="plan_cpu_quick",
                project_version_id=f"pv_{suffix}",
                project_version_label="v1",
                source_run_configuration_id=None,
                source_run_id=None,
                name=f"{suffix} run",
                status="succeeded",
                initiated_by_user_id=initiator,
                created_at=now,
                finished_at=now,
            )
        )
    await session.commit()

    alice_home = (await client.get("/api/v1/me", headers=ALICE)).json()
    bob_home = (await client.get("/api/v1/me", headers=BOB)).json()
    assert [run["id"] for run in alice_home["recent_runs"]] == ["run_alice"]
    assert [run["id"] for run in bob_home["recent_runs"]] == ["run_bob"]
