# 107 Workspace

面向中国科学技术大学 107 算力场景的协作式计算工作空间。平台以 Workspace、Project、
不可变 Version / Snapshot、Run、独立 Worker、调度执行、状态、日志和 Artifact 为核心
证据链，让计算更容易被正确、可靠地提交、观察、复现和追溯；访问、协作和复用能力围绕
这条主线演进。

当前近期交付是 [`Competition Minimum`](docs/product/design.md)：在受信任、非公开的
Linux / WSL2 或私有外部 Linux 服务器上，以明确标注的 Mock 模式展示不可变证据链、
Shared Resource 最小闭环、Fork、引导式 Run 和可观察授权边界。它不是产品终点，也不证明
真实 107 或生产就绪；M0–M5 是 Product V1 工程基线阶段，之后仍按活动产品设计演进。

当前仓库是**可运行的本地候选**，不是 Competition Minimum 或 M1 已完成的声明。现有实现
覆盖 FastAPI 后端、React 控制台、数据库迁移、真实 Git Project Version、独立 Worker、
Run workspace / Shared FS seam、本地内容存储、MockScheduler 和 Slurm REST 适配器。
Fork 后端与界面路径已经存在，但其 Run Configuration 来自源 Project 当前配置而非所选
版本；Run 终态和部分 Workspace 通知已经有站内通知与已读界面。Shared Resource 的实际
执行与非空 Input Binding 尚未实现，完整通知能力也尚未完成。

目标 107 当前 advertise 的 API profile 与候选不兼容，真实 profile、认证、三方存储 /
身份映射、correlation 恢复和端到端验收仍为 M1 `BLOCKED / HANDOFF`。Mock、本地 fixture
和个人 SSH / Tailscale / SCOW 操作探针都不能改变该状态。

## 事实来源

| 内容 | 位置 |
| :--- | :--- |
| 产品定位、Competition Minimum、三层 Roadmap、产品能力、领域术语与规则 | [`docs/product/design.md`](docs/product/design.md) |
| Git、分支、提交与评审 | [`docs/contributing/git-workflow.md`](docs/contributing/git-workflow.md) |
| AI 与工程协作入口 | [`AGENTS.md`](AGENTS.md) |
| 高影响工程决策 | [`docs/decisions/`](docs/decisions/README.md) |
| 在途工作记录 | [`docs/journal/`](docs/journal/) |
| 通用部署入口与运行边界 | [`deploy/`](deploy/README.md) 与 [`docs/operations/deployment.md`](docs/operations/deployment.md) |
| 真实 107 条件拓扑、运行事实与 M1 人工验收 | [`docs/operations/107-cluster.md`](docs/operations/107-cluster.md) |
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
- `docs/operations/`：通用容器部署方式、目标 107 当前运行事实和上线前约束。

本地 `mock` 调度器会通过宿主机 shell **真实执行用户命令**，仅适合开发、测试和
受信任演示。它不是沙箱，也不能替代真实集群验收。

## 容器

```bash
cp .env.example .env
# 设置 POSTGRES_PASSWORD
docker compose --project-directory . --file deploy/compose.yaml up -d --build
```

本机浏览器默认访问 <http://127.0.0.1:8107>。同一 Compose 可以运行在受信任、访问受控的
私有外部 Linux 演示服务器上，但不得直接作为公开服务；容器必须保持非 root。`.env`、OS
权限、防火墙和私有网络只是缓解措施，不是产品认证或隐私模型。Competition Minimum 边界见
[`docs/product/design.md`](docs/product/design.md)；部署和外部主机 TCB 见
[`docs/operations/deployment.md`](docs/operations/deployment.md)；真实 107 候选拓扑、运行事实与
M1 人工验收见 [`docs/operations/107-cluster.md`](docs/operations/107-cluster.md)。
