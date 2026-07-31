"""GR-001：Workspace 是基础归属边界。

Run、Log、Artifact 的归属 Workspace 由 Project 决定；
Membership 只在对应 Workspace 内生效，不会传播到别的空间。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

BOB = {"X-User": "bob"}


async def test_run_和_artifact_归属于_project_所在的_workspace(
    client: httpx.AsyncClient,
) -> None:
    workspace_id = await use_default_environment(client)
    project = await create_project_with_version(
        client,
        name="归属测试",
        files={"main.py": "import pathlib; pathlib.Path('outputs').mkdir(); "},
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "artifact_rules": [{"path": "outputs"}],
            },
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()

    detail = await wait_for_run(client, run["id"])
    assert detail["run"]["workspace_id"] == workspace_id
    assert detail["run"]["project_id"] == project["id"]
    assert all(a["run_id"] == run["id"] for a in detail["artifacts"])


async def test_加入协作空间不会带来别的空间的权限(client: httpx.AsyncClient) -> None:
    # student 的 Personal Workspace 里有一个私有项目
    private = await create_project_with_version(client, name="个人私有项目")

    # student 建一个协作空间并邀请 bob
    shared = (await client.post("/api/v1/workspaces", json={"name": "算法组"})).json()
    await client.get("/api/v1/me", headers=BOB)
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/members",
        json={"username": "bob", "role": "member"},
    )
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/invitation", json={"accept": True}, headers=BOB
    )

    # bob 能看见协作空间
    assert (await client.get(f"/api/v1/workspaces/{shared['id']}", headers=BOB)).status_code == 200
    # 但看不见 student 个人空间里的项目
    assert (await client.get(f"/api/v1/projects/{private['id']}", headers=BOB)).status_code == 404


async def test_协作空间成员可以共同使用同一个_project(client: httpx.AsyncClient) -> None:
    shared = (await client.post("/api/v1/workspaces", json={"name": "算法组"})).json()
    await client.patch(
        f"/api/v1/workspaces/{shared['id']}",
        json={"default_environment_version_id": "ev_python_312"},
    )
    project = (
        await client.post(f"/api/v1/workspaces/{shared['id']}/projects", json={"name": "共享项目"})
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('hello from shared')"},
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "v1"})

    await client.get("/api/v1/me", headers=BOB)
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/members",
        json={"username": "bob", "role": "member"},
    )
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/invitation", json={"accept": True}, headers=BOB
    )

    # bob 可以在共享 Project 上创建运行方案并提交 Run
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "bob 的运行",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
            },
            headers=BOB,
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
            headers=BOB,
        )
    ).json()

    detail = await wait_for_run(client, run["id"], headers=BOB)
    assert detail["run"]["status"] == "succeeded"
    assert detail["run"]["workspace_id"] == shared["id"]
    # student 作为 Owner 也能看到 bob 提交的 Run
    assert (await client.get(f"/api/v1/runs/{run['id']}")).status_code == 200


async def test_被移除后立刻失去访问(client: httpx.AsyncClient) -> None:
    shared = (await client.post("/api/v1/workspaces", json={"name": "算法组"})).json()
    bob = (await client.get("/api/v1/me", headers=BOB)).json()
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/members",
        json={"username": "bob", "role": "member"},
    )
    await client.post(
        f"/api/v1/workspaces/{shared['id']}/invitation", json={"accept": True}, headers=BOB
    )
    assert (await client.get(f"/api/v1/workspaces/{shared['id']}", headers=BOB)).status_code == 200

    removed = await client.delete(f"/api/v1/workspaces/{shared['id']}/members/{bob['user']['id']}")
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/workspaces/{shared['id']}", headers=BOB)).status_code == 404
