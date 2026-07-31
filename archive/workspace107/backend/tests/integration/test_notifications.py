"""通知中心。

活动回答「这里发生了什么」，通知回答「有什么需要我关注」。
这个文件重点测三件事：**谁收到**、**谁收不到**、**发不出去时会怎样**。
"""

from __future__ import annotations

import httpx

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}
CAROL = {"X-User": "carol"}


async def _collaborative(client: httpx.AsyncClient, name: str = "算法组") -> str:
    workspace = (await client.post("/api/v1/workspaces", json={"name": name}, headers=ALICE)).json()
    return str(workspace["id"])


async def _invite(
    client: httpx.AsyncClient, workspace_id: str, username: str, role: str = "member"
) -> str:
    """邀请并返回被邀请人的 user id。"""
    user = (await client.get("/api/v1/me", headers={"X-User": username})).json()["user"]
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": username, "role": role},
        headers=ALICE,
    )
    return str(user["id"])


async def _notifications(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict]:
    response = await client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 200
    return list(response.json()["items"])


async def _unread(client: httpx.AsyncClient, headers: dict[str, str]) -> int:
    response = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert response.status_code == 200
    return int(response.json()["unread"])


async def test_被邀请的人收到通知(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")

    items = await _notifications(client, BOB)
    assert len(items) == 1
    assert items[0]["type"] == "workspace_invited"
    assert "算法组" in items[0]["title"]
    assert items[0]["read_at"] is None
    assert await _unread(client, BOB) == 1


async def test_不给自己发通知(client: httpx.AsyncClient) -> None:
    """自己做的事自己知道。通知里全是自己的操作，未读数就成了噪音。"""
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")

    # alice 是操作者，她不该收到「你邀请了 bob」这种东西
    assert await _notifications(client, ALICE) == []
    assert await _unread(client, ALICE) == 0
    assert workspace_id


async def test_被移除的人仍然读得到那条通知(client: httpx.AsyncClient) -> None:
    """这是通知和活动分开的核心理由。

    移除之后 bob 已经看不到这个 Workspace 了。如果通知也按 Workspace 过滤，
    他就永远不知道自己被移除了——那这条通知等于没发。
    """
    workspace_id = await _collaborative(client)
    bob_id = await _invite(client, workspace_id, "bob")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )

    await client.delete(f"/api/v1/workspaces/{workspace_id}/members/{bob_id}", headers=ALICE)

    # 空间确实已经看不见了
    assert (await client.get(f"/api/v1/workspaces/{workspace_id}", headers=BOB)).status_code == 404

    # 但通知还在
    types = [n["type"] for n in await _notifications(client, BOB)]
    assert "member_removed" in types

    removed = next(n for n in await _notifications(client, BOB) if n["type"] == "member_removed")
    assert removed["mandatory"] is True
    # 不给跳转链接：链过去只会是 404
    assert removed["target_id"] is None


async def test_角色变更通知本人(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    bob_id = await _invite(client, workspace_id, "bob")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )

    await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}",
        json={"role": "admin"},
        headers=ALICE,
    )

    changed = next(n for n in await _notifications(client, BOB) if n["type"] == "role_changed")
    assert "admin" in changed["title"]
    assert changed["mandatory"] is True


async def test_转让所有权通知新所有者(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    bob_id = await _invite(client, workspace_id, "bob")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/transfer-ownership/{bob_id}", headers=ALICE
    )

    types = [n["type"] for n in await _notifications(client, BOB)]
    assert "ownership_received" in types


