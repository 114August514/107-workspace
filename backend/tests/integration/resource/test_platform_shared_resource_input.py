"""平台运营 User Group Shared Resource 作 Run 输入的授权语义（GR-401）。

普通 actor 在 #40 USE Grant 实现前不可发现或消费跨 Owner 资源；平台运营资产没有
特殊 Platform/public 绕过路径。本 Core 阶段提交 Run 时按不存在或无权访问拒绝。

服务层不会创建跨 Owner SR（owner authority 只允许 actor 或其 active User Group），
所以这里通过 ``session`` 夹具直接插入一条平台组 SR + 版本，再经 HTTP 尝试保存
Run Configuration，断言跨 Owner exact reference 在持久化前按不存在拒绝（404）。
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
    UserGroupRow,
    UserRow,
)
from workspace107.tools.seed import PLATFORM_ASSET_GROUP_ID

ALICE = {"X-User": "alice"}
PLATFORM_USER_ID = "usr_platform_operator"


async def _seed_platform_resource_with_version(session: AsyncSession) -> str:
    """直接插一条平台组 SR + 单文件版本，返回 version_id。"""
    now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    session.add(
        UserRow(
            id=PLATFORM_USER_ID,
            username="platform-operator",
            display_name="Platform Operator",
            email=None,
            created_at=now,
        )
    )
    await session.flush()
    session.add(
        UserGroupRow(
            id=PLATFORM_ASSET_GROUP_ID,
            name="平台资产",
            description="",
            created_by_id=PLATFORM_USER_ID,
            created_at=now,
        )
    )
    await session.flush()
    session.add(
        SharedResourceRow(
            id="shr_platform",
            name="平台组资源",
            description="",
            owner_user_id=None,
            owner_user_group_id=PLATFORM_ASSET_GROUP_ID,
            created_at=now,
        )
    )
    session.add(
        SharedResourceVersionRow(
            id="shrv_platform_1",
            shared_resource_id="shr_platform",
            sequence=1,
            description="v1",
            created_by=PLATFORM_USER_ID,
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


async def test_platform_shared_resource_作_run_输入被挡在运行方案保存前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """引用平台组 SR 版本时保存 Run Configuration 即按不存在拒绝。"""
    version_id = await _seed_platform_resource_with_version(session)
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)

    project = await create_project_with_version(
        client, name="引用平台资源", files={"main.py": "pass"}, headers=ALICE
    )
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "消费平台资源",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
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
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
