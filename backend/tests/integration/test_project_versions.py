"""项目文件与版本管理。

对应 GR-201：Project Working State 可变，Project Version 不可变。
"""

from __future__ import annotations

import httpx

from tests.helpers import create_project_with_version, use_default_environment


async def test_保存版本后工作区没有未保存变更(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="版本测试", files={"a.py": "print(1)"})
    changes = (await client.get(f"/api/v1/projects/{project['id']}/changes")).json()
    assert changes == []


async def test_未保存变更按新增_修改_删除分类(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(
        client, name="变更测试", files={"a.py": "print(1)", "b.py": "print(2)"}
    )

    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "a.py", "content": "print(11)"}
    )
    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "c.py", "content": "print(3)"}
    )
    await client.delete(f"/api/v1/projects/{project['id']}/files", params={"path": "b.py"})

    changes = (await client.get(f"/api/v1/projects/{project['id']}/changes")).json()
    assert changes == [
        {"path": "a.py", "change": "modified"},
        {"path": "b.py", "change": "removed"},
        {"path": "c.py", "change": "added"},
    ]


async def test_内容没变时拒绝保存重复版本(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="重复版本")
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "再存一次"}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


async def test_版本序号递增且内容固定(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="序号测试", files={"a.py": "print(1)"})
    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "a.py", "content": "print(2)"}
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "第二版"})

    versions = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()["items"]
    assert [v["label"] for v in versions] == ["v2", "v1"]

    # v1 的内容不会因为工作区后来的修改而改变。
    v1 = (await client.get(f"/api/v1/versions/{versions[1]['id']}")).json()
    content = (
        await client.get(f"/api/v1/versions/{v1['id']}/files/content", params={"path": "a.py"})
    ).json()
    assert content["content"] == "print(1)"


async def test_比较两个版本(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(
        client, name="比较测试", files={"a.py": "print(1)", "b.py": "print(2)"}
    )
    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "a.py", "content": "print(11)"}
    )
    await client.delete(f"/api/v1/projects/{project['id']}/files", params={"path": "b.py"})
    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "c.py", "content": "print(3)"}
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "第二版"})

    versions = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()["items"]
    diff = (
        await client.get(
            f"/api/v1/versions/{versions[0]['id']}/diff", params={"base": versions[1]["id"]}
        )
    ).json()

    assert diff == [
        {"path": "a.py", "change": "modified"},
        {"path": "b.py", "change": "removed"},
        {"path": "c.py", "change": "added"},
    ]


async def test_恢复历史版本只改工作区(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="恢复测试", files={"a.py": "print(1)"})
    await client.put(
        f"/api/v1/projects/{project['id']}/files", json={"path": "a.py", "content": "print(2)"}
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "第二版"})
    versions = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()["items"]
    v1_id = versions[1]["id"]

    restored = await client.post(f"/api/v1/versions/{v1_id}/restore")
    assert restored.status_code == 200

    current = (
        await client.get(f"/api/v1/projects/{project['id']}/files/content", params={"path": "a.py"})
    ).json()
    assert current["content"] == "print(1)"

    # v2 依然存在，内容也没变。
    v2 = (
        await client.get(
            f"/api/v1/versions/{versions[0]['id']}/files/content", params={"path": "a.py"}
        )
    ).json()
    assert v2["content"] == "print(2)"


async def test_移动目录会带上其中全部文件(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(
        client,
        name="移动测试",
        files={"src/a.py": "print(1)", "src/nested/b.py": "print(2)", "keep.py": "print(3)"},
    )

    moved = await client.post(
        f"/api/v1/projects/{project['id']}/files/move",
        json={"source": "src", "destination": "lib"},
    )
    assert moved.status_code == 200

    files = (await client.get(f"/api/v1/projects/{project['id']}/files")).json()
    assert sorted(f["path"] for f in files) == ["keep.py", "lib/a.py", "lib/nested/b.py"]


async def test_删除目录会删除其中全部文件(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(
        client, name="删除目录", files={"src/a.py": "1", "src/b.py": "2", "keep.py": "3"}
    )

    response = await client.delete(
        f"/api/v1/projects/{project['id']}/files", params={"path": "src"}
    )
    assert response.status_code == 204

    files = (await client.get(f"/api/v1/projects/{project['id']}/files")).json()
    assert [f["path"] for f in files] == ["keep.py"]


async def test_同一个_workspace_内项目重名被拒绝(client: httpx.AsyncClient) -> None:
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "重名"})

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "重名"}
    )
    assert response.status_code == 409


