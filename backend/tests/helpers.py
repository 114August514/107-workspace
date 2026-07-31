"""测试辅助函数。"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

RUN_WAIT_TIMEOUT = 30.0
TERMINAL = {"succeeded", "failed", "cancelled", "submit_failed"}


async def wait_for_run(
    client: httpx.AsyncClient, run_id: str, *, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    """轮询直到 Run 进入终态，返回 Run 详情。

    走的是真实路径：触发状态同步 -> 读取 Run。同步只会把调度系统的实际状态
    映射过来，不会伪造结果（GR-015）。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + RUN_WAIT_TIMEOUT
    while True:
        await client.post("/api/v1/runs/sync")
        response = await client.get(f"/api/v1/runs/{run_id}", headers=headers)
        response.raise_for_status()
        detail = response.json()
        if detail["run"]["status"] in TERMINAL:
            return detail
        if loop.time() > deadline:
            raise AssertionError(f"Run {run_id} 在 {RUN_WAIT_TIMEOUT} 秒内没有结束")
        await asyncio.sleep(0.05)


async def create_project_with_version(
    client: httpx.AsyncClient,
    *,
    name: str = "测试项目",
    files: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """创建 Project、写入文件并保存一个版本，返回 Project。"""
    home = (await client.get("/api/v1/me", headers=headers)).json()
    workspace_id = home["workspaces"][0]["id"]

    project = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": name, "description": "测试用"},
            headers=headers,
        )
    ).json()

    for path, content in (files or {"run.sh": "echo hello"}).items():
        response = await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": path, "content": content},
            headers=headers,
        )
        response.raise_for_status()

    version = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "初始版本"},
        headers=headers,
    )
    version.raise_for_status()
    return project


async def use_default_environment(
    client: httpx.AsyncClient, *, headers: dict[str, str] | None = None
) -> str:
    """把 Personal Workspace 的默认环境设为 Python 3.12，返回 Workspace ID。"""
    home = (await client.get("/api/v1/me", headers=headers)).json()
    workspace_id = home["workspaces"][0]["id"]
    await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": "ev_python_312"},
        headers=headers,
    )
    return workspace_id
