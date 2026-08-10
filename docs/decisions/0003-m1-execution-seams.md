# 0003. 以四个责任接缝打通 M1 真实执行链路

- 状态：提议中
- 日期：2026-08-10

## 背景

### 产品事实

以下事实来自当前 `docs/product/design.md`，不是本 ADR 新增的技术偏好：

1. Project Version 是不可变内容快照；Run 必须先确定 Project Version，再创建独立且不可变的 Run Snapshot（§3.1.2、§3.1.6、GR-201、GR-202、GR-302、GR-303）。
2. 平台先创建 Run 并固定 Snapshot，再提交调度任务；Scheduler Job Reference、状态、时间、Log 和 Artifact 是执行信息或结果，不属于 Snapshot（§3.1.6、GR-305）。
3. API Backend 与 Background Worker 是独立运行组件；耗时流程脱离 HTTP 生命周期（§4.1–4.3）。
4. M1 用真实 Git、Shared FS、Worker 和 slurmrestd / Slurm 跑通最薄 Run 链路；Shared Resource 和完整 Input Binding 属于 M3（§6.2–6.5）。所以 Shared Resource **不是 M1 前置功能**，M1 可用无 Input Binding 的 Run 验收。
5. Input Binding 是未来给 Run 增加确定内容的统一关系；Shared Resource Version 只是可能来源之一，不拥有 Run workspace、Worker 或 Scheduler 接缝（§3.1.3）。

本 Work Unit 明确 M1 最小闭环为：确定 Project Version → 固定 Run Snapshot → 独立 Worker → Shared FS workspace → slurmrestd / Slurm → 状态、stdout/stderr 和一个配置的 Artifact 回写。完整 Log/Artifact 产品体验仍在 M2；M1 只保留证明真实链路所需的最小证据。

### 当前代码事实

当前 `main@74a41f9` 是 Mock 开发基线，不是 M1：

- `RunService.create()` 在 HTTP 请求事务内创建 Snapshot 与 `QUEUED` Run，随后同步准备本地目录并 submit；外部副作用发生在请求事务提交前。
- FastAPI `main.py` 内的 `_sync_loop` 负责 poll、状态和 Artifact；API 退出即停止，不是独立 Worker。
- `LocalStorage.prepare_run_directory()` 删除既有 Run 目录再重建，Project Version 来自本地 blob；没有证明真实 Git 或三方可见 Shared FS。
- `SlurmRestScheduler` 按未在目标环境核验的 v0.0.40 形状编写。
- public `RunStatus` 为 `QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELLED / SUBMIT_FAILED`，`scheduler_job_id` 可空。

PR #3（读取时 open，head `ab7a086`）实现 M3 Shared Resource，并修改 `run_service.py`、`run_configuration_service.py`、`StoragePort`、`LocalStorage`、仓储容器和 Input Binding 物化。它与 M1 的 B/C 接缝有机械重叠，但产品范围不同；M1 不以该 PR 为依赖。

### 核心风险

- HTTP 数据库事务不能与 Slurm submit 原子提交；“Slurm 已接受、job id 未落库”时盲目重试会重复作业。
- Worker 与计算节点若看到不同路径或内容，Mock 全绿不能证明真实链路。
- 继续扩张当前 `StoragePort` 会混合 Git、workspace、输入、日志与 Artifact ownership。
- 提前引入 provider、消息队列或新 public 状态会固化未验证设计。

## 选项

1. **保留 HTTP 同步提交与轮询**：改动小，但不满足独立 Worker，歧义窗口仍在。
2. **以 Run 为持久事实，建立独立 Worker 和四个窄接缝**：API 只固定 Snapshot、Run 和执行意图；Worker 编排外部能力并回写。
3. **先建通用异步平台、Storage provider 和完整 M3 输入**：扩展性高，但 M1 无需求支撑，审计和运维面过大。

## 决定

采用选项 2，按 A → B → C → D 四张 Issue clean cutover，不保留同步旧路径。

