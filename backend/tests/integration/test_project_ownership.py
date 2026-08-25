"""Issue #36：Project Ownership / Visibility 的访问边界。"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import ensure_user_group
from workspace107.domain import ids
from workspace107.infrastructure.db.tables import EnvironmentRow, EnvironmentVersionRow

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _group_environment_version(session: AsyncSession, user_group_id: str) -> str:
    """直插一个 User Group 拥有的 Environment Version，返回 version id。"""
    environment_id = ids.new_id(ids.ENVIRONMENT)
    version_id = ids.new_id(ids.ENVIRONMENT_VERSION)
    session.add(
        EnvironmentRow(
            id=environment_id,
            name=f"{environment_id} environment",
            description="",
            owner_user_group_id=user_group_id,
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
    return version_id


@pytest.mark.asyncio
async def test_user_owned_project_is_not_visible_to_other_users(client) -> None:
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    created = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice["id"]}, "name": "Alice Project"},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["owner"]["kind"] == "user"
    assert project["owner"]["id"] == alice["id"]
    # Owner 摘要是解析出的真实显示名，不是裸 id。
    assert project["owner"]["display_name"] == alice["display_name"] == "alice"
    assert project["visibility"] == "owner_scope"
    assert (await client.get(f"/api/v1/projects/{project['id']}", headers=BOB)).status_code == 404


@pytest.mark.asyncio
async def test_canonical_create_requires_owner_to_match_compatibility_anchor(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    created = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user_group", "id": group_id}, "name": "Group Project"},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    assert created.json()["owner"]["kind"] == "user_group"
    assert created.json()["owner"]["id"] == group_id

    # 负向：拿自己的 personal anchor 冒充 UserGroup Owner。
    # personal anchor 的 canonical owner 是 User(Alice)，与请求的 owner 不一致，
    # 必须干净地 404，而不是把 owner_user_group_id 落到 DB FK 边界。
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    personal = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice["id"]}, "name": "Alice Personal"},
        headers=ALICE,
    )
    assert personal.status_code == 201, personal.text
    personal_anchor = (await client.get("/api/v1/me", headers=ALICE)).json()[
        "personal_resource_context_id"
    ]
    assert personal_anchor is not None
    hijack = await client.post(
        "/api/v1/projects",
        json={
            "owner": {"kind": "user_group", "id": personal_anchor},
            "name": "Hijack Project",
        },
        headers=ALICE,
    )
    assert hijack.status_code == 404
    listing = await client.get("/api/v1/projects", headers=ALICE)
    assert listing.status_code == 200
    assert all(item["name"] != "Hijack Project" for item in listing.json()["items"])


@pytest.mark.asyncio
async def test_public_project_exposes_metadata_and_versions_but_not_working_state(
    client,
) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    created = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Public Project"},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["owner"]["kind"] == "user_group"
    assert project["owner"]["id"] == group_id
    updated = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"visibility": "public"},
        headers=ALICE,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["visibility"] == "public"
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "README.md", "content": "public"},
        headers=ALICE,
    )
    version = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "public version"},
        headers=ALICE,
    )
    assert version.status_code == 201, version.text

    metadata = await client.get(f"/api/v1/projects/{project['id']}", headers=BOB)
    assert metadata.status_code == 200
    assert metadata.json()["visibility"] == "public"
    # 公开读者看不到 Owner 的 mutable environment selection 和默认运行方案。
    assert metadata.json()["environment_version_id"] is None
    assert metadata.json()["default_run_configuration_id"] is None
    versions = await client.get(f"/api/v1/projects/{project['id']}/versions", headers=BOB)
    assert versions.status_code == 200
    assert len(versions.json()["items"]) == 1
    # 受保护子对象对公开读者 404：工作区、Run、活动、运行方案。
    assert (
        await client.get(f"/api/v1/projects/{project['id']}/files", headers=BOB)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/projects/{project['id']}/runs", headers=BOB)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/projects/{project['id']}/activities", headers=BOB)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/projects/{project['id']}/run-configurations", headers=BOB)
    ).status_code == 404
    # Project 本体可见但不可改：公开读者没有更新能力，是 403 而不是 404。
    patched = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "hijack"},
        headers=BOB,
    )
    assert patched.status_code == 403


@pytest.mark.asyncio
async def test_discovery_lists_public_projects_but_home_feed_does_not(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    project = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Discoverable"},
        headers=ALICE,
    )
    project_id = project.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"visibility": "public"},
            headers=ALICE,
        )
    ).status_code == 200

    # 发现列表包含他人的 PUBLIC Project。
    listing = await client.get("/api/v1/projects", headers=BOB)
    assert listing.status_code == 200
    assert any(item["id"] == project_id for item in listing.json()["items"])

    # 首页 feed 只包含自己 / 所在 User Group 拥有的 Project，不含他人 PUBLIC。
    home = await client.get("/api/v1/me", headers=BOB)
    assert home.status_code == 200
    assert all(item["id"] != project_id for item in home.json()["recent_projects"])


@pytest.mark.asyncio
async def test_public_version_can_be_forked_to_requesting_user_owner(client, session) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    env_version_id = await _group_environment_version(session, group_id)
    source = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "Fork Source"},
        headers=ALICE,
    )
    source_id = source.json()["id"]
    await client.patch(
        f"/api/v1/projects/{source_id}",
        json={"visibility": "public"},
        headers=ALICE,
    )
    await client.put(
        f"/api/v1/projects/{source_id}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=ALICE,
    )
    configuration = await client.post(
        f"/api/v1/projects/{source_id}/run-configurations",
        json={
            "name": "private config",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
        },
        headers=ALICE,
    )
    assert configuration.status_code == 201, configuration.text
    version = await client.post(
        f"/api/v1/projects/{source_id}/versions",
        json={"message": "forkable"},
        headers=ALICE,
    )
    bob = (await client.get("/api/v1/me", headers=BOB)).json()["user"]
    forked = await client.post(
        f"/api/v1/versions/{version.json()['id']}/fork",
        json={"target_owner": {"kind": "user", "id": bob["id"]}, "name": "Bob Fork"},
        headers=BOB,
    )
    assert forked.status_code == 201, forked.text
    assert forked.json()["owner"]["id"] == bob["id"]
    assert forked.json()["owner"]["display_name"] == "bob"
    # PUBLIC 读者派生：不携带源 Project 的 mutable environment selection。
    assert forked.json()["environment_version_id"] is None
    forked_id = forked.json()["id"]

    # 文件与不可变版本被复制；Run Configuration 属于源 Owner，不复制。
    files = await client.get(f"/api/v1/projects/{forked_id}/files", headers=BOB)
    assert files.status_code == 200
    assert [f["path"] for f in files.json()] == ["main.py"]
    copied = await client.get(f"/api/v1/projects/{forked_id}/run-configurations", headers=BOB)
    assert copied.status_code == 200
    assert copied.json() == []

    # 负向：不能把 Project Fork 到别人的 Owner 名下。
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    hijack = await client.post(
        f"/api/v1/versions/{version.json()['id']}/fork",
        json={"target_owner": {"kind": "user", "id": alice["id"]}, "name": "Stolen Fork"},
        headers=BOB,
    )
    assert hijack.status_code == 404
