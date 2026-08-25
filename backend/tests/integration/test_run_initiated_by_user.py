"""Issue #41：Run 按 Initiated By User 与确定配置收敛的可观察行为。

覆盖验收条件里最核心的语义：

- Run / Snapshot 唯一记录发起 User，贯穿 create / rerun / API；
- 同一 User Group Project 里两个成员因个人 entitlement / user secret
  不同得到不同 preflight 结果；
- Run Configuration 必须精确引用 Environment Version，无任何默认值回退；
- USE Grant 打开跨 Owner 的精确 Environment 引用；
- Artifact 直接输入仅限同一 Project Owner（GR-405）；
- 幂等键按发起 User 作用域；
- Rerun 生成新 Run + 新 Snapshot，发起人是当前重跑的 User，不漂移。
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import grant_test_entitlement, wait_for_run
from workspace107.domain import ids
from workspace107.infrastructure.db.tables import (
    ArtifactRow,
    EnvironmentRow,
    EnvironmentVersionRow,
)

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _create_group(client: httpx.AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/user-groups", json={"name": name}, headers=ALICE)
    response.raise_for_status()
    return str(response.json()["id"])


async def _create_environment(
    session: AsyncSession, *, owner_user_group_id: str
) -> tuple[str, str]:
    """Create an Environment + Version owned by the group. Returns (id, version_id)."""
    environment_id = ids.new_id(ids.ENVIRONMENT)
    version_id = ids.new_id(ids.ENVIRONMENT_VERSION)
    session.add(
        EnvironmentRow(
            id=environment_id,
            name=f"{environment_id} environment",
            description="",
            owner_user_group_id=owner_user_group_id,
        )
    )
    await session.flush()
    session.add(
        EnvironmentVersionRow(
            id=version_id,
            environment_id=environment_id,
            version="1",
            description="",
            image="python:3.12-slim",
            setup_command="",
        )
    )
    await session.commit()
    return environment_id, version_id


async def _create_project(client: httpx.AsyncClient, user_group_id: str, *, name: str) -> dict:
    response = await client.post(
        f"/api/v1/workspaces/{user_group_id}/projects",
        json={"name": name},
        headers=ALICE,
    )
    response.raise_for_status()
    project = response.json()
    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=ALICE,
    )
    response.raise_for_status()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "v1"},
        headers=ALICE,
    )
    response.raise_for_status()
    return project


async def _get_user_id(client: httpx.AsyncClient, headers: dict) -> str:
    response = await client.get("/api/v1/me", headers=headers)
    response.raise_for_status()
    return str(response.json()["user"]["id"])


async def _join_group(client: httpx.AsyncClient, group_id: str) -> None:
    """Make Bob an active member of the group Alice owns."""
    # Dev 身份按请求惰性创建：先让 Bob 出现，邀请才能按 username 找到他。
    await client.get("/api/v1/me", headers=BOB)
    response = await client.post(
        f"/api/v1/user-groups/{group_id}/members",
        json={"username": "bob"},
        headers=ALICE,
    )
    response.raise_for_status()
    response = await client.post(
        f"/api/v1/user-groups/{group_id}/invitation",
        json={"accept": True},
        headers=BOB,
    )
    response.raise_for_status()


async def _create_configuration(
    client: httpx.AsyncClient,
    project: dict,
    environment_version_id: str,
    *,
    input_bindings: list[dict] | None = None,
    environment_variables: dict[str, str] | None = None,
) -> dict:
    payload: dict = {
        "name": "config",
        "command": "python main.py",
        "compute_plan_id": "plan_cpu_quick",
        "environment_version_id": environment_version_id,
    }
    if input_bindings is not None:
        payload["input_bindings"] = input_bindings
    if environment_variables is not None:
        payload["environment_variables"] = environment_variables
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations", json=payload, headers=ALICE
    )
    response.raise_for_status()
    return response.json()


async def _preflight(
    client: httpx.AsyncClient, project: dict, configuration_id: str, headers: dict
) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# A. Initiated By User 贯穿 create / API / Snapshot
# ---------------------------------------------------------------------------


async def test_run_records_initiating_user_end_to_end(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group = await _create_group(client, "Initiator Group")
    _, environment_version_id = await _create_environment(session, owner_user_group_id=group)
    await grant_test_entitlement(session, "alice")
    project = await _create_project(client, group, name="initiator project")
    configuration = await _create_configuration(client, project, environment_version_id)
    alice_id = await _get_user_id(client, ALICE)

    created = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["initiated_by_user_id"] == alice_id
    assert "created_by" not in body

    detail = await client.get(f"/api/v1/runs/{body['id']}", headers=ALICE)
    detail.raise_for_status()
    assert detail.json()["run"]["initiated_by_user_id"] == alice_id
    assert detail.json()["snapshot"]["initiated_by_user_id"] == alice_id

    # 同一 User Group 的另一个成员提交同一个运行方案：身份跟着发起人走。
    await _join_group(client, group)
    await grant_test_entitlement(session, "bob")
    bob_id = await _get_user_id(client, BOB)
    bob_run = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=BOB,
    )
    assert bob_run.status_code == 201, bob_run.text
    assert bob_run.json()["initiated_by_user_id"] == bob_id


# ---------------------------------------------------------------------------
# B. 同 Group 两成员因个人 entitlement / user secret 得到不同 preflight
# ---------------------------------------------------------------------------


async def test_member_preflight_diverges_on_entitlement_and_user_secret(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group = await _create_group(client, "Divergence Group")
    _, environment_version_id = await _create_environment(session, owner_user_group_id=group)
    project = await _create_project(client, group, name="divergence project")
    alice_id = await _get_user_id(client, ALICE)
    bob_id = await _get_user_id(client, BOB)
    await _join_group(client, group)
    configuration = await _create_configuration(
        client,
        project,
        environment_version_id,
        environment_variables={
            "USER_LEVEL": "${{ user.vars.LEVEL }}",
            "USER_TOKEN": "${{ user.secrets.TOKEN }}",
        },
    )

    # Alice 武装好自己的 user scope 和个人权益。
    response = await client.put(
        f"/api/v1/users/{alice_id}/variables",
        json={"name": "LEVEL", "value": "alice"},
        headers=ALICE,
    )
    assert response.status_code == 200
    response = await client.put(
        f"/api/v1/users/{alice_id}/secrets",
        json={"name": "TOKEN", "value": "alice-token"},
        headers=ALICE,
    )
    assert response.status_code == 204
    await grant_test_entitlement(session, "alice")

    alice_result = await _preflight(client, project, configuration["id"], ALICE)
    assert alice_result["problems"] == []
    assert alice_result["secret_references"]["USER_TOKEN"] == f"user:{alice_id}:TOKEN"

    # Bob 什么都没有：权益、user variable、user secret 各自独立成问题。
    bob_first = await _preflight(client, project, configuration["id"], BOB)
    problems = bob_first["problems"]
    assert len(problems) == 3, problems
    assert any("使用权益" in problem for problem in problems)
    assert any("USER_LEVEL" in problem for problem in problems)
    assert any("USER_TOKEN" in problem for problem in problems)

    # 只补权益：剩下的是 Bob 自己 user scope 里的引用。
    await grant_test_entitlement(session, "bob")
    bob_second = await _preflight(client, project, configuration["id"], BOB)
    assert len(bob_second["problems"]) == 2, bob_second["problems"]

    # Bob 武装自己的 user scope 后干净通过，引用指向他自己的 scope。
    response = await client.put(
        f"/api/v1/users/{bob_id}/variables", json={"name": "LEVEL", "value": "bob"}, headers=BOB
    )
    assert response.status_code == 200
    response = await client.put(
        f"/api/v1/users/{bob_id}/secrets", json={"name": "TOKEN", "value": "bob-token"}, headers=BOB
    )
    assert response.status_code == 204
    bob_third = await _preflight(client, project, configuration["id"], BOB)
    assert bob_third["problems"] == []
    assert bob_third["secret_references"]["USER_TOKEN"] == f"user:{bob_id}:TOKEN"


# ---------------------------------------------------------------------------
# C. Run Configuration 必须精确引用 Environment Version
# ---------------------------------------------------------------------------


async def test_configuration_requires_exact_environment_version(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group = await _create_group(client, "Exact Env Group")
    # Group 有自己的 Environment，但保存运行方案时不会因此获得默认值。
    await _create_environment(session, owner_user_group_id=group)
    project = await _create_project(client, group, name="exact env project")

    missing = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "missing-env",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
        },
        headers=ALICE,
    )
    assert missing.status_code == 422, missing.text
    assert "environment_version_id" in missing.text

    blank = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "blank-env",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": "",
        },
        headers=ALICE,
    )
    assert blank.status_code == 422, blank.text
    assert "Environment Version" in blank.text


# ---------------------------------------------------------------------------
# D. USE Grant 打开跨 Owner 的精确 Environment 引用
# ---------------------------------------------------------------------------


async def test_cross_owner_environment_grant_enables_exact_configuration_use(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group_a = await _create_group(client, "Env Use Group A")
    group_b = await _create_group(client, "Env Use Group B")
    environment_b_id, environment_b_version_id = await _create_environment(
        session, owner_user_group_id=group_b
    )
    project = await _create_project(client, group_a, name="env grant project")
    alice_id = await _get_user_id(client, ALICE)
    await grant_test_entitlement(session, "alice")

    # 没有 Grant：引用 B 的 Environment Version → 404。
    blocked = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "cross-owner-env",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_b_version_id,
        },
        headers=ALICE,
    )
    assert blocked.status_code == 404, blocked.text

    grant = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "environment",
            "target_id": environment_b_id,
            "grantee": {"kind": "user", "id": alice_id},
        },
        headers=ALICE,
    )
    assert grant.status_code == 201, grant.text

    allowed = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "cross-owner-env-granted",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_b_version_id,
        },
        headers=ALICE,
    )
    assert allowed.status_code == 201, allowed.text
    result = await _preflight(client, project, allowed.json()["id"], ALICE)
    assert result["problems"] == []


# ---------------------------------------------------------------------------
# F. Artifact 直接输入仅限同一 Project Owner（GR-405）
# ---------------------------------------------------------------------------


async def test_artifact_input_boundary_follows_project_owner(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group_a = await _create_group(client, "Artifact Group A")
    group_b = await _create_group(client, "Artifact Group B")
    _, environment_a = await _create_environment(session, owner_user_group_id=group_a)
    _, environment_b = await _create_environment(session, owner_user_group_id=group_b)
    await grant_test_entitlement(session, "alice")
    project_a = await _create_project(client, group_a, name="artifact source")
    project_b = await _create_project(client, group_b, name="artifact consumer")
    configuration = await _create_configuration(client, project_a, environment_a)

    run = await client.post(
        f"/api/v1/projects/{project_a['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert run.status_code == 201, run.text
    detail = await wait_for_run(client, run.json()["id"], headers=ALICE)
    assert detail["run"]["status"] == "succeeded"

    artifact_id = ids.new_id(ids.ARTIFACT)
    session.add(
        ArtifactRow(
            id=artifact_id,
            run_id=run.json()["id"],
            project_id=project_a["id"],
            workspace_id=run.json()["workspace_id"],
            name="输出",
            source_path="outputs",
            size=4,
            file_count=1,
            content_hash="hash_artifact_boundary",
            status="available",
            description="",
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()

    binding = {
        "source_type": "artifact",
        "source_id": artifact_id,
        "access_path": "/inputs/art",
    }
    # 跨 Owner 直接引用 Artifact → 404；要先发布成 Shared Resource。
    cross = await client.post(
        f"/api/v1/projects/{project_b['id']}/run-configurations",
        json={
            "name": "cross-owner-artifact",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_b,
            "input_bindings": [binding],
        },
        headers=ALICE,
    )
    assert cross.status_code == 404, cross.text

    # 同 Owner 引用保存成功，preflight 干净通过。
    same = await client.post(
        f"/api/v1/projects/{project_a['id']}/run-configurations",
        json={
            "name": "same-owner-artifact",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_a,
            "input_bindings": [binding],
        },
        headers=ALICE,
    )
    assert same.status_code == 201, same.text
    result = await _preflight(client, project_a, same.json()["id"], ALICE)
    assert result["problems"] == []


# ---------------------------------------------------------------------------
# G. 幂等键按发起 User 作用域
# ---------------------------------------------------------------------------


async def test_idempotency_key_is_scoped_to_initiating_user(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group = await _create_group(client, "Idempotency Group")
    _, environment_version_id = await _create_environment(session, owner_user_group_id=group)
    await grant_test_entitlement(session, "alice")
    await _join_group(client, group)
    await grant_test_entitlement(session, "bob")
    project = await _create_project(client, group, name="idempotency project")
    configuration = await _create_configuration(client, project, environment_version_id)
    payload = {"run_configuration_id": configuration["id"]}
    url = f"/api/v1/projects/{project['id']}/runs"
    key = {"Idempotency-Key": "shared-key"}

    first = await client.post(url, json=payload, headers={**ALICE, **key})
    assert first.status_code == 201, first.text
    replay = await client.post(url, json=payload, headers={**ALICE, **key})
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]

    # 同一个键对另一个发起 User 是全新的提交：作用域是 (user, key)。
    bob_first = await client.post(url, json=payload, headers={**BOB, **key})
    assert bob_first.status_code == 201, bob_first.text
    assert bob_first.json()["id"] != first.json()["id"]
    bob_replay = await client.post(url, json=payload, headers={**BOB, **key})
    assert bob_replay.status_code == 200, bob_replay.text
    assert bob_replay.json()["id"] == bob_first.json()["id"]


# ---------------------------------------------------------------------------
# H. Rerun：新 Run + 新 Snapshot，发起人是当前重跑的 User，不漂移
# ---------------------------------------------------------------------------


async def test_rerun_creates_new_run_for_current_user_without_drift(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    group = await _create_group(client, "Rerun Group")
    _, environment_v1 = await _create_environment(session, owner_user_group_id=group)
    _, environment_v2 = await _create_environment(session, owner_user_group_id=group)
    await grant_test_entitlement(session, "alice")
    await _join_group(client, group)
    await grant_test_entitlement(session, "bob")
    project = await _create_project(client, group, name="rerun project")
    configuration = await _create_configuration(client, project, environment_v1)

    original = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert original.status_code == 201, original.text
    run_id = original.json()["id"]
    detail = await wait_for_run(client, run_id, headers=ALICE)
    assert detail["run"]["status"] == "succeeded"
    original_snapshot = detail["snapshot"]

    # 快照固化之后 Group 默认环境漂移到 v2。
    response = await client.patch(
        f"/api/v1/workspaces/{group}",
        json={"default_environment_version_id": environment_v2},
        headers=ALICE,
    )
    assert response.status_code == 200, response.text

    bob_id = await _get_user_id(client, BOB)
    rerun = await client.post(f"/api/v1/runs/{run_id}/rerun", headers=BOB)
    assert rerun.status_code == 201, rerun.text
    body = rerun.json()
    assert body["id"] != run_id
    assert body["source_run_id"] == run_id
    assert body["initiated_by_user_id"] == bob_id

    rerun_detail = await client.get(f"/api/v1/runs/{body['id']}", headers=BOB)
    rerun_detail.raise_for_status()
    snapshot = rerun_detail.json()["snapshot"]
    assert snapshot["id"] != original_snapshot["id"]
    assert snapshot["initiated_by_user_id"] == bob_id
    # 不漂移：仍引用来源快照固定的 v1，而不是 Group 的新默认 v2。
    assert snapshot["environment_version_id"] == environment_v1

    rerun_final = await wait_for_run(client, body["id"], headers=BOB)
    assert rerun_final["run"]["status"] == "succeeded"
