# 部署

这里说明当前 107 Workspace 应用容器的运行方式，以及它距离真实集群部署还差什么。
容器编排是开发和受信任演示基线，不代表生产验收已经完成。
可执行清单及目录边界见 [`deploy/README.md`](../../deploy/README.md)。以下命令均在仓库
根目录运行。

本部署拓扑和 M1 Worker 只支持 Linux / WSL2 的 POSIX 语义；原生 Windows 不属于部署
目标。权威平台矩阵见 [ADR-0004](../decisions/0004-platform-support-matrix.md)。

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
| `WORKSPACE107_AUTH_MODE` | `dev` 仅用于本地；真实部署必须替换 |

镜像不包含凭据，`.env` 也不会进入 Git 或构建上下文。

## Mock 不是沙箱

`WORKSPACE107_SCHEDULER=mock` 会由独立 Worker 在 **Worker 容器及其运行身份**下，通过
宿主 shell 子进程真实执行 Run Configuration 的命令；Mock 子进程的创建、轮询和取消均
归 Worker，不归 API。任何能提交 Run 的用户都能执行该 Worker 身份允许的命令，因此它
只能用于本地开发、自动化测试和受信任演示，不能对不受信任用户开放。

`MockScheduler` adapter 保留 Windows 系统命令解释器分支并由 contributor check 覆盖；
POSIX 下使用 Bash。完整 Worker 组合仍只支持 Linux / WSL2，平台不会翻译 Project 命令。

## 接入真实集群

当前代码包含 Slurm REST 适配器。2026-08-11 的真实 107 探针已确认部分平台事实，
但 PR8 当前 v0.0.40 profile 与目标 API 不兼容，且 correlation 精确查询能力未满足；
切换配置不等于完成接入。

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

### Slurm 与运行环境：M1 人工验收 runbook

当前实现只是**本地候选**：唯一 schema profile 由确定性 v0.0.40 fixture 覆盖。2026-08-11
真实探针确认目标 Slurm/client/local slurmrestd 为 25.11.2、ClusterName 为 `training`；
登录节点 local plugins 列出 `v0.0.41-44`，authenticated online OpenAPI 也独立 advertise
`v0.0.41-44`；两者均不提供当前 v0.0.40 profile，因此 PR8 当前 profile 与目标兼容性 **FAIL**。
未经明确授权不得登录 SCOW、调用 SSH、挂载共享存储、获取 JWT、提交或查询真实作业；
2026-08-11 的 evidence 来自本次获授权 probe，只有实际执行者或 runner 才能在受控窗口
执行这些动作。

> **Human gate BLOCKER（历史输入冲突已重新分类）**：2026-07-14 采集的培训材料只能作为
> 待核对的历史输入；它描述 `/public`、`/home`、Slurm 25.11、`v0.0.41` 和
> `Authorization: Bearer`。这些历史描述不覆盖下方 2026-08-11 的 current facts，也不能
> 直接写入默认配置。认证、correlation 完整性和三方部署映射仍须按当前证据与后续 profile
> 重新核验。

#### 1. 提交前记录并再次确认

先在脱敏记录中逐项写下“已确认/未确认”；任何一项未确认就停止，保持
`WORKSPACE107_SCHEDULER=mock`：

1. slurmrestd endpoint 对应的单一目标 cluster identity、真实 Slurm 版本、可用 API version、
   submit/job/list/cancel path 及响应 schema。把脱敏后的 identity 记录为
   `WORKSPACE107_SLURM_TARGET_CLUSTER_ID`；Snapshot 的 `scheduler.cluster` 必须精确匹配，
   mismatch 会在 Worker 发出 slurmrestd HTTP 前拒绝。只有目标版本与已审 profile 一致时
   才能配置；不同版本必须先增加并评审 profile，不能把 `v0.0.40` 当作 107 事实。
2. 认证 header 和 JWT 生命周期。JWT 只由 Secret 管理设施注入进程内存，不进入命令行、
   `.env`、日志、异常、数据库、evidence bundle 或 sbatch 正文。
3. Slurm `comment` 是否能无截断保存完整 correlation、最大字节数、精确查询参数与查询权限；
   还要证明结果没有隐藏分页。只有这些证据齐全才能把
   `WORKSPACE107_SLURM_CORRELATION_QUERY_COMPLETE` 设为 `true`。权限、网络、分页、metadata、
   filter 或 schema 任一不确定时，adapter 返回 `complete=false`，不得把空 `job_ids` 当作零匹配。
4. 本次获批的 Account、Partition、QoS、nodes、tasks、CPU、memory、GPU GRES 和 time limit。
   当前 M1 adapter 只接受 `nodes=1`，将总 CPU/memory/GPU 安全映射到这个节点的单个 task；
   `nodes>1` 会在 Worker 发出 slurmrestd HTTP 前 fail-fast，不能把总量静默放大为 per-node 资源。
5. API、独立 Worker、Shared FS 和计算节点的 mount mapping、canonical path、UID/GID 与权限。
6. 选择 Native 还是 Apptainer。当前只实现 Native：所选 Environment Version 的
   `environment_image` 必须为空，`setup_command` 必须是已批准的原生环境准备步骤。
   需要 Apptainer 时必须停止；当前配置会 fail-fast，没有 no-op 或 Native fallback。
