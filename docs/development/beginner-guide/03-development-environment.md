# 第三章：搭建开发环境

本章只覆盖仓库实际使用的工具和命令。安装前先确认你位于 `107-workspace/` 根目录，而不是
它的上级目录。

## 3.1 所需工具

| 工具 | 仓库要求 | 用途 |
| --- | --- | --- |
| Python | 3.12（项目允许 `<3.14`） | 后端和仓库任务脚本 |
| uv | 使用当前稳定版本 | Python 依赖、虚拟环境和命令运行 |
| Node.js | 24 LTS | 前端工具运行时 |
| pnpm | 11 | 前端依赖管理 |
| Git | 较新的稳定版本 | 版本控制与协作 |
| GNU Make | 可选 | 转发到统一 Python 任务入口 |
| Docker Compose | 使用容器演示时需要 | 启动 Web、API 和 PostgreSQL |

版本约束分别记录在 `backend/pyproject.toml`、`.node-version` 和
`frontend/package.json` 中。不要同时使用 npm、yarn 和 pnpm；仓库只提交 pnpm 锁文件。

## 3.2 自动引导

POSIX 系统运行：

```bash
./scripts/platform/posix/bootstrap.sh
```

Windows PowerShell 运行：

```powershell
.\scripts\platform\windows\bootstrap.ps1
```

平台脚本只负责检查前置条件并进入公共 Python 工作流，真正的任务逻辑位于
`scripts/workspace.py` 和 `scripts/tasks/`。如果引导失败，先阅读最后一条明确错误，不要通过
删除锁文件或改版本约束绕过检查。

也可以在根目录运行：

```bash
make doctor
make setup
```

`doctor` 检查本地工程基线，`setup` 按锁文件安装前后端依赖。

## 3.3 本地配置

后端配置统一使用 `WORKSPACE107_*` 环境变量。复制模板：

```bash
cp .env.example backend/.env
```

默认配置使用 SQLite、本地 `var/storage`、Mock Scheduler 和开发身份，适合本机开发。几个最
常见的变量是：

| 变量 | 本地作用 |
| --- | --- |
| `WORKSPACE107_DATABASE_URL` | 数据库连接地址 |
| `WORKSPACE107_STORAGE_ROOT` | Project 文件、Run 目录、日志和 Artifact 根目录 |
| `WORKSPACE107_SCHEDULER` | `mock` 或 `slurm` |
| `WORKSPACE107_AUTH_MODE` | 本地通常为 `dev` |
| `WORKSPACE107_RUN_SYNC_INTERVAL_SECONDS` | 后台同步 Run 状态的间隔 |

`.env` 可能包含真实凭据，已被 Git 忽略。不要修改 `.gitignore` 后把它提交，也不要把真实
JWT 写回 `.env.example`。

## 3.4 初始化数据库

执行所有数据库迁移：

```bash
make migrate
```

需要演示数据时，在后端目录运行种子命令：

```bash
cd backend
uv run python -m workspace107.tools.seed
cd ..
```

`make dev` 不会自动写入演示数据。迁移失败时不要直接删除迁移文件；先确认数据库地址、依赖
安装和当前迁移版本。

仓库还提供：

```bash
make migrate-down
```

它回退一个版本。涉及迁移的改动在合并前必须实际验证升级和回退，不过当前协作规则要求修改
迁移相关代码前先提出来由维护者决定。

## 3.5 启动项目

在根目录运行：

```bash
make dev
```

默认地址：

- 前端：<http://127.0.0.1:5173>
- 后端 OpenAPI 文档：<http://127.0.0.1:8000/docs>
- 后端健康检查：<http://127.0.0.1:8000/api/v1/health>

前端开发服务器把 `/api` 代理到 `127.0.0.1:8000`，因此前端源代码不应硬编码后端地址。

开发模式以 `X-User` 请求头识别身份。可以用命令验证后端：

```bash
curl -H 'X-User: student' http://127.0.0.1:8000/api/v1/me
```

第一次出现的用户会自动创建，并准备 Personal Workspace。前端右上角的用户切换控件本质上
设置同一个开发身份。

## 3.6 认识日常命令

| 命令 | 何时使用 |
| --- | --- |
| `make dev` | 启动前后端开发服务 |
| `make fmt` | 自动格式化可安全处理的代码 |
| `make test` | 运行活动测试 |
| `make check-backend` | 只检查后端 |
| `make check-frontend` | 只检查前端 |
| `make contract` | 更新 OpenAPI 和前端生成类型 |
| `make coverage` | 生成后端覆盖率报告 |
| `make journal` | 查看在途工作和孤儿记录 |
| `make check` | 提交前运行全部统一检查 |

Makefile 只是薄入口。Windows 上对应的完整检查为：

```powershell
uv run --no-project python scripts/workspace.py check
```

不要在 CI 中另写一套直接调用 Pytest 或 pnpm 的流程；统一入口的目的就是让本地和 CI 使用
相同检查链。

## 3.7 常见启动问题

### 找不到命令

先运行 `make doctor`，确认 Python、uv、Node 和 pnpm 的版本与 PATH。关闭并重新打开终端
有时是让新安装 PATH 生效的必要步骤。

### 前端能打开但请求失败

确认后端 `8000` 端口正在监听，并直接访问健康检查。再查看浏览器开发者工具的 Network
面板，记录失败请求的状态码和 `request_id`。

### 数据库报错

确认 `backend/.env` 中的数据库地址。SQLite 文件所在目录需要可写；PostgreSQL 则要确认
服务、用户、密码和数据库名。

### Mock Run 执行失败

Mock 会通过当前系统的命令解释器真实运行用户命令。确认命令本身能在本机运行，并检查
`var/storage/runs/<run_id>/job.sh`、Run 日志和进程退出码。Windows 与 POSIX 的 Shell 语法
不同，平台不会自动翻译命令。
