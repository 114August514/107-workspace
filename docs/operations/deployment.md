# 部署

这里说明当前 107 Workspace 应用容器在本机或受信任、访问受控的私有外部 Linux 服务器
上的运行方式，以及它距离真实集群和公开生产部署还差什么。容器编排是开发与私有演示
基线，不代表产品认证、隐私、生产验收或真实 107 已经完成。
可执行清单及目录边界见 [`deploy/README.md`](../../deploy/README.md)。以下命令均在仓库
根目录运行。

本部署拓扑和 M1 Worker 只支持 Linux / WSL2 的 POSIX 语义；原生 Windows 不属于部署
目标。权威平台矩阵见 [ADR-0004](../decisions/0004-platform-support-matrix.md)。

## 受信任的私有演示

```bash
cp .env.example .env
# 编辑 .env，至少设置 POSTGRES_PASSWORD
docker compose --project-directory . --file deploy/compose.yaml up -d --build
```

打开 <http://127.0.0.1:8107>。停止服务但保留数据：

```bash
docker compose --project-directory . --file deploy/compose.yaml down
```

`docker compose --project-directory . --file deploy/compose.yaml down -v` 会删除数据库和
存储卷，只能在明确不需要其中数据时执行。

默认从同一主机访问 `127.0.0.1`。也可以把 Compose 运行在私有外部 Linux 演示服务器上，
但入口必须只对受信任参与者开放，不得直接发布为公开服务，容器必须保持非 root。

`.env`、文件权限、防火墙、VPN 或私有网络只能降低暴露面，不提供产品认证或隐私语义。
应用仍须按 development persona 执行正常的 Workspace ownership、Membership、能力、
版本、路径、Secret 脱敏、幂等和 correlation 规则。外部主机的 root / admin 对该主机实际
控制的 API、数据库、存储、执行请求及放置其中的凭据属于 TCB；没有放在该主机上的集群
凭据不能因此被假定由它控制。公开访问必须先满足本页“上线前最低条件”，不能沿用 dev 身份。

## 拓扑

```text
browser :8107
      |
      v
web (nginx :8080)
      | /api
      v
api (uvicorn :8000) -------------> db (PostgreSQL)
      |
      `-- read-only B installed logs / Artifacts

independent worker --------------> db (PostgreSQL)
      |-- A ProjectVersionExporter -> installed Project Git content
      |-- B RunWorkspacePort ------> Shared FS workspace / logs / Artifact install
      `-- D SchedulerPort ---------> mock child process or slurmrestd
```

API 容器启动时会执行 Alembic 升级和幂等的平台目录 seed，然后启动应用。该流程假设
单个 API 实例；扩展到多副本之前，必须把迁移拆成独立的一次性任务。Run 的 workspace
准备、提交、取消和轮询只由单 active 的独立 Worker 执行；API 对 B 已安装日志和 Artifact
内容的适配器是只读的，不持有 Scheduler。

## 关键配置

完整变量和默认值见 [`.env.example`](../../.env.example)。

| 变量 | 说明 |
| :--- | :--- |
| `POSTGRES_PASSWORD` | 必填，不得使用可猜测的默认值 |
| `WORKSPACE107_HTTP_PORT` | Web 暴露端口，默认 `8107` |
| `WORKSPACE107_SCHEDULER` | 仅由 Worker 选择 `mock` 或 `slurm`；API 不构造 Scheduler |
| `WORKSPACE107_STORAGE_MOUNT` | API 只读查询 B installed 内容；Worker 与计算节点共享 workspace 来源 |
| `WORKSPACE107_SLURM_API_BASE_URL/USER/JWT` | 仅注入 Worker 的目标地址、身份与认证 Secret；不得提交或记录 JWT |
| `WORKSPACE107_SLURM_TARGET_CLUSTER_ID` | Worker 使用、与 slurmrestd endpoint 人工绑定的单一 cluster identity；Snapshot 必须精确匹配 |
| `WORKSPACE107_SLURM_API_VERSION/SCHEMA_PROFILE` | Worker 使用、经人工核验的版本与本地已实现 schema profile；不匹配即停止 |
| `WORKSPACE107_SLURM_*_PATH*` | Worker 使用、经人工核验的 submit/job/list/cancel 路径契约；无默认猜测 |
| `WORKSPACE107_SLURM_CORRELATION_*` | Worker 使用的完整 correlation 字段、精确查询参数、容量和查询完整性确认 |
| `WORKSPACE107_SLURM_RUNTIME_MODE` | Worker 当前候选只支持经人工确认的 `native`；`apptainer` 会 fail-fast |
| `WORKSPACE107_AUTH_MODE` | `dev` 只用于受信任、非公开的 development persona；不构成认证 |

镜像不包含凭据，`.env` 也不会进入 Git 或构建上下文；这只减少凭据泄露风险，不提供认证。

## Mock 不是沙箱

