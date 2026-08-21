from __future__ import annotations

import hashlib
import json

import pytest

from tests.helpers import (
    create_project_with_version,
    grant_test_entitlement,
    use_default_environment,
    wait_for_run,
)


@pytest.mark.asyncio
async def test_run_snapshot_current_secret_rotation_and_redaction(client, session) -> None:
    me = await client.get("/api/v1/me")
    me.raise_for_status()
    user_id = me.json()["user"]["id"]
    group_id = await use_default_environment(client)
    project = await create_project_with_version(client, name="run-config-evidence")
    await grant_test_entitlement(session, group_id)

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
            "environment_version_id": "ev_python_312",
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
    assert "project:" in json.dumps(body["secret_references"])
    assert "owner" not in json.dumps(body["secret_references"])
    assert "project-token" not in json.dumps(body)

    run = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": config_id}
    )
    assert run.status_code == 201
    detail = await wait_for_run(client, run.json()["id"])
    snapshot = detail["snapshot"]
    assert snapshot["environment_variables"]["LEVEL"] == "project-level"
    assert "project:" in json.dumps(snapshot["secret_references"])
    assert "project-token" not in json.dumps(snapshot)
    logs = await client.get(f"/api/v1/runs/{run.json()['id']}/logs")
    logs.raise_for_status()
    text = json.dumps(logs.json())
    assert hashlib.sha256(b"project-token").hexdigest() in text
    assert "project-token" not in text
