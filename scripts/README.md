# 仓库任务入口

`workspace.py` 是任务的唯一实现，`Makefile` 是方便使用的薄入口。仓库支持 Linux，
以及 Windows 主机上使用 Linux toolchain 与 Linux filesystem 的 WSL2 环境；不支持
原生 Windows / PowerShell runtime。

前端工具链统一使用 Node.js 24 LTS 与 pnpm 11。仓库只提交
`frontend/pnpm-lock.yaml` 这一份前端依赖锁文件；同目录的 `pnpm-workspace.yaml` 只允许
esbuild 必需的安装脚本。

主要命令如下：

```text
setup                  按锁文件安装前后端依赖
check [target]         运行格式、lint、类型、测试、构建和契约检查
contract sync|check    重新生成或核对 OpenAPI 与前端类型
dev                    启动前后端开发服务（AUTH_MODE=dev，无登录页）
demo / smoke           验证隔离的 Project 到 Artifact 工作流
migrate / migrate-down 升级或回退一个数据库版本
coverage               生成后端覆盖率报告（重构期不设全仓门槛）
journal / audit        检查在途记录和需要评审的改动
doctor                 检查本地工程基线
```

`target` 可以是 `all`、`backend`、`frontend`；`check` 还支持 `contract`。
`dev` 默认 `WORKSPACE107_AUTH_MODE=dev`，浏览器不会出现登录页。公开登录页见
[`deploy/cas-revproxy/README.md`](../deploy/cas-revproxy/README.md)。

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
    └── posix/bootstrap.sh
```

bootstrap 文件只检查 Linux 前置条件并进入公共 Python 工作流。质量检查、契约、迁移
和演示逻辑不在 shell 中重复实现。公共 CLI 不包含按平台复制的任务逻辑，CI 只在实际
支持的 Linux 环境中验证这些入口。
