"""测试辅助函数。"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace107.domain import ids
from workspace107.domain.compute import ResourceEntitlement
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.tables import EnvironmentRow, EnvironmentVersionRow

RUN_WAIT_TIMEOUT = 30.0
TERMINAL = {"succeeded", "failed", "cancelled", "submit_failed"}


async def wait_for_run(
    client: httpx.AsyncClient, run_id: str, *, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    """轮询直到 Run 进入终态，返回 Run 详情。

    走的是真实路径：触发状态同步 -> 读取 Run。同步只会把调度系统的实际状态
    映射过来，不会伪造结果。
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


async def ensure_user_group(
    client: httpx.AsyncClient, *, headers: dict[str, str] | None = None
) -> str:
    """Return the caller's first User Group, creating one when needed."""
    home_response = await client.get("/api/v1/me", headers=headers)
    home_response.raise_for_status()
    home = home_response.json()
    if home["user_groups"]:
        return str(home["user_groups"][0]["id"])
    response = await client.post(
        "/api/v1/user-groups",
        json={"name": f"{home['user']['username']} test group"},
        headers=headers,
    )
    response.raise_for_status()
    return str(response.json()["id"])


async def grant_test_entitlement(
    session: AsyncSession,
    username: str,
    compute_plan_id: str = "plan_cpu_quick",
    *,
    max_concurrent_runs: int = 2,
    expires_at: str | None = None,
) -> None:
    """Seed the entitlement of the user named ``username``; nothing grants one implicitly."""
    user = (
        await session.execute(select(t.UserRow).where(t.UserRow.username == username))
    ).scalar_one()
    await SqlRepositories(session).entitlements.add(
        ResourceEntitlement(
            id=ids.new_id(ids.ENTITLEMENT),
            user_id=user.id,
            compute_plan_id=compute_plan_id,
            max_concurrent_runs=max_concurrent_runs,
            expires_at=expires_at,
        )
    )
    await session.commit()


async def create_project_with_version(
    client: httpx.AsyncClient,
    *,
    name: str = "测试项目",
    files: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """创建 Project、写入文件并保存一个版本，返回 Project。"""
    workspace_id = await ensure_user_group(client, headers=headers)

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
    session: AsyncSession,
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    """Create the group's own default environment and return its compatibility ID."""
    workspace_id = await ensure_user_group(client, headers=headers)
    environment_id = ids.new_id(ids.ENVIRONMENT)
    version_id = ids.new_id(ids.ENVIRONMENT_VERSION)
    session.add(
        EnvironmentRow(
            id=environment_id,
            name="Test Environment",
            description="测试环境",
            owner_user_group_id=workspace_id,
        )
    )
    await session.flush()
    session.add(
        EnvironmentVersionRow(
            id=version_id,
            environment_id=environment_id,
            version="3.12",
            description="Python 3.12 标准库环境。",
            image="python:3.12-slim",
            setup_command="",
        )
    )
    await session.commit()
    response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"default_environment_version_id": version_id},
        headers=headers,
    )
    response.raise_for_status()
    return workspace_id
