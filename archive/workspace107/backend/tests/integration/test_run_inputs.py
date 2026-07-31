"""Artifact 作为后续 Run 的输入。

对应 GR-010：Artifact 不必先发布为 Shared Resource 就能作为输入。
对应 GR-011：输入默认只读，Run 不得原地修改输入对象。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

PRODUCER = """import pathlib
pathlib.Path("outputs").mkdir(exist_ok=True)
pathlib.Path("outputs/dataset.txt").write_text("第一阶段的结果")
print("produced")
"""

CONSUMER = """import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/stage1"
print("读到:", (root / "dataset.txt").read_text())
"""

WRITER = """import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/stage1"
try:
    (root / "dataset.txt").write_text("篡改")
    print("写成功了")
except (PermissionError, OSError) as exc:
    print("写入被拒绝:", type(exc).__name__)
"""


async def _produce_artifact(client: httpx.AsyncClient) -> tuple[dict, dict]:
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="两阶段项目", files={"produce.py": PRODUCER}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "第一阶段",
                "command": "python produce.py",
                "compute_plan_id": "plan_cpu_quick",
                "artifact_rules": [{"path": "outputs", "name": "阶段一结果", "optional": False}],
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
    assert detail["run"]["status"] == "succeeded"
    return project, detail["artifacts"][0]


async def _run_with_input(
    client: httpx.AsyncClient, project: dict, artifact: dict, *, script: str, entry: str
) -> dict:
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": entry, "content": script},
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "加入消费端"})

    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": f"第二阶段-{entry}",
                "command": f"python {entry}",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "artifact",
                        "source_id": artifact["id"],
                        "access_path": "/inputs/stage1",
                    }
                ],
            },
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    return await wait_for_run(client, run["id"])


async def test_artifact_可以直接作为后续_run_的输入(client: httpx.AsyncClient) -> None:
    project, artifact = await _produce_artifact(client)
    detail = await _run_with_input(client, project, artifact, script=CONSUMER, entry="consume.py")

    assert detail["run"]["status"] == "succeeded"
    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs")).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "读到: 第一阶段的结果" in stdout["content"]

    # 输入绑定被固定进快照，不是运行时才去查的。
    binding = detail["snapshot"]["input_bindings"][0]
    assert binding["source_type"] == "artifact"
    assert binding["source_id"] == artifact["id"]
    assert binding["access_path"] == "/inputs/stage1"


async def test_输入以只读方式提供(client: httpx.AsyncClient) -> None:
    project, artifact = await _produce_artifact(client)
    detail = await _run_with_input(client, project, artifact, script=WRITER, entry="write.py")

    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs")).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "写入被拒绝" in stdout["content"]
    assert "写成功了" not in stdout["content"]


async def test_引用不存在的_artifact_会挡在提交前(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(client, name="错误输入")
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "echo hi",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "artifact",
                        "source_id": "art_not_exist",
                        "access_path": "/inputs/x",
                    }
                ],
            },
        )
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
    )
    assert response.status_code == 422
    assert any("不存在或无权访问" in p for p in response.json()["problems"])


async def test_必需的_artifact_没生成时_run_被标记失败(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="不产出结果", files={"main.py": "print('什么都没写')"}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "artifact_rules": [{"path": "outputs", "optional": False}],
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
    assert detail["run"]["status"] == "failed"
    assert "outputs" in detail["run"]["failure_reason"]
    assert any(e["type"] == "artifact_missing" for e in detail["events"])

    # 衍生记录必须和落库的状态一致。
    #
    # 这几条断言是补上去的：原来只检查 run.status，而 bug 恰恰只出现在
    # 事件、活动和通知上——库里 failed，用户收到的通知却说「Run 成功」。
    # **只断言主对象的状态，等于放过了所有用陈旧副本产生的衍生记录。**
    finished = next(e for e in detail["events"] if e["type"] == "finished")
    assert "failed" in finished["message"], finished["message"]

    notifications = (await client.get("/api/v1/notifications")).json()["items"]
    about_run = [n for n in notifications if n["target_id"] == run["id"]]
    assert about_run, "Run 结束了却没有通知"
    assert about_run[0]["type"] == "run_failed", about_run[0]
    assert "失败" in about_run[0]["title"]
    # 失败原因要带上，否则用户拿到一条「失败了」但不知道为什么
    assert "outputs" in about_run[0]["body"]

    activities = (await client.get(f"/api/v1/projects/{project['id']}/activities")).json()["items"]
    finished_activity = next(a for a in activities if a["action"] == "run_finished")
    assert finished_activity["detail"] == "failed"


async def test_可选的_artifact_没生成时只记录事件(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="可选产出", files={"main.py": "print('ok')"}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "artifact_rules": [{"path": "outputs", "optional": True}],
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
    assert detail["run"]["status"] == "succeeded"
    assert detail["artifacts"] == []
    assert any(e["type"] == "artifact_missing" for e in detail["events"])


async def test_编辑运行方案不会清空输入绑定(client: httpx.AsyncClient) -> None:
    """PUT 是整体替换，所以调用方必须把不改的字段原样带回来。

    前端的编辑弹窗不管输入绑定，早先提交时也不带——改一次名称就把
    Artifact 输入全清空了，而且没有任何提示。这条守的是**接口的替换语义**：
    带全字段才不会丢东西。
    """
    project, artifact = await _produce_artifact(client)
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "带输入的",
                "command": "python x.py",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "artifact",
                        "source_id": artifact["id"],
                        "access_path": "/inputs/stage1",
                    }
                ],
            },
        )
    ).json()
    assert len(configuration["input_bindings"]) == 1

    # 带全字段更新：绑定还在
    updated = (
        await client.put(
            f"/api/v1/run-configurations/{configuration['id']}",
            json={
                "name": "改了名字",
                "command": configuration["command"],
                "compute_plan_id": configuration["compute_plan_id"],
                "input_bindings": configuration["input_bindings"],
            },
        )
    ).json()
    assert updated["name"] == "改了名字"
    assert len(updated["input_bindings"]) == 1

    # 不带的话确实会清空——这是 PUT 的语义，不是 bug，
    # 所以责任在调用方；这条断言把语义钉住，免得以后有人以为它会合并。
    cleared = (
        await client.put(
            f"/api/v1/run-configurations/{configuration['id']}",
            json={
                "name": "又改一次",
                "command": configuration["command"],
                "compute_plan_id": configuration["compute_plan_id"],
            },
        )
    ).json()
    assert cleared["input_bindings"] == []
