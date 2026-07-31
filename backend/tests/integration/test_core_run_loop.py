"""本地 Mock 核心运行闭环端到端测试。

    创建 Project -> 准备代码 -> 保存 Project Version -> 配置运行方案
    -> 提交前检查 -> 提交 Run -> 状态流转 -> 日志 -> Artifact -> 复现快照

作业由 MockScheduler 以子进程**真实执行**，状态来自真实退出码。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

TRAIN_SCRIPT = """import json, os, pathlib
pathlib.Path("outputs").mkdir(exist_ok=True)
epochs = int(os.environ["EPOCHS"])
print(f"training for {epochs} epochs")
pathlib.Path("outputs/metrics.json").write_text(json.dumps({"epochs": epochs, "acc": 0.93}))
print("done")
"""


async def test_完整核心闭环(client: httpx.AsyncClient) -> None:
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    assert home["user"]["username"] == "student"
    # 新用户自动获得 Personal Workspace。
    assert home["workspaces"][0]["kind"] == "personal"

    # 1. 选择 Workspace 默认环境
    await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": "ev_python_312"},
    )

    # 2. 准备代码并保存版本
    project = await create_project_with_version(
        client, name="端到端项目", files={"train.py": TRAIN_SCRIPT}
    )
    listing = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()
    assert listing["total"] == 1
    assert listing["has_more"] is False
    versions = listing["items"]
    assert len(versions) == 1
    assert versions[0]["label"] == "v1"

    # 3. Workspace Variable + 运行方案
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables", json={"name": "EPOCHS", "value": "3"}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "默认运行",
                "command": "python train.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_variables": {"EPOCHS": "${{ vars.EPOCHS }}"},
                "artifact_rules": [{"path": "outputs", "name": "结果", "optional": False}],
            },
        )
    ).json()

    # 第一个运行方案自动成为 Project 默认方案
    project_detail = (await client.get(f"/api/v1/projects/{project['id']}")).json()
    assert project_detail["default_run_configuration_id"] == configuration["id"]

    # 4. 提交前检查
    preflight = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs/preflight",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    assert preflight["ok"], preflight["problems"]
    assert preflight["resolved_environment_variables"] == {"EPOCHS": "3"}
    assert preflight["compute_request"]["cpus"] == 2

    # 5. 提交 Run
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"], "name": "第一次训练"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] in {"queued", "running"}
    assert run["scheduler_job_id"]

    # 6. 状态流转到终态
    detail = await wait_for_run(client, run["id"])
    assert detail["run"]["status"] == "succeeded"
    assert detail["run"]["exit_code"] == 0
    assert detail["run"]["finished_at"] is not None

    # 7. 平台事件时间线
    event_types = [e["type"] for e in detail["events"]]
    assert event_types[0] == "created"
    assert "submitted" in event_types
    assert "artifact_collected" in event_types
    assert "finished" in event_types

    # 8. 日志
    logs = (await client.get(f"/api/v1/runs/{run['id']}/logs")).json()
    stdout = next(chunk for chunk in logs if chunk["stream"] == "stdout")
    assert "training for 3 epochs" in stdout["content"]
    assert "done" in stdout["content"]

    # 9. Artifact
    assert len(detail["artifacts"]) == 1
    artifact = detail["artifacts"][0]
    assert artifact["name"] == "结果"
    assert artifact["file_count"] == 1

    files = (await client.get(f"/api/v1/artifacts/{artifact['id']}/files")).json()
    assert [f["path"] for f in files] == ["metrics.json"]

    download = await client.get(
        f"/api/v1/artifacts/{artifact['id']}/download", params={"path": "metrics.json"}
    )
    assert download.status_code == 200
    assert b'"epochs": 3' in download.content

    # 10. 复现快照：完整记录本次到底按什么配置跑的
    snapshot = detail["snapshot"]
    assert snapshot["project_version_id"] == versions[0]["id"]
    assert snapshot["command"] == "python train.py"
    assert snapshot["environment_version_id"] == "ev_python_312"
    assert snapshot["environment_variables"] == {"EPOCHS": "3"}
    assert snapshot["scheduler"]["partition"] == "debug"
    assert snapshot["scheduler"]["qos"] == "normal"


async def test_失败的作业被如实记录为_failed(client: httpx.AsyncClient) -> None:
    """退出码非 0 就是失败，平台不会替用户把它变成成功。"""
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="会失败的项目", files={"main.py": "import sys; sys.exit(3)"}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "会失败",
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
    assert detail["run"]["status"] == "failed"
    assert detail["run"]["exit_code"] == 3


async def test_没有保存版本时提交被拒绝(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client)
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "空项目"})
    ).json()
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={"name": "跑一下", "command": "echo hi", "compute_plan_id": "plan_cpu_quick"},
        )
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "preflight_rejected"
    assert any("Project Version" in p for p in body["problems"])


async def test_没有可用环境时提交被拒绝(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="没配环境")
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={"name": "跑一下", "command": "echo hi", "compute_plan_id": "plan_cpu_quick"},
        )
    ).json()

    preflight = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs/preflight",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    assert not preflight["ok"]
    assert any("运行环境" in p for p in preflight["problems"])


async def test_超出算力方案上限时提交被拒绝(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(client, name="要资源太多")
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={"name": "跑一下", "command": "echo hi", "compute_plan_id": "plan_cpu_quick"},
        )
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "run_configuration_id": configuration["id"],
            "compute_request_override": {
                "nodes": 8,
                "cpus": 128,
                "memory_mb": 1024,
                "gpus": 0,
                "time_limit_minutes": 10,
            },
        },
    )
    assert response.status_code == 422
    assert any("超出算力方案" in p for p in response.json()["problems"])
