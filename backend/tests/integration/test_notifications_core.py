"""Notification Core observable behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from workspace107.application.notifier import Notifier
from workspace107.domain.enums import NotificationType, TargetType
from workspace107.domain.ids import NOTIFICATION, new_id
from workspace107.domain.models import Notification
from workspace107.domain.ownership import OwnerKind, OwnerReference
from workspace107.infrastructure.db.notifications import DatabaseNotificationPublisher
from workspace107.infrastructure.db.repositories import (
    NotificationRepositoryImpl,
    SqlRepositories,
)

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _user_id(client, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/me", headers=headers)
    response.raise_for_status()
    return response.json()["user"]["id"]


@pytest.mark.asyncio
async def test_notification_can_switch_read_state_and_count(client, session) -> None:
    alice_id = await _user_id(client, ALICE)
    repos = SqlRepositories(session)
    created_at = datetime(2026, 8, 20, tzinfo=UTC)
    await repos.notifications.add(
        Notification(
            id=new_id(NOTIFICATION),
            recipient_id=alice_id,
            type=NotificationType.RUN_SUCCEEDED,
            title="Run 完成",
            body="",
            created_at=created_at,
            target_type=TargetType.RUN,
            target_id="run-1",
        )
    )
    await session.commit()

    listed = await client.get("/api/v1/notifications", headers=ALICE)
    notification_id = listed.json()["items"][0]["id"]
    assert (await client.get("/api/v1/notifications/unread-count", headers=ALICE)).json() == {
        "unread": 1
    }

    assert (
        await client.post(f"/api/v1/notifications/{notification_id}/read", headers=ALICE)
    ).status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=ALICE)).json() == {
        "unread": 0
    }
    assert (
        await client.post(f"/api/v1/notifications/{notification_id}/unread", headers=ALICE)
    ).status_code == 204
    assert (await client.get("/api/v1/notifications/unread-count", headers=ALICE)).json() == {
        "unread": 1
    }


@pytest.mark.asyncio
async def test_optional_preferences_suppress_only_optional_events(client, session, context) -> None:
    alice_id = await _user_id(client, ALICE)
    repos = SqlRepositories(session)
    notifier = Notifier(
        DatabaseNotificationPublisher(repos.notifications),
        context.clock,
        session,
        repos.notifications,
    )
    disabled = await client.put(
        "/api/v1/notifications/preferences/run_succeeded",
        json={"enabled": False},
        headers=ALICE,
    )
    assert disabled.status_code == 200
    assert disabled.json() == {
        "type": "run_succeeded",
        "enabled": False,
        "mandatory": False,
    }

    await notifier.run_finished(
        recipient_id=alice_id, run_id="run-optional", run_name="optional", succeeded=True
    )
    await notifier.member_removed(
        actor_id="actor", member_id=alice_id, user_group_id="group", user_group_name="group"
    )
    await session.commit()
    items = (await client.get("/api/v1/notifications", headers=ALICE)).json()["items"]
    assert [item["type"] for item in items] == ["member_removed"]

    blocked = await client.put(
        "/api/v1/notifications/preferences/member_removed",
        json={"enabled": False},
        headers=ALICE,
    )
    assert blocked.status_code == 422
    assert (await client.get("/api/v1/notifications/preferences", headers=ALICE)).status_code == 200


@pytest.mark.asyncio
async def test_role_change_notifies_the_affected_member(client) -> None:
    await _user_id(client, ALICE)
    bob_id = await _user_id(client, BOB)
    group = await client.post(
        "/api/v1/user-groups",
        json={"name": "Role notification lab"},
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
    accepted = await client.post(
        f"/api/v1/user-groups/{group_id}/invitation",
        json={"accept": True},
        headers=BOB,
    )
    assert accepted.status_code == 204

    changed = await client.patch(
        f"/api/v1/user-groups/{group_id}/members/{bob_id}",
        json={"role": "admin"},
        headers=ALICE,
    )
    assert changed.status_code == 200

    notifications = await client.get("/api/v1/notifications", headers=BOB)
    assert notifications.status_code == 200
    role_change = next(
        item for item in notifications.json()["items"] if item["type"] == "role_changed"
    )
    assert role_change["mandatory"] is True
    assert role_change["target_type"] == "user_group"
    assert role_change["target_id"] == group_id


@pytest.mark.asyncio
async def test_core_event_notifiers_have_explicit_types_and_targets(
    client, session, context
) -> None:
    alice_id = await _user_id(client, ALICE)
    repos = SqlRepositories(session)
    notifier = Notifier(
        DatabaseNotificationPublisher(repos.notifications),
        context.clock,
        session,
        repos.notifications,
    )
    await notifier.asset_unavailable(
        recipient_id=alice_id,
        project_id="project-1",
        project_name="Project",
        type=NotificationType.ENVIRONMENT_UNAVAILABLE,
        asset_label="Environment v1",
        detail="不可用",
    )
    await notifier.asset_unavailable(
        recipient_id=alice_id,
        project_id="project-1",
        project_name="Project",
        type=NotificationType.SHARED_RESOURCE_UNAVAILABLE,
        asset_label="Dataset v1",
        detail="内容不可用",
    )
    await notifier.platform_incident(recipient_id=alice_id, title="平台维护", body="服务异常")
    await session.commit()

    items = (await client.get("/api/v1/notifications", headers=ALICE)).json()["items"]
    assert {item["type"] for item in items} == {
        "environment_unavailable",
        "shared_resource_unavailable",
        "platform_incident",
    }
    assert all(item["mandatory"] for item in items)
    asset_items = [
        item
        for item in items
        if item["type"] in {"environment_unavailable", "shared_resource_unavailable"}
    ]
    assert all(item["target_type"] == "project" for item in asset_items)


@pytest.mark.asyncio
async def test_notification_preferences_are_recipient_scoped(client) -> None:
    await _user_id(client, ALICE)
    await _user_id(client, BOB)
    response = await client.put(
        "/api/v1/notifications/preferences/run_failed",
        json={"enabled": False},
        headers=ALICE,
    )
    assert response.status_code == 200
    bob_preferences = await client.get("/api/v1/notifications/preferences", headers=BOB)
    run_failed = next(item for item in bob_preferences.json() if item["type"] == "run_failed")
    assert run_failed["enabled"] is True


@pytest.mark.asyncio
async def test_shared_resource_permission_failure_does_not_emit_unavailable(
    services, monkeypatch
) -> None:
    version = SimpleNamespace(shared_resource_id="shr-1")
    resource = SimpleNamespace(id="shr-1", owner=OwnerReference(OwnerKind.USER, "resource-owner"))

    async def not_discoverable(_user_id: str, _version_id: str):
        return None

    async def trusted_version(_version_id: str):
        return version

    async def trusted_resource(_resource_id: str):
        return resource

    async def no_grant(*_args):
        return False

    monkeypatch.setattr(
        services.runs._repos.shared_resources,
        "get_version_discoverable_for_user",
        not_discoverable,
    )
    monkeypatch.setattr(services.runs._repos.shared_resources, "get_version_by_id", trusted_version)
    monkeypatch.setattr(services.runs._repos.shared_resources, "get_by_id", trusted_resource)
    monkeypatch.setattr(services.runs._repos.grants, "exists_use_grant", no_grant)

    message = await services.runs._check_shared_resource_version_input(
        "user-without-grant",
        "shrv-1",
        "/inputs/data",
        "",
        OwnerReference(OwnerKind.USER_GROUP, "project-owner"),
        raise_unavailable=True,
    )

    assert message == "输入 /inputs/data 引用的 Shared Resource Version 不存在或无权访问"


@pytest.mark.asyncio
async def test_notification_preference_failure_does_not_break_invitation(
    client, monkeypatch
) -> None:
    await _user_id(client, ALICE)
    await _user_id(client, BOB)
    group = await client.post(
        "/api/v1/user-groups",
        json={"name": "Preference failure lab"},
        headers=ALICE,
    )
    assert group.status_code == 201

    async def fail_preference(_self, _user_id: str, _type: NotificationType) -> bool:
        raise RuntimeError("preference store unavailable")

    monkeypatch.setattr(NotificationRepositoryImpl, "is_enabled", fail_preference)
    invited = await client.post(
        f"/api/v1/user-groups/{group.json()['id']}/members",
        json={"username": "bob"},
        headers=ALICE,
    )

    assert invited.status_code == 201
