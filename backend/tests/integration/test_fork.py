"""Fork：从确定版本派生 Project。

ADR-0001 说「实现时对着这张表写测试」，这个文件就是那张表——
**复制什么**一组，**不复制什么**一组。后一组更重要：
复制多了是越权，而越权不会自己报错。
"""

from __future__ import annotations

import httpx

from tests.helpers import use_default_environment

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _project_with_version(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> tuple[str, str, str]:
    """建一个有内容、有版本、有运行方案的 Project。

    返回 (workspace_id, project_id, version_id)。
    """
    workspace_id = await use_default_environment(client, headers=headers)
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": "分子动力学", "description": "第三次作业"},
            headers=headers,
        )
    ).json()
    for path, content in [("main.py", "print('hi')"), ("lib/util.py", "X = 1")]:
        await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": path, "content": content},
            headers=headers,
        )
    await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "标准跑法",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_variables": {"EPOCHS": "5"},
        },
        headers=headers,
    )
    version = (
        await client.post(
            f"/api/v1/projects/{project['id']}/versions",
            json={"message": "第一版"},
            headers=headers,
        )
    ).json()
    return workspace_id, str(project["id"]), str(version["id"])


async def _personal_workspace(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    home = (await client.get("/api/v1/me", headers=headers)).json()
    return str(next(w for w in home["workspaces"] if w["kind"] == "personal")["id"])


async def _shared_project(client: httpx.AsyncClient, bob_role: str) -> tuple[str, str]:
    """alice 建协作空间并拉 bob 进来，返回 (workspace_id, version_id)。

    涉及第二个人的测试必须用协作空间——Personal Workspace 不能有成员，
    在里面邀请会被拒，然后 bob 只是「看不见」，测出来的就不是想测的东西了。
    """
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "课程组"}, headers=ALICE)
    ).json()
    workspace_id = str(workspace["id"])
    await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": "ev_python_312"},
        headers=ALICE,
    )
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": "共享项目"},
            headers=ALICE,
        )
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('hi')"},
        headers=ALICE,
    )
    version = (
        await client.post(
            f"/api/v1/projects/{project['id']}/versions",
            json={"message": "第一版"},
            headers=ALICE,
        )
    ).json()

    await client.get("/api/v1/me", headers=BOB)
    invited = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": bob_role},
        headers=ALICE,
    )
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )
    assert accepted.status_code == 204, accepted.text
    return workspace_id, str(version["id"])


# --------------------------------------------------------------------------
# 复制什么
# --------------------------------------------------------------------------


async def test_fork_出新_project_不是分支(client: httpx.AsyncClient) -> None:
    _, _, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)

    forked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": target, "name": "我的副本"},
        headers=ALICE,
    )
    assert forked.status_code == 201
    assert forked.json()["workspace_id"] == target
    assert forked.json()["name"] == "我的副本"


async def test_文件内容一并复制(client: httpx.AsyncClient) -> None:
    _, _, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)

    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    files = (await client.get(f"/api/v1/projects/{forked['id']}/files", headers=ALICE)).json()
    assert sorted(f["path"] for f in files) == ["lib/util.py", "main.py"]

    content = (
        await client.get(
            f"/api/v1/projects/{forked['id']}/files/content",
            params={"path": "main.py"},
            headers=ALICE,
        )
    ).json()
    assert content["content"] == "print('hi')"


async def test_副本自带一个起始版本(client: httpx.AsyncClient) -> None:
    """只给工作区不给版本的话，提交前检查会直接拦下「还没保存过版本」。"""
    _, _, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)

    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    versions = (await client.get(f"/api/v1/projects/{forked['id']}/versions", headers=ALICE)).json()
    assert versions["total"] == 1
    assert versions["items"][0]["sequence"] == 1
    assert "Fork 自" in versions["items"][0]["message"]


async def test_运行方案一并复制(client: httpx.AsyncClient) -> None:
    _, _, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)

    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    configurations = (
        await client.get(f"/api/v1/projects/{forked['id']}/run-configurations", headers=ALICE)
    ).json()
    assert len(configurations) == 1
    assert configurations[0]["name"] == "标准跑法"
    assert configurations[0]["command"] == "python main.py"
    assert configurations[0]["environment_variables"] == {"EPOCHS": "5"}
    # 是新对象，不是同一条记录
    assert configurations[0]["project_id"] == forked["id"]


async def test_来源记录可以查到(client: httpx.AsyncClient) -> None:
    _, source_project_id, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)

    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    source = (
        await client.get(f"/api/v1/projects/{forked['id']}/fork-source", headers=ALICE)
    ).json()
    assert source["source_project_id"] == source_project_id
    assert source["source_version_id"] == version_id
    assert source["source_project_name"] == "分子动力学"
    assert source["source_version_label"] == "v1"


