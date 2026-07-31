"""Admin / Viewer 扩展角色与角色修改。

重点不是「角色叫什么」，而是**每个角色实际拦得住什么**。
权限模型只有在越权请求真的被拒绝时才成立。
"""

from __future__ import annotations

import httpx

from tests.helpers import use_default_environment

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _shared_workspace(client: httpx.AsyncClient, bob_role: str) -> tuple[str, str]:
    """建一个协作空间，把 bob 拉进来并设成指定角色。返回 (空间 ID, bob 的用户 ID)。"""
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "角色测试"}, headers=ALICE)
    ).json()
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]

    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"username": "bob", "role": bob_role},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/invitation", json={"accept": True}, headers=BOB
    )
    return workspace["id"], bob["id"]


async def test_创建者拿到全部能力(client: httpx.AsyncClient) -> None:
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "新空间"}, headers=ALICE)
    ).json()

    assert workspace["role"] == "owner"
    assert "ownership.transfer" in workspace["capabilities"]
    assert "member.manage" in workspace["capabilities"]


async def test_viewer_能看不能改(client: httpx.AsyncClient) -> None:
    workspace_id, _ = await _shared_workspace(client, "viewer")

    visible = await client.get(f"/api/v1/workspaces/{workspace_id}", headers=BOB)
    assert visible.status_code == 200
    assert visible.json()["role"] == "viewer"
    assert visible.json()["capabilities"] == [
        "config.view",
        "entitlement.view",
        "member.view",
        "project.view",
        "run.view",
        "workspace.view",
    ]

    # 看得见列表
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/projects", headers=BOB)
    ).status_code == 200

    # 但建不了 Project
    blocked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "偷偷建"}, headers=BOB
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "permission_denied"
    assert "创建 Project" in blocked.json()["message"]


async def test_viewer_不能提交_run(client: httpx.AsyncClient) -> None:
    """Viewer 不该能花掉这个空间的算力。"""
    workspace_id, _ = await _shared_workspace(client, "viewer")
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
        json={"path": "main.py", "content": "print(1)"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "v1"}, headers=ALICE
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={"name": "跑", "command": "python main.py", "compute_plan_id": "plan_cpu_quick"},
            headers=ALICE,
        )
    ).json()

    blocked = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=BOB,
    )
    assert blocked.status_code == 403
    assert "提交 Run" in blocked.json()["message"]


async def test_member_能干活但管不了人(client: httpx.AsyncClient) -> None:
    workspace_id, _ = await _shared_workspace(client, "member")

    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "我的项目"}, headers=BOB
    )
    assert created.status_code == 201

    blocked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "alice", "role": "member"},
        headers=BOB,
    )
    assert blocked.status_code == 403

    config_blocked = await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables",
        json={"name": "X", "value": "1"},
        headers=BOB,
    )
    assert config_blocked.status_code == 403


async def test_admin_能管人和配置但不能转让所有权(client: httpx.AsyncClient) -> None:
    workspace_id, _ = await _shared_workspace(client, "admin")
    await client.get("/api/v1/me", headers={"X-User": "carol"})

    invited = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "carol", "role": "member"},
        headers=BOB,
    )
    assert invited.status_code == 201

    configured = await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables",
        json={"name": "EPOCHS", "value": "3"},
        headers=BOB,
    )
    assert configured.status_code == 200

    carol = (await client.get("/api/v1/me", headers={"X-User": "carol"})).json()["user"]
    blocked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/transfer-ownership/{carol['id']}", headers=BOB
    )
    assert blocked.status_code == 403
    assert "转让空间所有权" in blocked.json()["message"]


async def test_修改成员角色(client: httpx.AsyncClient) -> None:
    workspace_id, bob_id = await _shared_workspace(client, "member")

    changed = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}",
        json={"role": "admin"},
        headers=ALICE,
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "admin"

    # 新角色立刻生效
    now_allowed = await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables",
        json={"name": "X", "value": "1"},
        headers=BOB,
    )
    assert now_allowed.status_code == 200


