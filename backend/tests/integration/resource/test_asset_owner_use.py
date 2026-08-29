"""Issue #39 asset use is scoped to the consuming Project owner."""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import grant_test_entitlement, wait_for_run
from workspace107.domain import ids
from workspace107.infrastructure.db.tables import (
    EnvironmentRow,
    EnvironmentVersionRow,
    RunConfigurationRow,
    RunRow,
    SharedResourceRow,
    SharedResourceVersionRow,
)

ALICE = {"X-User": "alice"}


async def _create_group(client: httpx.AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/user-groups", json={"name": name}, headers=ALICE)
    response.raise_for_status()
    return str(response.json()["id"])


async def _create_project_with_version(
    client: httpx.AsyncClient, user_group_id: str, *, name: str
) -> dict:
    response = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user_group", "id": user_group_id}, "name": name},
        headers=ALICE,
    )
    response.raise_for_status()
    project = response.json()
    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=ALICE,
    )
    response.raise_for_status()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "v1"},
        headers=ALICE,
    )
    response.raise_for_status()
    project["_version_id"] = response.json()["id"]
    return project


async def _create_resource_version(client: httpx.AsyncClient, user_group_id: str) -> str:
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "owner": {"kind": "user_group", "id": user_group_id},
            "name": "Group B resource",
        },
        headers=ALICE,
    )
    response.raise_for_status()
    resource_id = str(response.json()["id"])
    response = await client.post(
        f"/api/v1/shared-resources/{resource_id}/versions",
        data={"description": "v1"},
        files={"files": ("data.txt", b"data", "text/plain")},
        headers=ALICE,
    )
    response.raise_for_status()
    return str(response.json()["id"])


async def _create_environment_version(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    owner_user_group_id: str | None = None,
) -> str:
    environment_id = ids.new_id(ids.ENVIRONMENT)
    version_id = ids.new_id(ids.ENVIRONMENT_VERSION)
    session.add(
        EnvironmentRow(
            id=environment_id,
            name=f"{environment_id} environment",
            description="",
            owner_user_id=owner_user_id,
            owner_user_group_id=owner_user_group_id,
        )
    )
    await session.flush()
    session.add(
        EnvironmentVersionRow(
            id=version_id,
            environment_id=environment_id,
            version="1",
            description="",
        )
    )
    await session.commit()
    return version_id


async def _set_group_environment(
    session: AsyncSession, client: httpx.AsyncClient, user_group_id: str
) -> str:
    return await _create_environment_version(session, owner_user_group_id=user_group_id)


