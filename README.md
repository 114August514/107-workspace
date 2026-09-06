# 107 Workspace

面向中国科学技术大学 107 算力平台的协作式计算工作空间。用户可以在浏览器中管理
Workspace 和 Project、保存 Project Version、配置并提交 Run，以及查看日志和
Artifact。

当前仓库是**可运行的开发基线**，不是 `docs/product/design.md` 路线图中 M1 已完成的声明。
现有实现覆盖 FastAPI 后端、React 控制台、数据库迁移、本地内容存储、Mock 调度和
Slurm REST 适配器；真实 Git、Shared FS、独立 Worker、Apptainer、学校认证和真实
Slurm 环境仍需要按现行 Milestone 验证或实现。

## 事实来源

| 内容 | 位置 |
| :--- | :--- |
| 产品能力、领域术语与规则 | [`docs/product/design.md`](docs/product/design.md) |
| 延后设计事项与已接受的实现妥协 | [`docs/product/deferred.md`](docs/product/deferred.md) |
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

只读 README 即可从零跑通。先满足环境前提，再按你要的形态二选一：
**本地开发**（`make dev`，源码热载）或 **容器**（Docker Compose，一体化演示）。

### 环境前提

| 工具 | 版本 | 用途 |
| :--- | :--- | :--- |
| Python | 3.12 | 后端与脚本 |
| [uv](https://docs.astral.sh/uv/) | 任意近期版 | Python 依赖与环境 |
| Node.js | 24 LTS | 前端构建 |
| pnpm | 11 | 前端依赖 |
| GNU Make | 任意 | 任务入口 |
| Docker + Compose 插件 | 任意 | 仅容器形态需要 |

支持 Linux 开发环境；Windows 主机只支持在 WSL2 中使用 Linux toolchain，并将仓库放在
WSL2 的 Linux filesystem。原生 Windows / PowerShell runtime 不受支持，部署与运行目标
均为 Linux。

### 方式一：本地开发（`make dev`）

```bash
make setup                                # 安装后端与前端依赖（等价 scripts/platform/posix/bootstrap.sh）
cp .env.example backend/.env              # 本地开发用 backend/.env
# 编辑 backend/.env，至少填：
#   WORKSPACE107_AUTH_SECRET_KEY=<随机长字符串>     # ustc 登录会话签名，必填
#   WORKSPACE107_LOCAL_ADMIN_PASSWORD=<本地账密>    # 本地账密登录，必填
make migrate                              # 初始化/升级数据库
make dev                                  # 拉起 后端 + 前端 + 认证服务
```

`make dev` 后逐一确认（全部应返回 200）：

```bash
curl -fsS http://127.0.0.1:8000/api/v1/ready   # 后端就绪且数据库可用
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5174/   # 前端可达
```

- 后端接口文档：<http://127.0.0.1:8000/docs>
- 前端入口：<http://127.0.0.1:5174>
- 模板默认 `WORKSPACE107_AUTH_MODE=ustc`：`make dev` 会拉起认证服务，Vite 对 `/api`
  做 `auth_request`，浏览器打开会看到公开登录页（本地账密 + 统一身份认证）。账密和
  会话密钥都写在 `backend/.env`，不要提交。把 `WORKSPACE107_AUTH_MODE` 改成 `dev`
  则跳过登录页，直接以 `student` 进入。

停止：`make dev` 前台运行，按 `Ctrl+C` 结束全部组件。

### 方式二：容器（Docker Compose）

```bash
cp .env.example .env                      # 容器用仓库根的 .env（注意：不是 backend/.env）
# 编辑 .env，至少改两项：
#   POSTGRES_PASSWORD=<强随机密码>          # Compose 必填
#   WORKSPACE107_AUTH_MODE=dev             # 模板默认 ustc，Compose web 无登录页，必须改成 dev
docker compose --project-directory . --file deploy/compose.yaml up -d --build
```

确认容器栈就绪：

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
curl -fsS http://127.0.0.1:8107/api/v1/ready   # 经 web 反代的后端就绪
```

浏览器访问 <http://127.0.0.1:8107>。上面把 `AUTH_MODE` 设为 `dev`，打开即已登录为
开发用户，**没有登录页**。

> 注意：本地开发的 `backend/.env`（`make dev` 用）与容器的根 `.env`（Compose 用）是
> 两个不同文件、必填项也不同。带登录页的 `:8107` 入口是
> [`deploy/cas-revproxy/`](deploy/cas-revproxy/README.md) 那套独立 Nginx（`auth_request`
> + `/login`），不要与 Compose 栈同时占用 `:8107`。

### 提交前

```bash
make check
```

任务入口、可选目标和平台边界见 [`scripts/README.md`](scripts/README.md)。

安装后端包后可用 rsync 将本地代码目录增量同步到有写权限的 Project：

```bash
107 project sync ./my-project <project-id-or-exact-name>
```

该入口需要部署方先配置受控 SSH 暂存目标（`WORKSPACE107_PROJECT_SYNC_SSH_TARGET` 与
`WORKSPACE107_PROJECT_SYNC_REMOTE_ROOT`，见 `.env.example`）；具体配置与 `.107ignore`
行为见 [`backend/README.md`](backend/README.md#project-本地目录同步)。

## 架构

后端是模块化单体，内部依赖按层次单向流动：

```text
api -> application -> domain ports <- infrastructure
```

- `backend/`：FastAPI、SQLAlchemy/Alembic、Scheduler/Storage 适配器和测试。
- `frontend/`：React、TypeScript、Vite 和从 OpenAPI 生成的接口类型。
- `contracts/`：后端导出、前端消费的 OpenAPI 机器契约。
- `deploy/`：可执行的容器编排和部署入口，不存放服务自己的镜像构建文件。
- `scripts/`：仓库公共 Python 任务实现和 Linux 引导脚本。
- `docs/operations/`：当前容器部署方式和上线前仍需满足的约束。

本地 `mock` 调度器会通过宿主机 shell **真实执行用户命令**，仅适合开发、测试和
受信任演示。它不是沙箱，也不能替代真实集群验收。

## 容器

容器形态的完整从零步骤见上文「快速开始 → 方式二」。共享存储、真实 Slurm 接入、
上线前最低条件与排障命令见
[`docs/operations/deployment.md`](docs/operations/deployment.md)。
