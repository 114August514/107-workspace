"""GR-012：Secret 不得通过普通对象传播，也不得出现在快照、日志和响应里。"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

SECRET_VALUE = "hf_this_must_never_be_visible"

LEAKY_SCRIPT = """import os
print("token is", os.environ["TOKEN"])
print("normal var is", os.environ["LOG_LEVEL"])
"""


async def test_secret_没有任何读取接口(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": "HF_TOKEN", "value": SECRET_VALUE},
    )

    listed = await client.get(f"/api/v1/workspaces/{workspace_id}/secrets")
    assert listed.json() == ["HF_TOKEN"]
    assert SECRET_VALUE not in listed.text


async def test_run_snapshot_只保存引用_不保存明文(client: httpx.AsyncClient) -> None:
    workspace_id = await use_default_environment(client)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": "HF_TOKEN", "value": SECRET_VALUE},
    )
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables",
        json={"name": "LOG_LEVEL", "value": "INFO"},
    )

    project = await create_project_with_version(
        client, name="会打印密钥的项目", files={"main.py": LEAKY_SCRIPT}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_variables": {
                    "TOKEN": "${{ secrets.HF_TOKEN }}",
                    "LOG_LEVEL": "${{ vars.LOG_LEVEL }}",
                },
            },
        )
    ).json()

    # 运行方案本身也只保存表达式。
    assert configuration["environment_variables"]["TOKEN"] == "${{ secrets.HF_TOKEN }}"

    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    detail = await wait_for_run(client, run["id"])
    assert detail["run"]["status"] == "succeeded"

    snapshot = detail["snapshot"]
    # Variable 被解析成字面值固定下来；Secret 只留引用关系。
    assert snapshot["environment_variables"] == {"LOG_LEVEL": "INFO"}
    assert snapshot["secret_references"] == {"TOKEN": "HF_TOKEN"}
    assert SECRET_VALUE not in str(snapshot)


async def test_程序把_secret_打到_stdout_也会被抹掉(client: httpx.AsyncClient) -> None:
    """最后一道防线：用户程序自己泄露时，日志接口仍然不返回明文。"""
    workspace_id = await use_default_environment(client)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": "HF_TOKEN", "value": SECRET_VALUE},
    )
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/variables",
        json={"name": "LOG_LEVEL", "value": "INFO"},
    )

    project = await create_project_with_version(
        client, name="泄露测试", files={"main.py": LEAKY_SCRIPT}
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "environment_variables": {
                    "TOKEN": "${{ secrets.HF_TOKEN }}",
                    "LOG_LEVEL": "${{ vars.LOG_LEVEL }}",
                },
            },
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
        )
    ).json()
    await wait_for_run(client, run["id"])

    logs = (await client.get(f"/api/v1/runs/{run['id']}/logs")).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")

    # Secret 已经真的注入到进程里了（程序读到了它），但输出里不能有明文。
    assert "token is ***" in stdout["content"]
    assert SECRET_VALUE not in stdout["content"]
    # 非敏感变量照常显示。
    assert "normal var is INFO" in stdout["content"]


async def test_引用不存在的_secret_会挡在提交前(client: httpx.AsyncClient) -> None:
    await use_default_environment(client)
    project = await create_project_with_version(client, name="引用缺失密钥")
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "echo hi",
                "compute_plan_id": "plan_cpu_quick",
                "environment_variables": {"TOKEN": "${{ secrets.NOT_CONFIGURED }}"},
            },
        )
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
    )
    assert response.status_code == 422
    assert any("NOT_CONFIGURED" in p for p in response.json()["problems"])