```text
HTTP API
  └─ 同一数据库事务：确定 Project Version
                     + INSERT immutable Run Snapshot
                     + INSERT Run(QUEUED, scheduler_job_id=NULL)
                     + INSERT claimable execution intent
                                  │
                                  ▼
Independent Worker ──Snapshot──► A Git Version
       │                              └─精确 Git tree
       ▼
B Shared FS ──Run workspace / logs / artifact staging
       │
       ▼
D slurmrestd / Slurm ──计算节点读写同一 Shared FS
       │
       ▼
Independent Worker ──job id / status / time / Log / Artifact 回写
```

M1 使用已有 PostgreSQL 实现持久 claim/lease，并与 Run/Snapshot 同事务创建；它是内部协调记录，不建设通用消息队列、事件平台或 provider 接口。真实需求证明数据库领取不足时，再新增 ADR。

### Ownership、依赖与禁区

| 包 | 唯一 ownership | 输入 → 输出 | 依赖 | 禁止修改的 seam |
| --- | --- | --- | --- | --- |
| **A Git Version** | Project Version 对应精确、不可漂移的 Git commit/tree；读取 manifest，并向调用方指定空目录导出 | `project_version_id` → commit OID、manifest/内容 | Git、Project Version 仓储 | 不选 Run 路径；不建 Run/Snapshot；不碰 Worker、Shared FS 布局、Scheduler、Log/Artifact；不接受 `HEAD/current/latest` |
| **B Shared FS** | 分配 Run workspace，校验路径/权限，调用 A 物化；给 Worker/Slurm 提供 work/log/artifact 路径 | run/snapshot/version identity → `RunWorkspace` | A、部署提供的 POSIX Shared FS | 不读可变 Run Configuration；不提交 Slurm；不推进状态；不实现 Shared Resource；不建立 `SharedFSStorage`/provider registry |
| **C Worker** | 独立入口；领取、续租、恢复；只按 Snapshot 编排 A/B/D；拥有执行信息与结果回写 | durable intent → 终态或显式待恢复事实 | A、B、D 窄端口 | 不实现 Git/FS/slurmrestd 细节；不改 Snapshot；不引消息队列；不新增 public `SUBMITTED` |
| **D Slurm** | 目标集群 submit/poll/cancel、稳定 correlation、Slurm→内部 scheduler state | Snapshot+RunWorkspace 形成的 submission → job id/state | C、真实 slurmrestd/Slurm | 不物化内容；不选 workspace；不直接写 DB/RunStatus/Log/Artifact；不固定未经核验 API 版本 |

这些是责任边界，不要求四个同名类。具体接口只提供当前调用方所需最小方法。

### Version 与 workspace 语义

- Worker 只执行 Project Version 绑定的完整 commit OID；Branch、Working State、`HEAD/current/latest` 均不是执行依据。
- A 导出确定 tree；B 独占目标目录选择、路径安全和布局。
- 每个 Run 有独立 workspace。prepared identity 绑定 `run_id + snapshot_id + project_version_id + commit_oid`；同一 identity 可恢复，不同 identity 复用目录必须失败，不能删目录后静默换内容。
- M1 `inputs/` 可为空。未来 Input Binding 的来源只提供确定内容，不接管 workspace ownership。
- Worker 与计算节点必须使用同一 Shared FS canonical path，不能依赖容器私有路径偶然一致。

### Worker 幂等与提交歧义

HTTP 幂等键只能防重复创建 Run。Worker 以 `run_id` 为一次逻辑执行的稳定 identity：

1. claim 后重读 Run/Snapshot；终态或已有 `scheduler_job_id` 不再 submit。
2. submit 带可由目标 Slurm 精确查询的稳定 correlation，由完整 run id 派生；具体承载字段必须经 human gate 核验，不能只靠可能截断/重复的展示名。
3. submit 前持久记录 attempt/correlation；返回 job id 后 compare-and-set `scheduler_job_id: NULL → id` 并写 `submitted_at`。已有同 id 是重放成功，已有不同 id 进入歧义，禁止覆盖。
4. “可能已提交但 job id 未落库”时先按 correlation reconcile：0 个且查询完整才允许 submit；1 个则关联；多匹配、权限不足、网络不确定均停止 submit，Run 保持 `QUEUED`，持久记录并写 Run Event `submission uncertain`，等待恢复。
5. 歧义不修改 Snapshot，不伪造成功/失败。`SUBMIT_FAILED` 只用于已经确定没有可关联 Scheduler Job 的失败。