async def test_不是_fork_出来的项目没有来源记录(client: httpx.AsyncClient) -> None:
    _, project_id, _ = await _project_with_version(client, ALICE)
    response = await client.get(f"/api/v1/projects/{project_id}/fork-source", headers=ALICE)
    assert response.status_code == 200
    assert response.json() is None


# --------------------------------------------------------------------------
# 不复制什么（GR-006）
# --------------------------------------------------------------------------


async def test_两边后续修改互不影响(client: httpx.AsyncClient) -> None:
    """GR-005：复制产生独立内容，Fork Relation 不是同步通道。"""
    source_workspace, version_id = await _shared_project(client, "member")
    source_project_id = (
        await client.get(f"/api/v1/workspaces/{source_workspace}/projects", headers=ALICE)
    ).json()["items"][0]["id"]
    target = await _personal_workspace(client, ALICE)
    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    # 改副本
    await client.put(
        f"/api/v1/projects/{forked['id']}/files",
        json={"path": "main.py", "content": "print('副本改过了')"},
        headers=ALICE,
    )
    # 改源
    await client.put(
        f"/api/v1/projects/{source_project_id}/files",
        json={"path": "main.py", "content": "print('源改过了')"},
        headers=ALICE,
    )

    async def read(project_id: str) -> str:
        body = (
            await client.get(
                f"/api/v1/projects/{project_id}/files/content",
                params={"path": "main.py"},
                headers=ALICE,
            )
        ).json()
        return str(body["content"])

    assert await read(forked["id"]) == "print('副本改过了')"
    assert await read(source_project_id) == "print('源改过了')"


async def test_不复制_run_历史(client: httpx.AsyncClient) -> None:
    """Run 历史属于源 Workspace 的执行事实，跟着复制过来毫无意义。"""
    source_workspace, version_id = await _shared_project(client, "member")
    source_project_id = (
        await client.get(f"/api/v1/workspaces/{source_workspace}/projects", headers=ALICE)
    ).json()["items"][0]["id"]
    configuration = (
        await client.post(
            f"/api/v1/projects/{source_project_id}/run-configurations",
            json={"name": "跑", "command": "echo hi", "compute_plan_id": "plan_cpu_quick"},
            headers=ALICE,
        )
    ).json()
    submitted = await client.post(
        f"/api/v1/projects/{source_project_id}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert submitted.status_code == 201

    target = await _personal_workspace(client, ALICE)
    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    runs = (await client.get(f"/api/v1/projects/{forked['id']}/runs", headers=ALICE)).json()
    assert runs["total"] == 0


async def test_不复制_secret_的值_只复制引用(client: httpx.AsyncClient) -> None:
    """GR-012 规则 4，也是最容易搞错的一条。

    表达式跟着走，值留在源空间。目标空间没有同名 Secret 时，
    提交前检查必须拦下——**不能静默降级成空字符串**。
    """
    # 源必须在**另一个** Workspace 里，否则「值没跟过来」根本无从谈起——
    # 同一个空间里 Secret 本来就在，测了个寂寞。
    workspace_id, version_id = await _shared_project(client, "member")
    project_id = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/projects", headers=ALICE)
    ).json()["items"][0]["id"]

    await client.put(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": "HF_TOKEN", "value": "hf_真的密钥"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project_id}/run-configurations",
        json={
            "name": "要用 Token 的",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_variables": {"TOKEN": "${{ secrets.HF_TOKEN }}"},
        },
        headers=ALICE,
    )
    # 不用再存版本：运行方案挂在 Project 上，版本只固定文件内容，
    # 内容没变的话存版本会被 409 拦下。Fork 复制的正是「当前的」运行方案。
    target = await _personal_workspace(client, ALICE)
    forked = (
        await client.post(
            f"/api/v1/versions/{version_id}/fork",
            json={"target_workspace_id": target, "name": "副本"},
            headers=ALICE,
        )
    ).json()

    # 引用表达式复制过来了
    configurations = (
        await client.get(f"/api/v1/projects/{forked['id']}/run-configurations", headers=ALICE)
    ).json()
    with_secret = next(c for c in configurations if c["name"] == "要用 Token 的")
    assert with_secret["environment_variables"]["TOKEN"] == "${{ secrets.HF_TOKEN }}"

    # 但值没有跟过来：目标空间里没有这个 Secret
    names = (await client.get(f"/api/v1/workspaces/{target}/secrets", headers=ALICE)).json()
    assert "HF_TOKEN" not in names

    # 提交前检查拦下
    preflight = (
        await client.post(
            f"/api/v1/projects/{forked['id']}/runs/preflight",
            json={"run_configuration_id": with_secret["id"]},
            headers=ALICE,
        )
    ).json()
    assert preflight["ok"] is False
    assert any("HF_TOKEN" in problem for problem in preflight["problems"])


