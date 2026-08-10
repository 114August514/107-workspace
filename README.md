# 107 Workspace

面向中国科学技术大学 107 算力平台的协作式计算工作空间。用户可以在浏览器中管理
Workspace 和 Project、保存 Project Version、配置并提交 Run，以及查看日志和
Artifact。

当前仓库是**可运行的开发基线**，不是 `docs/product/design.md` 路线图中 M1 已完成的声明。
现有实现覆盖 FastAPI 后端、React 控制台、数据库迁移、真实 Git Project Version、
本地内容存储、Mock 调度和 Slurm REST 适配器；Shared FS、独立 Worker、Apptainer、
学校认证和真实 Slurm 环境仍需要按现行 Milestone 验证或实现。

## 事实来源

| 内容 | 位置 |
| :--- | :--- |
| 产品能力、领域术语与规则 | [`docs/product/design.md`](docs/product/design.md) |
| Git、分支、提交与评审 | [`docs/contributing/git-workflow.md`](docs/contributing/git-workflow.md) |
| AI 与工程协作入口 | [`AGENTS.md`](AGENTS.md) |
| 高影响工程决策 | [`docs/decisions/`](docs/decisions/README.md) |
| 在途工作记录 | [`docs/journal/`](docs/journal/) |
| 部署入口与运行边界 | [`deploy/`](deploy/README.md) 与 [`docs/operations/`](docs/operations/deployment.md) |
| 前后端 API 机器契约 | [`contracts/`](contracts/README.md) |

迁移来源 `workspace107@293c8d8` 的完整快照保存在
[`archive/workspace107/`](archive/workspace107/ARCHIVE.md)。归档只用于审查和追溯，
不参与活动代码的构建与验证。

## 快速开始

平台能力边界以 [ADR-0004](docs/decisions/0004-platform-support-matrix.md) 为准。完整开发运行
目标是 Linux；WSL2 按 Linux 语义使用，仓库、storage 与 PostgreSQL 数据必须放在 Linux
filesystem，Ubuntu CI 结果不等于 WSL2 实机证据。

需要 Python 3.12、[uv](https://docs.astral.sh/uv/)、Node.js 24 LTS 和 pnpm 11。

```bash
# Linux / WSL2
./scripts/platform/posix/bootstrap.sh
make migrate
make dev
```

原生 Windows 保留无 Make 的 contributor setup/check，以及前端、API、Git 和
MockScheduler NT 分支；不运行 M1 POSIX Worker、Shared FS、smoke 或部署：

```powershell
.\scripts\platform\windows\bootstrap.ps1
uv run --no-project python scripts/workspace.py check
```

后端接口文档默认位于 <http://127.0.0.1:8000/docs>，前端默认位于
<http://127.0.0.1:5173>。

Linux / WSL2 提交前运行统一检查：

```bash
make check
```

任务入口、可选目标和平台边界见 [`scripts/README.md`](scripts/README.md)。

## 架构

后端是模块化单体，内部依赖按层次单向流动：

```text
api -> application -> domain ports <- infrastructure
```

- `backend/`：FastAPI、SQLAlchemy/Alembic、Scheduler/Storage 适配器和测试。
- `frontend/`：React、TypeScript、Vite 和从 OpenAPI 生成的接口类型。
- `contracts/`：后端导出、前端消费的 OpenAPI 机器契约。
- `deploy/`：可执行的容器编排和部署入口，不存放服务自己的镜像构建文件。
- `scripts/`：跨平台 Python 任务实现，以及位于平台边缘的引导脚本。
- `docs/operations/`：当前容器部署方式和上线前仍需满足的约束。

本地 `mock` 调度器会通过宿主机 shell **真实执行用户命令**，仅适合开发、测试和
受信任演示。它不是沙箱，也不能替代真实集群验收。

## 容器

```bash
cp .env.example .env
# 设置 POSTGRES_PASSWORD
docker compose --project-directory . --file deploy/compose.yaml up -d --build
```

浏览器访问 <http://127.0.0.1:8107>。部署和共享存储约束见
[`docs/operations/deployment.md`](docs/operations/deployment.md)。
