"""API 契约与错误码映射。"""

from __future__ import annotations

import httpx
import pytest

from workspace107 import __version__
from workspace107.api.errors import status_for
from workspace107.domain.errors import (
    ConflictError,
    ImmutableObjectError,
    ObjectNotFound,
    PermissionDenied,
    PreflightRejected,
    SchedulerError,
    ValidationFailed,
)


async def test_健康检查(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["scheduler"] == "mock"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ObjectNotFound("Project", "prj_1"), 404),
        (PermissionDenied("需要 Owner"), 403),
        (ConflictError("重名"), 409),
        # ImmutableObjectError 是 ConflictError 的子类，必须同样映射到 409。
        (ImmutableObjectError("快照不可修改"), 409),
        (ValidationFailed("字段不合法"), 422),
        (PreflightRejected(["缺少版本"]), 422),
        (SchedulerError("Slurm 挂了"), 502),
    ],
)
def test_领域错误映射到正确的状态码(error, expected: int) -> None:
    assert status_for(error) == expected


async def test_错误响应结构统一(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/projects/prj_not_exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"code", "message", "problems", "request_id"}
    assert body["code"] == "not_found"
    assert body["problems"] == []


async def test_错误体里的_request_id_和响应头一致(client: httpx.AsyncClient) -> None:
    """这条线索能不能用，取决于两边是不是同一个值。

    用户报错时给的是响应体里的 request_id，运维查的是日志；
    响应头则方便在浏览器网络面板里直接看到。两者必须对得上。
    """
    response = await client.get("/api/v1/projects/prj_not_exist")

    body_id = response.json()["request_id"]
    assert body_id, "错误响应没有 request_id，出问题时无法定位到日志"
    assert response.headers["X-Request-Id"] == body_id


async def test_上游传来的_request_id_会被沿用(client: httpx.AsyncClient) -> None:
    """网关已经生成了标识时应当沿用，这样才能跨服务串联同一次请求。"""
    response = await client.get("/api/v1/health", headers={"X-Request-Id": "req_from_gateway"})
    assert response.headers["X-Request-Id"] == "req_from_gateway"
    assert response.json()["request_id"] == "req_from_gateway"


async def test_就绪探针和存活探针分开(client: httpx.AsyncClient) -> None:
    """进程活着不等于依赖都通，两者要分开回答。"""
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = await client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "ready": True,
        "database": True,
        "detail": "",
        "request_id": ready.json()["request_id"],
    }


async def test_数据库不可用时就绪探针返回_503(client: httpx.AsyncClient, context) -> None:
    await context.engine.dispose()
    # 换成一个连不上的地址，模拟依赖故障
    from sqlalchemy.ext.asyncio import create_async_engine

    from workspace107.infrastructure.db.session import create_session_factory

    broken = create_async_engine("sqlite+aiosqlite:////nonexistent-dir/broken.db")
    context.session_factory = create_session_factory(broken)

    response = await client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["database"] is False


async def test_提交前检查失败时返回全部问题(client: httpx.AsyncClient) -> None:
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "空的"})
    ).json()
    configuration = (
        await client.post(
            f"/api/v1/projects/{project['id']}/run-configurations",
            json={"name": "跑一下", "command": "echo hi", "compute_plan_id": "plan_cpu_quick"},
        )
    ).json()

    response = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration["id"]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "preflight_rejected"
    # 没有版本、没有环境，两个问题应该一次性都报出来，而不是让用户来回试。
    assert len(body["problems"]) >= 2


async def test_目录接口返回平台环境和算力方案(client: httpx.AsyncClient) -> None:
    environments = (await client.get("/api/v1/catalog/environments")).json()
    assert {e["id"] for e in environments} == {"env_python_base", "env_pytorch"}
    assert any(v["id"] == "ev_python_312" for e in environments for v in e["versions"])

    plans = (await client.get("/api/v1/catalog/compute-plans")).json()
    codes = {p["code"] for p in plans}
    assert codes == {"cpu-quick", "cpu-standard", "gpu-standard"}


async def test_新用户自动获得_personal_workspace_和默认权益(client: httpx.AsyncClient) -> None:
    home = (await client.get("/api/v1/me", headers={"X-User": "newcomer"})).json()
    assert len(home["workspaces"]) == 1
    workspace = home["workspaces"][0]
    assert workspace["kind"] == "personal"

    entitlements = (
        await client.get(
            f"/api/v1/workspaces/{workspace['id']}/entitlements",
            headers={"X-User": "newcomer"},
        )
    ).json()
    assert {e["compute_plan_id"] for e in entitlements} == {
        "plan_cpu_quick",
        "plan_cpu_standard",
        "plan_gpu_standard",
    }


