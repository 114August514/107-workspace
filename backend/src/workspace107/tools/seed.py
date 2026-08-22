"""载入本地开发 Compute Plans，以及显式请求的演示资产和 Project。

    uv run python -m workspace107.tools.seed
    uv run python -m workspace107.tools.seed --demo
    uv run python -m workspace107.tools.seed --demo --platform-owner-username <username>

不带 ``--demo`` 时只创建 Compute Plans。演示模式另建平台资产 User Group、平台
Environment/Version、演示 User Group 专用 Environment 和演示 Project；这些均不是
production provisioning。GPU 型号、分区、QoS 和配额都是演示值，不能当成 107 事实。
"""

from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import build_services
from ..application.run_configuration_service import RunConfigurationInput
from ..config import get_settings
from ..domain import ids
from ..domain.config_scope import ConfigScope
from ..domain.enums import LegacyWorkspaceKind, MembershipRole, MembershipStatus
from ..domain.pagination import PageRequest
from ..infrastructure.db import tables as t
from ..main import build_context

DEMO_USER = "student"
DEMO_PROJECT = "第一个训练任务"
DEMO_USER_GROUP_ID = "grp_demo"
DEMO_OWNER_MEMBERSHIP_ID = "mbr_demo_owner"
PLATFORM_ASSET_GROUP_ID = "grp_platform_assets"
PLATFORM_ENVIRONMENT_ID = "env_platform_python_base_2026"
DEMO_ENVIRONMENT_ID = "env_demo_python_2026"
DEMO_ENVIRONMENT_VERSION_ID = "ev_demo_python_312_2026"
PLATFORM_ENVIRONMENT_VERSION_ID = "ev_platform_python_312_2026"
PLATFORM_PYTORCH_ENVIRONMENT_ID = "env_platform_pytorch_2026"
PLATFORM_PYTORCH_ENVIRONMENT_VERSION_ID = "ev_platform_pytorch_24_2026"
PLATFORM_OWNER_ENV = "WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME"

_PLATFORM_ENVIRONMENTS = (
    {
        "id": PLATFORM_ENVIRONMENT_ID,
        "name": "Python 基础环境",
        "description": "通用 Python 运行环境，适合脚本、数据处理和入门实验。",
        "owner_user_id": None,
        "owner_user_group_id": PLATFORM_ASSET_GROUP_ID,
    },
    {
        "id": PLATFORM_PYTORCH_ENVIRONMENT_ID,
        "name": "PyTorch 环境",
        "description": "预装 PyTorch 的深度学习环境。具体版本以平台页面为准。",
        "owner_user_id": None,
        "owner_user_group_id": PLATFORM_ASSET_GROUP_ID,
    },
)

_PLATFORM_ENVIRONMENT_VERSIONS = (
    {
        "id": PLATFORM_ENVIRONMENT_VERSION_ID,
        "environment_id": PLATFORM_ENVIRONMENT_ID,
        "version": "3.12",
        "description": "Python 3.12 标准库环境。",
        "image": "python:3.12-slim",
        "setup_command": "",
        "available": True,
    },
    {
        "id": PLATFORM_PYTORCH_ENVIRONMENT_VERSION_ID,
        "environment_id": PLATFORM_PYTORCH_ENVIRONMENT_ID,
        "version": "2.4-cuda12.1",
        "description": "PyTorch 2.4 + CUDA 12.1。可用性以平台页面为准。",
        "image": "pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime",
        "setup_command": "",
        "available": True,
    },
)

DEMO_SCRIPT = '''"""演示训练脚本。

它不依赖任何第三方库，跑完会在 outputs/ 下留下结果文件。
把它换成你自己的训练代码即可。
"""

import json
import os
import pathlib
import random

OUTPUT_DIR = pathlib.Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

epochs = int(os.environ.get("EPOCHS", "5"))
seed = int(os.environ.get("SEED", "42"))
random.seed(seed)

history = []
loss = 2.0
for epoch in range(1, epochs + 1):
    loss = round(loss * random.uniform(0.55, 0.85), 4)
    accuracy = round(min(0.99, 1 - loss / 3), 4)
    history.append({"epoch": epoch, "loss": loss, "accuracy": accuracy})
    print(f"epoch {epoch}/{epochs}  loss={loss}  accuracy={accuracy}", flush=True)

result = {"epochs": epochs, "seed": seed, "final": history[-1], "history": history}
(OUTPUT_DIR / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("结果已写入 outputs/metrics.json")
'''

