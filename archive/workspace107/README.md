# 107 Workspace

面向中国科学技术大学 107 算力平台的协作式计算工作空间。

用户在浏览器里管理项目、保存版本、配置运行方案并提交计算作业，
不需要直接编写 `sbatch` 脚本或记忆分区、QoS 等调度参数。

```text
创建 Project → 准备代码 → 保存 Project Version → 配置运行方案
→ 提交 Run → 查看状态 → 查看日志 → 获取 Artifact
```

当前阶段：**M1 Core Run Loop**。范围与完成标准见
[`docs/milestones/M1-core-run-loop.md`](docs/milestones/M1-core-run-loop.md)。

## 仓库结构

```text
workspace107/
├── backend/          FastAPI 服务，分层单体
├── frontend/         React + TypeScript 控制台
├── docs/
│   ├── product/      产品设计最终稿
│   ├── domain/       领域语言与全局不变量
│   ├── milestones/   阶段目标与完成标准
│   ├── development/  Git 工作流、Commit 规范、评审规范
│   └── api/          生成的 OpenAPI Contract
└── scripts/          本地自检与开发脚本
```

## 架构

后端是模块化单体，依赖方向单向：

```text
api  →  application  →  domain ports  ←  infrastructure
```

- `domain/` 领域对象、枚举、不变量和端口定义。不依赖框架，不 import
  `fastapi` 或 `sqlalchemy`。
- `application/` 用例编排、权限校验、事务边界。只依赖 domain 中的端口。
- `infrastructure/` 端口的具体实现：数据库仓储、文件存储、调度适配器。
- `api/` HTTP 路由与 schema。不写业务规则。

调度通过 `SchedulerPort` 抽象，提供两个适配器：

| 适配器 | 用途 |
| :--- | :--- |
| `mock` | 在本机以子进程真实执行作业，用于开发、测试和演示 |
| `slurm` | 通过 Slurm REST API 提交到真实集群 |

按 GR-015，Slurm 是实际调度状态的事实来源，107 不重新实现调度算法。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 和 Node 22+。

```bash
git clone <仓库地址>
cd workspace107
cp .env.example backend/.env
```

后端：

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run python -m workspace107.tools.seed        # 载入演示数据
uv run uvicorn workspace107.main:create_app --factory --reload
```

接口文档在 <http://127.0.0.1:8000/docs>。

前端：

```bash
cd frontend
npm ci
npm run dev
```

控制台在 <http://127.0.0.1:5173>。

一条命令跑通端到端演示（创建项目 → 提交 Run → 取回 Artifact）：

```bash
./scripts/demo.sh
```

## 开发

提交前自检，和 CI 执行同一组命令：

```bash
./scripts/check.sh
```

单项命令：

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run format:check && npm run lint && npm run typecheck && npm run test -- --run && npm run build
```

修改了 API 之后重新生成 Contract，否则 CI 的 `api-contract-check` 会失败：

```bash
./scripts/sync-api-contract.sh
```

## 容器部署

```bash
cp .env.example .env      # 至少填上 POSTGRES_PASSWORD
docker compose up -d --build
```

打开 <http://127.0.0.1:8107>。三个容器：PostgreSQL、后端、nginx（前端静态资源 +
`/api` 反代）。启动时自动执行数据库迁移并载入平台目录。

默认使用 `mock` 调度器，**用户作业会在后端容器内执行**——仅用于演示和内部试用。
对外提供服务、接入真实 107 集群的完整说明见 [`deploy/README.md`](deploy/README.md)，
其中有一条容易踩的约束：用 Slurm 时存储必须是计算节点也能看到的共享文件系统。

## 配置

所有配置通过环境变量注入，变量清单见 [`.env.example`](.env.example)。

**Slurm JWT 等价于密码**，只能通过环境变量提供，不得写入代码或提交仓库。
仓库中只保留 `.env.example`，且只有变量名和说明。

## 参与开发

先读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。团队约定一句话：

> Issue 说明要做什么，分支隔离修改，Commit 记录过程，PR 完成评审，
> CI 保证基本质量，main 保存可信版本。

## 文档

先看 [文档索引](docs/README.md)，里面有一张「改哪块先读什么」的表。

- [产品设计最终稿](docs/product/design-final.md)
- [领域语言](docs/domain/glossary.md)
- [全局不变量](docs/domain/invariants.md)
- [Milestone 规划](docs/milestones/README.md)
- [设计决策记录](docs/decisions/README.md)
- [部署说明](deploy/README.md)
- [参考材料](docs/references/README.md)
- [Git 工作流](docs/development/git-workflow.md)
- [Commit 规范](docs/development/commit-convention.md)
- [代码评审规范](docs/development/code-review.md)
- [Git 问题处理](docs/development/troubleshooting-git.md)
