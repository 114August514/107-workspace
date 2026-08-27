# 仓库任务入口

`scripts/workspace.py` 是任务的唯一实现；`Makefile` 是薄入口。支持 Linux，以及使用 Linux
toolchain 与 Linux filesystem 的 WSL2；原生 Windows / PowerShell runtime 不受支持。统一
Python CLI 不构成跨平台承诺。权威边界见
[ADR-0005](../docs/decisions/0005-platform-support-matrix.md)。

前端工具链统一使用 Node.js 24 LTS 与 pnpm 11。仓库只提交
`frontend/pnpm-lock.yaml` 这一份前端 lockfile。

```text
setup                  按 lockfile 安装前后端依赖
check [target]         运行格式、lint、类型、测试、构建和 contract check
contract sync|check    重新生成或核对 OpenAPI 与前端类型
dev                    启动前后端开发服务
demo / smoke           API + PostgreSQL + 独立 Worker + Mock Scheduler 闭环
migrate / migrate-down 升级或回退一个数据库版本
coverage               生成后端 coverage report（不设全仓门槛）
journal / audit        检查在途记录和需要评审的改动
doctor                 检查本地工程基线
```

`target` 可以是 `all`、`backend`、`frontend`；`check` 还支持 `contract`。

默认 `smoke` 在没有配置 PostgreSQL 时自行启动临时 PostgreSQL container；每次调用都创建唯一
database 和临时 storage，并以 backend venv 的 exact interpreter 执行本地 demo workload。结束后
清理自己创建的 container、database、进程与目录。

外部栈模式不把控制机的 venv 路径发送给目标 Worker；默认使用目标环境的 `python3 train.py`。
目标环境需要其他命令时显式设置 `WORKSPACE107_EXTERNAL_SMOKE_COMMAND`：

```bash
WORKSPACE107_EXTERNAL_SMOKE_COMMAND="python3 train.py" \
uv run --no-project python scripts/workspace.py smoke \
  --base-url http://127.0.0.1:8107/api/v1
```

外部模式不启动/停止服务，也不清理目标栈业务数据。

```text
scripts/
├── workspace.py
├── tasks/
│   ├── common.py
│   ├── check.py
│   ├── contract.py
│   └── project.py
└── platform/
    └── posix/bootstrap.sh
```

bootstrap 只检查平台前置条件并进入公共 Python workflow；质量检查、contract、migration 和 smoke
逻辑不在 shell 中复制。完整 executable smoke 由 Linux + PostgreSQL 承担，Ubuntu 结果不能被
描述成 WSL2 实机证据。
