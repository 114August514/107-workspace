from __future__ import annotations

import io
import zipfile

import pytest

from tests.helpers import (
    create_project_with_version,
    grant_test_entitlement,
    use_default_environment,
    wait_for_run,
)


@pytest.mark.asyncio
async def test_adjusted_rerun_creates_new_snapshot_without_mutating_source(client, session) -> None:
    _, environment_version_id = await use_default_environment(session, client)
    project = await create_project_with_version(client, name="adjusted-rerun")
    await grant_test_entitlement(session, "student")
    configuration = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "source",
            "command": "echo original",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
        },
    )
    assert configuration.status_code == 201
    created = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration.json()["id"]},
    )
    assert created.status_code == 201
    source = await wait_for_run(client, created.json()["id"])

    adjusted = await client.post(
        f"/api/v1/runs/{created.json()['id']}/rerun/adjusted",
        json={
            "name": "adjusted",
            "project_version_id": source["snapshot"]["project_version_id"],
            "environment_version_id": environment_version_id,
            "working_directory": ".",
            "command": "echo adjusted",
            "compute_request": source["snapshot"]["compute_request"],
            "input_bindings": [],
        },
    )
    assert adjusted.status_code == 201, adjusted.text
    assert adjusted.json()["id"] != created.json()["id"]
    assert adjusted.json()["source_run_id"] == created.json()["id"]

    adjusted_detail = await wait_for_run(client, adjusted.json()["id"])
    assert adjusted_detail["snapshot"]["command"] == "echo adjusted"
    assert adjusted_detail["snapshot"]["environment_version_id"] == environment_version_id
    source_again = await client.get(f"/api/v1/runs/{created.json()['id']}")
    assert source_again.json()["snapshot"]["command"] == "echo original"

    invalid = await client.post(
        f"/api/v1/runs/{created.json()['id']}/rerun/adjusted",
        json={
            "name": "invalid",
            "project_version_id": source["snapshot"]["project_version_id"],
            "environment_version_id": "env_missing",
            "working_directory": ".",
            "command": "echo invalid",
            "compute_request": source["snapshot"]["compute_request"],
            "input_bindings": [],
        },
    )
    assert invalid.status_code == 422
    assert "运行环境版本" in invalid.text


@pytest.mark.asyncio
async def test_run_logs_and_artifact_downloads_are_complete(client, session) -> None:
    _, environment_version_id = await use_default_environment(session, client)
    project = await create_project_with_version(client, name="run-downloads")
    await grant_test_entitlement(session, "student")
    configuration = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "outputs",
            "command": (
                'python -c "from pathlib import Path; '
                "Path('outputs').mkdir(); "
                "Path('outputs/result.txt').write_text('artifact-content'); "
                "print('x' * 300000)\""
            ),
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "artifact_rules": [{"path": "outputs", "name": "outputs", "optional": False}],
        },
    )
    assert configuration.status_code == 201
    created = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration.json()["id"]},
    )
    assert created.status_code == 201
    detail = await wait_for_run(client, created.json()["id"])
    artifact = detail["artifacts"][0]

    logs = await client.get(
        f"/api/v1/runs/{created.json()['id']}/logs/download",
        params={"stream": "stdout"},
    )
    assert logs.status_code == 200
    assert len(logs.content) > 300000
    assert 'filename="stdout.log"' in logs.headers["content-disposition"]

    archive = await client.get(f"/api/v1/artifacts/{artifact['id']}/download")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert bundle.namelist() == ["result.txt"]
        assert bundle.read("result.txt") == b"artifact-content"

    foreign = await client.get(
        f"/api/v1/artifacts/{artifact['id']}/download", headers={"X-User": "foreign"}
    )
    assert foreign.status_code == 404
