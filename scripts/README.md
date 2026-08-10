# 仓库任务入口

`workspace.py` 是任务的唯一实现，`Makefile` 只是 Linux / WSL2 上方便使用的薄入口。
原生 Windows 协作者直接运行同一个 Python CLI；该入口保留 setup/check 以及适用的
前端、API、Git 检查，不代表支持 M1 POSIX Worker、Shared FS、smoke 或部署：

```powershell
uv run --no-project python scripts/workspace.py check
```

权威能力边界见 [ADR-0004](../docs/decisions/0004-platform-support-matrix.md)。

前端工具链统一使用 Node.js 24 LTS 与 pnpm 11。仓库只提交
`frontend/pnpm-lock.yaml` 这一份前端依赖锁文件；同目录的 `pnpm-workspace.yaml` 只允许
esbuild 必需的安装脚本。

主要命令如下：

```text
setup                  按锁文件安装前后端依赖
check [target]         运行格式、lint、类型、测试、构建和契约检查
contract sync|check    重新生成或核对 OpenAPI 与前端类型
dev                    启动前后端开发服务
demo / smoke           验证隔离的 Project 到 Artifact 工作流
migrate / migrate-down 升级或回退一个数据库版本
coverage               生成后端覆盖率报告（重构期不设全仓门槛）
journal / audit        检查在途记录和需要评审的改动
doctor                 检查本地工程基线
```

`target` 可以是 `all`、`backend`、`frontend`；`check` 还支持 `contract`。

任务实现按职责分层：

```text
scripts/
├── workspace.py
├── tasks/
│   ├── common.py
│   ├── check.py
│   ├── contract.py
│   └── project.py
└── platform/
    ├── windows/bootstrap.ps1
    └── posix/bootstrap.sh
```

各平台的 bootstrap 文件只检查前置条件并进入公共 Python 工作流。质量检查、契约和迁移
逻辑不在 shell 或 PowerShell 中重复实现。

公共 CLI 不复制平台任务逻辑。CI 在 Windows runner 上实际运行 contributor setup/check；
依赖 POSIX UID/GID、signal 或文件系统语义的 adapter tests 只在 POSIX 执行。Windows
兼容性以该 runner 的结果为准，不从 Linux 环境推测；完整 Worker smoke 由 Linux
Compose + PostgreSQL job 负责。
