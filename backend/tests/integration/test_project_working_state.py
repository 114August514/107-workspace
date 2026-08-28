"""Issue #47：Project Working State 文件管理 Core。

覆盖复制、建目录、压缩包展开、下载、内容级变更详情和放弃指定变更，
包括验收条件点名的安全场景（路径穿越、zip 炸弹、只读角色越权）。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.helpers import ensure_user_group
from workspace107.config import Settings

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """收紧上限，让超限 / zip 炸弹场景不用生成大文件就能触发。"""
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        storage_root=tmp_path / "storage",
        scheduler="mock",
        auth_mode="dev",
        run_sync_interval_seconds=0,
        # zip 自身有数百字节的开销，压缩包预算要给到开销之上、
        # 又小到单测能触发超限分支。
        max_file_bytes=1024,
        max_archive_total_bytes=2048,
        max_archive_entries=3,
    )


async def create_owned_project(client: httpx.AsyncClient, name: str) -> str:
    alice = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    created = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice["id"]}, "name": name},
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def write_file(client: httpx.AsyncClient, project_id: str, path: str, content: str) -> None:
    response = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": path, "content": content},
        headers=ALICE,
    )
    assert response.status_code == 200


def make_zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def make_zip_entries(members: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            archive.writestr(name, content)
    return buffer.getvalue()


def with_encrypted_flag(data: bytes) -> bytes:
    """把中央目录里第一个条目的加密标志位置 1。"""
    signature = b"PK\x01\x02"
    index = data.index(signature)
    mutable = bytearray(data)
    mutable[index + 8] |= 0x1
    return bytes(mutable)


def with_corrupt_member(data: bytes, member_name: str) -> bytes:
    """破坏指定 stored 条目内容，同时保留可读取的中央目录。"""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo(member_name)
        assert info.compress_type == zipfile.ZIP_STORED
        header = data[info.header_offset : info.header_offset + 30]
        filename_length = int.from_bytes(header[26:28], "little")
        extra_length = int.from_bytes(header[28:30], "little")
        content_offset = info.header_offset + 30 + filename_length + extra_length

    mutable = bytearray(data)
    mutable[content_offset] ^= 0xFF
    return bytes(mutable)


# -- 复制 ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_file_and_directory(client) -> None:
    project_id = await create_owned_project(client, "复制")
    await write_file(client, project_id, "a.txt", "hello")
    await write_file(client, project_id, "src/main.py", "print(1)")
    await write_file(client, project_id, "src/util/u.py", "x = 1")

    copied_file = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "a.txt", "destination": "backup/a.txt"},
        headers=ALICE,
    )
    assert copied_file.status_code == 200, copied_file.text
    assert [f["path"] for f in copied_file.json()] == ["backup/a.txt"]

    copied_dir = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "src", "destination": "src-copy"},
        headers=ALICE,
    )
    assert copied_dir.status_code == 200
    assert sorted(f["path"] for f in copied_dir.json()) == [
        "src-copy/main.py",
        "src-copy/util/u.py",
    ]

    # 原件还在，且副本与原件内容一致。
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    paths = {f["path"] for f in listing}
    assert {"a.txt", "backup/a.txt", "src/main.py"} <= paths

    original = (
        await client.get(
            f"/api/v1/projects/{project_id}/files/content",
            params={"path": "src/main.py"},
            headers=ALICE,
        )
    ).json()
    duplicate = (
        await client.get(
            f"/api/v1/projects/{project_id}/files/content",
            params={"path": "src-copy/main.py"},
            headers=ALICE,
        )
    ).json()
    assert duplicate["content"] == original["content"] == "print(1)"


@pytest.mark.asyncio
async def test_copy_rejects_same_path_own_subtree_and_missing_source(client) -> None:
    project_id = await create_owned_project(client, "复制负向")
    await write_file(client, project_id, "a.txt", "hi")
    await write_file(client, project_id, "src/main.py", "print(1)")

    same = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "a.txt", "destination": "a.txt"},
        headers=ALICE,
    )
    assert same.status_code == 422

    into_self = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "src", "destination": "src/inner"},
        headers=ALICE,
    )
    assert into_self.status_code == 422

    missing = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "nope.txt", "destination": "elsewhere.txt"},
        headers=ALICE,
    )
    assert missing.status_code == 404


# -- 目录 ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_created_empty_directory_supports_directory_path_operations(client) -> None:
    project_id = await create_owned_project(client, "目录")

    created = await client.post(
        f"/api/v1/projects/{project_id}/files/mkdir",
        json={"path": "data/raw"},
        headers=ALICE,
    )
    assert created.status_code == 200, created.text

    moved = await client.post(
        f"/api/v1/projects/{project_id}/files/move",
        json={"source": "data/raw", "destination": "data/processed"},
        headers=ALICE,
    )
    assert moved.status_code == 200, moved.text

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    moved_paths = {file["path"] for file in listing}
    assert moved_paths
    assert all(path.startswith("data/processed/") for path in moved_paths)
    assert not any(path.startswith("data/raw/") for path in moved_paths)

    deleted = await client.delete(
        f"/api/v1/projects/{project_id}/files",
        params={"path": "data/processed"},
        headers=ALICE,
    )
    assert deleted.status_code == 204, deleted.text

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_create_directory_conflicts_with_existing_path_without_mutation(client) -> None:
    project_id = await create_owned_project(client, "目录冲突")
    await write_file(client, project_id, "a.txt", "x")
    await write_file(client, project_id, "existing/child.txt", "y")

    created = await client.post(
        f"/api/v1/projects/{project_id}/files/mkdir",
        json={"path": "empty"},
        headers=ALICE,
    )
    assert created.status_code == 200, created.text

    before = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    for path in ("a.txt", "existing", "empty"):
        conflict = await client.post(
            f"/api/v1/projects/{project_id}/files/mkdir",
            json={"path": path},
            headers=ALICE,
        )
        assert conflict.status_code == 409

    after = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["write", "upload"])
async def test_reserved_gitkeep_basename_is_rejected_without_hidden_file(
    client, operation: str
) -> None:
    project_id = await create_owned_project(client, f"保留占位文件 {operation}")

    if operation == "write":
        response = await client.put(
            f"/api/v1/projects/{project_id}/files",
            json={"path": "notes/.gitkeep", "content": "user content"},
            headers=ALICE,
        )
    else:
        response = await client.post(
            f"/api/v1/projects/{project_id}/files/upload",
            files={"files": (".gitkeep", b"user content", "application/octet-stream")},
            params={"prefix": "notes"},
            headers=ALICE,
        )

    assert response.status_code == 422
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_file_directory_namespace_is_preserved_before_mutation(client) -> None:
    project_id = await create_owned_project(client, "路径命名空间")
    await write_file(client, project_id, "blocked", "file")
    await write_file(client, project_id, "src/main.py", "print(1)")

    child_of_file = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "blocked/child.txt", "content": "no"},
        headers=ALICE,
    )
    assert child_of_file.status_code == 409

    file_over_directory = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "src", "content": "no"},
        headers=ALICE,
    )
    assert file_over_directory.status_code == 409

    nested_directory = await client.post(
        f"/api/v1/projects/{project_id}/files/mkdir",
        json={"path": "blocked/nested"},
        headers=ALICE,
    )
    assert nested_directory.status_code == 409

    for operation in ("copy", "move"):
        response = await client.post(
            f"/api/v1/projects/{project_id}/files/{operation}",
            json={"source": "src", "destination": "blocked"},
            headers=ALICE,
        )
        assert response.status_code == 409

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert {file["path"] for file in listing} == {"blocked", "src/main.py"}


# -- 压缩包 --------------------------------------------------------------------


async def upload_archive(
    client: httpx.AsyncClient,
    project_id: str,
    payload: bytes,
    *,
    filename: str = "bundle.zip",
    prefix: str = "",
) -> httpx.Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/files/archive",
        files={"file": (filename, payload, "application/zip")},
        params={"prefix": prefix} if prefix else {},
        headers=ALICE,
    )


@pytest.mark.asyncio
async def test_upload_archive_expands_members_under_prefix(client) -> None:
    project_id = await create_owned_project(client, "压缩包")
    payload = make_zip({"src/main.py": "print(1)", "docs/readme.md": "# hi"})

    response = await upload_archive(client, project_id, payload, prefix="libs")
    assert response.status_code == 200, response.text
    assert sorted(f["path"] for f in response.json()) == [
        "libs/docs/readme.md",
        "libs/src/main.py",
    ]

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert {f["path"] for f in listing} == {"libs/src/main.py", "libs/docs/readme.md"}
    preview = (
        await client.get(
            f"/api/v1/projects/{project_id}/files/content",
            params={"path": "libs/src/main.py"},
            headers=ALICE,
        )
    ).json()
    assert preview["content"] == "print(1)"


@pytest.mark.asyncio
async def test_upload_archive_rejects_traversal_without_partial_write(client) -> None:
    project_id = await create_owned_project(client, "穿越")
    payload = make_zip({"ok.txt": "fine", "../evil.txt": "boom"})

    response = await upload_archive(client, project_id, payload)
    assert response.status_code == 422
    assert "evil" in response.json()["message"]

    # 整体拒绝：合法条目也不能落进去。
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_upload_archive_rejects_reserved_gitkeep_atomically(client) -> None:
    project_id = await create_owned_project(client, "压缩包保留占位文件")
    payload = make_zip_entries(
        [("safe.txt", "must not be written"), ("empty/.gitkeep", "reserved")]
    )

    response = await upload_archive(client, project_id, payload)

    assert response.status_code == 422
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "member",
    ["/absolute.txt", "\\leading.txt", "C:\\drive.txt", "\\\\server\\share\\unc.txt"],
)
async def test_upload_archive_rejects_absolute_platform_paths_before_normalization(
    client, member: str
) -> None:
    project_id = await create_owned_project(client, f"绝对路径 {member}")

    response = await upload_archive(client, project_id, make_zip({member: "no"}))

    assert response.status_code == 422
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_upload_archive_validates_complete_namespace_before_writing(client) -> None:
    project_id = await create_owned_project(client, "压缩包命名空间")
    await write_file(client, project_id, "blocked", "existing")

    conflicts_with_existing = make_zip_entries(
        [("safe.txt", "would be partial"), ("blocked/child.txt", "no")]
    )
    response = await upload_archive(client, project_id, conflicts_with_existing)
    assert response.status_code == 409

    internal_collision = make_zip_entries([("node", "file"), ("node/child.txt", "child")])
    response = await upload_archive(client, project_id, internal_collision)
    assert response.status_code == 409

    normalized_duplicate = make_zip_entries([("same.txt", "first"), ("./same.txt", "second")])
    response = await upload_archive(client, project_id, normalized_duplicate)
    assert response.status_code == 409

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert {file["path"] for file in listing} == {"blocked"}


@pytest.mark.asyncio
async def test_upload_archive_rejects_symlink_entry(client) -> None:
    project_id = await create_owned_project(client, "符号链接")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("link.txt")
        info.external_attr = 0o120777 << 16  # S_IFLNK | 0777
        archive.writestr(info, "../../etc/passwd")
        archive.writestr("normal.txt", "ok")

    response = await upload_archive(client, project_id, buffer.getvalue())
    assert response.status_code == 422
    assert "link.txt" in response.json()["message"]
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_upload_archive_rejects_encrypted_entry(client) -> None:
    project_id = await create_owned_project(client, "加密条目")
    payload = with_encrypted_flag(make_zip({"secret.txt": "content"}))

    response = await upload_archive(client, project_id, payload)
    assert response.status_code == 422
    assert "加密" in response.json()["message"]


@pytest.mark.asyncio
async def test_upload_archive_enforces_entry_count_and_total_budget(client) -> None:
    project_id = await create_owned_project(client, "预算")

    too_many = make_zip({f"f{i}.txt": "x" for i in range(5)})
    response = await upload_archive(client, project_id, too_many)
    assert response.status_code == 422
    assert "上限" in response.json()["message"]

    # 单文件都在限内，但解压后总量超预算：zip 炸弹的主要形态。
    too_big_total = make_zip({name: "y" * 700 for name in ("a.txt", "b.txt", "c.txt")})
    response = await upload_archive(client, project_id, too_big_total)
    assert response.status_code == 422
    assert "总大小" in response.json()["message"]

    single_oversize = make_zip({"big.txt": "z" * 1500})
    response = await upload_archive(client, project_id, single_oversize)
    assert response.status_code == 422
    assert "单个文件上限" in response.json()["message"]


@pytest.mark.asyncio
async def test_upload_archive_rejects_corrupt_member_without_partial_write(client) -> None:
    project_id = await create_owned_project(client, "损坏压缩包")
    payload = with_corrupt_member(
        make_zip_entries([("safe.txt", "would be partial"), ("corrupt.txt", "damaged")]),
        "corrupt.txt",
    )

    response = await upload_archive(client, project_id, payload, filename="damaged.zip")

    assert response.status_code == 422
    assert "damaged.zip" in response.json()["message"]
    assert "损坏" in response.json()["message"]
    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    assert listing == []


@pytest.mark.asyncio
async def test_upload_archive_rejects_invalid_and_empty_zip(client) -> None:
    project_id = await create_owned_project(client, "非法压缩包")

    not_a_zip = await upload_archive(client, project_id, b"this is not a zip")
    assert not_a_zip.status_code == 422

    empty = await upload_archive(client, project_id, make_zip({}), filename="empty.zip")
    assert empty.status_code == 422


# -- 下载 ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_returns_full_content_with_attachment_header(client) -> None:
    project_id = await create_owned_project(client, "下载")
    content = "line1\nline2\n"
    await write_file(client, project_id, "notes/记录.txt", content)

    response = await client.get(
        f"/api/v1/projects/{project_id}/files/download",
        params={"path": "notes/记录.txt"},
        headers=ALICE,
    )
    assert response.status_code == 200
    assert response.content.decode("utf-8") == content
    disposition = response.headers["Content-Disposition"]
    assert "attachment" in disposition and "%E8%AE%B0%E5%BD%95.txt" in disposition

    missing = await client.get(
        f"/api/v1/projects/{project_id}/files/download",
        params={"path": "nope.txt"},
        headers=ALICE,
    )
    assert missing.status_code == 404


# -- 只读角色的越权边界 ----------------------------------------------------------


@pytest.mark.asyncio
async def test_public_reader_cannot_download_or_write_working_state(client) -> None:
    group_id = await ensure_user_group(client, headers=ALICE)
    # 用 canonical 建项目的入口才能带上 visibility；旧 workspace 入口不收这个字段。
    created = await client.post(
        "/api/v1/projects",
        json={
            "owner": {"kind": "user_group", "id": group_id},
            "name": "公开项目",
            "visibility": "public",
        },
        headers=ALICE,
    )
    assert created.status_code == 201, created.text
    assert created.json()["visibility"] == "public"
    project_id = str(created.json()["id"])
    await write_file(client, project_id, "run.sh", "echo hi")

    # PUBLIC 读者能看见元数据，但 Working State 的读和写都在 Owner 范围内：
    # 读越界按不可发现处理（404），写越界按权限不足处理（403）。
    download = await client.get(
        f"/api/v1/projects/{project_id}/files/download",
        params={"path": "run.sh"},
        headers=BOB,
    )
    assert download.status_code == 404

    detail = await client.get(
        f"/api/v1/projects/{project_id}/changes/detail",
        params={"path": "run.sh"},
        headers=BOB,
    )
    assert detail.status_code == 404

    write = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "hacked.txt", "content": "nope"},
        headers=BOB,
    )
    assert write.status_code == 403

    copy = await client.post(
        f"/api/v1/projects/{project_id}/files/copy",
        json={"source": "run.sh", "destination": "stolen.sh"},
        headers=BOB,
    )
    assert copy.status_code == 403

    mkdir = await client.post(
        f"/api/v1/projects/{project_id}/files/mkdir",
        json={"path": "stolen-dir"},
        headers=BOB,
    )
    assert mkdir.status_code == 403

    discard = await client.post(
        f"/api/v1/projects/{project_id}/changes/discard",
        json={"paths": ["run.sh"]},
        headers=BOB,
    )
    assert discard.status_code == 403

    archive = await client.post(
        f"/api/v1/projects/{project_id}/files/archive",
        files={"file": ("evil.zip", make_zip({"x.txt": "x"}), "application/zip")},
        headers=BOB,
    )
    assert archive.status_code == 403


# -- 变更详情与放弃 -------------------------------------------------------------


async def setup_project_with_baseline(client: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
    """创建带基线版本的 Project：v1 含 a.txt 与 dir/b.txt，返回 ``(id, 版本)``。"""
    project_id = await create_owned_project(client, "变更详情")
    await write_file(client, project_id, "a.txt", "original a")
    await write_file(client, project_id, "dir/b.txt", "original b")
    version_response = await client.post(
        f"/api/v1/projects/{project_id}/versions",
        json={"message": "v1"},
        headers=ALICE,
    )
    assert version_response.status_code == 201
    return project_id, version_response.json()


async def change_detail(client: httpx.AsyncClient, project_id: str, path: str) -> httpx.Response:
    return await client.get(
        f"/api/v1/projects/{project_id}/changes/detail",
        params={"path": path},
        headers=ALICE,
    )


@pytest.mark.asyncio
async def test_change_detail_returns_both_sides_of_each_change_kind(client) -> None:
    project_id, _ = await setup_project_with_baseline(client)
    await write_file(client, project_id, "a.txt", "changed a")  # modified
    await write_file(client, project_id, "new.txt", "brand new")  # added
    await client.delete(
        f"/api/v1/projects/{project_id}/files", params={"path": "dir/b.txt"}, headers=ALICE
    )  # removed

    detail = (await change_detail(client, project_id, "a.txt")).json()
    assert detail["change"] == "modified"
    assert detail["previous"]["content"] == "original a"
    assert detail["current"]["content"] == "changed a"

    added = (await change_detail(client, project_id, "new.txt")).json()
    assert added["change"] == "added"
    assert added["previous"] is None
    assert added["current"]["content"] == "brand new"

    removed = (await change_detail(client, project_id, "dir/b.txt")).json()
    assert removed["change"] == "removed"
    assert removed["previous"]["content"] == "original b"
    assert removed["current"] is None

    unchanged = await change_detail(client, project_id, "missing.txt")
    assert unchanged.status_code == 404


@pytest.mark.asyncio
async def test_discard_selected_changes_restores_working_state_only(client) -> None:
    project_id, baseline_version = await setup_project_with_baseline(client)
    await write_file(client, project_id, "a.txt", "changed a")
    await write_file(client, project_id, "new.txt", "brand new")
    await client.delete(
        f"/api/v1/projects/{project_id}/files", params={"path": "dir/b.txt"}, headers=ALICE
    )

    remaining = await client.post(
        f"/api/v1/projects/{project_id}/changes/discard",
        json={"paths": ["a.txt", "new.txt", "dir/b.txt", "not-changed.txt"]},
        headers=ALICE,
    )
    assert remaining.status_code == 200, remaining.text
    assert remaining.json() == []

    listing = (await client.get(f"/api/v1/projects/{project_id}/files", headers=ALICE)).json()
    contents = {
        f["path"]: (
            await client.get(
                f"/api/v1/projects/{project_id}/files/content",
                params={"path": f["path"]},
                headers=ALICE,
            )
        ).json()["content"]
        for f in listing
    }
    assert contents == {"a.txt": "original a", "dir/b.txt": "original b"}

    # 历史版本不动：基线版本内容保持原样，也没有产生新版本。
    restored = (
        await client.get(
            f"/api/v1/versions/{baseline_version['id']}/files/content",
            params={"path": "a.txt"},
            headers=ALICE,
        )
    ).json()
    assert restored["content"] == "original a"
    versions = (await client.get(f"/api/v1/projects/{project_id}/versions", headers=ALICE)).json()
    assert versions["total"] == 1

    # 工作区已和基线一致，再保存版本会被拒绝；重复 discard 幂等。
    no_changes = await client.post(
        f"/api/v1/projects/{project_id}/versions", json={"message": "空"}, headers=ALICE
    )
    assert no_changes.status_code == 409
    again = await client.post(
        f"/api/v1/projects/{project_id}/changes/discard",
        json={"paths": ["a.txt"]},
        headers=ALICE,
    )
    assert again.status_code == 200
    assert again.json() == []


@pytest.mark.asyncio
async def test_discard_requires_at_least_one_path(client) -> None:
    project_id, _ = await setup_project_with_baseline(client)
    empty = await client.post(
        f"/api/v1/projects/{project_id}/changes/discard",
        json={"paths": []},
        headers=ALICE,
    )
    assert empty.status_code == 422
