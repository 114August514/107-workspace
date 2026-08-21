import pytest

from tests.helpers import create_project_with_version, ensure_user_group


@pytest.mark.asyncio
async def test_fork_preserves_config_expressions_without_copying_scope_values(client) -> None:
    source = await create_project_with_version(client, name="source-config")
    source_group = await ensure_user_group(client)
    versions = await client.get(f"/api/v1/projects/{source['id']}/versions")
    assert versions.status_code == 200
    version_id = versions.json()["items"][0]["id"]
    expressions = {
        "STANDARD_VAR": "${{ vars.LEVEL }}",
        "STANDARD_SECRET": "${{ secrets.TOKEN }}",
        "USER_VAR": "${{ user.vars.LEVEL }}",
        "USER_SECRET": "${{ user.secrets.TOKEN }}",
    }
    source_config = await client.post(
        f"/api/v1/projects/{source['id']}/run-configurations",
        json={
            "name": "config",
            "command": "echo ok",
            "compute_plan_id": "plan_cpu_quick",
            "environment_variables": expressions,
        },
    )
    assert source_config.status_code == 201
    for suffix, payload in (
        ("variables", {"name": "LEVEL", "value": "source"}),
        ("secrets", {"name": "TOKEN", "value": "source-secret"}),
    ):
        response = await client.put(f"/api/v1/projects/{source['id']}/{suffix}", json=payload)
        assert response.status_code in (200, 204)
    target_group = await client.post("/api/v1/user-groups", json={"name": "fork-target"})
    assert target_group.status_code == 201
    target_id = target_group.json()["id"]
    fork = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": target_id, "name": "target-config"},
    )
    assert fork.status_code == 201
    target = fork.json()
    configs = await client.get(f"/api/v1/projects/{target['id']}/run-configurations")
    assert configs.status_code == 200
    assert configs.json()[0]["environment_variables"] == expressions
    assert (await client.get(f"/api/v1/projects/{target['id']}/variables")).json() == []
    assert (await client.get(f"/api/v1/projects/{target['id']}/secrets")).json() == []
    preflight = await client.post(
        f"/api/v1/projects/{target['id']}/runs/preflight",
        json={"run_configuration_id": configs.json()[0]["id"]},
    )
    assert preflight.status_code == 200
    assert preflight.json()["problems"]