DEMO_README = """# 第一个训练任务

这是 107 Workspace 的演示项目，用来跑通完整的核心闭环：

```text
准备代码 -> 保存 Project Version -> 配置运行方案 -> 提交 Run
-> 查看状态 -> 查看日志 -> 获取 Artifact
```

`train.py` 不依赖第三方库，改成你自己的训练脚本即可。
"""


async def seed_catalog(session: AsyncSession) -> None:
    """幂等载入本地开发使用的 Compute Plans；不创建任何资产。"""
    existing = (
        await session.execute(select(func.count()).select_from(t.ComputePlanRow))
    ).scalar_one()
    if existing:
        return

    session.add_all(
        [
            t.ComputePlanRow(
                id="plan_cpu_quick",
                code="cpu-quick",
                name="CPU 快速测试",
                description="用于验证代码能不能跑起来，不适合正式训练。",
                default_nodes=1,
                default_cpus=2,
                default_memory_mb=4096,
                default_gpus=0,
                default_time_limit_minutes=15,
                max_nodes=1,
                max_cpus=4,
                max_memory_mb=8192,
                max_gpus=0,
                max_time_limit_minutes=30,
                cluster="107",
                account="undergraduate",
                partition="debug",
                qos="normal",
            ),
            t.ComputePlanRow(
                id="plan_cpu_standard",
                code="cpu-standard",
                name="CPU 标准",
                description="常规 CPU 计算任务。",
                default_nodes=1,
                default_cpus=8,
                default_memory_mb=16384,
                default_gpus=0,
                default_time_limit_minutes=120,
                max_nodes=2,
                max_cpus=32,
                max_memory_mb=65536,
                max_gpus=0,
                max_time_limit_minutes=1440,
                cluster="107",
                account="undergraduate",
                partition="cpu",
                qos="normal",
            ),
            t.ComputePlanRow(
                id="plan_gpu_standard",
                code="gpu-standard",
                name="GPU 标准",
                description="单卡 GPU 训练。GPU 型号以平台页面为准。",
                default_nodes=1,
                default_cpus=8,
                default_memory_mb=32768,
                default_gpus=1,
                default_time_limit_minutes=240,
                max_nodes=1,
                max_cpus=16,
                max_memory_mb=131072,
                max_gpus=2,
                max_time_limit_minutes=1440,
                cluster="107",
                account="undergraduate",
                partition="gpu",
                qos="normal",
            ),
        ]
    )
    await session.flush()


def _resolve_platform_owner_username(explicit: str | None) -> str:
    if explicit is not None:
        username = explicit.strip()
        if not username:
            raise ValueError("--platform-owner-username 不能为空")
        return username
    return os.environ.get(PLATFORM_OWNER_ENV, "").strip() or DEMO_USER


async def _ensure_platform_asset_group(
    session: AsyncSession,
    services,
    platform_owner_username: str | None,
    now,
) -> None:
    group = await session.get(t.UserGroupRow, PLATFORM_ASSET_GROUP_ID)
    if group is not None:
        return

    owner_username = _resolve_platform_owner_username(platform_owner_username)
    owner = await services.identity.ensure_user(owner_username)
    session.add(
        t.UserGroupRow(
            id=PLATFORM_ASSET_GROUP_ID,
            name="平台资产",
            description="平台管理员维护的运行环境和共享资源。",
            created_by_id=owner.id,
            created_at=now,
        )
    )
    await session.flush()
    session.add(
        t.LegacyWorkspaceRow(
            id=PLATFORM_ASSET_GROUP_ID,
            kind=LegacyWorkspaceKind.COLLABORATIVE.value,
            name="平台资产",
            description="平台管理员维护的运行环境和共享资源。",
            owner_id=owner.id,
            default_environment_version_id=None,
            created_at=now,
        )
    )
    session.add(
        t.MembershipRow(
            id=ids.new_id(ids.MEMBERSHIP),
            user_group_id=PLATFORM_ASSET_GROUP_ID,
            user_id=owner.id,
            role=MembershipRole.OWNER.value,
            status=MembershipStatus.ACTIVE.value,
            created_at=now,
        )
    )
    await session.flush()


