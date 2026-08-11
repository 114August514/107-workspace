"""Shared Resource Version 子路径过滤的闭环测试（设计稿 §3.1.3）。

InputBinding 的 ``source_subpath`` 让调用方只取来源内容的一个子路径，剥掉前缀
映射到 ``access_path`` 下。这里覆盖物化行为和 preflight 校验：

- 子路径指向目录 → 只物化该目录、剥前缀
- 子路径指向单个文件 → 物化到 ``access_path/<basename>``
- 同前缀陷阱（``train`` vs ``training``）只取边界匹配的
- 子路径不存在 → preflight 422 拒绝

闭环测试用 Mock 调度器以子进程真实执行脚本，Windows 上跳过（同
``test_shared_resource_input_binding.py``）。
"""

from __future__ import annotations

import sys

import httpx
import pytest

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Mock 调度器的子进程执行在 Windows 上行为不稳定，跳过闭环测试",
)

ALICE = {"X-User": "alice"}


async def _personal_workspace(client: httpx.AsyncClient) -> str:
    home = (await client.get("/api/v1/me", headers=ALICE)).json()
    return str(next(w for w in home["workspaces"] if w["kind"] == "personal")["id"])


async def _create_resource_with_version(
    client: httpx.AsyncClient, *, name: str, files: list[tuple[str, bytes]]
) -> dict:
    """建资源 + 发布 v1，返回版本详情。"""
    workspace_id = await _personal_workspace(client)
    resource = (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/shared-resources",
            json={"name": name},
            headers=ALICE,
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/shared-resources/{resource['id']}/versions",
            params={"prefix": ""},
            data={"description": "v1"},
            files=[
                ("files", (path, content, "application/octet-stream")) for path, content in files
            ],
            headers=ALICE,
        )
    ).json()
    return (
        await client.get(f"/api/v1/shared-resource-versions/{version['id']}", headers=ALICE)
    ).json()


async def _run_listing_input(
    client: httpx.AsyncClient,
    *,
    project: dict,
    version: dict,
    access_path: str,
    subpath: str,
) -> dict:
    """提交一个引用 SR 版本（带子路径）的 Run，Run 把 inputs 树打印出来。"""
    # access_path 在 storage 端被 lstrip("/") 后挂到 inputs 根下，所以这里也用相对路径拼。
    relative = access_path.lstrip("/")
    script = f"""import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / {relative!r}
for p in sorted(root.rglob("*")):
    if p.is_file():
        print(str(p.relative_to(root).as_posix()), "=", p.read_text())
"""
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "list.py", "content": script},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "消费端"},
        headers=ALICE,
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "子路径消费",
                "command": "python list.py",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": access_path,
                        "source_subpath": subpath,
                    }
                ],
            },
            headers=ALICE,
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
            headers=ALICE,
        )
    ).json()
    return await wait_for_run(client, run["id"], headers=ALICE)


async def _stdout_lines(client: httpx.AsyncClient, detail: dict) -> str:
    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stderr = next((c for c in logs if c["stream"] == "stderr"), None)
    assert detail["run"]["status"] == "succeeded", (
        f"Run failed: {detail['run']['failure_reason']} stderr={stderr['content']!r}"
        if stderr
        else ""
    )
    return next(c for c in logs if c["stream"] == "stdout")["content"]


# -- 目录子路径 ------------------------------------------------------------