7. C Worker 已具备 correlation attempt/reconcile 语义；HTTP API 不再同步 submit。缺少该前置
   时不要用旧 API 同步路径验证 D。

配置模板故意不给 endpoint、target cluster identity、version、path、user、JWT、Account、
Partition 或 QoS 默认值。endpoint 与 identity 必须由同一份人工核验事实绑定；本 adapter
不做 cluster 路由。填入目标事实后先启动 Worker 配置解析；任一必填值、cluster mismatch、
查询完整性确认、容量或 runtime 不满足时，Worker 必须在发出 slurmrestd HTTP 请求前失败。

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
目标 107 的状态码及响应 schema allowlist 时，Worker submit 的任意 HTTP 非 2xx（包括普通
400、408、409、425、429 和 5xx）、timeout、传输失败或 2xx 缺 job id 都是 ambiguous；只有
Worker 发出 slurmrestd HTTP 请求前的本地校验失败是明确 Rejected。poll 404 或未映射 state
是 `UNKNOWN`，上述情况都不能伪造成成功或确定的零匹配。

2026-08-11 的 fresh evidence 已确认目标版本、ClusterName、认证探针和部分 Shared FS 行为；
但真实 M1 Worker/REST submit 尚未执行，PR8 v0.0.40 profile 与目标 v0.0.41-44 不兼容，
且 v0.0.44 暴露的查询接口没有 comment 精确过滤，也无法证明 correlation 查询完整性。
因此真实 slurmrestd/Slurm 端到端、认证 profile、三方 mount、Native 环境和 M1 仍为
**INSUFFICIENT**；PR8 correlation server-side exact filter 与 `correlation_query_complete`
为 **FAIL**。不得把没有分页参数夸大为服务必然截断。
本地 v0.0.40 fixture 通过只证明 adapter 候选的协议行为。

### 2026-08-11 current facts（带日期的可复用事实）

以下只记录可跨后续验收复用的、已脱敏且带日期的平台事实；一次性 job 详情和仓外副作用
记录在当前 journal，不在这里重复。历史 `docs/references/` 材料不覆盖本矩阵。

| fact | 状态（2026-08-11） | 证据边界与复验触发 |
| :--- | :--- | :--- |
| Slurm/client/local slurmrestd 版本 | 已确认：25.11.2 | 版本升级、endpoint/profile 变化时复验 |
| target cluster | 已确认：`training` | cluster identity、Snapshot 或 endpoint 变化时复验 |
| API schema/profile | 已确认目标 advertise `v0.0.41-44`；PR8 v0.0.40 兼容性 **FAIL** | adapter profile 变更或 API 升级时复验 |
| 认证方式 | 已确认：远端进程内短时生成 token，仅通过 `X-SLURM-USER-NAME`/`X-SLURM-USER-TOKEN` 使用 | Secret 管理、认证插件或进程模型变化时复验；不记录 token |
| 关联查询 | **FAIL**：v0.0.44 jobs 查询未提供 comment 精确过滤，无法证明完整性；不得设 `correlation_query_complete=true` | schema、权限、filter 或分页能力变化后复验 |
| `stu`/`Students` 资源 | 已确认：默认 QoS `qos_stu_medium_2gpu`；允许 `qos_stu_default,qos_stu_medium_2gpu`；DefMemPerCPU 4096 MiB、MaxNodes 2、up | association、partition、QoS 或资源策略变化时复验 |
| Shared FS | 部分确认：login/compute 对 canonical HOME 与 `/public` 可见同 backend/inodes；login marker read、同目录 staging→final rename 可见且 inode 保持 | service identity、shared_gid、专用 storage root 或挂载路径变化时复验 |
| 身份边界 | 仅确认 probe compute identity `66703:66703`；不是 service identity | service image、compute identity 或权限策略变化时复验 |

安全复验入口（命令均为只读、不含 endpoint、token、个人绝对路径或凭据）：

```bash
scontrol --version
scontrol show config | grep -E '^(ClusterName|AuthAltTypes|SlurmctldParameters)[[:space:]]*='
sacctmgr -nP show assoc where user="$USER" account=stu partition=students format=Cluster,Account,User,Partition,DefaultQOS,QOS
scontrol show partition Students -o
slurmrestd -a list
slurmrestd -d list
slurmrestd -d v0.0.44 --generate-openapi-spec | python3 -c 'import json,re,sys; d=json.load(sys.stdin); versions=sorted({v for path in d.get("paths",{}) for v in re.findall(r"/slurm/(v[0-9.]+)",path)}); params=sorted({p["name"] for path,item in d.get("paths",{}).items() if "job" in path.lower() for op in item.values() if isinstance(op,dict) for p in op.get("parameters",[]) if isinstance(p,dict) and isinstance(p.get("name"),str)}); print({"versions":versions,"job_query_parameters":params})'
```

以上命令只核对版本、cluster、认证插件、association、partition、profile 与 OpenAPI
查询参数名；不得把缺少分页参数解释为服务必然截断。mount/rename 需要新的授权脚本，
并须分别以 service/compute 身份执行，本文不提供假命令。

复验输出只能保存配置项名称、脱敏值、时间、摘要和结论；JWT、认证 header 值、Secret、
内部 endpoint/IP、用户凭据和个人绝对路径不得进入文档或 evidence。

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