async def test_超过上限的文件被拒绝(client: httpx.AsyncClient, context) -> None:
    """大数据集和模型权重属于算力平台存储，不该塞进 Project 文件。

    中间件按 Content-Length 挡的是明显超大的请求，这里验证的是用例层
    那道真正的上限——Content-Length 可能缺失或被伪造。
    """
    context.settings.max_file_bytes = 1024

    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "大文件"})
    ).json()

    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "big.bin", "content": "x" * 2048},
    )

    assert response.status_code == 422
    assert "上限" in response.json()["message"]


async def test_上限之内的文件正常写入(client: httpx.AsyncClient, context) -> None:
    context.settings.max_file_bytes = 1024

    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "小文件"})
    ).json()

    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "small.txt", "content": "x" * 100},
    )
    assert response.status_code == 200


async def test_版本列表分页(client: httpx.AsyncClient) -> None:
    """历史类列表会随时间单调增长，必须分页。"""
    project = await create_project_with_version(client, name="分页测试", files={"a.py": "v1"})
    for index in range(2, 6):
        await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": "a.py", "content": f"v{index}"},
        )
        await client.post(
            f"/api/v1/projects/{project['id']}/versions", json={"message": f"第 {index} 版"}
        )

    first = (
        await client.get(
            f"/api/v1/projects/{project['id']}/versions", params={"page": 1, "page_size": 2}
        )
    ).json()
    assert first["total"] == 5
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert first["has_more"] is True
    assert [v["label"] for v in first["items"]] == ["v5", "v4"]

    last = (
        await client.get(
            f"/api/v1/projects/{project['id']}/versions", params={"page": 3, "page_size": 2}
        )
    ).json()
    assert last["has_more"] is False
    assert [v["label"] for v in last["items"]] == ["v1"]


async def test_超出范围的页码返回空页而不是报错(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="空页测试")
    result = (
        await client.get(f"/api/v1/projects/{project['id']}/versions", params={"page": 99})
    ).json()

    assert result["items"] == []
    assert result["total"] == 1
    assert result["has_more"] is False


async def test_非法分页参数被拒绝(client: httpx.AsyncClient) -> None:
    project = await create_project_with_version(client, name="非法分页")

    zero = await client.get(f"/api/v1/projects/{project['id']}/versions", params={"page": 0})
    assert zero.status_code == 422

    too_large = await client.get(
        f"/api/v1/projects/{project['id']}/versions", params={"page_size": 9999}
    )
    assert too_large.status_code == 422


async def test_状态类列表不分页(client: httpx.AsyncClient) -> None:
    """文件树、成员、运行方案这些由当前状态决定规模，分页只会更难用。"""
    project = await create_project_with_version(
        client, name="不分页的列表", files={"a.py": "1", "b.py": "2"}
    )
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]

    for path in (
        f"/api/v1/projects/{project['id']}/files",
        f"/api/v1/projects/{project['id']}/run-configurations",
        f"/api/v1/workspaces/{workspace_id}/members",
        f"/api/v1/workspaces/{workspace_id}/entitlements",
        "/api/v1/catalog/compute-plans",
    ):
        body = (await client.get(path)).json()
        assert isinstance(body, list), f"{path} 不该分页"


async def test_删除目录不会被路径里的通配符放大(client: httpx.AsyncClient) -> None:
    """`startswith` 生成的是 LIKE，而 % 和 _ 在路径里是合法字符。

    不转义的话，删一个叫「%」的目录会变成 `LIKE '%/%'`，
    把项目里**所有**子目录的文件一起删掉。
    """
    await use_default_environment(client)
    project = await create_project_with_version(client, name="通配符路径")

    for path in ["%/a.txt", "src/keep.py", "docs/keep.md", "top.txt"]:
        response = await client.put(
            f"/api/v1/projects/{project['id']}/files",
            json={"path": path, "content": "x"},
        )
        assert response.status_code == 200, response.text

    removed = await client.request(
        "DELETE",
        f"/api/v1/projects/{project['id']}/files",
        params={"path": "%"},
    )
    assert removed.status_code == 204

    remaining = {
        f["path"] for f in (await client.get(f"/api/v1/projects/{project['id']}/files")).json()
    }
    # 只有 "%" 目录下的没了，别的子目录一个都不能少
    assert "%/a.txt" not in remaining
    assert {"src/keep.py", "docs/keep.md", "top.txt"} <= remaining
