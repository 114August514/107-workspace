from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from tests.helpers import (
    create_project_with_version,
    grant_test_entitlement,
    use_default_environment,
)
from workspace107.domain.errors import ValidationFailed


@pytest.mark.asyncio
async def test_run_snapshot_current_secret_rotation_and_redaction(
    client, session, services
) -> None:
    me = await client.get("/api/v1/me")
    me.raise_for_status()
    user_id = me.json()["user"]["id"]
    group_id, env_version_id = await use_default_environment(session, client)
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

    config = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "snapshot-evidence",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
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
    assert body["resolved_environment_variables"] == {
        "LEVEL": "project-level",
        "OWNER_ONLY": "owner-only",
        "USER_LEVEL": "user-level",
    }
    expected_secret_references = {
        "TOKEN": f"project:{project['id']}:TOKEN",
        "OWNER_ONLY_SECRET": f"user_group:{group_id}:OWNER_ONLY_SECRET",
        "USER_TOKEN": f"user:{user_id}:USER_TOKEN",
    }
    assert body["secret_references"] == expected_secret_references
    assert all(
        value not in json.dumps(body)
        for value in ("project-token", "owner-only-secret", "user-token")
    )

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": config_id}
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "queued"
    assert run["scheduler_job_id"] is None
    assert run["initiated_by_user_id"] == user_id
    detail_response = await client.get(f"/api/v1/runs/{run['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["run"]["id"] == run["id"]
    assert detail["run"]["status"] == "queued"
    snapshot = detail["snapshot"]
    assert snapshot["source_run_configuration_id"] == config_id
    assert snapshot["project_id"] == project["id"]
    assert snapshot["project_version_id"] == body["project_version_id"]
    assert snapshot["environment_version_id"] == env_version_id
    assert snapshot["command"] == "python main.py"
    assert snapshot["compute_plan_id"] == "plan_cpu_quick"
    assert snapshot["initiated_by_user_id"] == user_id
    assert snapshot["environment_variables"] == body["resolved_environment_variables"]
    assert snapshot["secret_references"] == expected_secret_references
    assert all(
        value not in json.dumps(detail)
        for value in ("project-token", "owner-only-secret", "user-token")
    )

    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "LEVEL", "project-level-rotated"),
        (f"/api/v1/user-groups/{group_id}", "OWNER_ONLY", "owner-only-rotated"),
        (f"/api/v1/users/{user_id}", "USER_LEVEL", "user-level-rotated"),
    ):
        assert (
            await client.put(f"{owner}/variables", json={"name": name, "value": value})
        ).status_code == 200
    rotated_secrets = {
        "TOKEN": "project-token-rotated",
        "OWNER_ONLY_SECRET": "owner-only-secret-rotated",
        "USER_TOKEN": "user-token-rotated",
    }
    for owner, name, value in (
        (f"/api/v1/projects/{project['id']}", "TOKEN", rotated_secrets["TOKEN"]),
        (
            f"/api/v1/user-groups/{group_id}",
            "OWNER_ONLY_SECRET",
            rotated_secrets["OWNER_ONLY_SECRET"],
        ),
        (f"/api/v1/users/{user_id}", "USER_TOKEN", rotated_secrets["USER_TOKEN"]),
    ):
        assert (
            await client.put(f"{owner}/secrets", json={"name": name, "value": value})
        ).status_code == 204

    persisted = await services.runs.get_detail(user_id, run["id"])
    validated = await services.runs._execution_context.validate(persisted.run, persisted.snapshot)
    assert validated.secret_values == rotated_secrets
    await session.commit()

    rerun_response = await client.post(f"/api/v1/runs/{run['id']}/rerun")
    assert rerun_response.status_code == 201
    rerun = rerun_response.json()
    assert rerun["status"] == "queued"
    assert rerun["scheduler_job_id"] is None
    assert rerun["source_run_id"] == run["id"]
    rerun_detail_response = await client.get(f"/api/v1/runs/{rerun['id']}")
    rerun_detail_response.raise_for_status()
    rerun_detail = rerun_detail_response.json()
    rerun_snapshot = rerun_detail["snapshot"]
    assert rerun_snapshot["id"] != snapshot["id"]
    rerun_execution_snapshot = {
        key: value for key, value in rerun_snapshot.items() if key not in {"id", "created_at"}
    }
    original_execution_snapshot = {
        key: value for key, value in snapshot.items() if key not in {"id", "created_at"}
    }
    assert rerun_execution_snapshot == original_execution_snapshot
    assert all(value not in json.dumps(rerun_detail) for value in rotated_secrets.values())

    persisted_rerun = await services.runs.get_detail(user_id, rerun["id"])
    rerun_context = await services.runs._execution_context.validate(
        persisted_rerun.run, persisted_rerun.snapshot
    )
    assert rerun_context.secret_values == rotated_secrets
    await session.commit()

    assert (
        await client.get(f"/api/v1/runs/{run['id']}", headers={"X-User": "foreign"})
    ).status_code == 404
    before = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    assert (
        await client.delete(f"/api/v1/projects/{project['id']}/secrets/TOKEN")
    ).status_code == 204
    session.expire_all()
    with pytest.raises(ValidationFailed, match="exact Secret"):
        await services.runs._execution_context.validate(persisted.run, persisted.snapshot)
    failed = await client.post(f"/api/v1/runs/{run['id']}/rerun")
    assert failed.status_code == 422
    assert "exact Secret" in failed.text
    after = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    assert after == before


@pytest.mark.asyncio
async def test_rerun_rechecks_concurrency_and_plan_limits(client, session) -> None:
    await client.get("/api/v1/me")
    _, env_version_id = await use_default_environment(session, client)
    project = await create_project_with_version(client, name="rerun-guards")
    await grant_test_entitlement(session, "student")
    config = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "guard",
            "command": "echo ok",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
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
    before = (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"]
    await session.execute(
        text(
            "UPDATE resource_entitlements SET max_concurrent_runs=1 "
            "WHERE user_id=(SELECT id FROM users WHERE username='student')"
        )
    )
    await session.commit()
    blocked = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert blocked.status_code == 422
    assert (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"] == before
    await session.execute(
        text("UPDATE runs SET status='succeeded', finished_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": run.json()["id"]},
    )
    await session.execute(text("UPDATE compute_plans SET max_cpus=1 WHERE id='plan_cpu_quick'"))
    await session.commit()
    blocked_plan = await client.post(f"/api/v1/runs/{run.json()['id']}/rerun")
    assert blocked_plan.status_code == 422
    assert (await client.get(f"/api/v1/projects/{project['id']}/runs")).json()["total"] == before
