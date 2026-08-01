"""载入平台目录数据和演示项目。

    uv run python -m workspace107.tools.seed           只载入平台目录
    uv run python -m workspace107.tools.seed --demo    额外创建演示 Project

平台目录（运行环境、算力方案）在真实部署里由平台管理员维护（设计稿 2.13 E）。
本地开发和演示用这个脚本载入一份可用的初始数据。

**注意**：这里的 GPU 型号、分区、QoS 和配额都是演示值。
真实取值以平台页面和集群实际配置为准，不要当成固定结论。
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import build_services
from ..application.run_configuration_service import RunConfigurationInput
from ..config import get_settings
from ..domain.pagination import PageRequest
from ..infrastructure.db import tables as t
from ..main import build_context

DEMO_USER = "student"
DEMO_PROJECT = "第一个训练任务"

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
    """载入平台运行环境和算力方案。幂等，可以重复执行。"""
    existing = (
        await session.execute(select(func.count()).select_from(t.ComputePlanRow))
    ).scalar_one()
    if existing:
        return

    session.add_all(
        [
            t.EnvironmentRow(
                id="env_python_base",
                name="Python 基础环境",
                description="通用 Python 运行环境，适合脚本、数据处理和入门实验。",
            ),
            t.EnvironmentRow(
                id="env_pytorch",
                name="PyTorch 环境",
                description="预装 PyTorch 的深度学习环境。具体版本以平台页面为准。",
            ),
        ]
    )
    # 环境版本对环境有外键。这两张表之间没有 ORM relationship，
    # 同一次 flush 里的顺序不保证，所以先把环境落库。
    await session.flush()

    session.add_all(
        [
            t.EnvironmentVersionRow(
                id="ev_python_312",
                environment_id="env_python_base",
                version="3.12",
                description="Python 3.12 标准库环境。",
                image="python:3.12-slim",
                setup_command="",
            ),
            t.EnvironmentVersionRow(
                id="ev_pytorch_24",
                environment_id="env_pytorch",
                version="2.4-cuda12.1",
                description="PyTorch 2.4 + CUDA 12.1。可用性以平台页面为准。",
                image="pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime",
                setup_command="",
            ),
        ]
    )
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


async def seed_demo(session: AsyncSession, context) -> str:
    """创建演示用户、Project、文件、版本和运行方案，返回 Project ID。"""
    services = build_services(context, session)
    user = await services.workspaces.ensure_user(DEMO_USER, "演示同学")
    workspace = await services.workspaces.personal_workspace(user.id)

    # 幂等：已经载入过就直接返回，不重复创建
    existing = await services.projects.list_for_workspace(user.id, workspace.id, PageRequest())
    for project in existing.items:
        if project.name == DEMO_PROJECT:
            return project.id

    await services.workspaces.update(
        user.id, workspace.id, default_environment_version_id="ev_python_312"
    )

    project = await services.projects.create(
        user.id, workspace.id, DEMO_PROJECT, "跑通核心闭环的演示项目"
    )
    await services.projects.write_file(user.id, project.id, "train.py", DEMO_SCRIPT.encode("utf-8"))
    await services.projects.write_file(
        user.id, project.id, "README.md", DEMO_README.encode("utf-8")
    )
    await services.projects.save_version(user.id, project.id, "初始版本")

    await services.workspaces.set_variable(user.id, workspace.id, "EPOCHS", "5")
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


async def main(with_demo: bool) -> int:
    settings = get_settings()
    context = build_context(settings)
    session = context.session_factory()
    project_id: str | None = None
    try:
        await seed_catalog(session)
        if with_demo:
            project_id = await seed_demo(session, context)
        await session.commit()
    finally:
        await session.close()
        await context.engine.dispose()

    print("平台目录已载入（运行环境与算力方案）")
    if project_id is not None:
        print(f"演示 Project：{project_id}")
        print(f"用请求头 {DEMO_USER!r} 访问，例如： curl -H 'X-User: {DEMO_USER}' …/api/v1/me")
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m workspace107.tools.seed",
        description="载入平台目录数据；加 --demo 时额外创建演示 Project。",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="额外创建演示用户、Project、版本和运行方案",
    )
    args = parser.parse_args()
    return asyncio.run(main(with_demo=args.demo))


if __name__ == "__main__":
    raise SystemExit(cli())