def _assert_fixed_record(row, expected: dict[str, object], record_kind: str) -> None:
    conflicts = {
        field: (getattr(row, field), value)
        for field, value in expected.items()
        if getattr(row, field) != value
    }
    if conflicts:
        details = ", ".join(
            f"{field}={actual!r} (expected {wanted!r})"
            for field, (actual, wanted) in conflicts.items()
        )
        raise RuntimeError(f"conflicting fixed {record_kind} {expected['id']}: {details}")


async def _seed_platform_environments(session: AsyncSession) -> None:
    """Insert missing fixed platform assets and reject drift without rewriting it."""
    for expected in _PLATFORM_ENVIRONMENTS:
        row = await session.get(t.EnvironmentRow, expected["id"])
        if row is None:
            session.add(t.EnvironmentRow(**expected))
        else:
            _assert_fixed_record(row, expected, "Environment")
    await session.flush()

    for expected in _PLATFORM_ENVIRONMENT_VERSIONS:
        row = await session.get(t.EnvironmentVersionRow, expected["id"])
        if row is None:
            session.add(t.EnvironmentVersionRow(**expected))
        else:
            _assert_fixed_record(row, expected, "EnvironmentVersion")
    await session.flush()


async def _seed_demo_environment(session: AsyncSession) -> None:
    existing = await session.get(t.EnvironmentRow, DEMO_ENVIRONMENT_ID)
    if existing is not None:
        return
    session.add(
        t.EnvironmentRow(
            id=DEMO_ENVIRONMENT_ID,
            name="演示 Python 环境",
            description="演示 User Group 拥有的基础 Python 运行环境。",
            owner_user_group_id=DEMO_USER_GROUP_ID,
        )
    )
    await session.flush()
    session.add(
        t.EnvironmentVersionRow(
            id=DEMO_ENVIRONMENT_VERSION_ID,
            environment_id=DEMO_ENVIRONMENT_ID,
            version="3.12",
            description="Python 3.12 标准库环境。",
            image="python:3.12-slim",
            setup_command="",
        )
    )
    await session.flush()


