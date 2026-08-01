# 仓库任务入口

`workspace.py` 是任务的唯一实现，`Makefile` 只是方便使用的薄入口。没有 Make 的协作者，
包括使用原生 Windows 的协作者，直接运行同一个 Python CLI：

```powershell
uv run --no-project python scripts/workspace.py check
```

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

各平台的 bootstrap 文件只检查前置条件并进入公共 Python 工作流。质量检查、契约、迁移
和演示逻辑都不在 shell 或 PowerShell 中重复实现。

公共 CLI 不包含按平台复制的任务逻辑。CI 会在 Windows runner 上实际运行不依赖 Make
的入口，防止跨平台支持静默退化；Windows 兼容性以该 runner 的结果为准，不从 Linux
环境推测。
