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

#### 裸机引导（什么都没有的 Ubuntu）

`make setup` / `bootstrap.sh` 只安装**项目内**的 Python 与 npm 依赖，**不会**替你装上表中的
系统级工具——裸机上第一步就会因缺 `git`/`curl` 而失败。在一台只有网络的 Ubuntu 24.04 上，
先执行下面这段把工具链装齐，再继续任一形态（以下命令已在裸 `ubuntu:24.04` 实测通过）：

```bash
sudo apt-get update
sudo apt-get install -y git curl make python3 python3-venv ca-certificates
curl -fsSL https://astral.sh/uv/install.sh | sh                 # 安装 uv
export PATH="$HOME/.local/bin:$PATH"
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo bash -  # Node 24 LTS 源
sudo apt-get install -y nodejs
sudo corepack enable                                            # 启用 pnpm（按仓库锁定 11.x）
```

之后 `git clone` 本仓库并进入目录，pnpm 会按 `frontend/package.json` 的
`packageManager: pnpm@11.18.0` 自动锁定版本。仅容器形态还需另外安装
[Docker Engine 与 Compose 插件](https://docs.docker.com/engine/install/ubuntu/)。

> 提示：`make setup` 在干净 clone 上一次通过；若在保留了旧 `node_modules` 的目录里复跑，
> pnpm 可能因无 TTY 拒绝清理而中止——删掉 `frontend/node_modules` 或设 `CI=true` 后重跑即可。

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

想先快速验证核心链路再决定是否常驻开发，可跑一次性演示（自带临时 SQLite + mock 调度 +
seed 数据，跑完即焚，不需要 `.env` 或 `make migrate`）：

```bash
make demo    # Project -> Version -> Run -> logs -> Artifact，成功结尾打印 Demo complete
```

`make demo` 用 mock 调度器在宿主机真实执行命令，只验证核心流程闭环，不代表真实集群验收。

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
>
> 重复部署或更换 `POSTGRES_PASSWORD` 前，先 `docker compose --project-directory . --file
> deploy/compose.yaml down -v` 清掉旧数据卷（**会删除数据库与存储数据**）。Compose 卷不在
> git 里，仅靠 `git clean` 清不掉；卷内残留的旧密码与新 `.env` 不一致会导致 api 容器
> 报 `password authentication failed` 起不来。

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

### 从演示走向真实部署

上面的两种方式默认都是 `mock` 调度 + dev/ustc 演示身份，**不是生产形态**。当以下条件
（字段 + 平台事实）就位并通过验收后，才谈得上真实集群部署：

| 领域 | 关键字段 / 前提 | 当前状态 |
| :--- | :--- | :--- |
| 调度器 | `WORKSPACE107_SCHEDULER=slurm` + `WORKSPACE107_SLURM_API_BASE_URL` / `_API_USER` / `_JWT` | 适配器已实现，未在真实 107 集群验收 |
| 共享存储 | API 与各计算节点以同一绝对路径 `/var/lib/workspace107/storage` 访问同一文件系统 | Docker 命名卷只单机可见，需真实共享 FS |
| 运行环境 | Environment Version 用平台 Modules 或经真实 Apptainer 校验的 SIF | seed 是演示目录，需替换为平台事实 |
| 身份认证 | 关闭 `dev` 模式，ustc 认证经真实环境验收 | Compose 默认 `dev`，无生产登录 |

切换配置不等于完成接入。共享存储拓扑、Slurm 接入验收、上线前最低条件（HTTPS、备份、
多副本拆分等）的权威说明见
[`docs/operations/deployment.md`](docs/operations/deployment.md#接入真实集群)；107 平台端到端
验收属于 Issue #7。

## 容器

容器形态的完整从零步骤见上文「快速开始 → 方式二」。共享存储、真实 Slurm 接入、
上线前最低条件与排障命令见
[`docs/operations/deployment.md`](docs/operations/deployment.md)。