async def seed_demo(
    session: AsyncSession,
    context,
    *,
    platform_owner_username: str | None = None,
) -> str:
    """创建演示用户、资产、Project、文件、版本和运行方案，返回 Project ID。"""
    services = build_services(context, session)
    user = await services.identity.ensure_user(DEMO_USER, "演示同学")
    now = context.clock.now()

    await _ensure_platform_asset_group(session, services, platform_owner_username, now)
    await _seed_platform_environments(session)
    group = await session.get(t.UserGroupRow, DEMO_USER_GROUP_ID)
    if group is None:
        group = t.UserGroupRow(
            id=DEMO_USER_GROUP_ID,
            name="演示 User Group",
            description="本地演示数据",
            created_by_id=user.id,
            created_at=now,
        )
        session.add(group)

    anchor = await session.get(t.LegacyWorkspaceRow, DEMO_USER_GROUP_ID)
    if anchor is None:
        anchor = t.LegacyWorkspaceRow(
            id=DEMO_USER_GROUP_ID,
            kind=LegacyWorkspaceKind.COLLABORATIVE.value,
            name=group.name,
            description=group.description,
            owner_id=user.id,
            default_environment_version_id=None,
            created_at=now,
        )
        session.add(anchor)
    await session.flush()

    membership = await session.get(t.MembershipRow, DEMO_OWNER_MEMBERSHIP_ID)
    if membership is None:
        session.add(
            t.MembershipRow(
                id=DEMO_OWNER_MEMBERSHIP_ID,
                user_group_id=DEMO_USER_GROUP_ID,
                user_id=user.id,
                role=MembershipRole.OWNER.value,
                status=MembershipStatus.ACTIVE.value,
                created_at=now,
            )
        )
        await session.flush()

    await _seed_demo_environment(session)

    entitlement = (
        await session.execute(
            select(t.ResourceEntitlementRow).where(
                t.ResourceEntitlementRow.workspace_id == DEMO_USER_GROUP_ID,
                t.ResourceEntitlementRow.compute_plan_id == "plan_cpu_quick",
            )
        )
    ).scalar_one_or_none()
    if entitlement is None:
        # Demo data explicitly opts into the still-legacy Run qualification model.
        # Creating a real User Group grants no Workspace-scoped entitlement.
        session.add(
            t.ResourceEntitlementRow(
                id=ids.new_id(ids.ENTITLEMENT),
                workspace_id=DEMO_USER_GROUP_ID,
                compute_plan_id="plan_cpu_quick",
                max_concurrent_runs=2,
                expires_at=None,
            )
        )
        await session.flush()

    # 幂等：已经载入过就直接返回，不重复创建
    existing = await services.projects.list_for_workspace(
        user.id, DEMO_USER_GROUP_ID, PageRequest()
    )
    for project in existing.items:
        if project.name == DEMO_PROJECT:
            return project.id

    await services.legacy_workspaces.set_default_environment(
        user.id, DEMO_USER_GROUP_ID, DEMO_ENVIRONMENT_VERSION_ID
    )

    project = await services.projects.create(
        user.id, DEMO_USER_GROUP_ID, DEMO_PROJECT, "跑通核心闭环的演示项目"
    )
    await services.projects.write_file(user.id, project.id, "train.py", DEMO_SCRIPT.encode("utf-8"))
    await services.projects.write_file(
        user.id, project.id, "README.md", DEMO_README.encode("utf-8")
    )
    await services.projects.save_version(user.id, project.id, "初始版本")

    await services.configuration.set_variable(
        ConfigScope.user_group(DEMO_USER_GROUP_ID), "EPOCHS", "5"
    )
    await services.run_configurations.create(
        user.id,
        project.id,
        RunConfigurationInput(
            name="默认运行",
            command="python train.py",
            compute_plan_id="plan_cpu_quick",
            description="用 CPU 快速测试方案跑一遍训练脚本",
            environment_variables={"EPOCHS": "${{ vars.EPOCHS }}", "SEED": "42"},
            artifact_rules=[{"path": "outputs", "name": "训练结果", "optional": False}],
        ),
    )
    return project.id


async def main(with_demo: bool, platform_owner_username: str | None = None) -> int:
    settings = get_settings()
    context = build_context(settings)
    session = context.session_factory()
    project_id: str | None = None
    try:
        await seed_catalog(session)
        if with_demo:
            project_id = await seed_demo(
                session,
                context,
                platform_owner_username=platform_owner_username,
            )
        await session.commit()
    finally:
        await session.close()
        await context.engine.dispose()

    print("本地开发 Compute Plans 已载入")
    if project_id is not None:
        print("本地演示资产已载入（平台资产 User Group 与演示 User Group 分开持有）")
        print(f"演示 Project：{project_id}")
        print(f"用请求头 {DEMO_USER!r} 访问，例如： curl -H 'X-User: {DEMO_USER}' …/api/v1/me")
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m workspace107.tools.seed",
        description="载入本地开发 Compute Plans；加 --demo 时再载入演示资产与 Project。",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="额外创建本地演示用户、资产、Project、版本和运行方案",
    )
    parser.add_argument(
        "--platform-owner-username",
        help=(
            f"平台资产 User Group 首次创建时的 Owner；优先于 {PLATFORM_OWNER_ENV}，默认 {DEMO_USER}"
        ),
    )
    args = parser.parse_args()
    return asyncio.run(
        main(
            with_demo=args.demo,
            platform_owner_username=args.platform_owner_username,
        )
    )


if __name__ == "__main__":
    raise SystemExit(cli())
