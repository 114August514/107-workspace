"""Shared Resource 作为 Run 输入的闭环测试。

走完 创建资源 → 上传文件形成版本 → 在 Run Configuration 的 Input Binding 中引用 →
提交 Run → Run 读取到输入 → 输入只读 全流程。

对应设计稿 §2.6 与 §3.1.3：Shared Resource 是独立于 Project 的内容资源，
通过 InputBinding 统一引用，Run 执行时物化到 inputs/ 下、只读（GR-404）。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run

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


async def _personal_workspace(client: httpx.AsyncClient) -> str:
    home = (await client.get("/api/v1/me", headers=ALICE)).json()
    return str(next(w for w in home["workspaces"] if w["kind"] == "personal")["id"])


async def _create_resource_with_version(
    client: httpx.AsyncClient, *, name: str, files: list[tuple[str, bytes]]
) -> dict:
    """建资源 + 发布 v1，返回版本详情（含 files）。"""
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


async def _run_with_input(
    client: httpx.AsyncClient,
    *,
    project: dict,
    version: dict,
    script: str,
    entry: str,
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
    run = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": configuration["id"]},
            headers=ALICE,
        )
    ).json()
    return await wait_for_run(client, run["id"], headers=ALICE)


# -- 闭环主路径 --------------------------------------------------------------


async def test_shared_resource_version_可以作为_run_输入(client: httpx.AsyncClient) -> None:
    """最关键的闭环：上传文件 → 引用 → Run 真的读到。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="预训练权重", files=[("weights.txt", b"model-params")]
    )
    project = await create_project_with_version(
        client, name="消费资源", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_with_input(
        client, project=project, version=version, script=CONSUMER, entry="consume.py"
    )

    assert detail["run"]["status"] == "succeeded", detail["run"]
    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "读到: model-params" in stdout["content"]

    # 输入绑定被固定进快照
    binding = detail["snapshot"]["input_bindings"][0]
    assert binding["source_type"] == "shared_resource_version"
    assert binding["source_id"] == version["id"]
    assert binding["access_path"] == "/inputs/dataset"


async def test_shared_resource_输入以只读方式提供(client: httpx.AsyncClient) -> None:
    """GR-404：输入只读，Run 不得原地修改。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="只读验证", files=[("weights.txt", b"original")]
    )
    project = await create_project_with_version(
        client, name="尝试篡改", files={"placeholder.py": "pass"}, headers=ALICE
    )
    detail = await _run_with_input(
        client, project=project, version=version, script=WRITER, entry="write.py"
    )

    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "写入被拒绝" in stdout["content"]
    assert "写成功了" not in stdout["content"]


async def test_shared_resource_支持多文件和子目录(client: httpx.AsyncClient) -> None:
    """版本里多文件 + 子目录结构，物化到 inputs 后保持原相对路径。"""
    await use_default_environment(client, headers=ALICE)
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
        print(p.relative_to(root), "=", p.read_text())
"""
    detail = await _run_with_input(
        client, project=project, version=version, script=listing_script, entry="list.py"
    )

    assert detail["run"]["status"] == "succeeded", detail["run"]
    logs = (await client.get(f"/api/v1/runs/{detail['run']['id']}/logs", headers=ALICE)).json()
    stdout = next(c for c in logs if c["stream"] == "stdout")
    assert "nested/deep.txt = 嵌套" in stdout["content"]
    assert "top.txt = 顶层" in stdout["content"]


# -- 错误路径 ---------------------------------------------------------------


async def test_引用不存在的_version_会挡在提交前(client: httpx.AsyncClient) -> None:
    await use_default_environment(client, headers=ALICE)
    project = await create_project_with_version(
        client, name="错误输入", files={"main.py": "pass"}, headers=ALICE
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
                        "source_id": "shrv_not_exist",
                        "access_path": "/inputs/x",
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
    assert any("不存在" in p for p in response.json()["problems"])


# -- 跨 Workspace 引用 -------------------------------------------------------


async def test_跨_workspace_引用_shared_resource_被挡在提交前(
    client: httpx.AsyncClient,
) -> None:
    """Bob 看不到 Alice 的 Personal Workspace 资源，引用时按不存在处理。"""
    await use_default_environment(client, headers=ALICE)
    version = await _create_resource_with_version(
        client, name="Alice 私有", files=[("a.txt", b"x")]
    )
    # Bob 在自己的 Personal Workspace 里建项目，引用 Alice 的资源版本
    bob_headers = {"X-User": "bob"}
    await client.patch(
        "/api/v1/workspaces/" + (await _personal_workspace(client)).replace("alice", "bob"),
        json={"default_environment_version_id": "ev_python_312"},
        headers=bob_headers,
    )
    bob_home = (await client.get("/api/v1/me", headers=bob_headers)).json()
    bob_ws = next(w for w in bob_home["workspaces"] if w["kind"] == "personal")["id"]
    project = (
        await client.post(
            f"/api/v1/workspaces/{bob_ws}/projects",
            json={"name": "Bob 项目"},
            headers=bob_headers,
        )
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "pass"},
        headers=bob_headers,
    )
    await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "v1"},
        headers=bob_headers,
    )
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={
                "name": "引用 Alice 的",
                "command": "python main.py",
                "compute_plan_id": "plan_cpu_quick",
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
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
        headers=bob_headers,
    )
    assert response.status_code == 422
    assert any("不存在" in p for p in response.json()["problems"])
