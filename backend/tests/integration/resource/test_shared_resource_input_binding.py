"""Shared Resource input binding API and snapshot integration tests."""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import (
    create_project_with_version,
    ensure_user_group,
    grant_test_entitlement,
    use_default_environment,
)

ALICE = {"X-User": "alice"}


async def _user_group(client: httpx.AsyncClient) -> str:
    return await ensure_user_group(client, headers=ALICE)


async def _create_resource_with_version(
    client: httpx.AsyncClient, *, name: str, files: list[tuple[str, bytes]]
) -> dict:
    """建资源 + 发布 v1，返回版本详情（含 files）。"""
    user_group_id = await _user_group(client)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": name,
                "owner": {"kind": "user_group", "id": user_group_id},
            },
            headers=ALICE,
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/shared-resources/{resource['id']}/versions",
            params={"prefix": ""},
            data={"description": "v1"},
            files=[
                ("files", (path, content, "application/octet-stream")) for path, content in files
            ],
            headers=ALICE,
        )
    ).json()
    return (
        await client.get(f"/api/v1/shared-resource-versions/{version['id']}", headers=ALICE)
    ).json()


async def _queue_run(
    client: httpx.AsyncClient,
    *,
    project: dict,
    version: dict,
    environment_version_id: str,
    access_path: str = "/inputs/dataset",
    source_subpath: str = "",
) -> dict:
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "消费资源",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_version_id": environment_version_id,
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": access_path,
                        "source_subpath": source_subpath,
                    }
                ],
            },
            headers=ALICE,
        )
    ).json()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "queued"
    detail = (await client.get(f"/api/v1/runs/{run['id']}", headers=ALICE)).json()
    assert detail["run"]["status"] == "queued"
    return detail


async def test_shared_resource_version_作为_run_输入并固定精确快照(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")

    version = await _create_resource_with_version(
        client, name="预训练权重", files=[("weights.txt", b"model-params")]
    )
    project = await create_project_with_version(
        client, name="消费资源", files={"main.py": "pass"}, headers=ALICE
    )
    detail = await _queue_run(
        client, project=project, version=version, environment_version_id=env_version_id
    )
    binding = detail["snapshot"]["input_bindings"][0]
    assert binding == {
        "source_type": "shared_resource_version",
        "source_id": version["id"],
        "access_path": "/inputs/dataset",
        "source_subpath": "",
    }


async def test_引用不存在的_version_会挡在运行前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    project = await create_project_with_version(
        client, name="错误输入", files={"main.py": "pass"}, headers=ALICE
    )
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "跑一下",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": "shrv_not_exist",
                    "access_path": "/inputs/x",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# -- 跨 Owner 引用 -------------------------------------------------------


async def test_跨_owner_引用_user_group_shared_resource_被挡在运行方案保存前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await use_default_environment(session, client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="Alice 私有", files=[("a.txt", b"x")]
    )
    bob_headers = {"X-User": "bob"}
    bob_group_id, bob_env_version_id = await use_default_environment(
        session, client, headers=bob_headers
    )
    project = (
        await client.post(
            "/api/v1/projects",
            json={"owner": {"kind": "user_group", "id": bob_group_id}, "name": "Bob 项目"},
            headers=bob_headers,
        )
    ).json()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "引用 Alice 的",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": bob_env_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": version["id"],
                    "access_path": "/inputs/x",
                }
            ],
        },
        headers=bob_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
