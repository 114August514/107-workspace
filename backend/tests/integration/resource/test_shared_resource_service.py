"""SharedResourceService 的服务层行为（经 HTTP 走完整栈）。

走 HTTP 而不是直接拿 services fixture，是因为 ``ensure_user`` 的写入需要
``GET /api/v1/me`` 这条事务边界来落库——直接用 ``services`` 在测试函数里
调 ``ensure_user`` 后，下一个用例内的服务调用看不到这条用户记录。

通过 HTTP 时每次请求都有完整的 commit/rollback 边界，避免这种跨请求可见性
的坑；同时这也更接近真实使用方式，能顺带验证路由层和 schema。

错误响应约定（见 ``api/errors.py``）：
- ``ValidationFailed`` → ``problems=[]``，原因写进 ``message``
- ``PreflightRejected`` → ``problems=[...]``，原因写进 ``problems``
"""

from __future__ import annotations

import httpx

from tests.helpers import ensure_user_group
from workspace107.api.deps import AppContext, build_services
from workspace107.application.shared_resource_service import MAX_RESOURCE_NAME_LEN

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _user_group(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    return await ensure_user_group(client, headers=headers)


async def _create_resource(
    client: httpx.AsyncClient, name: str = "测试资源", headers: dict[str, str] | None = None
) -> dict:
    workspace_id = await _user_group(client, headers or ALICE)
    return (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": name,
                "owner": {"kind": "user_group", "id": workspace_id},
            },
            headers=headers or ALICE,
        )
    ).json()


async def _publish_version(
    client: httpx.AsyncClient,
    context: AppContext,
    resource_id: str,
    *,
    files: list[tuple[str, bytes]],
    description: str = "v1",
    prefix: str = "",
    headers: dict[str, str] | None = None,
) -> dict:
    """Upload, run the real publication processor, and return version detail."""
    attempt = (
        await client.post(
            f"/api/v1/shared-resources/{resource_id}/versions",
            params={"prefix": prefix},
            data={"description": description},
            files=[
                ("files", (path, content, "application/octet-stream")) for path, content in files
            ],
            headers=headers or ALICE,
        )
    ).json()
    claim_session = context.session_factory()
    try:
        services = build_services(context, claim_session)
        claimed = await services.shared_resource_publications.claim_next()
        await claim_session.commit()
    finally:
        await claim_session.close()
    assert claimed is not None and claimed.id == attempt["id"]
    process_session = context.session_factory()
    try:
        services = build_services(context, process_session)
        result = await services.shared_resource_publications.process(claimed.id)
        await process_session.commit()
    finally:
        await process_session.close()
    assert result.version_id is not None
    return (
        await client.get(
            f"/api/v1/shared-resource-versions/{result.version_id}",
            headers=headers or ALICE,
        )
    ).json()


# -- create ------------------------------------------------------------------


async def test_create_rejects_empty_name(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "   ",
            "owner": {"kind": "user_group", "id": workspace_id},
        },
        headers=ALICE,
    )
    assert response.status_code == 422
    body = response.json()
    # ValidationFailed 把原因写进 message，problems 是空
    assert "名称" in body["message"]


async def test_create_rejects_oversized_name(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "x" * (MAX_RESOURCE_NAME_LEN + 1),
            "owner": {"kind": "user_group", "id": workspace_id},
        },
        headers=ALICE,
    )
    # 超长在 Pydantic max_length 校验阶段就被拦下，错误体走 RequestValidationError
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    # 字段级原因在 problems，描述里会提到 name 字段
    assert any("name" in p for p in body["problems"])


async def test_create_assigns_owner_group(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "数据集 A",
            "description": "训练用",
            "owner": {"kind": "user_group", "id": workspace_id},
        },
        headers=ALICE,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "数据集 A"
    assert body["description"] == "训练用"
    assert body["owner"] == {
        "kind": "user_group",
        "id": workspace_id,
        "display_name": "alice test group",
    }


async def test_create_requires_manage_capability(client: httpx.AsyncClient) -> None:
    """非成员不能为另一个 User Group 创建资源，且按不存在处理。"""
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "越权创建",
            "owner": {"kind": "user_group", "id": workspace_id},
        },
        headers=BOB,
    )
    assert response.status_code == 404


# -- update ------------------------------------------------------------------


async def test_update_changes_name_and_description(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": "原名",
                "owner": {"kind": "user_group", "id": workspace_id},
            },
            headers=ALICE,
        )
    ).json()
    response = await client.patch(
        f"/api/v1/shared-resources/{resource['id']}",
        json={"name": "新名", "description": "新说明"},
        headers=ALICE,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "新名"
    assert body["description"] == "新说明"


async def test_update_rejects_empty_name(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": "保留",
                "owner": {"kind": "user_group", "id": workspace_id},
            },
            headers=ALICE,
        )
    ).json()
    response = await client.patch(
        f"/api/v1/shared-resources/{resource['id']}",
        json={"name": "   "},
        headers=ALICE,
    )
    assert response.status_code == 422
    assert "名称" in response.json()["message"]


# -- publication ingress and successful processing ---------------------------


async def test_publication_ingress_rejects_duplicate_paths(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "重复路径")
    response = await client.post(
        f"/api/v1/shared-resources/{resource['id']}/versions",
        params={"prefix": ""},
        data={"description": "v1"},
        files=[
            ("files", ("data.txt", b"hello", "text/plain")),
            ("files", ("/data.txt", b"world", "text/plain")),
        ],
        headers=ALICE,
    )
    assert response.status_code == 422
    assert "重复路径" in response.json()["message"]


