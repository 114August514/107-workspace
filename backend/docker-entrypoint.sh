#!/bin/sh
# 容器启动流程：升级数据库结构 → 载入平台目录 → 拉起应用。
#
# 前提是单实例部署。多副本同时启动会有迁移竞争，那时要把迁移拆成
# 独立的一次性任务；部署边界见 docs/operations/deployment.md。
set -eu

echo "==> 应用数据库迁移"
alembic upgrade head

echo "==> 载入平台目录（运行环境与算力方案）"
if [ "${WORKSPACE107_SEED_DEMO:-false}" = "true" ]; then
  # 演示数据是给人看的，默认不载入，由 WORKSPACE107_SEED_DEMO 显式打开。
  python -m workspace107.tools.seed --demo
else
  python -m workspace107.tools.seed
fi

if [ "${WORKSPACE107_SCHEDULER:-mock}" = "mock" ]; then
  echo "!!  当前使用 mock 调度器：用户作业会在本容器内以子进程执行。"
  echo "!!  仅用于演示和内部试用，对外提供服务必须切换到 slurm。"
fi

echo "==> 启动 $*"
exec "$@"
