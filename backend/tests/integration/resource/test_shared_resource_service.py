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
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": name},
            headers=headers or ALICE,
        )
    ).json()


async def _publish_version(
    client: httpx.AsyncClient,
    resource_id: str,
    *,
    files: list[tuple[str, bytes]],
    description: str = "v1",
    prefix: str = "",
    headers: dict[str, str] | None = None,
) -> dict:
    """发布版本并返回**详情**（含 files 列表）。

    ``POST /shared-resources/{id}/versions`` 返回 ``SharedResourceVersionOut``，
    其中只有 file_count / total_size，没有 files；要拿到完整文件清单需要再请求
    一次 ``GET /shared-resource-versions/{id}``。
    """
    version = (
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
    return (
        await client.get(
            f"/api/v1/shared-resource-versions/{version['id']}",
            headers=headers or ALICE,
        )
    ).json()


# -- create ------------------------------------------------------------------


async def test_create_rejects_empty_name(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/shared-resources",
        json={"name": "   "},
        headers=ALICE,
    )
    assert response.status_code == 422
    body = response.json()
    # ValidationFailed 把原因写进 message，problems 是空
    assert "名称" in body["message"]


async def test_create_rejects_oversized_name(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/shared-resources",
        json={"name": "x" * (MAX_RESOURCE_NAME_LEN + 1)},
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
        f"/api/v1/workspaces/{workspace_id}/shared-resources",
        json={"name": "数据集 A", "description": "训练用"},
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
    """非成员在别人的 Workspace 上 create 会被挡掉，且按不存在处理。"""
    workspace_id = await _user_group(client, ALICE)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/shared-resources",
        json={"name": "越权创建"},
        headers=BOB,
    )
    # Bob 看不到 Alice 的 Personal Workspace，按不存在处理
    assert response.status_code == 404


# -- update ------------------------------------------------------------------


async def test_update_changes_name_and_description(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": "原名"},
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
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": "保留"},
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


# -- publish_version ---------------------------------------------------------


async def test_publish_version_rejects_duplicate_paths(client: httpx.AsyncClient) -> None:
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


async def test_publish_version_rejects_path_that_escapes_root(
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


async def test_publish_version_rejects_empty_uploads(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "空版本")
    # 不带 files 字段：FastAPI 在 RequestValidationError 阶段就拦下
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
    client: httpx.AsyncClient,
) -> None:
    resource = await _create_resource(client, "多版本")
    v1 = (
        await client.post(
            f"/api/v1/shared-resources/{resource['id']}/versions",
            params={"prefix": ""},
            data={"description": "v1"},
            files=[("files", ("a.txt", b"first", "text/plain"))],
            headers=ALICE,
        )
    ).json()
    v2 = (
        await client.post(
            f"/api/v1/shared-resources/{resource['id']}/versions",
            params={"prefix": ""},
            data={"description": "v2"},
            files=[("files", ("a.txt", b"second", "text/plain"))],
            headers=ALICE,
        )
    ).json()
    assert v1["sequence"] == 1
    assert v2["sequence"] == 2
    assert v1["label"] == "v1"
    assert v2["label"] == "v2"


async def test_publish_version_records_file_size_and_hash(
    client: httpx.AsyncClient,
) -> None:
    resource = await _create_resource(client, "带尺寸")
    version = await _publish_version(
        client,
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


async def test_publish_version_supports_multiple_files(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "多文件")
    version = await _publish_version(
        client,
        resource["id"],
        files=[("a.txt", b"first"), ("nested/b.txt", b"second")],
    )
    assert version["file_count"] == 2
    paths = sorted(f["path"] for f in version["files"])
    assert paths == ["a.txt", "nested/b.txt"]


# -- read_version_file -------------------------------------------------------


async def test_read_version_file_returns_blob_content(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "可读版本")
    version = await _publish_version(client, resource["id"], files=[("notes.txt", b"hello")])
    response = await client.get(
        f"/api/v1/shared-resource-versions/{version['id']}/files/content",
        params={"path": "notes.txt"},
        headers=ALICE,
    )
    assert response.status_code == 200
    assert response.text == "hello"


async def test_read_version_file_rejects_missing_path(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client, "缺文件")
    version = await _publish_version(client, resource["id"], files=[("a.txt", b"x")])
    response = await client.get(
        f"/api/v1/shared-resource-versions/{version['id']}/files/content",
        params={"path": "missing.txt"},
        headers=ALICE,
    )
    assert response.status_code == 404


# -- 跨 Workspace 可见性 -----------------------------------------------------


async def test_list_for_workspace_excludes_other_workspace_resources(
    client: httpx.AsyncClient,
) -> None:
    alice_ws = await _user_group(client, ALICE)
    bob_ws = await _user_group(client, BOB)
    await client.post(
        f"/api/v1/workspaces/{alice_ws}/shared-resources",
        json={"name": "Alice 的"},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/workspaces/{bob_ws}/shared-resources",
        json={"name": "Bob 的"},
        headers=BOB,
    )

    alice_resources = (
        await client.get(f"/api/v1/workspaces/{alice_ws}/shared-resources", headers=ALICE)
    ).json()
    assert [r["name"] for r in alice_resources] == ["Alice 的"]


async def test_get_version_blocks_cross_workspace_access(
    client: httpx.AsyncClient,
) -> None:
    resource = await _create_resource(client, "私有数据")
    version = await _publish_version(client, resource["id"], files=[("a.txt", b"x")])

    # Bob 看不到 Alice 的 Personal Workspace 资源
    not_found = await client.get(f"/api/v1/shared-resource-versions/{version['id']}", headers=BOB)
    assert not_found.status_code == 404


# -- 活动记录 ----------------------------------------------------------------


async def test_create_records_activity(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": "会被记录的"},
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


async def test_publish_version_records_activity(client: httpx.AsyncClient) -> None:
    workspace_id = await _user_group(client, ALICE)
    resource = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": "会发布版本"},
            headers=ALICE,
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/shared-resources/{resource['id']}/versions",
            params={"prefix": ""},
            data={"description": "v1"},
            files=[("files", ("a.txt", b"x", "text/plain"))],
            headers=ALICE,
        )
    ).json()

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
    client: httpx.AsyncClient,
) -> None:
    """同一份内容多次上传按内容寻址去重，版本里的 content_hash 相同。"""
    resource = await _create_resource(client, "去重")
    v1 = await _publish_version(client, resource["id"], files=[("a.txt", b"same")])
    v2 = await _publish_version(client, resource["id"], files=[("b.txt", b"same")])
    assert v1["files"][0]["content_hash"] == v2["files"][0]["content_hash"]
