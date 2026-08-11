# 107 集群运行事实与 M1 人工验收

这里记录赛后目标 107 集成轨的可复用运行事实与 M1 human-gate runbook；该验收不再
阻塞当前 Competition Demo，也不会因本地演示通过而自动完成。通用部署拓扑、容器与
共享存储边界仍以 [`deployment.md`](deployment.md) 为准；一次性作业及仓外副作用只记录在
当前 [`journal`](../journal/2026-08-10-m1-execution-seams.md)。

## Slurm 与运行环境：M1 人工验收 runbook

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

### 1. 提交前记录并再次确认

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

### 2. 最小真实 Run（需要新的执行授权）

1. 经产品 API 创建一个**无 Input Binding**的最小 Run，绑定明确 Project Version 和不可变
   Snapshot；API 返回时应为 `QUEUED` 且 job id 为空，随后由独立 Worker 处理。
2. Native 命令只读取 version marker，把 marker 分别写到 stdout/stderr，并在批准的 Artifact
   staging path 写一个小结果。不要用 seed 的演示 image、算力映射或 Mock 结果代替真实事实。
3. 保存平台 run id、完整 correlation、Slurm job id、原始 state、映射后的 state、exit code、
   submitted/started/finished 时间。过短作业未采到 `RUNNING` 时明确记录，不补写状态。
4. 比对平台 job id 与站点权威查询；再按 correlation 精确查询并证明唯一匹配。Log、Artifact
   内容与摘要必须能通过产品 API 读回，且 marker 与固定版本一致。
5. 在另一个明确批准的窗口验证 submit 响应丢失或 job id 落库前退出：恢复只能得到完整
   0/1/多匹配之一；1 个时关联原 job，多匹配或 `complete=false` 时停止，绝不盲目重提。

### 3. 脱敏证据与停止条件

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

## 2026-08-11 current facts（带日期的可复用事实）

以下只记录可跨后续验收复用的、已脱敏且带日期的平台事实；一次性 job 详情和仓外副作用
记录在当前 journal，不在这里重复。历史 `docs/references/` 材料不覆盖本矩阵。

| fact | 状态（2026-08-11） | 证据边界与复验触发 |
| :--- | :--- | :--- |
| Slurm/client/local slurmrestd 版本 | 已确认：25.11.2 | 版本升级、endpoint/profile 变化时复验 |
| target cluster | 已确认：`training` | cluster identity、Snapshot 或 endpoint 变化时复验 |
| API schema/profile | 已确认目标 advertise `v0.0.41-44`；PR8 v0.0.40 兼容性 **FAIL** | adapter profile 变更或 API 升级时复验 |
| 认证方式 | 已确认：远端进程内短时生成 token，仅通过 `X-SLURM-USER-NAME`/`X-SLURM-USER-TOKEN` 使用 | Secret 管理、认证插件或进程模型变化时复验；不记录 token |
| 关联查询 | **FAIL**：v0.0.44 jobs 查询未提供 comment 精确过滤，无法证明完整性；不得设 `correlation_query_complete=true` | schema、权限、filter 或分页能力变化后复验 |
| account `stu` / partition `Students` 资源 | 已确认：默认 QoS `qos_stu_medium_2gpu`；允许 `qos_stu_default,qos_stu_medium_2gpu`；DefMemPerCPU 4096 MiB、MaxNodes 2、up | association、partition、QoS 或资源策略变化时复验 |
| Shared FS | 部分确认：login/compute 对 canonical HOME 与 `/public` 可见同 backend/inodes；login marker read、同目录 staging→final rename inode 保持且 login 可见 | service identity、shared_gid、专用 storage root 或挂载路径变化时复验 |
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