async def test_issue_39_actor_in_a_and_b_cannot_use_b_resource_for_a_project(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Discovery through B membership must not authorize use by an A-owned Project."""
    group_a = await _create_group(client, "Group A")
    group_b = await _create_group(client, "Group B")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_version_id = await _create_resource_version(client, group_b)

    # Alice is an active Owner member of both groups, so B remains discoverable.
    response = await client.get(
        f"/api/v1/shared-resource-versions/{resource_version_id}", headers=ALICE
    )
    assert response.status_code == 200

    attempted = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "cross-owner",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert attempted.status_code == 404, attempted.text

    # Simulate stale/bypassed persisted state: Run preflight must enforce the same boundary.
    configuration_id = "rc_cross_owner_bypass"
    session.add(
        RunConfigurationRow(
            id=configuration_id,
            project_id=project["id"],
            name="bypassed",
            description="",
            working_directory=".",
            command="python main.py",
            environment_version_id=environment_version_id,
            environment_variables={},
            input_bindings=[
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_version_id,
                    "access_path": "/inputs/data",
                    "source_subpath": "",
                }
            ],
            compute_plan_id="plan_cpu_quick",
            compute_request=None,
            artifact_rules=[],
        )
    )
    await session.commit()

    preflight = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers=ALICE,
    )
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["ok"] is False
    assert len(preflight_body["problems"]) == 1

    create = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration_id},
        headers=ALICE,
    )
    assert create.status_code == 422
    assert create.json()["code"] == "preflight_rejected"
    assert len(create.json()["problems"]) == 1
    persisted_runs = (
        await session.execute(select(RunRow.id).where(RunRow.project_id == project["id"]))
    ).scalars()
    assert list(persisted_runs) == []


async def test_issue_39_environment_assignment_requires_exact_project_owner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group_a = await _create_group(client, "Environment Group A")
    group_b = await _create_group(client, "Environment Group B")
    environment_a = await _set_group_environment(session, client, group_a)
    environment_b = await _set_group_environment(session, client, group_b)
    home = await client.get("/api/v1/me", headers=ALICE)
    home.raise_for_status()
    user_environment = await _create_environment_version(
        session, owner_user_id=home.json()["user"]["id"]
    )
    project = await _create_project_with_version(client, group_a, name="Environment owner A")

    # Project assignment rejects both another Group's asset and the actor's User asset.
    for version_id in (environment_b, user_environment):
        response = await client.patch(
            f"/api/v1/projects/{project['id']}",
            json={"environment_version_id": version_id},
            headers=ALICE,
        )
        assert response.status_code == 404
    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": environment_a},
        headers=ALICE,
    )
    assert response.status_code == 200

    for version_id in (environment_b, user_environment):
        response = await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": f"cross-owner-{version_id}",
                "command": "python main.py",
                "environment_version_id": version_id,
                "compute_plan_id": "plan_cpu_quick",
            },
            headers=ALICE,
        )
        assert response.status_code == 404

    same_owner = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "same-owner",
            "command": "python main.py",
            "environment_version_id": environment_a,
            "compute_plan_id": "plan_cpu_quick",
        },
        headers=ALICE,
    )
    assert same_owner.status_code == 201, same_owner.text

    # A bypassed exact Environment reference is rejected again during Run resolution.
    await grant_test_entitlement(session, "alice")
    bypass_id = "rc_environment_owner_bypass"
    session.add(
        RunConfigurationRow(
            id=bypass_id,
            project_id=project["id"],
            name="bypassed environment",
            description="",
            working_directory=".",
            command="python main.py",
            environment_version_id=environment_b,
            environment_variables={},
            input_bindings=[],
            compute_plan_id="plan_cpu_quick",
            compute_request=None,
            artifact_rules=[],
        )
    )
    await session.commit()
    preflight = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": bypass_id},
        headers=ALICE,
    )
    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["ok"] is False
    assert len(preflight_body["problems"]) == 1


async def test_issue_39_fork_validates_assets_against_target_owner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group_a = await _create_group(client, "Fork Group A")
    group_b = await _create_group(client, "Fork Group B")
    environment_a = await _set_group_environment(session, client, group_a)
    project = await _create_project_with_version(client, group_a, name="Fork source")
    resource_a = await _create_resource_version(client, group_a)
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "source config",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_a,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_a,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": environment_a},
        headers=ALICE,
    )
    assert response.status_code == 200

    cross_environment = await client.post(
        f"/api/v1/versions/{project['_version_id']}/fork",
        json={
            "target_owner": {"kind": "user_group", "id": group_b},
            "name": "cross Environment fork",
        },
        headers=ALICE,
    )
    assert cross_environment.status_code == 404

    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": None},
        headers=ALICE,
    )
    assert response.status_code == 200
    cross_resource = await client.post(
        f"/api/v1/versions/{project['_version_id']}/fork",
        json={"target_owner": {"kind": "user_group", "id": group_b}, "name": "cross Resource fork"},
        headers=ALICE,
    )
    assert cross_resource.status_code == 404

    same_owner = await client.post(
        f"/api/v1/versions/{project['_version_id']}/fork",
        json={"target_owner": {"kind": "user_group", "id": group_a}, "name": "same owner fork"},
        headers=ALICE,
    )
    assert same_owner.status_code == 201, same_owner.text
    configurations = await client.get(
        f"/api/v1/projects/{same_owner.json()['id']}/run-configurations", headers=ALICE
    )
    configurations.raise_for_status()
    assert configurations.json()[0]["input_bindings"][0]["source_id"] == resource_a


async def test_issue_39_rerun_revalidates_snapshot_asset_owners(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group_a = await _create_group(client, "Rerun Group A")
    group_b = await _create_group(client, "Rerun Group B")
    environment_a = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="Rerun source")
    resource_a = await _create_resource_version(client, group_a)
    configuration = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "same-owner run",
            "command": "python main.py",
            "environment_version_id": environment_a,
            "compute_plan_id": "plan_cpu_quick",
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_a,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert configuration.status_code == 201, configuration.text
    create = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration.json()["id"]},
        headers=ALICE,
    )
    assert create.status_code == 201, create.text
    detail = await wait_for_run(client, create.json()["id"], headers=ALICE)
    assert detail["run"]["status"] == "succeeded"

    environment_version = await session.get(EnvironmentVersionRow, environment_a)
    assert environment_version is not None
    environment = await session.get(EnvironmentRow, environment_version.environment_id)
    resource_version = await session.get(SharedResourceVersionRow, resource_a)
    assert environment is not None and resource_version is not None
    resource = await session.get(SharedResourceRow, resource_version.shared_resource_id)
    assert resource is not None
    environment.owner_user_group_id = group_b
    resource.owner_user_group_id = group_b
    await session.commit()

    # Alice still discovers both assets through active Group B membership.
    response = await client.get(f"/api/v1/shared-resource-versions/{resource_a}", headers=ALICE)
    assert response.status_code == 200

    rerun = await client.post(f"/api/v1/runs/{create.json()['id']}/rerun", headers=ALICE)
    assert rerun.status_code == 422
    assert rerun.json()["code"] == "preflight_rejected"
    assert len(rerun.json()["problems"]) == 2
    persisted_runs = (
        await session.execute(select(RunRow.id).where(RunRow.project_id == project["id"]))
    ).scalars()
    assert list(persisted_runs) == [create.json()["id"]]
