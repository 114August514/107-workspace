"""Platform Shared Resource 作 Run 输入的授权语义（GR-401）。

Platform 持有的资源可以浏览，但作为 Run 输入消费需要有效的 Workspace Asset Grant；
Asset Grant 在 M4 实现，本 Core 阶段一律拒绝 Platform 资源作 Run 输入。

服务层不会创建 Platform SR（``publish_version`` 对 platform 资源直接抛
PermissionDenied），所以这里通过 ``session`` 夹具直接插入一条 Platform SR + 版本，
再经 HTTP 引用它提交 Run，断言被挡在提交前（422）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_project_with_version, use_default_environment
from workspace107.infrastructure.db.tables import (
    SharedResourceRow,
    SharedResourceVersionFileRow,
    SharedResourceVersionRow,
)

ALICE = {"X-User": "alice"}


async def _seed_platform_resource_with_version(session: AsyncSession) -> str:
    """直接插一条 Platform SR（owner_workspace_id=None）+ 单文件版本，返回 version_id。"""
    now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    session.add(
        SharedResourceRow(
            id="shr_platform",
            name="平台公共资源",
            description="",
            owner_workspace_id=None,
            created_at=now,
        )
    )
    session.add(
        SharedResourceVersionRow(
            id="shrv_platform_1",
            shared_resource_id="shr_platform",
            sequence=1,
            description="v1",
            created_by="platform",
            created_at=now,
        )
    )
    await session.flush()  # 让 version 行先落库，文件行的外键才能解析
    session.add(
        SharedResourceVersionFileRow(
            version_id="shrv_platform_1",
            path="weights.txt",
            size=4,
            content_hash="hash_platform_weights",
        )
    )
    await session.commit()
    return "shrv_platform_1"


async def test_platform_shared_resource_作_run_输入被挡在提交前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """引用 Platform SR 版本作 Run 输入 → preflight 422，提示需 M4 Asset Grant。"""
    await use_default_environment(client, headers=ALICE)
    version_id = await _seed_platform_resource_with_version(session)

    project = await create_project_with_version(
        client, name="引用平台资源", files={"main.py": "pass"}, headers=ALICE
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "消费平台资源",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version_id,
                        "access_path": "/inputs/w",
                    }
                ],
            },
            headers=ALICE,
        )
    ).json()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert response.status_code == 422
    problems = response.json()["problems"]
    assert any("Platform" in p and "Asset Grant" in p for p in problems), problems