保持现有 public 状态：`QUEUED` 覆盖已创建、待 Worker、准备中和已提交等待；`scheduler_job_id != NULL` 表示底层任务已唯一关联；`RUNNING`/终态由 Slurm 查询驱动；**不新增 `SUBMITTED`**。如产品以后要求展示区分，单独走 API 契约决策。

### clean-cutover

1. `RunService.create/rerun` 不再准备目录或 submit；API 事务只写 Snapshot、Run、幂等记录和 execution intent。
2. 删除 FastAPI `_sync_loop`；submit、poll、终态竞争保护、最小 Log/Artifact 回写移到 Worker 调用的 application use case。
3. 当前 LocalStorage“存在即删除重建”退出 M1 执行路径，改为绑定 Snapshot identity 的恢复语义。
4. `SchedulerPort` 的 submit/poll/cancel 方向可保留，但 producer、consumer 和 adapter 一次迁移，不留同步 wrapper。
5. 当前无共享/生产 Run 数据保留承诺，开发 schema 可重建或整理；发现真实保留状态时停止破坏性迁移并升级人类决策。
6. 能表达 M1 时保持 public Run API/RunStatus；claim/lease/ambiguity 不进入 Snapshot。

### PR #3 接缝

- Shared Resource 是 M3，不进入 M1 验收依赖。
- PR #3 先合并时，B/C 可 clean-cutover 它对 `StoragePort`、`RunService`、Input Binding 的机械接缝，但不删除其独立领域模型；M1 无输入路径不依赖 Shared Resource。
- M1 先落地时，PR #3 应 rebase 到 B 的只读确定内容 seam；它只能提供 manifest/materialization source，不得恢复 HTTP submit 或接管 C。
- 不为降低冲突保留两套 `prepare_run_directory` 或 `_submit`。

### 真实环境 human gate

用户明确禁用 `ustc-107-runner`。任何 Agent 均不得为本 ADR 或四张 Issue 调用该 skill、登录 107、启动 SSH bridge、访问真实 Shared FS 或提交/查询 Slurm 作业。真实 Shared FS/slurmrestd/Slurm 证据只能由有权限的人类在接受 ADR、审完候选实现并提供参数后亲自执行或逐步授权。没有人类 fresh evidence，只能称“实现候选”，不得声明 M1 真实链路通过。

## 四张 Issue 的顺序与验收

### A — Git-backed Project Version（顺序 1，B 前置）

1. 在测试创建的真实本地 Git repo 保存 version 后，可由 version 得到完整 commit OID；不是 branch 名。
2. 后续修改 Working State、移动 branch、新建 commit，不改变旧 version 导出的路径、字节和摘要。
3. 导出到调用方指定空目录后逐路径匹配 manifest；缺 object/identity mismatch 时失败且不留下伪成功目录。
4. 执行入口拒绝 `HEAD/latest` 或未确定 branch。
5. 针对性测试记录本地 Git commit OID/摘要；统一检查通过；不得访问 107。

### B — Shared FS Run Workspace（顺序 2，依赖 A，C 前置）

1. 给定 run/snapshot/version/commit identity，在测试 POSIX 根创建唯一 workspace，返回 work/stdout/stderr/artifact staging 绝对路径。
2. 调用 A 导出；marker 与 commit/tree 证据一致；显式空 inputs 成功。
3. 拒绝绝对用户路径、`..` 和 symlink 越界，不写 workspace 外。
4. 同 identity 重试不删 Log、不用不同内容覆盖；不同 identity 复用目录失败并留诊断事实。
5. 两个本地独立进程读取同一 marker；真实三方 mount mapping 留 human gate；统一检查通过；不得访问 107。

### C — Independent Worker（顺序 3，依赖 A/B，以 Fake Scheduler 验证）