async def test_标记已读(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")

    notification = (await _notifications(client, BOB))[0]
    marked = await client.post(f"/api/v1/notifications/{notification['id']}/read", headers=BOB)
    assert marked.status_code == 204
    assert await _unread(client, BOB) == 0

    # 已读的仍然在列表里，只是带上了时间
    assert (await _notifications(client, BOB))[0]["read_at"] is not None


async def test_不能标记别人的通知(client: httpx.AsyncClient) -> None:
    """仓储的每个查询都带 recipient_id 条件。少一个就是越权。"""
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")
    await client.get("/api/v1/me", headers=CAROL)

    notification = (await _notifications(client, BOB))[0]
    # carol 拿着 bob 的通知 ID 去标记
    response = await client.post(f"/api/v1/notifications/{notification['id']}/read", headers=CAROL)
    assert response.status_code == 204  # 静默处理，不泄露这个 ID 存在

    # bob 的未读数没有被动过
    assert await _unread(client, BOB) == 1


async def test_只看未读(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")
    first = (await _notifications(client, BOB))[0]
    await client.post(f"/api/v1/notifications/{first['id']}/read", headers=BOB)

    second_workspace = await _collaborative(client, "第二个空间")
    await _invite(client, second_workspace, "bob")

    everything = (await client.get("/api/v1/notifications", headers=BOB)).json()
    unread = (
        await client.get("/api/v1/notifications", params={"unread_only": True}, headers=BOB)
    ).json()

    assert everything["total"] == 2
    assert unread["total"] == 1
    assert unread["items"][0]["read_at"] is None


async def test_全部标记已读(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")
    await _invite(client, await _collaborative(client, "第二个"), "bob")

    assert await _unread(client, BOB) == 2
    response = await client.post("/api/v1/notifications/read-all", headers=BOB)
    assert response.status_code == 200
    assert response.json()["unread"] == 0
    assert await _unread(client, BOB) == 0
    assert workspace_id


async def test_只看得到发给自己的(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")
    await client.get("/api/v1/me", headers=CAROL)

    assert len(await _notifications(client, BOB)) == 1
    assert await _notifications(client, CAROL) == []


async def test_通知发不出去也不能让用例失败(client: httpx.AsyncClient, context) -> None:
    """和活动同一条规则，同一个坑。

    成员已经邀请成功了，不该因为通知表写不进去而看到报错，
    更不该因此把刚建好的 Membership 一起丢掉。
    """
    from sqlalchemy import text

    workspace_id = await _collaborative(client)
    await client.get("/api/v1/me", headers=BOB)

    # 把通知表改坏：加一个永远不满足的约束
    async with context.engine.begin() as connection:
        await connection.execute(text("DROP TABLE notifications"))
        await connection.execute(
            text(
                "CREATE TABLE notifications ("
                "  id VARCHAR(40) PRIMARY KEY,"
                "  recipient_id VARCHAR(40) NOT NULL,"
                "  type VARCHAR(64) NOT NULL,"
                "  title VARCHAR(255) NOT NULL,"
                "  body TEXT NOT NULL,"
                "  workspace_id VARCHAR(40),"
                "  target_type VARCHAR(32),"
                "  target_id VARCHAR(40),"
                "  mandatory BOOLEAN NOT NULL,"
                "  created_at TIMESTAMP NOT NULL,"
                "  read_at TIMESTAMP,"
                "  CHECK (id IS NULL)"  # 任何插入都会失败
                ")"
            )
        )

    invited = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"username": "bob", "role": "member"},
        headers=ALICE,
    )
    # 邀请本身必须成功
    assert invited.status_code == 201

    # 而且真的落库了——不是「返回了 201 但事务回滚了」
    members = (await client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=ALICE)).json()
    assert any(m["username"] == "bob" for m in members)


async def test_被邀请的人能看到并接受邀请(client: httpx.AsyncClient) -> None:
    """整条链路要接得上：收到通知 -> 在首页看到邀请 -> 接受 -> 进得去。

    早先这条链在前端是断的：空间列表只查 ACTIVE，被邀请人看不到那个空间；
    通知链到 /workspaces/{id} 必然 404；接受邀请的接口定义了但零引用。
    **通知指着一个打不开的页面和一个不存在的入口。**
    """
    workspace_id = await _collaborative(client, "分布式系统")
    await _invite(client, workspace_id, "bob", "admin")

    # 还没接受：空间列表里没有它
    workspaces = (await client.get("/api/v1/workspaces", headers=BOB)).json()
    assert workspace_id not in [w["id"] for w in workspaces]
    # 也确实进不去（GR-013）
    assert (await client.get(f"/api/v1/workspaces/{workspace_id}", headers=BOB)).status_code == 404

    # 但邀请看得到，而且带着做决定需要的信息
    invitations = (await client.get("/api/v1/invitations", headers=BOB)).json()
    assert len(invitations) == 1
    assert invitations[0]["workspace_id"] == workspace_id
    assert invitations[0]["workspace_name"] == "分布式系统"
    assert invitations[0]["role"] == "admin"

    # 通知不带跳转目标——链过去只会是 404
    notification = next(
        n for n in await _notifications(client, BOB) if n["type"] == "workspace_invited"
    )
    assert notification["target_id"] is None

    # 接受之后进得去，邀请也从列表里消失
    accepted = await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )
    assert accepted.status_code == 204
    assert (await client.get(f"/api/v1/workspaces/{workspace_id}", headers=BOB)).status_code == 200
    assert (await client.get("/api/v1/invitations", headers=BOB)).json() == []


async def test_拒绝之后邀请也不再显示(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": False}, headers=BOB
    )
    assert (await client.get("/api/v1/invitations", headers=BOB)).json() == []
    assert (await client.get(f"/api/v1/workspaces/{workspace_id}", headers=BOB)).status_code == 404


async def test_只看得到发给自己的邀请(client: httpx.AsyncClient) -> None:
    workspace_id = await _collaborative(client)
    await _invite(client, workspace_id, "bob")
    await client.get("/api/v1/me", headers=CAROL)

    assert len((await client.get("/api/v1/invitations", headers=BOB)).json()) == 1
    assert (await client.get("/api/v1/invitations", headers=CAROL)).json() == []


async def test_重新邀请退出过的成员照样发通知(client: httpx.AsyncClient) -> None:
    """复用旧 membership 那条分支早先既不记活动也不发通知。

    对被邀请的人来说这就是一次全新的邀请，他没有理由因为「以前来过」
    就收不到通知——而且没有通知，他连有人重新邀请他都不知道。
    """
    workspace_id = await _collaborative(client, "回来吧")
    await _invite(client, workspace_id, "bob")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )
    await client.post(f"/api/v1/workspaces/{workspace_id}/leave", headers=BOB)
    await client.post("/api/v1/notifications/read-all", headers=BOB)

    await _invite(client, workspace_id, "bob", "admin")

    assert await _unread(client, BOB) == 1
    invitations = (await client.get("/api/v1/invitations", headers=BOB)).json()
    assert len(invitations) == 1
    assert invitations[0]["role"] == "admin"

    activities = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/activities", headers=ALICE)
    ).json()["items"]
    assert [a["action"] for a in activities].count("member_invited") == 2


async def test_重复移除同一个成员不会重复发通知(client: httpx.AsyncClient) -> None:
    """member_removed 是 mandatory 通知，用户关都关不掉，更不能重复发。"""
    workspace_id = await _collaborative(client)
    bob_id = await _invite(client, workspace_id, "bob")
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/invitation", json={"accept": True}, headers=BOB
    )

    first = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}", headers=ALICE
    )
    assert first.status_code == 204
    second = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{bob_id}", headers=ALICE
    )
    assert second.status_code == 204  # 幂等，不报错

    removed = [n for n in await _notifications(client, BOB) if n["type"] == "member_removed"]
    assert len(removed) == 1, f"发了 {len(removed)} 条「你被移出了」"
