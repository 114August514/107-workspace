"""Shared Resource 作为 Run 输入的闭环测试。

走完 创建资源 → 上传文件形成版本 → 在 Run Configuration 的 Input Binding 中引用 →
提交 Run → Run 读取到输入 → 输入只读 全流程。

对应设计稿 §2.6 与 §3.1.3：Shared Resource 是独立于 Project 的内容资源，
通过 InputBinding 统一引用，Run 执行时物化到 inputs/ 下、只读（GR-404）。

闭环测试使用 Mock 调度器以子进程真实执行脚本，覆盖 Linux 开发、测试和部署目标。
"""

from __future__ import annotations

import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import (
    create_project_with_version,
    ensure_user_group,
    grant_test_entitlement,
    use_default_environment,
    wait_for_run,
)

ALICE = {"X-User": "alice"}

CONSUMER = """import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/dataset"
print("读到:", (root / "weights.txt").read_text())
print("文件数:", len(list(root.rglob("*"))))
"""

WRITER = """import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/dataset"
try:
    (root / "weights.txt").write_text("篡改")
    print("写成功了")
except (PermissionError, OSError) as exc:
    print("写入被拒绝:", type(exc).__name__)
"""


def _norm_path(p: str) -> str:
    return p.replace(os.sep, "/")


async def _user_group(client: httpx.AsyncClient) -> str:
    return await ensure_user_group(client, headers=ALICE)


async def _create_resource_with_version(
    client: httpx.AsyncClient, *, name: str, files: list[tuple[str, bytes]]
) -> dict:
    """建资源 + 发布 v1，返回版本详情（含 files）。"""
    user_group_id = await _user_group(client)
    resource = (
        await client.post(
            "/api/v1/shared-resources",
            json={
                "name": name,
                "owner": {"kind": "user_group", "id": user_group_id},
            },
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


async def _run_with_input(
    client: httpx.AsyncClient,
    *,
    project: dict,
    version: dict,
    script: str,
    entry: str,
    environment_version_id: str,
    access_path: str = "/inputs/dataset",
) -> dict:
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": entry, "content": script},
        headers=ALICE,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "加入消费端"},
        headers=ALICE,
    )

    configuration_response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": f"消费-{entry}",
            "command": f"python {entry}",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": version["id"],
                    "access_path": access_path,
                }
            ],
        },
        headers=ALICE,
    )
    assert configuration_response.status_code == 201, configuration_response.text
    configuration = configuration_response.json()
    run_response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=ALICE,
    )
    assert run_response.status_code == 201, run_response.text
    run = run_response.json()
    return await wait_for_run(client, run["id"], headers=ALICE)


# -- 闭环主路径 --------------------------------------------------------------


async def test_shared_resource_version_可以作为_run_输入(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """最关键的闭环：上传文件 → 引用 → Run 真的读到。"""
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(
        client, name="预训练权重", files=[("weights.txt", b"model-params")]
    )
    project = await create_project_with_version(
        client, name="消费资源", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_with_input(
        client,
        project=project,
        version=version,
        script=CONSUMER,
        entry="consume.py",
        environment_version_id=env_version_id,
    )

    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stderr = next((c for c in logs if c["stream"] == "stderr"), None)

    assert detail["run"]["status"] == "succeeded", (
        f"Run failed: {detail['run']['failure_reason']} stderr={stderr['content']!r}"
        if stderr
        else ""
    )

    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "读到: model-params" in stdout["content"]

    # 输入绑定被固定进快照
    binding = detail["snapshot"]["input_bindings"][0]
    assert binding["source_type"] == "shared_resource_version"
    assert binding["source_id"] == version["id"]
    assert binding["access_path"] == "/inputs/dataset"


async def test_shared_resource_输入以只读方式提供(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """GR-404：输入只读，Run 不得原地修改。"""
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(
        client, name="只读验证", files=[("weights.txt", b"original")]
    )
    project = await create_project_with_version(
        client, name="尝试篡改", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_with_input(
        client,
        project=project,
        version=version,
        script=WRITER,
        entry="write.py",
        environment_version_id=env_version_id,
    )

    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stderr = next((c for c in logs if c["stream"] == "stderr"), None)

    assert detail["run"]["status"] == "succeeded", (
        f"Run failed: {detail['run']['failure_reason']} stderr={stderr['content']!r}"
        if stderr
        else ""
    )

    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "写入被拒绝" in stdout["content"]
    assert "写成功了" not in stdout["content"]


async def test_shared_resource_支持多文件和子目录(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """版本里多文件 + 子目录结构，物化到 inputs 后保持原相对路径。"""
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    await grant_test_entitlement(session, "alice")
    version = await _create_resource_with_version(
        client,
        name="多文件资源",
        files=[
            ("top.txt", "顶层".encode()),
            ("nested/deep.txt", "嵌套".encode()),
        ],
    )
    project = await create_project_with_version(
        client, name="多文件消费", files={"placeholder.py": "pass"}, headers=ALICE
    )

    listing_script = """import os, pathlib
root = pathlib.Path(os.environ["WORKSPACE107_INPUTS_DIR"]) / "inputs/dataset"
for p in sorted(root.rglob("*")):
    if p.is_file():
        print(str(p.relative_to(root).as_posix()), "=", p.read_text())
"""
    detail = await _run_with_input(
        client,
        project=project,
        version=version,
        script=listing_script,
        entry="list.py",
        environment_version_id=env_version_id,
    )

    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stderr = next((c for c in logs if c["stream"] == "stderr"), None)
    failure_info = f"stderr={stderr['content']!r}" if stderr else ""

    assert detail["run"]["status"] == "succeeded", (
        f"Run failed: {detail['run']['failure_reason']} {failure_info}"
    )

    stdout = next(c for c in logs if c["stream"] == "stdout")["content"]
    assert "nested/deep.txt = 嵌套" in stdout, stdout
    assert "top.txt = 顶层" in stdout, stdout


# -- 错误路径 ---------------------------------------------------------------


async def test_引用不存在的_version_会挡在运行方案保存前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, env_version_id = await use_default_environment(session, client, headers=ALICE)
    project = await create_project_with_version(
        client, name="错误输入", files={"main.py": "pass"}, headers=ALICE
    )
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "跑一下",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": env_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": "shrv_not_exist",
                    "access_path": "/inputs/x",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# -- 跨 Owner 引用 -------------------------------------------------------


async def test_跨_owner_引用_user_group_shared_resource_被挡在运行方案保存前(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Bob cannot persist an asset owned by Alice's exact User Group."""
    await use_default_environment(session, client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="Alice 私有", files=[("a.txt", b"x")]
    )
    bob_headers = {"X-User": "bob"}
    bob_group_id, bob_env_version_id = await use_default_environment(
        session, client, headers=bob_headers
    )
    project = (
        await client.post(
            "/api/v1/projects",
            json={"owner": {"kind": "user_group", "id": bob_group_id}, "name": "Bob 项目"},
            headers=bob_headers,
        )
    ).json()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "引用 Alice 的",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": bob_env_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": version["id"],
                    "access_path": "/inputs/x",
                }
            ],
        },
        headers=bob_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