async def test_子路径指向目录只物化该目录并剥前缀(client: httpx.AsyncClient) -> None:
    """``dataset/train/`` 子目录 → 在 Run 中暴露为 ``/inputs/train`` 下的内容（剥前缀）。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client,
        name="带子目录的数据集",
        files=[
            ("train/a.py", "训练A".encode()),
            ("train/sub/b.py", "训练B".encode()),
            ("test/c.py", "测试C".encode()),
            ("top.txt", "顶层".encode()),
        ],
    )
    project = await create_project_with_version(
        client, name="消费子目录", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_listing_input(
        client, project=project, version=version, access_path="/inputs/train", subpath="train/"
    )
    stdout = await _stdout_lines(client, detail)
    assert "a.py = 训练A" in stdout, stdout
    assert "sub/b.py = 训练B" in stdout, stdout
    # 不在子路径下的文件不应出现
    assert "c.py" not in stdout, stdout
    assert "top.txt" not in stdout, stdout


async def test_子路径深层目录同样剥前缀(client: httpx.AsyncClient) -> None:
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client,
        name="深层子路径",
        files=[
            ("a/b/c.py", "深".encode()),
            ("a/x.py", "浅".encode()),
            ("other.py", "外".encode()),
        ],
    )
    project = await create_project_with_version(
        client, name="消费深层", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_listing_input(
        client, project=project, version=version, access_path="/inputs/d", subpath="a/b/"
    )
    stdout = await _stdout_lines(client, detail)
    assert "c.py = 深" in stdout, stdout
    assert "x.py" not in stdout, stdout
    assert "other.py" not in stdout, stdout


# -- 同前缀陷阱 ------------------------------------------------------------


async def test_子路径按目录边界匹配不误纳同前缀目录(client: httpx.AsyncClient) -> None:
    """``subpath="train"`` 只匹配 ``train/`` 下文件，不误纳 ``training/``。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client,
        name="同前缀",
        files=[
            ("train/a.py", "对的".encode()),
            ("training/b.py", "错的".encode()),
        ],
    )
    project = await create_project_with_version(
        client, name="同前缀消费", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_listing_input(
        client, project=project, version=version, access_path="/inputs/x", subpath="train"
    )
    stdout = await _stdout_lines(client, detail)
    assert "a.py = 对的" in stdout, stdout
    assert "b.py" not in stdout, stdout
    assert "training" not in stdout, stdout


# -- 单文件子路径（B3 守卫：不剥到空串，落到 basename）---------------------


async def test_子路径指向单个文件物化到_basename(client: httpx.AsyncClient) -> None:
    """``subpath="train"`` 命名一个文件时，物化到 ``access_path/train``，不剥到空串崩掉。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client,
        name="单文件子路径",
        files=[
            ("train", "我是一个文件".encode()),
            ("other.txt", "别的".encode()),
        ],
    )
    project = await create_project_with_version(
        client, name="消费单文件", files={"placeholder.py": "pass"}, headers=ALICE
    )
    # 注意脚本里直接读 access_path/train（文件本身），而非遍历目录。
    # access_path 在 storage 端 lstrip("/") 后挂到 inputs 根，这里用相对路径拼。
    script = """import os, pathlib
base = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/x"
p = base / "train"
print("content=", p.read_text())
print("exists_other=", (base / "other.txt").exists())
"""
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "read.py", "content": script},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "读单文件"},
        headers=ALICE,
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "单文件消费",
                "command": "python read.py",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": "/inputs/x",
                        "source_subpath": "train",
                    }
                ],
            },
            headers=ALICE,
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
            headers=ALICE,
        )
    ).json()
    detail = await wait_for_run(client, run["id"], headers=ALICE)
    stdout = await _stdout_lines(client, detail)
    assert "content= 我是一个文件" in stdout, stdout
    assert "exists_other= False" in stdout, stdout


# -- preflight：子路径不存在 → 422 ----------------------------------------


async def test_子路径不存在被挡在提交前(client: httpx.AsyncClient) -> None:
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="不存在子路径", files=[("a.txt", b"x")]
    )
    project = await create_project_with_version(
        client, name="错误子路径", files={"main.py": "pass"}, headers=ALICE
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "跑一下",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
                "input_bindings": [
                    {
                        "source_type": "shared_resource_version",
                        "source_id": version["id"],
                        "access_path": "/inputs/x",
                        "source_subpath": "nope/",
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
    assert any("子路径" in p for p in response.json()["problems"])


# -- 空子路径物化全部（不回归）--------------------------------------------


async def test_空子路径物化整份内容(client: httpx.AsyncClient) -> None:
    """不传 source_subpath（默认空）→ 物化整份内容，与既有行为一致。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client,
        name="全量",
        files=[("top.txt", "顶层".encode()), ("nested/deep.txt", "嵌套".encode())],
    )
    project = await create_project_with_version(
        client, name="全量消费", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_listing_input(
        client, project=project, version=version, access_path="/inputs/d", subpath=""
    )
    stdout = await _stdout_lines(client, detail)
    assert "top.txt = 顶层" in stdout, stdout
    assert "nested/deep.txt = 嵌套" in stdout, stdout
