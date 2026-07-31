"""并发下的资源权益与唯一约束。

两类问题：

1. 「数一数还有几个名额 -> 创建 Run」中间会被别的请求插进来，
   不串行化的话并发上限形同虚设。
2. 「先查重 -> 再插入」同样有窗口，兜底靠数据库唯一约束；
   但约束抛的是 SQLAlchemy 异常，不翻译就变成 500。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from tests.helpers import create_project_with_version, use_default_environment, wait_for_run
from workspace107.domain import ids
from workspace107.domain.errors import ConflictError
from workspace107.domain.models import ProjectVersion, ProjectVersionFile
from workspace107.infrastructure.db.repositories import SqlRepositories

LONG_JOB = "import time; time.sleep(30)"


async def _configure(client: httpx.AsyncClient, project: dict, name: str, command: str) -> str:
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={"name": name, "command": command, "compute_plan_id": "plan_cpu_quick"},
    )
    response.raise_for_status()
    return response.json()["id"]


async def test_重跑同样受并发上限约束(client: httpx.AsyncClient) -> None:
    """回归：重跑原来完全没查并发上限。

    漏掉这条，用户反复点「重新运行」就能绕过权益限制——
    而这恰恰是最容易被反复触发的路径。
    """
    await use_default_environment(client)
    project = await create_project_with_version(
        client, name="重跑并发", files={"quick.py": "print('done')", "slow.py": LONG_JOB}
    )
    quick = await _configure(client, project, "快任务", "python quick.py")
    slow = await _configure(client, project, "长任务", "python slow.py")

    # 先跑完一个，作为后面重跑的来源
    finished = (
        await client.post(
            f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": quick}
        )
    ).json()
    await wait_for_run(client, finished["id"])

    # 占满并发名额（默认权益是 2）
    occupying = []
    for _ in range(2):
        response = await client.post(
            f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": slow}
        )
        assert response.status_code == 201
        occupying.append(response.json())

    blocked = await client.post(f"/api/v1/runs/{finished['id']}/rerun")
    assert blocked.status_code == 422
    assert any("并发上限" in problem for problem in blocked.json()["problems"])

    for run in occupying:
        await client.post(f"/api/v1/runs/{run['id']}/cancel")


async def test_提交时会独占权益行(services, session) -> None:
    """锁本身要能在两种数据库上都跑通。

    PostgreSQL 上是真正的 SELECT ... FOR UPDATE；SQLite 不支持，
    SQLAlchemy 方言会忽略它——所以这里验证的是「调用不报错且拿得到权益」，
    严格的互斥保证只在生产数据库上成立。
    """
    user = await services.workspaces.ensure_user("locker")
    workspace = await services.workspaces.personal_workspace(user.id)

    repos = SqlRepositories(session)
    locked = await repos.entitlements.lock_for_plan(workspace.id, "plan_cpu_quick")

    assert locked is not None
    assert locked.workspace_id == workspace.id
    assert locked.max_concurrent_runs >= 1


async def test_不存在的权益锁返回_none(services, session) -> None:
    user = await services.workspaces.ensure_user("locker2")
    workspace = await services.workspaces.personal_workspace(user.id)

    repos = SqlRepositories(session)
    assert await repos.entitlements.lock_for_plan(workspace.id, "plan_not_exist") is None


async def test_版本序号撞车报_409_而不是_500(client, session) -> None:
    """两个人同时保存版本会拿到同一个序号，唯一约束挡下第二个。

    翻译成 ConflictError 之后，用户看到的是 409 和一句能看懂的话，
    而不是一个 500 加一串 SQLAlchemy 堆栈。
    """
    project = await create_project_with_version(client, name="序号撞车")

    repos = SqlRepositories(session)
    detail = (await client.get(f"/api/v1/projects/{project['id']}/versions")).json()["items"][0]

    duplicate = ProjectVersion(
        id=ids.new_id(ids.PROJECT_VERSION),
        project_id=project["id"],
        sequence=detail["sequence"],  # 和已有版本同号
        message="并发保存",
        files=(ProjectVersionFile(path="a.py", size=1, content_hash="0" * 64),),
        created_by="usr_other",
        created_at=datetime.now(UTC),
    )

    with pytest.raises(ConflictError) as excinfo:
        await repos.project_versions.add(duplicate)
    assert "同时保存" in str(excinfo.value)


async def test_project_重名撞车也报冲突(client, session) -> None:
    from workspace107.domain.enums import ProjectStatus
    from workspace107.domain.models import Project

    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    created = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "撞名字"})
    ).json()

    repos = SqlRepositories(session)
    duplicate = Project(
        id=ids.new_id(ids.PROJECT),
        workspace_id=workspace_id,
        name=created["name"],  # 同一个 Workspace 下同名
        status=ProjectStatus.ACTIVE,
        created_by="usr_other",
    )

    with pytest.raises(ConflictError) as excinfo:
        await repos.projects.add(duplicate)
    assert "同名 Project" in str(excinfo.value)


async def test_不同算力方案的名额互不挤占(client: httpx.AsyncClient) -> None:
    """当前实现的并发额度按「Workspace × 算力方案」计。

    这是口径不一致时最直观的症状：CPU 作业把 GPU 的名额吃掉。
    早先计数数的是整个 Workspace，比锁的范围大——两个请求提交到不同方案时
    锁不到一起，却读同一个计数。只测同方案的话这个错误检查不出来，
    所以这条**必须跨方案**。
    """
    workspace_id = await use_default_environment(client)
    project = await create_project_with_version(
        client, name="并发口径", files={"slow.py": "import time; time.sleep(5)"}
    )

    async def configuration(name: str, plan: str) -> str:
        body = (
            await client.post(
                f"/api/v1/projects/{project['id']}/run-configurations",
                json={"name": name, "command": "python slow.py", "compute_plan_id": plan},
            )
        ).json()
        return str(body["id"])

    quick = await configuration("快速", "plan_cpu_quick")
    standard = await configuration("标准", "plan_cpu_standard")

    # 把 plan_cpu_quick 的两个名额占满
    for _ in range(2):
        created = await client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"run_configuration_id": quick},
        )
        assert created.status_code == 201

    # 同一个方案上第三个应当被拦下
    blocked = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": quick}
    )
    assert blocked.status_code == 422
    assert any("并发上限" in p for p in blocked.json()["problems"])

    # 但另一个方案的名额没被动过
    other = await client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"run_configuration_id": standard}
    )
    assert other.status_code == 201, other.text
    assert workspace_id


async def test_新用户首屏并发请求不会互相打架(client: httpx.AsyncClient) -> None:
    """每个请求都会走 ensure_user，包括纯读接口。

    新用户第一次打开页面时前端会并发发好几个请求（未读数、首页数据……），
    它们同时发现用户不存在、同时插入，`users.username` 的唯一约束会让
    输掉的那个拿到 IntegrityError。**这不是理论竞态，是新用户必然遇到的首屏。**
    早先没有翻译规则，那个异常一路冒到 FastAPI 外面变成 500，
    响应体还不是契约里的错误信封。
    """
    # 用户名走 X-User 请求头，HTTP 头只能是 latin-1，所以这里用 ASCII。
    # 接入统一身份认证之后身份不再从请求头来，这个限制随之消失。
    headers = {"X-User": "newcomer-first-load"}
    responses = await asyncio.gather(
        client.get("/api/v1/me", headers=headers),
        client.get("/api/v1/notifications/unread-count", headers=headers),
        client.get("/api/v1/workspaces", headers=headers),
        return_exceptions=True,
    )

    for response in responses:
        assert not isinstance(response, BaseException), response
        assert response.status_code == 200, response.text

    # 而且只建出一个用户、一个个人空间，没有重复
    home = (await client.get("/api/v1/me", headers=headers)).json()
    assert len([w for w in home["workspaces"] if w["kind"] == "personal"]) == 1
