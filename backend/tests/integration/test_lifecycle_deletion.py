"""Issue #51：User Group / Project 删除与从属生命周期。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_project_with_version
from workspace107.infrastructure.db import tables as t

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _create_group(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post(
        "/api/v1/user-groups",
        json={"name": name, "description": "Issue 51 test"},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


@pytest.mark.asyncio
async def test_user_group_delete_blocks_owned_project_and_configuration(client) -> None:
    group = await _create_group(client, ALICE, "Delete Blocked Group")
    group_id = group["id"]
    project = await client.post(
        "/api/v1/projects",
        json={
            "owner": {"kind": "user_group", "id": group_id},
            "name": "Still Owned Project",
        },
        headers=ALICE,
    )
    project.raise_for_status()
    variable = await client.put(
        f"/api/v1/user-groups/{group_id}/variables",
        json={"name": "KEEP_ME", "value": "value"},
        headers=ALICE,
    )
    assert variable.status_code == 200, variable.text
    secret = await client.put(
        f"/api/v1/user-groups/{group_id}/secrets",
        json={"name": "KEEP_SECRET", "value": "secret-value"},
        headers=ALICE,
    )
    assert secret.status_code == 204, secret.text

    impact = await client.get(f"/api/v1/user-groups/{group_id}/deletion-impact", headers=ALICE)
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["can_delete"] is False
    assert body["problems"] == [
        "请先处理该 User Group 拥有的 1 个 Project",
        "请先删除该 User Group 的 1 个 Variable",
        "请先删除该 User Group 的 1 个 Secret",
    ]

    rejected = await client.delete(f"/api/v1/user-groups/{group_id}?confirm=true", headers=ALICE)
    assert rejected.status_code == 409
    assert rejected.json()["problems"] == body["problems"]
    assert (
        await client.get(f"/api/v1/projects/{project.json()['id']}", headers=ALICE)
    ).status_code == 200


@pytest.mark.asyncio
async def test_user_group_delete_preserves_user_and_other_group_membership(client) -> None:
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    keep = await _create_group(client, ALICE, "Keep Membership Group")
    remove = await _create_group(client, ALICE, "Delete Empty Group")
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]

    invited = await client.post(
        f"/api/v1/user-groups/{keep['id']}/members",
        json={"username": bob["username"]},
        headers=ALICE,
    )
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        f"/api/v1/user-groups/{keep['id']}/invitation",
        json={"accept": True},
        headers=BOB,
    )
    assert accepted.status_code == 204, accepted.text

    unconfirmed = await client.delete(f"/api/v1/user-groups/{remove['id']}", headers=ALICE)
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["problems"] == ["请在确认影响范围后重试"]
    deleted = await client.delete(f"/api/v1/user-groups/{remove['id']}?confirm=true", headers=ALICE)
    assert deleted.status_code == 204, deleted.text
    assert (
        await client.get(f"/api/v1/user-groups/{remove['id']}", headers=ALICE)
    ).status_code == 404
    personal_activities = await client.get("/api/v1/me/activities", headers=ALICE)
    assert personal_activities.status_code == 200, personal_activities.text
    deleted_group_events = [
        item
        for item in personal_activities.json()["items"]
        if item["action"] == "user_group_deleted" and item["target_id"] == remove["id"]
    ]
    assert len(deleted_group_events) == 1
    assert deleted_group_events[0]["owner"] == {"kind": "user", "id": alice["id"]}
    assert deleted_group_events[0]["project_id"] is None

    me = await client.get("/api/v1/me", headers=ALICE)
    assert me.status_code == 200
    assert me.json()["user"]["id"] == alice["id"]
    assert {group["id"] for group in me.json()["user_groups"]} == {keep["id"]}
    members = await client.get(f"/api/v1/user-groups/{keep['id']}/members", headers=BOB)
    assert members.status_code == 200
    assert any(
        member["user_id"] == bob["id"] and member["status"] == "active" for member in members.json()
    )


@pytest.mark.asyncio
async def test_project_delete_removes_owned_lifecycle_rows_and_storage(
    client: httpx.AsyncClient,
    context,
    session: AsyncSession,
) -> None:
    project = await create_project_with_version(
        client, headers=ALICE, name="Delete Project", files={"main.py": "print('ok')"}
    )
    project_id = project["id"]
    variable = await client.put(
        f"/api/v1/projects/{project_id}/variables",
        json={"name": "PROJECT_VALUE", "value": "value"},
        headers=ALICE,
    )
    assert variable.status_code == 200, variable.text
    secret = await client.put(
        f"/api/v1/projects/{project_id}/secrets",
        json={"name": "PROJECT_SECRET", "value": "secret-value"},
        headers=ALICE,
    )
    assert secret.status_code == 204, secret.text

    versions = await client.get(f"/api/v1/projects/{project_id}/versions", headers=ALICE)
    version_id = versions.json()["items"][0]["id"]
    user_id = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]["id"]
    run_id = "run_issue51_terminal"
    snapshot_id = "snap_issue51_terminal"
    artifact_id = "art_issue51_terminal"
    now = datetime.now(UTC)
    compute_plan_id = (await session.execute(select(t.ComputePlanRow.id))).scalars().first()
    assert compute_plan_id is not None
    session.add(t.RunSnapshotRow(id=snapshot_id, payload={"project_id": project_id}))
    await session.flush()
    session.add(
        t.RunRow(
            id=run_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            compute_plan_id=compute_plan_id,
            project_version_id=version_id,
            project_version_label="v1",
            source_run_configuration_id=None,
            source_run_id=None,
            name="terminal run",
            status="succeeded",
            scheduler_job_id=None,
            exit_code=0,
            failure_reason="",
            initiated_by_user_id=user_id,
            created_at=now,
            submitted_at=now,
            started_at=now,
            finished_at=now,
        )
    )
    await session.flush()
    session.add(
        t.RunEventRow(
            id="event_issue51_terminal",
            run_id=run_id,
            type="finished",
            message="done",
            created_at=now,
        )
    )
    session.add(
        t.RunSecretRedactionRow(
            run_id=run_id,
            value_digest="digest_issue51",
            value="secret-value",
        )
    )
    session.add(
        t.IdempotencyKeyRow(
            initiated_by_user_id=user_id,
            key="issue51-key",
            endpoint="create_run",
            run_id=run_id,
            created_at=now,
        )
    )
    session.add(
        t.ArtifactRow(
            id=artifact_id,
            run_id=run_id,
            project_id=project_id,
            name="result",
            source_path="result.txt",
            size=3,
            file_count=1,
            content_hash="artifact-digest",
            status="available",
            description="",
            created_at=now,
            cleaned_at=None,
        )
    )
    await session.commit()

    run_root = context.storage.run_paths(run_id).root
    run_root.mkdir(parents=True)
    (run_root / "stdout.log").write_text("log", encoding="utf-8")
    artifact_root = Path(context.settings.storage_root) / "artifacts" / artifact_id
    artifact_root.mkdir(parents=True)
    (artifact_root / "result.txt").write_text("out", encoding="utf-8")

    impact = await client.get(f"/api/v1/projects/{project_id}/deletion-impact", headers=ALICE)
    assert impact.status_code == 200, impact.text
    impact_body = impact.json()
    assert impact_body["can_delete"] is True
    counts = {item["kind"]: item["count"] for item in impact_body["items"]}
    assert counts["working_state_files"] == 1
    assert counts["versions"] == 1
    assert counts["runs"] == 1
    assert counts["snapshots"] == 1
    assert counts["artifacts"] == 1

    unconfirmed = await client.delete(f"/api/v1/projects/{project_id}", headers=ALICE)
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["problems"] == ["请在确认影响范围后重试"]
    deleted = await client.delete(f"/api/v1/projects/{project_id}?confirm=true", headers=ALICE)
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"/api/v1/projects/{project_id}", headers=ALICE)).status_code == 404
    group_activities = await client.get(
        f"/api/v1/user-groups/{project['owner']['id']}/activities", headers=ALICE
    )
    assert group_activities.status_code == 200, group_activities.text
    deleted_project_events = [
        item
        for item in group_activities.json()["items"]
        if item["action"] == "project_deleted" and item["target_id"] == project_id
    ]
    assert deleted_project_events[0]["owner"]["kind"] == project["owner"]["kind"]
    assert deleted_project_events[0]["owner"]["id"] == project["owner"]["id"]
    assert deleted_project_events[0]["project_id"] is None
    assert (
        await client.get(f"/api/v1/projects/{project_id}/activities", headers=ALICE)
    ).status_code == 404
    assert not run_root.exists()
    assert not artifact_root.exists()
    assert (
        await session.execute(select(t.RunRow).where(t.RunRow.id == run_id))
    ).scalar_one_or_none() is None
    assert (
        await session.execute(select(t.RunSnapshotRow).where(t.RunSnapshotRow.id == snapshot_id))
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(t.ProjectVersionRow).where(t.ProjectVersionRow.project_id == project_id)
        )
    ).scalars().all() == []
    assert (
        await session.execute(
            select(t.ProjectFileRow).where(t.ProjectFileRow.project_id == project_id)
        )
    ).scalars().all() == []


@pytest.mark.asyncio
async def test_source_project_delete_preserves_fork_relation_history(client) -> None:
    source = await create_project_with_version(
        client, headers=ALICE, name="Fork Source", files={"source.txt": "source"}
    )
    versions = await client.get(f"/api/v1/projects/{source['id']}/versions", headers=ALICE)
    version_id = versions.json()["items"][0]["id"]
    alice_id = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]["id"]
    forked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_owner": {"kind": "user", "id": alice_id}, "name": "Fork Target"},
        headers=ALICE,
    )
    assert forked.status_code == 201, forked.text
    target_id = forked.json()["id"]

    deleted = await client.delete(f"/api/v1/projects/{source['id']}?confirm=true", headers=ALICE)
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"/api/v1/projects/{source['id']}", headers=ALICE)).status_code == 404
    assert (await client.get(f"/api/v1/projects/{target_id}", headers=ALICE)).status_code == 200
    relation = await client.get(f"/api/v1/projects/{target_id}/fork-source", headers=ALICE)
    assert relation.status_code == 200
    assert relation.json()["source_project_id"] == source["id"]
    assert relation.json()["source_project_name"] == "Fork Source"