async def test_不复制资源权益(client: httpx.AsyncClient) -> None:
    """权益属于源 Workspace。跟着复制就等于「Fork 一下就能拿到别人的算力」。

    这条测过两次假：
    1. 源和目标都是 alice 的个人空间，等于在同一个空间内 Fork；
    2. 改成跨空间之后，断言比的是 compute_plan_id 的**集合**——
       而每个新空间默认都拿到全部三个方案，集合恒等，复制多少条都看不出来。

    所以现在比的是**权益行的 id 和条数**：复制过来的一定是新行、新 id。
    验证方式是往 fork 里塞一段「顺手把源空间权益也复制过去」的代码，
    这条必须变红。
    """
    workspace_id, version_id = await _shared_project(client, "member")
    target = await _personal_workspace(client, ALICE)

    async def entitlement_ids(workspace: str) -> set[str]:
        rows = (
            await client.get(f"/api/v1/workspaces/{workspace}/entitlements", headers=ALICE)
        ).json()
        return {e["id"] for e in rows}

    source_ids = await entitlement_ids(workspace_id)
    before = await entitlement_ids(target)
    assert source_ids and before, "两边都该有默认权益，否则这条测了个空"
    assert not (source_ids & before), "两个空间的权益行本来就该是各自独立的"

    forked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": target, "name": "副本"},
        headers=ALICE,
    )
    # 先确认 Fork 真的成功了。不断言这个的话，「Fork 失败 -> 什么都没变 ->
    # 断言通过」也会绿——测试就区分不出「没复制」和「压根没跑」。
    assert forked.status_code == 201, forked.text

    after = await entitlement_ids(target)
    # 一行都不该多，源空间的那些更不该出现在这里
    assert after == before
    assert not (after & source_ids)


async def test_不复制成员权限(client: httpx.AsyncClient) -> None:
    """bob 能 Fork alice 的东西，不代表 alice 能进 bob 的空间。"""
    _, version_id = await _shared_project(client, "member")

    bob_personal = await _personal_workspace(client, BOB)
    forked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": bob_personal, "name": "bob 的副本"},
        headers=BOB,
    )
    assert forked.status_code == 201

    # alice 看不到 bob 的个人空间，也看不到里面的副本
    assert (
        await client.get(f"/api/v1/workspaces/{bob_personal}", headers=ALICE)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/projects/{forked.json()['id']}", headers=ALICE)
    ).status_code == 404


# --------------------------------------------------------------------------
# 权限：两侧都要校验
# --------------------------------------------------------------------------


async def test_看不到源版本就_fork_不了(client: httpx.AsyncClient) -> None:
    """只校验目标空间的话，Fork 就成了「读到看不见的内容」的后门。"""
    _, _, version_id = await _project_with_version(client, ALICE)
    await client.get("/api/v1/me", headers=BOB)
    bob_personal = await _personal_workspace(client, BOB)

    blocked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": bob_personal, "name": "偷来的"},
        headers=BOB,
    )
    # GR-013：没有发现权限时当作不存在
    assert blocked.status_code == 404


async def test_不能往没有写权限的空间里_fork(client: httpx.AsyncClient) -> None:
    """只校验源的话，任何人都能往别人空间里塞项目。"""
    workspace_id, version_id = await _shared_project(client, "viewer")

    # bob 看得到这个空间（viewer），但没有 project.create
    blocked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": workspace_id, "name": "viewer 塞的"},
        headers=BOB,
    )
    assert blocked.status_code == 403
    assert "创建 Project" in blocked.json()["message"]


async def test_目标空间重名会被拒绝(client: httpx.AsyncClient) -> None:
    workspace_id, _, version_id = await _project_with_version(client, ALICE)

    blocked = await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": workspace_id, "name": "分子动力学"},
        headers=ALICE,
    )
    assert blocked.status_code == 409


async def test_fork_会记一条活动(client: httpx.AsyncClient) -> None:
    _, _, version_id = await _project_with_version(client, ALICE)
    target = await _personal_workspace(client, ALICE)
    await client.post(
        f"/api/v1/versions/{version_id}/fork",
        json={"target_workspace_id": target, "name": "副本"},
        headers=ALICE,
    )

    activities = (await client.get(f"/api/v1/workspaces/{target}/activities", headers=ALICE)).json()
    forked = next(a for a in activities["items"] if a["action"] == "project_forked")
    assert forked["target_name"] == "副本"
    assert "分子动力学" in forked["detail"]