async def test_不能把成员直接设成_owner(client: httpx.AsyncClient) -> None:
    """否则一个 Admin 就能自己造出一个所有者来。"""
    workspace_id, bob_id = await _shared_workspace(client, "member")

    blocked = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}",
        json={"role": "owner"},
        headers=ALICE,
    )
    assert blocked.status_code == 409
    assert "转让所有权" in blocked.json()["message"]


async def test_不能修改所有者的角色(client: httpx.AsyncClient) -> None:
    workspace_id, _ = await _shared_workspace(client, "admin")
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]

    blocked = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{alice['id']}",
        json={"role": "viewer"},
        headers=BOB,
    )
    assert blocked.status_code == 409
    assert "所有者" in blocked.json()["message"]


async def test_member_不能改别人的角色(client: httpx.AsyncClient) -> None:
    workspace_id, bob_id = await _shared_workspace(client, "member")

    blocked = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}",
        json={"role": "admin"},
        headers=BOB,
    )
    assert blocked.status_code == 403


async def test_转让之后原所有者留在_admin(client: httpx.AsyncClient) -> None:
    """交出的是所有权，不是团队。原所有者仍然能管事，新所有者可以再降级。"""
    workspace_id, bob_id = await _shared_workspace(client, "member")
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]

    transferred = await client.post(
        f"/api/v1/workspaces/{workspace_id}/transfer-ownership/{bob_id}", headers=ALICE
    )
    assert transferred.status_code == 204

    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=BOB)).json()
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[bob_id] == "owner"
    assert roles[alice["id"]] == "admin"


async def test_个人空间的所有者拥有全部能力(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client, headers=ALICE)
    workspace = (await client.get(f"/api/v1/workspaces/{workspace_id}", headers=ALICE)).json()

    assert workspace["kind"] == "personal"
    assert workspace["role"] == "owner"
    assert "config.manage" in workspace["capabilities"]


async def test_不能把人直接邀请成_owner(client: httpx.AsyncClient) -> None:
    """GR-104：``memberships.role == owner`` 只能由所有权转让流程写入。

    这条规则当初只在改角色那条路上落地，邀请接口漏了——审查时实跑复现出
    完整的夺权链：Admin 邀请一个 owner，对方接受后拿到 ownership.transfer，
    转手把整个空间转走。**规则对，只落在一条路径上，等于没有。**
    """
    workspace_id, _ = await _shared_workspace(client, "admin")
    await client.get("/api/v1/me", headers={"X-User": "carol"})

    # bob 是 Admin，有 MEMBER_MANAGE 但没有 OWNERSHIP_TRANSFER
    blocked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "carol", "role": "owner"},
        headers=BOB,
    )
    assert blocked.status_code == 409
    assert "转让所有权" in blocked.json()["message"]

    # 空间里仍然只有一个 owner
    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=ALICE)).json()
    assert [m["role"] for m in members].count("owner") == 1


async def test_重新邀请退出的成员也不能设成_owner(client: httpx.AsyncClient) -> None:
    """复用已有 membership 的那条分支同样要挡住。"""
    workspace_id, bob_id = await _shared_workspace(client, "member")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )
    await client.post(f"/api/v1/workspaces/{workspace_id}/leave", headers=BOB)

    blocked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": "owner"},
        headers=ALICE,
    )
    assert blocked.status_code == 409
    assert bob_id


async def test_转让降级的是在册所有者(client: httpx.AsyncClient) -> None:
    """降级对象必须是 workspace.owner_id，不是碰巧发起调用的人。

    否则一旦出现过第二个 role=owner 的成员，由他发起转让只会降他自己，
    真正的 owner 留在 owner 角色上——一个 role=owner 但不是 owner_id 的成员，
    他还能再转让一次。
    """
    workspace_id, bob_id = await _shared_workspace(client, "member")
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/transfer-ownership/{bob_id}", headers=ALICE
    )

    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=BOB)).json()
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[bob_id] == "owner"
    assert roles[alice["id"]] == "admin"
    # 全空间有且只有一个 owner
    assert list(roles.values()).count("owner") == 1
