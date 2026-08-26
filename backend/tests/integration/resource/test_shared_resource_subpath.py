"""Shared Resource source_subpath validation and Run snapshot integration tests."""

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
    """建资源 + 发布 v1，返回版本详情。"""
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


async def _queue_subpath_run(
    client: httpx.AsyncClient,
    *,
    project: dict,
    version: dict,
    environment_version_id: str,
    access_path: str,
    subpath: str,
) -> dict:
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "子路径消费",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_version_id": environment_version_id,
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": access_path,
                        "source_subpath": subpath,
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


async def test_目录子路径固定_source_subpath_和_access_path(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(
        client, name="训练集", files=[("train/a.py", b"a"), ("test/b.py", b"b")]
    )
    project = await create_project_with_version(
        client, name="消费", files={"main.py": "pass"}, headers=ALICE
    )
    detail = await _queue_subpath_run(
        client,
        project=project,
        version=version,
        environment_version_id=env,
        access_path="/inputs/train",
        subpath="train/",
    )
    assert detail["snapshot"]["input_bindings"][0] == {
        "source_type": "shared_resource_version",
        "source_id": version["id"],
        "access_path": "/inputs/train",
        "source_subpath": "train",
    }


async def test_深层子路径固定规范化后的快照(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(client, name="深层", files=[("a/b/c.py", b"c")])
    project = await create_project_with_version(
        client, name="消费深层", files={"main.py": "pass"}, headers=ALICE
    )
    detail = await _queue_subpath_run(
        client,
        project=project,
        version=version,
        environment_version_id=env,
        access_path="/inputs/d",
        subpath="a/b/",
    )
    assert detail["snapshot"]["input_bindings"][0]["source_subpath"] == "a/b"
    assert detail["snapshot"]["input_bindings"][0]["access_path"] == "/inputs/d"


async def test_不存在的子路径在提交前被拒绝(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(client, name="资源", files=[("a.txt", b"x")])
    project = await create_project_with_version(
        client, name="错误子路径", files={"main.py": "pass"}, headers=ALICE
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_version_id": env,
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": "/inputs/x",
                        "source_subpath": "nope/",
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
    assert response.status_code == 422
    assert any("子路径" in problem for problem in response.json()["problems"])


async def test_空子路径在快照中表示完整资源(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(client, name="全量", files=[("top.txt", b"x")])
    project = await create_project_with_version(
        client, name="全量消费", files={"main.py": "pass"}, headers=ALICE
    )
    detail = await _queue_subpath_run(
        client,
        project=project,
        version=version,
        environment_version_id=env,
        access_path="/inputs/d",
        subpath="",
    )
    assert detail["snapshot"]["input_bindings"][0]["source_subpath"] == ""
