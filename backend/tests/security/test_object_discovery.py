"""无发现权限时对象视为不存在。

关键点是**不能用错误码区分「不存在」和「存在但无权访问」**——
否则枚举 ID 就能探测到别人有哪些 Project 和 Run。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment

OTHER = {"X-User": "outsider"}


async def test_别人的_project_返回_404_而不是_403(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="私有项目")

    # 让 outsider 先建号，排除「用户不存在」这种巧合。
    await client.get("/api/v1/me", headers=OTHER)

    response = await client.get(f"/api/v1/projects/{project['id']}", headers=OTHER)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_不存在的_id_和无权访问的_id_返回一致(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="私有项目")
    await client.get("/api/v1/me", headers=OTHER)

    forbidden = await client.get(f"/api/v1/projects/{project['id']}", headers=OTHER)
    missing = await client.get("/api/v1/projects/prj_does_not_exist", headers=OTHER)

    assert forbidden.status_code == missing.status_code == 404
    # 连消息文本都不能有差别，否则一样能区分出来。
    assert forbidden.json()["message"].replace(project["id"], "X") == missing.json()[
        "message"
    ].replace("prj_does_not_exist", "X")


async def test_别人的_workspace_不出现在列表里(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client)
    outsider_home = (await client.get("/api/v1/me", headers=OTHER)).json()

    assert workspace_id not in [w["id"] for w in outsider_home["workspaces"]]
    assert outsider_home["recent_projects"] == []
    assert outsider_home["recent_runs"] == []


async def test_别人的_run_和_artifact_同样不可见(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(
        client,
        name="产出项目",
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

    await client.get("/api/v1/me", headers=OTHER)
    assert (await client.get(f"/api/v1/runs/{run['id']}", headers=OTHER)).status_code == 404
    assert (await client.get(f"/api/v1/runs/{run['id']}/logs", headers=OTHER)).status_code == 404


async def test_非_owner_不能修改_workspace(client: httpx.AsyncClient) -> None:
    """已经能看见对象了，这时角色不足应当返回 403，不再伪装成 404。"""
    owner_workspace = (await client.post("/api/v1/workspaces", json={"name": "算法组"})).json()
    await client.get("/api/v1/me", headers=OTHER)
    await client.post(
        f"/api/v1/workspaces/{owner_workspace['id']}/members",
        json={"username": "outsider", "role": "member"},
    )
    await client.post(
        f"/api/v1/workspaces/{owner_workspace['id']}/invitation",
        json={"accept": True},
        headers=OTHER,
    )

    visible = await client.get(f"/api/v1/workspaces/{owner_workspace['id']}", headers=OTHER)
    assert visible.status_code == 200

    denied = await client.patch(
        f"/api/v1/workspaces/{owner_workspace['id']}",
        json={"name": "我改个名"},
        headers=OTHER,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "permission_denied"
