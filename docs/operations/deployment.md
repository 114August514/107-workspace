# 部署

这里说明当前 107 Workspace 应用容器的运行方式，以及它距离真实集群部署还差什么。
容器编排是开发和受信任演示基线，不代表生产验收已经完成。
可执行清单及目录边界见 [`deploy/README.md`](../../deploy/README.md)。以下命令均在仓库
根目录运行。

## 本机演示

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

## 拓扑

```text
browser :8107
      |
      v
web (nginx :8080)
      | /api
      v
api (uvicorn :8000) ---> db (PostgreSQL)
      |
      +-- local/shared storage
      +-- mock process or slurmrestd
```

API 容器启动时会执行 Alembic 升级和幂等的平台目录 seed，然后启动应用。该流程假设
单个 API 实例；扩展到多副本之前，必须把迁移拆成独立的一次性任务。

## 关键配置

完整变量和默认值见 [`.env.example`](../../.env.example)。

| 变量 | 说明 |
| :--- | :--- |
| `POSTGRES_PASSWORD` | 必填，不得使用可猜测的默认值 |
| `WORKSPACE107_HTTP_PORT` | Web 暴露端口，默认 `8107` |
| `WORKSPACE107_SCHEDULER` | `mock` 或 `slurm` |
| `WORKSPACE107_STORAGE_MOUNT` | API、Worker 与计算节点需要共同看到的存储来源 |
| `WORKSPACE107_SLURM_API_BASE_URL/USER/JWT` | 目标地址、身份与运行时注入的认证 Secret；不得提交或记录 JWT |
| `WORKSPACE107_SLURM_TARGET_CLUSTER_ID` | 与 slurmrestd endpoint 人工绑定的单一 cluster identity；Snapshot 必须精确匹配 |
| `WORKSPACE107_SLURM_API_VERSION/SCHEMA_PROFILE` | 人工核验的版本与本地已实现 schema profile；不匹配即停止 |
| `WORKSPACE107_SLURM_*_PATH*` | 人工核验的 submit/job/list/cancel 路径契约；无默认猜测 |
| `WORKSPACE107_SLURM_CORRELATION_*` | 完整 correlation 的字段、精确查询参数、容量和查询完整性确认 |
| `WORKSPACE107_SLURM_RUNTIME_MODE` | 当前候选只支持经人工确认的 `native`；`apptainer` 会 fail-fast |
| `WORKSPACE107_AUTH_MODE` | `dev` 仅用于本地；真实部署必须替换 |

镜像不包含凭据，`.env` 也不会进入 Git 或构建上下文。

## Mock 不是沙箱

`WORKSPACE107_SCHEDULER=mock` 会在 API 进程所在主机或容器中，通过宿主 shell 真实
执行 Run Configuration 的命令。任何能提交 Run 的用户都能执行该运行身份允许的
命令，因此它只能用于本地开发、自动化测试和受信任演示，不能对不受信任用户开放。

Windows 下 Mock 使用系统命令解释器，POSIX 下使用 Bash。命令本身是否跨平台仍由
Project 负责；平台不会自动翻译 shell 语法。

## 接入真实集群

当前代码包含 Slurm REST 适配器，但尚未在真实 107 集群完成版本、认证、网络和状态
映射验收。切换配置不等于完成接入。

### 共享存储

M1 由独立 Worker 准备 Run 目录、读取日志并安装 Artifact，计算节点负责实际执行。API、
Worker 与计算节点必须对 Run 执行目录看到同一绝对路径：

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
`WORKSPACE107_STORAGE_MOUNT` 只决定 API 容器的挂载来源，容器内应用路径固定为
`/var/lib/workspace107/storage`。Run 提交给 Slurm 时使用的是 Worker 可见路径，因此真实
接入时必须由人确认 API、Worker 与每个计算节点的 canonical mount mapping，并验证：

1. API、Worker 和计算节点都能以 `/var/lib/workspace107/storage` 访问同一份 Run 内容；不能依赖容器私有路径巧合。
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

### Slurm 与运行环境：M1 人工验收 runbook

当前实现只是**本地候选**：唯一 schema profile 由确定性 v0.0.40 fixture 覆盖，并不证明
目标 107 使用该版本、路径或字段。Agent 不登录 SCOW、不调用 SSH、不挂载共享存储、
不获取 JWT，也不提交或查询真实作业。以下步骤只能由获授权的人在新的受控窗口执行。

> **Human gate BLOCKER（历史输入冲突）**：2026-06 培训 PDF 只能作为待核对的历史输入；
> 它描述共享路径为 `/public` 与 `/home`、Slurm 25.11、REST 路径为
> `/slurm/v0.0.41/*`，并使用 `Authorization: Bearer`。这些描述与当前仅供本地 fixture
> 验证的 v0.0.40 profile、`X-SLURM-*` 认证 header 及现有 mount 假设明显冲突，不能直接
> 写入默认配置或据此扩展 adapter。必须先调查成熟项目或官方 v0.0.41 契约，再由实际环境
> 确认版本、path、认证和 mount mapping；在此之前不得启用 Slurm profile 或执行真实验收。