async def test_openapi_可以生成(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "107 Workspace API"
    assert "/api/v1/projects/{project_id}/runs" in schema["paths"]


async def test_openapi_保留已编写的字段说明(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    expected = {
        ("WorkspaceOut", "capabilities"): "当前用户在这个空间里能做什么。",
        ("FileWriteIn", "content"): "文本内容。",
        ("PreflightOut", "secret_references"): "环境变量名 -> Secret 名称。",
        ("NotificationOut", "mandatory"): "不可关闭的重要通知。",
        ("ForkIn", "name"): "留空表示沿用源 Project 的名称。",
    }

    for (model, field), prefix in expected.items():
        description = schema["components"]["schemas"][model]["properties"][field]["description"]
        assert description.startswith(prefix), f"{model}.{field} 没有保留源码中的字段说明"


async def test_下载接口在契约里声明的是二进制(client: httpx.AsyncClient) -> None:
    """返回文件的接口不能在契约里写着返回 JSON。

    不声明 ``response_class`` 和 ``responses`` 的话，FastAPI 会按默认填成
    ``application/json`` + 空 schema。契约错了，据此生成的前端类型也会错，
    调用方最后只能靠强制转换绕过去——而强制转换正是契约存在的意义所在。
    """
    schema = (await client.get("/openapi.json")).json()
    download = schema["paths"]["/api/v1/artifacts/{artifact_id}/download"]["get"]
    content = download["responses"]["200"]["content"]

    assert set(content) == {"application/octet-stream"}
    assert content["application/octet-stream"]["schema"] == {"type": "string", "format": "binary"}


async def test_接口返回的时间一律带时区(client: httpx.AsyncClient) -> None:
    """时间戳必须带 ``Z`` 或明确的偏移量。

    SQLite 读回来的 datetime 没有时区。仓储里有 ``_aware`` / ``_required``
    负责补成 UTC，但**每写一个新的行到模型的转换函数就要记得用一次**，
    忘了不会报错——序列化出来只是少一个 Z，后端测试全绿。
    前端按本地时区解析，「刚刚」就显示成「8 小时前」。

    活动流上真踩过一次，所以这里对整批接口一起把关，
    而不是只给活动加一条断言。
    """
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "查时区"})
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print(1)"},
    )
    await client.post(f"/api/v1/projects/{project['id']}/versions", json={"message": "v1"})

    payloads = {
        "/me": home,
        "工作空间": (await client.get(f"/api/v1/workspaces/{workspace_id}")).json(),
        "Project 列表": (await client.get(f"/api/v1/workspaces/{workspace_id}/projects")).json(),
        "版本列表": (await client.get(f"/api/v1/projects/{project['id']}/versions")).json(),
        "成员": (await client.get(f"/api/v1/workspaces/{workspace_id}/members")).json(),
        "活动流": (await client.get(f"/api/v1/workspaces/{workspace_id}/activities")).json(),
        "Project 活动流": (await client.get(f"/api/v1/projects/{project['id']}/activities")).json(),
    }

    naive: list[str] = []
    for label, payload in payloads.items():
        for path, value in _timestamps(payload):
            # 形如 2026-07-26T14:36:01.476476Z 或 ...+08:00
            if not (value.endswith("Z") or _has_offset(value)):
                naive.append(f"{label}{path} = {value}")

    assert not naive, "这些时间字段没有时区，前端会按本地时区解析：\n" + "\n".join(naive)


def _has_offset(value: str) -> bool:
    tail = value[10:]  # 跳过日期部分，只看时间和其后
    return "+" in tail or tail.count("-") > 0


def _timestamps(node: object, path: str = "") -> list[tuple[str, str]]:
    """递归找出所有看起来像时间戳的字符串。"""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_timestamps(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_timestamps(value, f"{path}[{index}]"))
    elif isinstance(node, str) and _looks_like_timestamp(node):
        found.append((path, node))
    return found


def _looks_like_timestamp(value: str) -> bool:
    return (
        len(value) >= 19
        and value[4] == "-"
        and value[7] == "-"
        and value[10] == "T"
        and value[13] == ":"
    )


async def test_产物文件名带中文也能下载(client: httpx.AsyncClient) -> None:
    """HTTP 头只能是 latin-1。

    中文文件名直接塞进 Content-Disposition，会在 Starlette 编码响应头时抛
    UnicodeEncodeError；那不是 DomainError，没有 handler 接，最后是裸 500——
    **产物名字带中文就下载不了**，而中文名在这个平台上再正常不过。
    """
    from workspace107.api.routes.runs import _content_disposition

    header = _content_disposition("实验结果.csv")

    # 必须能编码进 HTTP 头，否则响应根本发不出去
    header.encode("latin-1")
    # RFC 5987 的那份带着真实名字，现代浏览器优先用它
    assert "filename*=UTF-8''" in header
    assert "%E5%AE%9E%E9%AA%8C" in header
    # ASCII 兜底那份也在，老客户端至少能存下来
    assert 'filename="' in header


async def test_下载头里的引号会被处理掉(client: httpx.AsyncClient) -> None:
    """文件名里的引号会把 Content-Disposition 的引号提前闭合。"""
    header = _content_disposition_of('a"b.csv')
    assert 'filename="a_b.csv"' in header


def _content_disposition_of(filename: str) -> str:
    from workspace107.api.routes.runs import _content_disposition

    return _content_disposition(filename)
