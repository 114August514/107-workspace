from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import text
from sqlalchemy import text as sql_text

from tests.helpers import (
    create_project_with_version,
    grant_test_entitlement,
    use_default_environment,
    wait_for_run,
)
from workspace107.domain.errors import SchedulerError
from workspace107.infrastructure.scheduler import MockScheduler


@pytest.mark.asyncio
async def test_run_snapshot_current_secret_rotation_and_redaction(client, session) -> None:
    me = await client.get("/api/v1/me")
    me.raise_for_status()
    user_id = me.json()["user"]["id"]
    group_id = await use_default_environment(session, client)
    project = await create_project_with_version(client, name="run-config-evidence")
    await grant_test_entitlement(session, "student")

    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "LEVEL", "project-level"),
        (f"/api/v1/user-groups/{group_id}", "LEVEL", "owner-level"),
        (f"/api/v1/user-groups/{group_id}", "OWNER_ONLY", "owner-only"),
        (f"/api/v1/users/{user_id}", "USER_LEVEL", "user-level"),
    ):
        response = await client.put(f"{owner}/variables", json={"name": name, "value": value})
        assert response.status_code == 200
    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "TOKEN", "project-token"),
        (f"/api/v1/user-groups/{group_id}", "TOKEN", "owner-token"),
        (f"/api/v1/user-groups/{group_id}", "OWNER_ONLY_SECRET", "owner-only-secret"),
        (f"/api/v1/users/{user_id}", "USER_TOKEN", "user-token"),
    ):
        response = await client.put(f"{owner}/secrets", json={"name": name, "value": value})
        assert response.status_code == 204

    command = (
        'python -c "import os,hashlib; '
        "print(os.environ['LEVEL']); print(os.environ['OWNER_ONLY']); "
        "print(os.environ['USER_LEVEL']); "
        "print(hashlib.sha256(os.environ['TOKEN'].encode()).hexdigest()); "
        "print(hashlib.sha256(os.environ['OWNER_ONLY_SECRET'].encode()).hexdigest()); "
        "print(hashlib.sha256(os.environ['USER_TOKEN'].encode()).hexdigest()); "
        "print(os.environ['TOKEN'])\""
    )
    config = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "execution-evidence",
            "command": command,
            "compute_plan_id": "plan_cpu_quick",
            "environment_variables": {
                "LEVEL": "${{ vars.LEVEL }}",
                "OWNER_ONLY": "${{ vars.OWNER_ONLY }}",
                "USER_LEVEL": "${{ user.vars.USER_LEVEL }}",
                "TOKEN": "${{ secrets.TOKEN }}",
                "OWNER_ONLY_SECRET": "${{ secrets.OWNER_ONLY_SECRET }}",
                "USER_TOKEN": "${{ user.secrets.USER_TOKEN }}",
            },
        },
    )
    assert config.status_code == 201
    config_id = config.json()["id"]
    preflight = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": config_id},
    )
    assert preflight.status_code == 200
    body = preflight.json()
    assert body["problems"] == []
    assert body["secret_references"] == {
        "TOKEN": f"project:{project['id']}:TOKEN",
        "OWNER_ONLY_SECRET": f"user_group:{group_id}:OWNER_ONLY_SECRET",
        "USER_TOKEN": f"user:{user_id}:USER_TOKEN",
    }
    assert "project-token" not in json.dumps(body)

    run = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": config_id}
    )
    assert run.status_code == 201
    detail = await wait_for_run(client, run.json()["id"])
    snapshot = detail["snapshot"]
    assert snapshot["environment_variables"] == {
        "LEVEL": "project-level",
        "OWNER_ONLY": "owner-only",
        "USER_LEVEL": "user-level",
    }
    assert snapshot["secret_references"] == {
        "TOKEN": f"project:{project['id']}:TOKEN",
        "OWNER_ONLY_SECRET": f"user_group:{group_id}:OWNER_ONLY_SECRET",
        "USER_TOKEN": f"user:{user_id}:USER_TOKEN",
    }
    assert "project-token" not in json.dumps(snapshot)
    logs = await client.get(f"/api/v1/runs/{run.json()['id']}/logs")
    logs.raise_for_status()
    text = json.dumps(logs.json())
    assert hashlib.sha256(b"project-token").hexdigest() in text
    assert "project-token" not in text

    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "LEVEL", "project-level-rotated"),
        (f"/api/v1/user-groups/{group_id}", "OWNER_ONLY", "owner-only-rotated"),
        (f"/api/v1/users/{user_id}", "USER_LEVEL", "user-level-rotated"),
    ):
        assert (
            await client.put(f"{owner}/variables", json={"name": name, "value": value})
        ).status_code == 200
    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "TOKEN", "project-token-rotated"),
        (f"/api/v1/user-groups/{group_id}", "OWNER_ONLY_SECRET", "owner-only-secret-rotated"),
        (f"/api/v1/users/{user_id}", "USER_TOKEN", "user-token-rotated"),
    ):
        assert (
            await client.put(f"{owner}/secrets", json={"name": name, "value": value})
        ).status_code == 204
    rerun = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert rerun.status_code == 201
    rerun_detail = await wait_for_run(client, rerun.json()["id"])
    assert rerun_detail["snapshot"]["environment_variables"] == snapshot["environment_variables"]
    rerun_logs = await client.get(f"/api/v1/runs/{rerun.json()['id']}/logs")
    rerun_text = json.dumps(rerun_logs.json())
    for value in ("project-token-rotated", "owner-only-secret-rotated", "user-token-rotated"):
        assert hashlib.sha256(value.encode()).hexdigest() in rerun_text
        assert value not in rerun_text

    before = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    assert (
        await client.delete(f"/api/v1/projects/{project['id']}/secrets/TOKEN")
    ).status_code == 204
    failed = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert failed.status_code == 422
    assert "exact Secret" in failed.text
    after = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    assert after == before
    assert (
        await client.get(f"/api/v1/runs/{run.json()['id']}", headers={"X-User": "foreign"})
    ).status_code == 404
    original_again = await client.get(f"/api/v1/runs/{run.json()['id']}/logs")
    original_text = json.dumps(original_again.json())

    await session.execute(
        sql_text("DELETE FROM run_secret_redactions WHERE run_id=:id"),
        {"id": run.json()["id"]},
    )
    await session.commit()
    missing_retention = await client.get(f"/api/v1/runs/{run.json()['id']}/logs")
    assert missing_retention.status_code == 422
    assert "project-token" not in original_text


