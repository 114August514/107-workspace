"""重跑与引用重新校验。

对应 GR-007：所有外部引用在使用时重新校验；曾经成功不代表现在还能用。
对应 GR-009：重跑必须创建新的 Run 和新的 Run Snapshot。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run


async def _run_once(client: httpx.AsyncClient, name: str = "重跑测试") -> tuple[dict, dict]:
    await use_default_environment(client)
    project = await create_project_with_version(client, name=name, files={"main.py": "print('v1')"})
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
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    detail = await wait_for_run(client, run["id"])
    return project, detail


async def test_重跑创建新的_run_和新的_snapshot(client: httpx.AsyncClient) -> None:
    _, first = await _run_once(client)

    response = await client.post(f"/api/v1/runs/{first['run']['id']}/rerun")
    assert response.status_code == 201
    second = response.json()

    assert second["id"] != first["run"]["id"]
    assert second["snapshot_id"] != first["run"]["snapshot_id"]
    assert second["source_run_id"] == first["run"]["id"]

    detail = await wait_for_run(client, second["id"])
    assert detail["run"]["status"] == "succeeded"
    # 代码快照一致：重跑跑的还是同一个 Project Version。
    assert detail["snapshot"]["project_version_id"] == first["snapshot"]["project_version_id"]
    assert detail["snapshot"]["command"] == first["snapshot"]["command"]


async def test_修改运行方案不影响已创建的_run(client: httpx.AsyncClient) -> None:
    _, first = await _run_once(client, name="改方案测试")
    configuration_id = first["snapshot"]["source_run_configuration_id"]

    await client.put(
        f"/api/v1/run-configurations/{configuration_id}",
        json={
            "name": "改过的方案",
            "command": "echo 完全不一样的命令",
            "compute_plan_id": "plan_cpu_standard",
        },
    )

    # 历史 Run 的快照保持原样。
    detail = (await client.get(f"/api/v1/runs/{first['run']['id']}")).json()
    assert detail["snapshot"]["command"] == "python main.py"
    assert detail["snapshot"]["compute_plan_id"] == "plan_cpu_quick"

    # 重跑用的也是原快照，不是改后的运行方案。
    rerun = (await client.post(f"/api/v1/runs/{first['run']['id']}/rerun")).json()
    rerun_detail = await wait_for_run(client, rerun["id"])
    assert rerun_detail["snapshot"]["command"] == "python main.py"
    assert rerun_detail["snapshot"]["compute_plan_id"] == "plan_cpu_quick"


async def test_环境版本下架后不能重跑(client: httpx.AsyncClient, session) -> None:
    """历史 Run 仍然能看，但不能再跑起来（GR-007 / GR-008）。"""
    from sqlalchemy import update

    from workspace107.infrastructure.db import tables as t

    _, first = await _run_once(client, name="环境下架测试")

    await session.execute(
        update(t.EnvironmentVersionRow)
        .where(t.EnvironmentVersionRow.id == "ev_python_312")
        .values(available=False)
    )
    await session.commit()

    # 历史事实仍然可见。
    detail = (await client.get(f"/api/v1/runs/{first['run']['id']}")).json()
    assert detail["snapshot"]["environment_version_id"] == "ev_python_312"

    response = await client.post(f"/api/v1/runs/{first['run']['id']}/rerun")
    assert response.status_code == 422
    assert any("不可用" in p for p in response.json()["problems"])


async def test_权益被撤销后不能重跑(client: httpx.AsyncClient, session) -> None:
    from sqlalchemy import delete

    from workspace107.infrastructure.db import tables as t

    _, first = await _run_once(client, name="权益撤销测试")

    await session.execute(
        delete(t.ResourceEntitlementRow).where(
            t.ResourceEntitlementRow.compute_plan_id == "plan_cpu_quick"
        )
    )
    await session.commit()

    response = await client.post(f"/api/v1/runs/{first['run']['id']}/rerun")
    assert response.status_code == 422
    assert any("使用权益" in p for p in response.json()["problems"])


async def test_并发上限挡住新的提交(client: httpx.AsyncClient) -> None:
    """默认权益允许 2 个未结束的 Run，第三个应该被挡下。"""
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="并发测试", files={"main.py": "import time; time.sleep(5)"}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "长任务",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
            },
        )
    ).json()

    payload = {"run_configuration_id": configuration["id"]}
    started = []
    for _ in range(2):
        response = await client.post(f"/api/v1/projects/{project['id']}/runs", json=payload)
        assert response.status_code == 201
        started.append(response.json())

    blocked = await client.post(f"/api/v1/projects/{project['id']}/runs", json=payload)
    assert blocked.status_code == 422
    assert any("并发上限" in p for p in blocked.json()["problems"])

    for run in started:
        await client.post(f"/api/v1/runs/{run['id']}/cancel")