1. HTTP 在单事务写 Snapshot、`QUEUED` Run、execution intent 后返回；路径无 Git 导出、FS 物化或 submit。
2. API 停止后独立 Worker 仍可领取并以 Fake Scheduler 推进终态。
3. 双 Worker 只有一个有效 lease；租约可恢复；重复处理不产生第二 job/Artifact。
4. 本地注入 submit 前、submit 返回后落库前崩溃；恢复遵守 0/1/多匹配与不确定策略，不盲目 submit。
5. `QUEUED` 在 job id 前后合法；job id 仅唯一关联后出现；无 `SUBMITTED`；Snapshot 全程不变。
6. 删除 FastAPI `_sync_loop` 和同步 `_submit`，迁移全部调用方，无 wrapper；统一检查通过；不得访问 107。

### D — slurmrestd / Slurm adapter 与 human acceptance（顺序 4，依赖 A/B/C）

Agent 的本地候选验收：

1. API version/path/state shape 可按目标事实适配，不把未核验 v0.0.40 当验收事实；JWT 不进日志、DB 或脚本正文。
2. fixture/fake transport 覆盖 submit/poll/cancel、完整 correlation、UNKNOWN 和协议错误；D 不直接写 Run DB。
3. 提供脱敏的人类验收步骤，不含凭据、不自动登录/挂载/提交。
4. 统一检查通过；不得调用 `ustc-107-runner` 或访问 107。

人类 gate 的充分证据：

1. 记录真实 slurmrestd/Slurm 版本、API path、认证方式（无 token）、Account/Partition/QoS、correlation 查询权限及 API/Worker/compute mount mapping。
2. 经产品 API 创建**无 Input Binding** Run；返回时 `QUEUED`，Snapshot 固定明确 version，Worker 独立。
3. 平台 job id 与 `squeue`/`sacct` 或站点权威查询一致，correlation 还原完整 run id。
4. 保存 scheduler 原始状态、平台状态、submitted/started/finished、exit code；状态不得由测试直接写。过短未采到 RUNNING 时明确记录。
5. 计算节点读取 version marker，stdout/stderr 分别输出 marker 并写结果；API 读回 Log，Artifact 元数据、下载内容与摘要一致。
6. 在人类批准的受控窗口验证 submit 响应丢失/落库前退出；恢复后最多一个可关联 job。不能安全注入则证据不足，不以 Mock 代替。
7. evidence bundle 脱敏保存，不含 JWT、Secret 或用户凭据。

## 后果

- 好：四个 Issue ownership 稳定；真实 Slurm 由人类 gate，而非 Mock 推断。
- 好：API 脱离长任务和外部副作用；Worker 有可审计恢复/歧义策略。
- 好：保留 `QUEUED` 与 `scheduler_job_id` 语义，不提前增加 `SUBMITTED`。
- 好：M1 无输入可验收，Shared Resource 保持 M3 身份。
- 坏：必须一次替换同步 Run、FastAPI loop 和本地目录重建语义。
- 坏：数据库 claim/lease 需要维护超时、并发与恢复，但避免新消息中间件。
- 坏：真实歧义仍依赖 Slurm correlation 与人工恢复。
- **反悔成本：中**。C 的 transport 可在语义不变时替换；public 状态/Snapshot 变化需独立契约决策。

## 未决人类决策

1. 真实验收集群、slurmrestd 地址、服务身份/JWT 获取方式及 Account/Partition/QoS。
2. API/Worker/计算节点的 Shared FS canonical mount mapping。
3. Native 或 Apptainer 验收环境及可运行命令/镜像。
4. Slurm 可保存完整 correlation 的字段与查询权限；不允许时的等价去重/查找机制。
5. human gate 执行者、窗口和脱敏 evidence bundle 保存位置。

## 重新评估条件

- 数据库 claim/lease 成为真实瓶颈或需要独立伸缩时，另行评估消息中间件。
- Shared FS 无法稳定跨 Worker/计算节点访问时，重选 staging 方案。
- Slurm 无法按 correlation 查询时，幂等策略必须重做。
- 产品要求区分“待处理/已提交”时，单独评估 `SUBMITTED`。
- M3 输入真实变化轴超出确定内容 manifest/materialization source 时再扩展，不提前建 provider。

---
> 决策变更时新增 ADR，并将本记录标为被取代，不重写历史。