@pytest.mark.asyncio
async def test_rerun_rechecks_concurrency_and_plan_limits(client, session) -> None:
    await client.get("/api/v1/me")
    await use_default_environment(session, client)
    project = await create_project_with_version(client, name="rerun-guards")
    await grant_test_entitlement(session, "student")
    config = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "guard",
            "command": "echo ok",
            "compute_plan_id": "plan_cpu_quick",
            "compute_request": {
                "nodes": 1,
                "cpus": 2,
                "memory_mb": 1,
                "gpus": 0,
                "time_limit_minutes": 1,
            },
        },
    )
    assert config.status_code == 201
    run = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": config.json()["id"]}
    )
    assert run.status_code == 201
    await wait_for_run(client, run.json()["id"])
    before = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    await session.execute(
        text(
            "UPDATE resource_entitlements SET max_concurrent_runs=1 "
            "WHERE user_id=(SELECT id FROM users WHERE username='student')"
        )
    )
    await session.execute(
        text("UPDATE runs SET status='running' WHERE id=:id"), {"id": run.json()["id"]}
    )
    await session.commit()
    blocked = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert blocked.status_code == 422
    assert (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"] == before
    await session.execute(
        text("UPDATE runs SET status='succeeded' WHERE id=:id"), {"id": run.json()["id"]}
    )
    await session.execute(text("UPDATE compute_plans SET max_cpus=1 WHERE id='plan_cpu_quick'"))
    await session.commit()
    blocked_plan = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert blocked_plan.status_code == 422
    assert (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"] == before


class _FailingScheduler(MockScheduler):
    async def submit(self, submission) -> str:
        raise SchedulerError("scheduler unavailable")


@pytest.mark.asyncio
async def test_scheduler_submit_failure_persists_run_and_notification(
    client, session, context
) -> None:
    context.scheduler = _FailingScheduler()
    await client.get("/api/v1/me")
    await use_default_environment(session, client)
    project = await create_project_with_version(client, name="submit-failure")
    await grant_test_entitlement(session, "student")
    config = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "failure",
            "command": "echo ok",
            "compute_plan_id": "plan_cpu_quick",
        },
    )
    assert config.status_code == 201
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": config.json()["id"]}
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "submit_failed"
    assert "scheduler unavailable" in run["failure_reason"]
    detail = await client.get(f"/api/v1/runs/{run['id']}")
    assert detail.status_code == 200
    assert detail.json()["run"]["failure_reason"] == run["failure_reason"]
    assert any(event["type"] == "submit_failed" for event in detail.json()["events"])
    notifications = await client.get("/api/v1/notifications")
    assert notifications.status_code == 200
    items = notifications.json()["items"]
    notification = next(item for item in items if item["type"] == "run_submit_failed")
    assert notification["target_type"] == "run"
    assert notification["target_id"] == run["id"]
