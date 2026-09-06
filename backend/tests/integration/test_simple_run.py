"""Simple Run preview consistency, current authorization and batch outputs."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import grant_test_entitlement, wait_for_run
from tests.integration.test_run_initiated_by_user import (
    ALICE,
    _create_configuration,
    _create_environment,
    _create_group,
    _create_project,
)
from workspace107.infrastructure.db.tables import ComputePlanRow, ResourceEntitlementRow


async def setup_run(client, session):
    group = await _create_group(client, "Simple Run")
    _, environment = await _create_environment(session, owner_user_group_id=group)
    await grant_test_entitlement(session, "alice")
    project = await _create_project(client, group, name="simple")
    configuration = await _create_configuration(client, project, environment)
    return group, project, configuration


async def preview(client, project, configuration):
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    response.raise_for_status()
    assert response.json()["ok"]
    return response.json()


def draft(configuration, result):
    return {
        "run_configuration_id": configuration["id"],
        "project_version_id": result["project_version_id"],
        "confirmation_token": result["confirmation_token"],
    }


@pytest.mark.parametrize("change", ["command", "artifact", "plan"])
async def test_preview_change_requires_confirmation(
    client: httpx.AsyncClient, session: AsyncSession, change
):
    _, project, configuration = await setup_run(client, session)
    result = await preview(client, project, configuration)
    if change == "plan":
        await session.execute(
            update(ComputePlanRow)
            .where(ComputePlanRow.id == "plan_cpu_quick")
            .values(default_cpus=3)
        )
        await session.commit()
    else:
        patch = (
            {"command": "echo changed"}
            if change == "command"
            else {"artifact_rules": [{"path": "new-output", "optional": True}]}
        )
        response = await client.put(
            f"/api/v1/run-configurations/{configuration['id']}",
            json={**configuration, **patch},
            headers=ALICE,
        )
        response.raise_for_status()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json=draft(configuration, result), headers=ALICE
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "run_confirmation_changed"
    runs = await client.get(f"/api/v1/projects/{project['id']}/runs", headers=ALICE)
    assert runs.json()["total"] == 0


async def test_confirmed_version_stays_pinned_and_retries_replay(client, session):
    _, project, configuration = await setup_run(client, session)
    result = await preview(client, project, configuration)
    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "new.txt", "content": "new"},
        headers=ALICE,
    )
    response.raise_for_status()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "v2"}, headers=ALICE
    )
    response.raise_for_status()
    headers = {**ALICE, "Idempotency-Key": "simple-intent"}
    url = f"/api/v1/projects/{project['id']}/runs"
    first = await client.post(url, json=draft(configuration, result), headers=headers)
    assert first.status_code == 201, first.text
    second = await client.post(url, json=draft(configuration, result), headers=headers)
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["project_version_id"] == result["project_version_id"]


async def test_confirmation_does_not_replace_current_entitlement(client, session):
    _, project, configuration = await setup_run(client, session)
    result = await preview(client, project, configuration)
    await session.execute(
        update(ResourceEntitlementRow).values(expires_at="2000-01-01T00:00:00+00:00")
    )
    await session.commit()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json=draft(configuration, result), headers=ALICE
    )
    assert response.status_code == 422
    assert response.json()["code"] == "preflight_rejected"


async def test_optional_output_missing_keeps_success_and_batch_logs(client, session):
    _, project, configuration = await setup_run(client, session)
    response = await client.put(
        f"/api/v1/run-configurations/{configuration['id']}",
        headers=ALICE,
        json={
            **configuration,
            "command": (
                "python -c \"import sys; assert sys.stdin.read() == ''; "
                "print('hello'); print('warning', file=sys.stderr)\""
            ),
            "artifact_rules": [{"path": "outputs/", "optional": True}],
        },
    )
    response.raise_for_status()
    result = await preview(client, project, configuration)
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json=draft(configuration, result), headers=ALICE
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]
    detail = await wait_for_run(client, run_id, headers=ALICE)
    assert detail["run"]["status"] == "succeeded"
    assert detail["artifacts"] == []
    logs = await client.get(f"/api/v1/runs/{run_id}/logs", headers=ALICE)
    logs.raise_for_status()
    assert any("hello" in chunk["content"] for chunk in logs.json())
    assert any("warning" in chunk["content"] for chunk in logs.json())


async def test_variable_changes_require_confirmation_but_secret_rotation_keeps_exact_reference(
    client,
    session,
):
    _, project, configuration = await setup_run(client, session)
    scope = f"/api/v1/projects/{project['id']}"
    for kind, name, value in [("variables", "EPOCHS", "1"), ("secrets", "TOKEN", "first-value")]:
        response = await client.put(
            f"{scope}/{kind}", json={"name": name, "value": value}, headers=ALICE
        )
        response.raise_for_status()
    response = await client.put(
        f"/api/v1/run-configurations/{configuration['id']}",
        headers=ALICE,
        json={
            **configuration,
            "environment_variables": {
                "EPOCHS": "${{ vars.EPOCHS }}",
                "TOKEN": "${{ secrets.TOKEN }}",
            },
        },
    )
    response.raise_for_status()
    initial = await preview(client, project, configuration)
    assert "first-value" not in str(initial)
    response = await client.put(
        f"{scope}/secrets", json={"name": "TOKEN", "value": "rotated-value"}, headers=ALICE
    )
    response.raise_for_status()
    rotated = await preview(client, project, configuration)
    assert rotated["confirmation_token"] == initial["confirmation_token"]
    assert "rotated-value" not in str(rotated)
    response = await client.put(
        f"{scope}/variables", json={"name": "EPOCHS", "value": "2"}, headers=ALICE
    )
    response.raise_for_status()
    response = await client.post(f"{scope}/runs", json=draft(configuration, initial), headers=ALICE)
    assert response.status_code == 409
