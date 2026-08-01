"""活动流。

重点有两块：**记了什么**，以及**记不上的时候会怎样**。
第二块比第一块重要——活动是附带产物，它出问题不该牵连用户真正要做的事。
"""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import use_default_environment

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _collaborative(client: httpx.AsyncClient) -> str:
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "算法组"}, headers=ALICE)
    ).json()
    return str(workspace["id"])


async def _activities(client: httpx.AsyncClient, workspace_id: str, headers=ALICE) -> list[dict]:
    response = await client.get(f"/api/v1/workspaces/{workspace_id}/activities", headers=headers)
    assert response.status_code == 200
    return list(response.json()["items"])


async def test_建空间会记一条活动(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)

    items = await _activities(client, workspace_id)
    assert len(items) == 1
    assert items[0]["action"] == "workspace_created"
    assert items[0]["actor_name"] == "alice"
    assert items[0]["target_name"] == "算法组"


async def test_成员变动按发生顺序记下来(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await client.get("/api/v1/me", headers=BOB)
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": "member"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )
    await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{bob['id']}",
        json={"role": "admin"},
        headers=ALICE,
    )

    items = await _activities(client, workspace_id)
    # 倒序返回：最近发生的在最前面
    assert [i["action"] for i in items] == [
        "member_role_changed",
        "member_joined",
        "member_invited",
        "workspace_created",
    ]
    changed = items[0]
    assert changed["target_name"] == "bob"
    assert changed["detail"] == "member → admin"


async def test_拒绝邀请不记活动(client: httpx.AsyncClient) -> None:
    """被邀请的人没有加入，这个空间里也就没发生什么。"""
    workspace_id = await _collaborative(client)
    await client.get("/api/v1/me", headers=BOB)
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": "member"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": False}, headers=BOB
    )

    actions = [i["action"] for i in await _activities(client, workspace_id)]
    assert "member_joined" not in actions


async def test_失败的操作不记活动(client: httpx.AsyncClient) -> None:
    """活动流回答「这里发生了什么」，不是审计日志。没做成的事没有发生。"""
    workspace_id = await _collaborative(client)
    before = len(await _activities(client, workspace_id))

    # 重名，会被拒绝
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "重复"}, headers=ALICE
    )
    duplicated = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "重复"}, headers=ALICE
    )
    assert duplicated.status_code == 409

    # 只多了成功那一次的活动
    assert len(await _activities(client, workspace_id)) == before + 1


async def test_project_活动同时出现在空间活动流里(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client, headers=ALICE)
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "实验"}, headers=ALICE
        )
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print(1)"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "第一版"}, headers=ALICE
    )

    project_feed = (
        await client.get(f"/api/v1/projects/{project['id']}/activities", headers=ALICE)
    ).json()
    assert [i["action"] for i in project_feed["items"]] == ["version_saved", "project_created"]
    assert project_feed["items"][0]["target_name"] == "v1"
    assert project_feed["items"][0]["detail"] == "第一版"

    # 同一批活动也能从空间的活动流里看到
    workspace_actions = [i["action"] for i in await _activities(client, workspace_id)]
    assert "version_saved" in workspace_actions


async def test_活动流分页(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    for index in range(5):
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": f"项目{index}"},
            headers=ALICE,
        )

    first = (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/activities",
            params={"page": 1, "page_size": 3},
            headers=ALICE,
        )
    ).json()
    assert first["total"] == 6  # 5 个 Project + 1 次建空间
    assert len(first["items"]) == 3
    assert first["has_more"] is True


async def test_看不见的空间就看不见它的活动(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await client.get("/api/v1/me", headers=BOB)

    blocked = await client.get(f"/api/v1/workspaces/{workspace_id}/activities", headers=BOB)
    # GR-013：没有发现权限时返回 404，不泄露「这个空间存在」
    assert blocked.status_code == 404


async def test_viewer_看得到活动(client: httpx.AsyncClient) -> None:
    """Viewer 就是来观摩的，不该连「这里发生了什么」都看不到。"""
    workspace_id = await _collaborative(client)
    await client.get("/api/v1/me", headers=BOB)
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": "viewer"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )

    items = await _activities(client, workspace_id, headers=BOB)
    assert any(i["action"] == "workspace_created" for i in items)


async def test_名字是当时抄下来的_改名之后活动不变(client: httpx.AsyncClient) -> None:
    """活动是历史事实。

    「alice 创建了 Project 旧名字」这句话在项目改名之后仍然要说旧名字——
    否则历史记录会被后来的改动悄悄改写。
    """
    workspace_id = await _collaborative(client)
    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "旧名字"}, headers=ALICE
        )
    ).json()

    await client.patch(f"/api/v1/projects/{project['id']}", json={"name": "新名字"}, headers=ALICE)

    items = await _activities(client, workspace_id)
    created = next(i for i in items if i["action"] == "project_created")
    assert created["target_name"] == "旧名字"

    updated = next(i for i in items if i["action"] == "project_updated")
    assert updated["target_name"] == "新名字"


@pytest.mark.anyio
async def test_活动写不进去也不能让用例失败(client: httpx.AsyncClient, context) -> None:
    """这条是 ActivityRecorder 存在的全部理由。

    用户的 Project 已经建成了，不该因为活动表写不进去而看到报错，
    更不该因此丢掉刚建好的 Project。

    做法是把活动写入包在 SAVEPOINT 里。光 try/except 吞掉异常是**不够**的：
    仓储用 ORM 的 add + flush，flush 失败会把整个 session 标记成需要回滚，
    请求结束时的 commit 会抛 PendingRollbackError，主用例的数据一起丢。
    """
    from sqlalchemy import text

    # 把活动表改坏：加一个永远不满足的约束，任何插入都会失败
    async with context.engine.begin() as connection:
        await connection.execute(text("DROP TABLE activities"))
        await connection.execute(
            text(
                "CREATE TABLE activities ("
                "id TEXT PRIMARY KEY, workspace_id TEXT, project_id TEXT, "
                "actor_id TEXT, actor_name TEXT, action TEXT, target_type TEXT, "
                "target_id TEXT, target_name TEXT, detail TEXT, created_at TEXT, "
                "CHECK (id IS NULL))"
            )
        )

    workspace_id = await _collaborative(client)
    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "照样建得成"}, headers=ALICE
    )

    assert created.status_code == 201, "活动写入失败连累了主用例"

    # 而且 Project 真的落库了，不是只返回了 201
    listed = (await client.get(f"/api/v1/workspaces/{workspace_id}/projects", headers=ALICE)).json()
    assert [item["name"] for item in listed["items"]] == ["照样建得成"]
