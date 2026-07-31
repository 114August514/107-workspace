"""提交 Run 的幂等性。

网络抖动、用户双击、前端自动重试，都不该变成两次真实计算——
对一个按 GPU 时长记账的平台，这不是体验问题，是钱的问题。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run


async def _prepare(client: httpx.AsyncClient, command: str = "print('ok')") -> tuple[str, str]:
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name=f"幂等-{command[:8]}", files={"main.py": command}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
            },
        )
    ).json()
    return project["id"], configuration["id"]


async def test_相同幂等键只会真的跑一次(client: httpx.AsyncClient) -> None:
    project_id, configuration_id = await _prepare(client)
    payload = {"run_configuration_id": configuration_id}
    headers = {"Idempotency-Key": "submit-attempt-0001"}

    first = await client.post(f"/api/v1/projects/{project_id}/runs", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post(f"/api/v1/projects/{project_id}/runs", json=payload, headers=headers)
    # 重放返回 200，和「新建成功」区分开
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    runs = (await client.get(f"/api/v1/projects/{project_id}/runs")).json()
    assert runs["total"] == 1, "重复提交产生了第二个 Run"


async def test_不同幂等键是两次独立提交(client: httpx.AsyncClient) -> None:
    project_id, configuration_id = await _prepare(client)
    payload = {"run_configuration_id": configuration_id}

    first = await client.post(
        f"/api/v1/projects/{project_id}/runs", json=payload, headers={"Idempotency-Key": "a"}
    )
    second = await client.post(
        f"/api/v1/projects/{project_id}/runs", json=payload, headers={"Idempotency-Key": "b"}
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


async def test_不带幂等键时行为不变(client: httpx.AsyncClient) -> None:
    """幂等键是可选的，老客户端不受影响。"""
    project_id, configuration_id = await _prepare(client)
    payload = {"run_configuration_id": configuration_id}

    first = await client.post(f"/api/v1/projects/{project_id}/runs", json=payload)
    second = await client.post(f"/api/v1/projects/{project_id}/runs", json=payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


async def test_幂等键按_workspace_隔离(client: httpx.AsyncClient) -> None:
    """两个空间用同一个键字符串不该互相影响。"""
    other = {"X-User": "another"}
    project_a, configuration_a = await _prepare(client)
    await client.get("/api/v1/me", headers=other)
    await use_default_environment(client, headers=other)
    project_b = await create_project_with_version(
        client, name="别人的项目", files={"main.py": "print('b')"}, headers=other
    )
    configuration_b = (
        await client.post(
            f"/api/v1/projects/{project_b['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
            },
            headers=other,
        )
    ).json()["id"]

    key = {"Idempotency-Key": "shared-key"}
    a = await client.post(
        f"/api/v1/projects/{project_a}/runs",
        json={"run_configuration_id": configuration_a},
        headers=key,
    )
    b = await client.post(
        f"/api/v1/projects/{project_b['id']}/runs",
        json={"run_configuration_id": configuration_b},
        headers={**other, **key},
    )

    assert a.status_code == 201
    assert b.status_code == 201, "另一个 Workspace 的同名键被误判成重复提交"


async def test_重跑同样支持幂等(client: httpx.AsyncClient) -> None:
    project_id, configuration_id = await _prepare(client)
    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/runs", json={"run_configuration_id": configuration_id}
        )
    ).json()
    await wait_for_run(client, run["id"])

    headers = {"Idempotency-Key": "rerun-attempt-0001"}
    first = await client.post(f"/api/v1/runs/{run['id']}/rerun", headers=headers)
    second = await client.post(f"/api/v1/runs/{run['id']}/rerun", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_登记在提交调度任务之前落库(client: httpx.AsyncClient, session) -> None:
    """键必须先落库，再提交作业。

    顺序反了的话，并发的第二个请求会先把作业提交出去，再因为键冲突回滚——
    数据库干净了，但集群上多跑了一个没人认领的作业。
    """
    from sqlalchemy import select

    from workspace107.infrastructure.db import tables as t

    project_id, configuration_id = await _prepare(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id},
        headers={"Idempotency-Key": "ordering-check"},
    )
    assert response.status_code == 201

    row = (
        await session.execute(
            select(t.IdempotencyKeyRow).where(t.IdempotencyKeyRow.key == "ordering-check")
        )
    ).scalar_one()

    assert row.endpoint == "create_run"
    assert row.run_id == response.json()["id"], "登记没有回填 Run，重放时会拿不到结果"


async def test_登记一定发生在调度提交之前(client: httpx.AsyncClient, monkeypatch) -> None:
    """GR-017 的实质：**产生外部副作用之前必须先完成去重登记**。

    上面那条只断言「事后登记行在」——顺序反了它照样绿，因为提交成功之后
    登记一样会落库。它守不住这条规则。

    本来想用并发来区分（先提交再登记的话，第二个请求会在集群上多跑一个
    没人认领的作业）。**试过，在这个测试环境里做不到**：SQLite 会把两个
    写事务串起来，第二个请求要等第一个提交完才动，于是走的是重放路径，
    两种顺序都只调用一次调度系统，区分不出来。

    所以改成直接观察调用顺序：在两个端口上打点，断言 reserve 出现在
    submit 之前。这个是确定性的，不依赖调度时序。
    """
    from workspace107.infrastructure.db.repositories import IdempotencyRepositoryImpl
    from workspace107.infrastructure.scheduler.mock import MockScheduler

    calls: list[str] = []

    original_reserve = IdempotencyRepositoryImpl.reserve
    original_submit = MockScheduler.submit

    async def spy_reserve(self, *args, **kwargs):
        calls.append("reserve")
        return await original_reserve(self, *args, **kwargs)

    async def spy_submit(self, *args, **kwargs):
        calls.append("submit")
        return await original_submit(self, *args, **kwargs)

    monkeypatch.setattr(IdempotencyRepositoryImpl, "reserve", spy_reserve)
    monkeypatch.setattr(MockScheduler, "submit", spy_submit)

    project_id, configuration_id = await _prepare(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id},
        headers={"Idempotency-Key": "ordering-observed"},
    )
    assert response.status_code == 201

    assert "reserve" in calls and "submit" in calls, calls
    assert calls.index("reserve") < calls.index("submit"), (
        f"登记发生在提交调度任务之后：{calls}。"
        "并发时第二个请求会先把作业丢到集群上再回滚，集群上就多了一个没人认领的作业。"
    )


async def test_同一个键在另一个_project_上不会静默返回别人的_run(
    client: httpx.AsyncClient,
) -> None:
    """键的作用域是 Workspace，而一个 Workspace 里有很多 Project。

    客户端复用同一个键（写死成常量、或者按天生成）在不同 Project 上提交时，
    光按键查会把上一个 Project 的 Run 原样返回——用户以为提交成功了，
    **这次提交根本没执行**，拿到的还是另一个项目的结果。
    报冲突让他换键，比静默返回错的东西好。
    """
    project_a, configuration_a = await _prepare(client, "print('a')")
    project_b, configuration_b = await _prepare(client, "print('b')")
    key = {"Idempotency-Key": "reused-across-projects"}

    first = await client.post(
        f"/api/v1/projects/{project_a}/runs",
        json={"run_configuration_id": configuration_a},
        headers=key,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/projects/{project_b}/runs",
        json={"run_configuration_id": configuration_b},
        headers=key,
    )
    assert second.status_code == 409
    assert "另一个 Project" in second.json()["message"]

    # B 项目下确实一个 Run 都没有，没有被悄悄算作提交过
    runs_b = (await client.get(f"/api/v1/projects/{project_b}/runs")).json()
    assert runs_b["total"] == 0


async def test_创建用过的键不能拿去重跑(client: httpx.AsyncClient) -> None:
    """动作类型也要对上，否则重跑会返回一个「创建」的 Run。"""
    project_id, configuration_id = await _prepare(client)
    key = {"Idempotency-Key": "same-key-different-action"}

    created = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id},
        headers=key,
    )
    assert created.status_code == 201
    await wait_for_run(client, created.json()["id"])

    reused = await client.post(f"/api/v1/runs/{created.json()['id']}/rerun", headers=key)
    assert reused.status_code == 409
    assert "create_run" in reused.json()["message"]