async def test_publication_ingress_rejects_path_that_escapes_root(
    client: httpx.AsyncClient,
) -> None:
    resource = await _create_resource(client, "越界路径")
    response = await client.post(
        f"/api/v1/shared-resources/{resource['id']}/versions",
        params={"prefix": ""},
        data={"description": "v1"},
        files=[("files", ("../outside.txt", b"x", "text/plain"))],
        headers=ALICE,
    )
    assert response.status_code == 422
    assert "越出" in response.json()["message"]


async def test_publication_ingress_rejects_empty_uploads(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "空版本")
    # No files field: transport validation rejects the raw request before an attempt is accepted.
    response = await client.post(
        f"/api/v1/shared-resources/{resource['id']}/versions",
        params={"prefix": ""},
        data={"description": "v1"},
        headers=ALICE,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    # FastAPI 把 missing files 报成 problems
    assert any("files" in p for p in body["problems"])


async def test_publish_version_assigns_increasing_sequence(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "多版本")
    v1 = await _publish_version(
        client, context, resource["id"], files=[("a.txt", b"first")], description="v1"
    )
    v2 = await _publish_version(
        client, context, resource["id"], files=[("a.txt", b"second")], description="v2"
    )
    assert v1["sequence"] == 1
    assert v2["sequence"] == 2
    assert v1["label"] == "v1"
    assert v2["label"] == "v2"


async def test_publish_version_records_file_size_and_hash(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "带尺寸")
    version = await _publish_version(
        client,
        context,
        resource["id"],
        files=[("data.txt", b"hello world")],
        prefix="dir",
    )
    file_entry = version["files"][0]
    assert file_entry["path"] == "dir/data.txt"
    assert file_entry["size"] == len(b"hello world")
    assert len(file_entry["content_hash"]) == 64
    assert version["file_count"] == 1
    assert version["total_size"] == file_entry["size"]


async def test_publish_version_supports_multiple_files(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "多文件")
    version = await _publish_version(
        client,
        context,
        resource["id"],
        files=[("a.txt", b"first"), ("nested/b.txt", b"second")],
    )
    assert version["file_count"] == 2
    paths = sorted(f["path"] for f in version["files"])
    assert paths == ["a.txt", "nested/b.txt"]


# -- read_version_file -------------------------------------------------------


async def test_read_version_file_returns_blob_content(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "可读版本")
    version = await _publish_version(
        client, context, resource["id"], files=[("notes.txt", b"hello")]
    )
    response = await client.get(
        f"/api/v1/shared-resource-versions/{version['id']}/files/content",
        params={"path": "notes.txt"},
        headers=ALICE,
    )
    assert response.status_code == 200
    assert response.text == "hello"


async def test_read_version_file_rejects_missing_path(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "缺文件")
    version = await _publish_version(client, context, resource["id"], files=[("a.txt", b"x")])
    response = await client.get(
        f"/api/v1/shared-resource-versions/{version['id']}/files/content",
        params={"path": "missing.txt"},
        headers=ALICE,
    )
    assert response.status_code == 404


# -- actor-scoped discovery -------------------------------------------------


async def test_discovery_excludes_resources_owned_by_other_user_group(
    client: httpx.AsyncClient,
) -> None:
    alice_ws = await _user_group(client, ALICE)
    bob_ws = await _user_group(client, BOB)
    await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "Alice 的",
            "owner": {"kind": "user_group", "id": alice_ws},
        },
        headers=ALICE,
    )
    await client.post(
        "/api/v1/shared-resources",
        json={
            "name": "Bob 的",
            "owner": {"kind": "user_group", "id": bob_ws},
        },
        headers=BOB,
    )

    alice_resources = (await client.get("/api/v1/shared-resources", headers=ALICE)).json()
    assert [(r["name"], r["owner"]["id"]) for r in alice_resources] == [("Alice 的", alice_ws)]


async def test_get_version_blocks_cross_workspace_access(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client, "私有数据")
    version = await _publish_version(client, context, resource["id"], files=[("a.txt", b"x")])

    # Bob 看不到 Alice 的 Personal Workspace 资源
    not_found = await client.get(f"/api/v1/shared-resource-versions/{version['id']}", headers=BOB)
    assert not_found.status_code == 404


# -- 活动记录 ----------------------------------------------------------------


async def test_create_records_activity(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": "会被记录的",
                "owner": {"kind": "user_group", "id": workspace_id},
            },
            headers=ALICE,
        )
    ).json()

    activities = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/activities", headers=ALICE)
    ).json()["items"]
    matched = [
        a
        for a in activities
        if a["action"] == "shared_resource_created" and a["target_id"] == resource["id"]
    ]
    assert matched, "create 后活动流里没看到 SHARED_RESOURCE_CREATED"
    assert matched[0]["target_name"] == "会被记录的"


async def test_publish_version_records_activity(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": "会发布版本",
                "owner": {"kind": "user_group", "id": workspace_id},
            },
            headers=ALICE,
        )
    ).json()
    version = await _publish_version(client, context, resource["id"], files=[("a.txt", b"x")])

    activities = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/activities", headers=ALICE)
    ).json()["items"]
    matched = [
        a
        for a in activities
        if a["action"] == "shared_resource_version_published" and a["target_id"] == version["id"]
    ]
    assert matched, "publish_version 后活动流里没看到 SHARED_RESOURCE_VERSION_PUBLISHED"


# -- storage 落盘 ------------------------------------------------------------


async def test_publish_version_deduplicates_identical_content(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    """同一份内容多次上传按内容寻址去重，版本里的 content_hash 相同。"""
    resource = await _create_resource(client, "去重")
    v1 = await _publish_version(client, context, resource["id"], files=[("a.txt", b"same")])
    v2 = await _publish_version(client, context, resource["id"], files=[("b.txt", b"same")])
    assert v1["files"][0]["content_hash"] == v2["files"][0]["content_hash"]
