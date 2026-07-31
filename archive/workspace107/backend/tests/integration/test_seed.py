"""种子脚本。

它不在业务代码路径上，但**每次容器启动都会跑**：平台目录是应用能工作的
前提，演示数据是新人第一次看到的东西。没有测试的话，一次重构就能把它写坏，
而且要等到 `docker compose up` 才发现——这正是它被写出来的原因。
"""

from __future__ import annotations

from workspace107.api.deps import build_services
from workspace107.tools.seed import DEMO_PROJECT, DEMO_USER, seed_catalog, seed_demo


async def test_载入平台目录是幂等的(session) -> None:
    """容器每次启动都会跑一遍，不能每次都往里塞一份。"""
    await seed_catalog(session)
    await seed_catalog(session)
    await session.commit()

    from sqlalchemy import func, select

    from workspace107.infrastructure.db import tables as t

    plans = (await session.execute(select(func.count()).select_from(t.ComputePlanRow))).scalar_one()
    assert plans == 3


async def test_演示数据能完整创建出来(context, session) -> None:
    project_id = await seed_demo(session, context)
    await session.commit()

    services = build_services(context, session)
    user = await services.workspaces.ensure_user(DEMO_USER)
    access = await services.projects.get(user.id, project_id)

    assert access.project.name == DEMO_PROJECT

    files = await services.projects.list_files(user.id, project_id)
    assert {f.path for f in files} == {"train.py", "README.md"}

    # 演示项目必须开箱即可提交：版本、运行方案、默认环境都要齐
    from workspace107.domain.pagination import PageRequest

    versions = await services.projects.list_versions(user.id, project_id, PageRequest())
    assert versions.total == 1

    configurations = await services.run_configurations.list_for_project(user.id, project_id)
    assert len(configurations) == 1
    assert configurations[0].command == "python train.py"

    workspace = await services.workspaces.personal_workspace(user.id)
    assert workspace.default_environment_version_id == "ev_python_312"


async def test_重复载入演示数据不会创建第二个项目(context, session) -> None:
    first = await seed_demo(session, context)
    second = await seed_demo(session, context)
    await session.commit()

    assert first == second