`WORKSPACE107_SCHEDULER=mock` 会由独立 Worker 在 **Worker 容器及其非 root 运行身份**下，
通过 shell 子进程真实执行 Run Configuration 的命令；Mock 子进程的创建、轮询和取消均归
Worker，不归 API。任何能提交 Run 的用户都能执行该 Worker 身份允许的命令，因此它只能用于
本地开发、自动化测试和受信任的私有演示，不能对不受信任用户开放。主机或容器权限限制只是
执行影响的边界，不会把 Mock 变成多租户沙箱。

`MockScheduler` adapter 保留 Windows 系统命令解释器分支并由 contributor check 覆盖；
POSIX 下使用 Bash。完整 Worker 组合仍只支持 Linux / WSL2，平台不会翻译 Project 命令。

## 接入真实集群

当前代码包含 Slurm REST 适配器，但切换配置不等于完成接入。个人 SSH / Tailscale / SCOW
runner 只是独立探针，不是部署方式、产品 bridge 或 `SshScheduler`。A2 / C / D 条件拓扑、
站点 gate、可复用运行事实与 M1 `BLOCKED / HANDOFF` 验收统一见
[`107 集群运行事实与 M1 人工验收`](107-cluster.md)。

### 共享存储

M1 由独立 Worker 准备 Run 目录、读取日志并安装 Artifact，计算节点负责实际执行；两者
必须对 Run 执行目录看到同一绝对路径。API 只通过只读适配器查询 B 已安装的日志和 Artifact：

```text
worker writes Run directory
        |
        v
shared filesystem
        ^
        |
compute node reads/writes it
```

Docker 命名卷只在单机 Docker 内可见，不满足真实 Slurm 计算节点的要求。Compose 中
`WORKSPACE107_STORAGE_MOUNT` 决定 API 与 Worker 容器的挂载来源，容器内应用路径固定为
`/var/lib/workspace107/storage`。Run 提交给 Slurm 时使用的是 Worker 可见路径，因此真实
接入时必须由人确认 API 的只读 installed-content 视图，以及 Worker 与每个计算节点的
canonical mount mapping，并验证：

1. Worker 和计算节点能以 `/var/lib/workspace107/storage` 访问同一份 Run 内容；API 在同一
   storage root 下只能通过只读 B 查询适配器读取已安装日志和 Artifact，不能准备或修复 workspace。
2. M1 只部署一个 active Worker，且部署、重启和滚动操作不得产生新旧 Worker overlap；
   B 不提供 per-Run/Artifact lock、claim 或多 writer takeover。
3. Worker 与计算任务使用不同 UID；两者属于配置的 `shared_gid`。Run root 为 `0750`，
   `work/`、`logs/` 和执行期 Artifact 目录为 setgid `02770`，stdout/stderr 为 `0660`，
   空 inputs 目录为只读 setgid `02550`；Worker 私有 `artifact-store/` 和 staging 控制目录
   为 `0700`/`0600`，计算 UID 不得 traverse。D 生成的 job wrapper 必须在执行用户命令前
   设置 `umask 0007`，保证新文件/目录不意外移除 shared GID 所需的 group 权限。
   同 UID 或计算 UID 不属于 `shared_gid` 时，部署验收必须失败。
4. M1 最小 Run 明确无 Input Binding；不得用仍属 M3 的 Shared Resource 替代 mount 证据。
5. 真实 service UID、compute UID、`shared_gid`、mount mapping 与同文件系统 atomic rename
   必须在目标 Shared FS 逐项 human gate；本地 stat/同 UID 子进程测试不能替代真实双 UID 验证。
6. M1 只承诺应用进程退出或重启后的 exporting/copying/finalizing 恢复，不承诺节点掉电、
   多 writer、滚动双活或任意 Shared FS power-loss durability。

只修改 `WORKSPACE107_STORAGE_MOUNT` 不会改变容器内应用路径；如果计算节点不能提供上述
固定路径，必须先调整部署映射和应用配置并完成端到端验证。

## 探针和排障

```text
GET /api/v1/health   只判断进程是否响应
GET /api/v1/ready    检查数据库是否可用
```

响应头和错误体包含 `request_id`。排障时记录它，并在 API 日志中按同一值检索。

常用命令：

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
docker compose --project-directory . --file deploy/compose.yaml logs -f api
docker compose --project-directory . --file deploy/compose.yaml exec api alembic current
docker compose --project-directory . --file deploy/compose.yaml exec api alembic history
```

## 上线前最低条件

- 使用强随机数据库密码，并确保 `.env` 未提交。
- 不向不受信任用户开放 Mock 调度器或 `dev` 身份模式。
- 完成真实 Slurm、共享存储、运行时和认证的环境验收。
- 将 seed 中的演示算力与环境目录替换为平台事实。
- 建立数据库和用户存储的备份、恢复、保留与清理流程。
- 在前置网关启用 HTTPS、访问控制、限流和日志采集。
- 验证 API 请求体上限与 nginx `client_max_body_size` 一致。
- 多副本部署前拆分数据库迁移和后台状态同步职责。

当前 Compose 没有提供 HTTPS、自动备份、多副本编排、监控告警或生产级 Secret
管理。这些缺口必须显式完成，不能依赖默认配置补齐。