#### 1. 提交前记录并再次确认

先在脱敏记录中逐项写下“已确认/未确认”；任何一项未确认就停止，保持
`WORKSPACE107_SCHEDULER=mock`：

1. slurmrestd endpoint 对应的单一目标 cluster identity、真实 Slurm 版本、可用 API version、
   submit/job/list/cancel path 及响应 schema。把脱敏后的 identity 记录为
   `WORKSPACE107_SLURM_TARGET_CLUSTER_ID`；Snapshot 的 `scheduler.cluster` 必须精确匹配，
   mismatch 会在 HTTP 前拒绝。只有目标版本与已审 profile 一致时才能配置；不同版本必须先
   增加并评审 profile，不能把 `v0.0.40` 当作 107 事实。
2. 认证 header 和 JWT 生命周期。JWT 只由 Secret 管理设施注入进程内存，不进入命令行、
   `.env`、日志、异常、数据库、evidence bundle 或 sbatch 正文。
3. Slurm `comment` 是否能无截断保存完整 correlation、最大字节数、精确查询参数与查询权限；
   还要证明结果没有隐藏分页。只有这些证据齐全才能把
   `WORKSPACE107_SLURM_CORRELATION_QUERY_COMPLETE` 设为 `true`。权限、网络、分页、metadata、
   filter 或 schema 任一不确定时，adapter 返回 `complete=false`，不得把空 `job_ids` 当作零匹配。
4. 本次获批的 Account、Partition、QoS、nodes、tasks、CPU、memory、GPU GRES 和 time limit。
   当前 M1 adapter 只接受 `nodes=1`，将总 CPU/memory/GPU 安全映射到这个节点的单个 task；
   `nodes>1` 会在 HTTP 前 fail-fast，不能把总量静默放大为 per-node 资源。
5. API、独立 Worker、Shared FS 和计算节点的 mount mapping、canonical path、UID/GID 与权限。
6. 选择 Native 还是 Apptainer。当前只实现 Native：所选 Environment Version 的
   `environment_image` 必须为空，`setup_command` 必须是已批准的原生环境准备步骤。
   需要 Apptainer 时必须停止；当前配置会 fail-fast，没有 no-op 或 Native fallback。
7. C Worker 已具备 correlation attempt/reconcile 语义；HTTP API 不再同步 submit。缺少该前置
   时不要用旧 API 同步路径验证 D。

配置模板故意不给 endpoint、target cluster identity、version、path、user、JWT、Account、
Partition 或 QoS 默认值。endpoint 与 identity 必须由同一份人工核验事实绑定；本 adapter
不做 cluster 路由。填入目标事实后先启动配置解析；任一必填值、cluster mismatch、查询
完整性确认、容量或 runtime 不满足时，应用必须在发出 HTTP 请求前失败。

#### 2. 最小真实 Run（需要新的执行授权）

1. 经产品 API 创建一个**无 Input Binding** 的最小 Run，绑定明确 Project Version 和不可变
   Snapshot；API 返回时应为 `QUEUED` 且 job id 为空，随后由独立 Worker 处理。
2. Native 命令只读取 version marker，把 marker 分别写到 stdout/stderr，并在批准的 Artifact
   staging path 写一个小结果。不要用 seed 的演示 image、算力映射或 Mock 结果代替真实事实。
3. 保存平台 run id、完整 correlation、Slurm job id、原始 state、映射后的 state、exit code、
   submitted/started/finished 时间。过短作业未采到 `RUNNING` 时明确记录，不补写状态。
4. 比对平台 job id 与站点权威查询；再按 correlation 精确查询并证明唯一匹配。Log、Artifact
   内容与摘要必须能通过产品 API 读回，且 marker 与固定版本一致。
5. 在另一个明确批准的窗口验证 submit 响应丢失或 job id 落库前退出：恢复只能得到完整
   0/1/多匹配之一；1 个时关联原 job，多匹配或 `complete=false` 时停止，绝不盲目重提。

#### 3. 脱敏证据与停止条件

evidence bundle 只保存版本、配置项名称、脱敏值、请求 correlation/job id、状态/时间、marker
摘要和验收结论；删除 JWT、认证 header、Secret、endpoint 中的内部信息及用户凭据。缺少
目标 107 的状态码及响应 schema allowlist 时，submit 的任意 HTTP 非 2xx（包括普通 400、
408、409、425、429 和 5xx）、timeout、传输失败或 2xx 缺 job id 都是 ambiguous；只有 HTTP
请求前的本地校验失败是明确 Rejected。poll 404 或未映射 state 是 `UNKNOWN`，上述情况都
不能伪造成成功或确定的零匹配。

在成熟项目或官方 v0.0.41 调查与实际环境确认完成、且上述 human gate 产生 fresh evidence
前，真实 slurmrestd/Slurm、认证、三方 mount、Native 环境和端到端 M1 证据均为
**INSUFFICIENT**。本地 v0.0.40 fixture 通过只证明 adapter 候选的协议行为。

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
