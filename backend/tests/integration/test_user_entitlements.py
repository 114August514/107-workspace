"""Issue #38：Resource Entitlement 属于发起 User。

覆盖验收条件：
- 无权益 / 权益过期明确阻止 Run；
- 权益按发起 User 校验——别人的权益帮不了你，Membership 不转移资格；
- 并发上限按「发起 User × 算力方案」统计，不共享别人的名额；
- ``GET /me/entitlements`` 只返回当前 User 自己的权益。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers import create_project_with_version, grant_test_entitlement, use_default_environment

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _prepare_submission(
    session: AsyncSession, client: httpx.AsyncClient, headers: dict[str, str]
) -> tuple[str, str]:
    """建好默认环境、带版本的 Project 和运行方案，返回 (project_id, configuration_id)。"""
    _, env_version_id = await use_default_environment(session, client, headers=headers)
    project = await create_project_with_version(client, headers=headers)
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "默认运行",
            "command": "python -V",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return project["id"], response.json()["id"]


async def _submit(
    client: httpx.AsyncClient, project_id: str, configuration_id: str, headers
) -> httpx.Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_没有权益的用户不能提交_run(client: httpx.AsyncClient, session: AsyncSession) -> None:
    project_id, configuration_id = await _prepare_submission(session, client, ALICE)

    response = await _submit(client, project_id, configuration_id, ALICE)

    assert response.status_code == 422
    assert any("使用权益" in problem for problem in response.json()["problems"])


@pytest.mark.asyncio
async def test_权益属于发起用户而不是_user_group(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    alice_project, alice_config = await _prepare_submission(session, client, ALICE)
    bob_project, bob_config = await _prepare_submission(session, client, BOB)
    await grant_test_entitlement(session, "alice")

    # alice 本人可以提交。
    response = await _submit(client, alice_project, alice_config, ALICE)
    assert response.status_code == 201, response.text

    # bob 在同一个平台上有自己的 User Group，但 alice 的权益不转移给他。
    response = await _submit(client, bob_project, bob_config, BOB)
    assert response.status_code == 422
    assert any("使用权益" in problem for problem in response.json()["problems"])


@pytest.mark.asyncio
async def test_过期权益阻止提交(client: httpx.AsyncClient, session: AsyncSession) -> None:
    project_id, configuration_id = await _prepare_submission(session, client, ALICE)
    await grant_test_entitlement(session, "alice", expires_at="2020-01-01T00:00:00+00:00")

    response = await _submit(client, project_id, configuration_id, ALICE)

    assert response.status_code == 422
    assert any("已过期" in problem for problem in response.json()["problems"])


@pytest.mark.asyncio
async def test_并发上限按发起用户统计(client: httpx.AsyncClient, session: AsyncSession) -> None:
    alice_project, alice_config = await _prepare_submission(session, client, ALICE)
    bob_project, bob_config = await _prepare_submission(session, client, BOB)
    await grant_test_entitlement(session, "alice", max_concurrent_runs=1)
    await grant_test_entitlement(session, "bob", max_concurrent_runs=1)

    # alice 的第一个 Run 已占用她唯一的并发名额（未同步前停在 queued）。
    first = await _submit(client, alice_project, alice_config, ALICE)
    assert first.status_code == 201, first.text

    second = await _submit(client, alice_project, alice_config, ALICE)
    assert second.status_code == 422
    assert any("并发上限" in problem for problem in second.json()["problems"])

    # bob 的名额独立计算，alice 的排队不挤占他。
    response = await _submit(client, bob_project, bob_config, BOB)
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_我的权益只返回自己的(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await client.get("/api/v1/me", headers=ALICE)
    await client.get("/api/v1/me", headers=BOB)
    await grant_test_entitlement(session, "alice")

    mine = (await client.get("/api/v1/me/entitlements", headers=ALICE)).json()
    assert [item["compute_plan_id"] for item in mine] == ["plan_cpu_quick"]
    assert mine[0]["compute_plan_name"] == "CPU 快速测试"
    assert mine[0]["max_concurrent_runs"] == 2
    assert mine[0]["expires_at"] is None

    assert (await client.get("/api/v1/me/entitlements", headers=BOB)).json() == []
