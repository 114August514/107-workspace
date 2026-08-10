# 0003. 以四个窄接缝打通最小 M1 真实执行链路

- 状态：提议中
- 日期：2026-08-10

## 背景

### 产品事实

以下事实来自当前 `docs/product/design.md`，不是本 ADR 新增的技术偏好：

1. Project Version 是不可变内容快照；Run 必须先确定 Project Version，再创建独立且不可变的 Run Snapshot（§3.1.2、§3.1.6、GR-201、GR-202、GR-302、GR-303）。
2. 平台先创建 Run 并固定 Snapshot，再提交调度任务；Scheduler Job Reference、状态、时间、Log 和 Artifact 是执行信息或结果，不属于 Snapshot（§3.1.6、GR-305）。
3. API Backend 与 Background Worker 是独立运行组件；耗时流程脱离 HTTP 生命周期（§4.1–4.3）。
4. M1 用真实 Git、Shared FS、Worker 和 slurmrestd / Slurm 跑通最薄 Run 链路；Shared Resource 和完整 Input Binding 属于 M3（§6.2–6.5）。所以 Shared Resource **不是 M1 前置功能**，M1 以无 Input Binding 的 Run 验收。
5. Input Binding 是未来给 Run 增加确定内容的统一关系；Shared Resource Version 只是可能来源之一，不拥有 Run workspace、Worker 或 Scheduler 接缝（§3.1.3）。

M1 最小闭环是：确定 Project Version → 固定 Run Snapshot → 独立 Worker → Shared FS workspace → slurmrestd / Slurm → 状态、stdout/stderr 和一个配置的 Artifact 回写。完整 Log/Artifact 产品体验仍在 M2；M1 只实现证明真实闭环必需的功能。

### 最新人类决定

系统整体简单性优先于自治能力。M1 要求功能最小但真实完整，可扩展性来自窄 seam，而不是提前实现多 writer、多 Worker、通用分布式租约、消息队列、provider registry 或 power-loss 恢复平台。

M1 必须满足：当前链路可运行、应用进程重启可恢复、绝不因恢复重复创建 Slurm Job、已确定 Version 不漂移、已安装 Artifact 不被覆盖。M1 不要求多 Worker 扩缩、滚动双活、任意网络分区或节点掉电下的通用一致性。

### 当前代码与候选事实

`main@74a41f9` 是 Mock 开发基线，不是 M1：

- `RunService.create()` 在 HTTP 请求事务内同步准备目录并 submit；外部副作用发生在请求事务提交前。
- FastAPI `_sync_loop` 负责 poll、状态和 Artifact；API 退出即停止，不是独立 Worker。
- `LocalStorage.prepare_run_directory()` 删除既有 Run 目录再重建，Project Version 来自本地 blob。
- 当前 Slurm 候选以本地 v0.0.40 fixture 为基础，尚未证明与目标 107 一致。
- public `RunStatus` 已能表达 M1；不需要新增 `SUBMITTED`。

A/B/C/D 候选曾分别加入 DB/Git saga、per-Run/Artifact flock 与 claim、per-Run lease/heartbeat/fencing 和多 Worker 测试。这些机制主要服务未来自治，不是最新 M1 验收所需；本 ADR clean replace 它们，不因已有代码量保留错误复杂度。

PR #3 实现 M3 Shared Resource，并与 B/C 有机械重叠。它不是 M1 依赖；M1 不删除其独立领域模型，也不把 Shared Resource 带入本里程碑。

### 历史平台材料

`docs/references/platform/107-cluster-competition-training.pdf` 是历史原始输入，不是部署契约。材料记载：

- `/public` 是所有节点共享挂载，`/home` 也位于共享存储；`/tmp`、`/usr`、`/var`、`/opt` 等各节点独立；
- Slurm `25.11`；
- REST 示例使用 `v0.0.41`、`Authorization: Bearer` 和 `/slurm/v0.0.41/...` 路径。

这些事实与当前 v0.0.40/X-SLURM-header 候选冲突，且参考材料明确要求实际使用前重新核实。因此它们只触发 human gate，**不得直接写成实现事实或默认配置**。

### 成熟实现核验与复用决定

以下是外部证据，读取日期均为 **2026-08-10**；tag/commit 只固定本次核验对象，不把上游整体变成本项目依赖：

- **系统 Git**：官方 [`git update-ref` 2.53.0](https://git-scm.com/docs/git-update-ref/2.53.0)、[`git cat-file` 2.53.0](https://git-scm.com/docs/git-cat-file/2.53.0) 与 [`git gc` 2.52.0](https://git-scm.com/docs/git-gc/2.52.0) 证明 create-only CAS、按对象读取与 ref 保活语义；DB 只存 OID 不能防止 unreachable object 被回收。
- **Cromwell**：官方 tag `92`、commit `e94341fdb32f0526b4338f9e1206a84b936dfcac`；[HPC 文档](https://raw.githubusercontent.com/broadinstitute/cromwell/e94341fdb32f0526b4338f9e1206a84b936dfcac/docs/backends/HPC.md) 与 [SFS actor](https://raw.githubusercontent.com/broadinstitute/cromwell/e94341fdb32f0526b4338f9e1206a84b936dfcac/supportedBackends/sfs/src/main/scala/cromwell/backend/sfs/SharedFileSystemAsyncJobExecutionActor.scala) 使用 durable workflow/call workspace、持久 job id、存活查询和 `rc.tmp → rc` 发布恢复；源码也暴露 submit 成功而 job id 尚未持久化的窗口。
- **OpenSCOW**：官方 tag `v1.6.4`、commit `7c238148d4ebcab50f174b3807a4e7de4e27bcb0`；[submit API](https://raw.githubusercontent.com/PKUHPC/OpenSCOW/7c238148d4ebcab50f174b3807a4e7de4e27bcb0/apps/portal-web/src/pages/api/job/submitJob.ts) 与 [portal job service](https://raw.githubusercontent.com/PKUHPC/OpenSCOW/7c238148d4ebcab50f174b3807a4e7de4e27bcb0/apps/portal-server/src/services/job.ts) 把认证 identity 贯穿 scheduler，并显式传递 `cwd`、`stdout`、`stderr`。
- **Airflow/PostgreSQL**：Airflow stable `3.3.0`、源码 commit `7cdb9ad47aff1168a6de06363066184dd029d8b9`；官方 [多 scheduler 文档](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html#running-more-than-one-scheduler) 和 PostgreSQL 18 [`SKIP LOCKED`](https://www.postgresql.org/docs/18/sql-select.html#SQL-FOR-UPDATE-SHARE) 文档说明该 queue-like claim/heartbeat/lease 模式解决多消费者并发，而不是单 active 进程的必需品。
- **Gitaly/Praefect**：核验 GitLab docs `19.3/master` 的 [operation atomicity](https://docs.gitlab.com/administration/gitaly/praefect/#atomicity-of-operations)：逻辑可见性最后发布、失败允许 orphan；这是发布顺序证据，不是引入 Gitaly/Praefect 服务的理由。
- **slurmrestd**：官方 [Slurm 25.11.3 slurmrestd](https://slurm.schedmd.com/archive/slurm-25.11.3/slurmrestd.html)、[REST API archive](https://slurm.schedmd.com/archive/slurm-24.05.8/rest_api.html) 与 [JWT 文档](https://slurm.schedmd.com/archive/slurm-25.11.3/jwt.html) 表明 25.11 可同时加载多个 `data_parser`；v0.0.41 官方路径是 singular `/slurm/v0.0.41/job/submit`，native JWT 使用 `X-SLURM-USER-NAME`/`X-SLURM-USER-TOKEN`。仓内 PDF 的 `Authorization: Bearer` 和 proxy 路径可能描述前置网关，与 native 契约冲突。

基于上述证据，本 ADR 作以下技术决定：

1. **直接复用**系统 Git `update-ref`/`cat-file` 和精确 tree 导出，不自建 Git storage service。
2. **只借窄模式**：借 Cromwell 的 durable workspace、job-id/存活/终态 marker 恢复，但用本 ADR 的 arm + correlation 消除其 job-id 落库窗口；借 OpenSCOW 的 identity 贯穿及显式 `cwd`/`stdout`/`stderr`，不复制其 SSH/SFTP 执行架构。
3. **明确不采用** Airflow 的 `SKIP LOCKED` claim、per-Run lease、heartbeat 和 fencing；它们适合多 scheduler，而 M1 已决定单 active Worker + session advisory lock。
4. 不引入 OpenSCOW、Cromwell、Airflow、Gitaly/Praefect 整套组件，也不新增 MQ、provider registry、全量 SDK 或第二套运行平台。
5. slurmrestd 只实现 human gate 确认后的一个 `data_parser`/path/auth profile；25.11、v0.0.41、native headers 与 PDF proxy 的冲突仍是外部核验项，不得靠多版本/header fallback 掩盖。

### 核心风险

- HTTP 数据库事务不能与 Slurm submit 原子提交；“Slurm 已接受、job id 未落库”时盲目重试会重复作业。
- Worker 与计算节点若看到不同路径、身份或内容，Mock 全绿不能证明真实链路。
- DB 与 Git 不必实现通用分布式事务，但 DB 可见的正式 Version 绝不能指向缺失或可漂移内容。
- 继续扩张当前 `StoragePort` 会混合 Git、workspace、输入、日志与 Artifact ownership。
- 为多副本自治提前增加 lease、fencing、claim 和恢复状态机会扩大失败面，反而妨碍 M1 审计。

## 决定

按 A → B → C → D 四张 Issue clean cutover，保留四个窄责任 seam；生产 M1 明确采用**单 Project writer**和**单 active Worker**。

```text
HTTP API
  └─ PostgreSQL transaction
       ├─ fixed Project Version
       ├─ immutable Run Snapshot
       ├─ Run(QUEUED, scheduler_job_id=NULL)
       └─ minimal execution intent
                         │
                         ▼
Independent Worker ── one PostgreSQL session advisory lock
       │
       ├─ A ProjectVersionExporter ── exact immutable Git commit
       ├─ B RunWorkspacePort ─────── Shared FS work/log paths
       └─ D SchedulerPort ────────── submit/find/poll/cancel
                         │
                         ▼
             Artifact + Run terminal DB transaction
```

### Ownership、依赖与禁区

| 包 | 唯一 ownership | 输入 → 输出 | 依赖 | 禁止承担 |
| --- | --- | --- | --- | --- |
| **A Git Version** | 正式 Project Version 对应精确、不可漂移的 Git commit/ref；按确定 Version 导出内容 | `project_version_id + expected_commit_oid` → commit/tree/manifest/内容 | PostgreSQL、Git | Run 路径、Worker、Shared FS 布局、Scheduler、DB/Git 通用 saga、`main` 一致性 |
| **B Shared FS** | 单 active Worker 下的 Run workspace 布局、权限、进程重启恢复、Artifact 原子安装 | run/snapshot/version identity → `RunWorkspace`；source → Artifact evidence | A、POSIX Shared FS、部署 UID/GID | per-Run/Artifact 锁与 claim、多 writer 协调、Slurm、Run 状态、Shared Resource、provider registry |
| **C Worker** | 单 active 独立入口；按 Snapshot 编排 A/B/D；持久化最小执行事实并回写结果 | minimal intent → 终态或显式 uncertainty | PostgreSQL、A、B、D | per-Run lease/heartbeat/fencing、attempt history、Git/FS/slurmrestd 细节、消息队列、新 public 状态 |
| **D Slurm** | 单目标集群和单 profile 的 submit/find/poll/cancel、稳定 correlation、状态映射 | `SchedulerSubmission` → job id/state/correlation result | C、人工核验的 slurmrestd/Slurm | 多 cluster router、多 profile registry、Apptainer、多节点资源分配、DB/RunStatus/FS 写入 |

具体接口只提供当前调用方所需方法；四个责任边界不要求四个同名大类。

### A：单 Project writer 与正式 Version 发布

1. 保存 Version 的 PostgreSQL 事务先取得按 `project_id` 分区的 transaction advisory lock，或等价的最小生产级单 writer 锁。
2. 锁内读取最新正式 Version，创建 Git tree/commit，并以 zero-OID compare-and-swap 安装 `refs/workspace107/versions/<version_id>`。
3. **immutable ref 必须先于正式 DB row**。ref 安装成功后，才 INSERT 正式 Version row 并提交事务。
4. Git ref 成功而 DB 事务失败或进程退出时，允许留下 public 不可见的 orphan ref。它只占存储，不进入 Version 列表或 Run Snapshot，不破坏任何正式 Version。
5. DB 可见 Version 必须始终能由 immutable ref/commit 导出；不维护 `refs/heads/main` 一致性，不增加 pending/finalized saga、pending ref、补偿事务或自动 orphan recovery。
6. Worker 只执行 Snapshot 绑定的完整 commit OID；拒绝 branch、Working State、`HEAD/current/latest`。

DB 是正式 Version 的可见索引，Git commit/ref 是内容事实。manifest 可按 commit 派生；不在 DB 再保存一套成为第二内容事实。

### B：单 writer workspace 与进程重启恢复

1. C 的单 active Worker 是 B 唯一 writer；B 不再建立 per-Run/Artifact flock、外置 claim 或多 owner fencing。
2. workspace identity 绑定 `run_id + snapshot_id + project_version_id + commit_oid`。同 identity 可恢复，不同 identity 复用目录必须失败；恢复不得删除既有 Log。
3. A 只向 owned staging 导出；B 验证 commit/tree/manifest 后用同目录 atomic rename 安装 `work/`。应用进程在 exporting/copying/finalizing 任一阶段退出后可按 marker 恢复。
4. Artifact 的 copying staging 可安全重建；finalizing evidence 是 first-installed truth，恢复不得重新读取已删除或变化的 source 来替换它；installed Artifact 永不覆盖。
5. compute 可控的 Artifact source 必须用 descriptor-relative `openat`、`O_NOFOLLOW`、`fstat` 和 non-blocking open 遍历，拒绝路径逃逸、symlink、FIFO 和 special file。
6. API/Worker 使用平台 service UID；计算任务使用不同 compute UID。两者使用经核验的 `shared_gid`：Run root 只允许计算身份 traverse，`work/`、`logs/` 和 stdout/stderr 给 compute 必需的写权限；Artifact store、marker 控制区和 staging 仅 service UID 可写。
7. M1 只承诺应用进程重启恢复；不以通用 fsync 状态机声称节点掉电或任意 Shared FS power-loss durability。

Shared FS canonical path 可以位于目标环境核验后的 `/public` 或 `/home`，也可以是另一条真实共享挂载；代码不猜路径。

### C：一个 active Worker 与最小 intent

1. Worker 启动时用专用 PostgreSQL 连接获取固定 namespace/key 的 session advisory lock，并在进程生命期持有。获取失败即退出或 NotReady；不作为自动 standby。
2. advisory-lock 连接丢失或数据库出错时 Worker fail-stop，不继续外部操作。M1 部署 `replicas=1`，锁只防误启动第二实例。
3. Worker 一次只推进一个 intent。没有多 Worker 领取，因此不需要 `SKIP LOCKED`、lease owner/token/generation/expiry、renew、heartbeat 或 fencing。
4. minimal intent 只保存恢复所需事实：`run_id`、唯一 `correlation`、`attempt_no`、`next_action_at`、可空取消/uncertainty，以及 Artifact 前必须保留的 scheduler 终态观察值和时间。Run 终态事务完成后删除 intent。
5. 不建立 submission-attempt history 表。attempt 的当前事实存在 intent；需要用户可见或审计的变化写 Run Event。
6. 状态由事实推导：
   - `job_id IS NULL, attempt_no = 0`：准备 workspace；
   - `job_id IS NULL, attempt_no > 0`：先按 correlation 查找；
   - `job_id IS NOT NULL` 且无终态观察：poll；
   - 已有终态观察：幂等安装 Artifact，再完成 Run。

### submit 歧义与绝不重复 Job

1. submit 前在短事务中持久增加 `attempt_no`；correlation 由完整稳定 run id 派生，所有 attempt 使用同一逻辑 correlation。
2. 返回 job id 后以 `scheduler_job_id: NULL → id` compare-and-swap 关联；已有同 id 是重放成功，已有不同 id 停止并记录 uncertainty。
3. 进程退出、timeout、HTTP non-2xx、无效响应或“可能已提交但 job id 未落库”后，重启必须先 `find_by_correlation`：
   - 查询完整且 0 个：才允许再次 arm/submit；
   - 1 个：关联原 job；
   - 多个、权限不足、网络失败、分页或 schema 不确定：停止 submit，记录 uncertainty，等待人工处置。
4. `SUBMIT_FAILED` 只用于已经确定 HTTP 请求前没有创建 Job 的本地拒绝；其他失败不得伪造为确定未提交。

保持现有 public 状态：`QUEUED` 覆盖待 Worker 和已提交等待；`scheduler_job_id != NULL` 表示底层任务已唯一关联；`RUNNING`/终态由 Scheduler 查询驱动；不新增 `SUBMITTED`。

### D：单目标 Slurm profile

1. M1 只实现 Native、`nodes=1`、单 target cluster、单 schema profile。Snapshot cluster 必须与 adapter target cluster 精确一致，失配在 HTTP 前拒绝。
2. `SchedulerPort` 只保留 `submit`、`find_by_correlation`、`poll`、`cancel`。correlation result 明确 `complete + job_ids + reason`。
3. 缺少目标 allowlist 时，所有 HTTP non-2xx、timeout、transport failure、2xx 缺 job id 均为 Uncertain；仅 HTTP 前本地校验失败为 Rejected。
4. correlation 查询出现未知 metadata、分页、filter、权限或 schema 时必须 `complete=false`；不得把空列表猜成权威零。
5. 不同时支持历史 v0.0.40 与参考材料 v0.0.41。human gate 确认目标事实后 clean replace 为一个真实 profile；不增加 registry 或兼容矩阵。

### clean-cutover 删除清单

集成提交必须删除，而不是保留 fallback：

- FastAPI 同步 `_submit`、`_sync_loop` 和旧 `RunLifecycleService`；
- M1 执行路径中的 `LocalStorage.prepare_run_directory` 和 blob Project Version；
- A 的 DB/Git saga、pending ref、pending/finalized 状态、`main` ref 维护和重复 manifest 状态；
- B 的 `.locks`、`.claims`、per-Run/Artifact flock、多 owner/cancellation 状态与对应测试；
- C 的 per-Run lease/heartbeat/fencing、submission-attempt history 表、完整 phase/outcome 状态机与双 Worker 测试；
- D 的临时同步 RunService consumer、多 cluster/profile/runtime 分支和未经核验的配置组合；
- 重复的 A/B 端口定义、兼容 alias、旧 wrapper 和第二条 export/workspace seam。

### PR #3 与 Shared Resource

- Shared Resource 是 M3，不进入 M1 验收依赖。
- PR #3 只能在未来作为 Input Binding 的确定内容来源；不得接管 Run workspace、Worker 或 Scheduler。
- 合并机械重叠时 clean-cutover `StoragePort`、`RunService` 和 Input Binding 调用方，不保留两套 `prepare_run_directory` 或 `_submit`。

## 四张 Issue 的顺序与验收

### A — Git-backed Project Version（顺序 1，B 前置）

1. 同一 Project 的并发保存由 PostgreSQL transaction advisory lock 或等价单 writer 锁串行；不同 Project 不需要全局串行。
2. 测试注入“immutable ref 成功、DB commit 失败”，Version 列表不可见该 ref；重试可成功，任何正式 Version 不悬空。
3. 后续修改 Working State、移动 branch、新建 commit、重启 API 和执行 `git gc`，旧 Version 导出的路径、字节和摘要不变。
4. 导出到调用方指定空目录后逐路径匹配 manifest；identity mismatch、缺 object 或非完整 OID 大声失败，不留下伪成功目录。
5. 代码和 schema 中不存在 pending saga/state/ref、`main` 一致性或第二份 manifest 内容事实。

### B — Shared FS Run Workspace（顺序 2，依赖 A，C 前置）

1. 给定 run/snapshot/version/commit identity，创建唯一 workspace，返回绝对 work/stdout/stderr 路径；显式空 inputs 成功。
2. 在 exporting、Artifact copying、Artifact finalizing 三个点终止进程，重启后恢复；Log 不删除，finalizing source 即使变化或删除仍安装 first evidence。
3. 同 identity 幂等；不同 identity 失败；Artifact 同摘要幂等、异摘要不覆盖。
4. 受控竞态证明 ancestor/final path 被换成 symlink、FIFO 或 special file 时不越界、不阻塞。
5. 两个本地 UID + shared GID 验证：compute 可写 work/log/stdout/stderr，但不能 traverse Artifact store/control。
6. 实现和测试中不存在 per-Run/Artifact flock、claim 或多 writer takeover；真实 mount/rename/权限留 human gate。

### C — Single-active Independent Worker（顺序 3，依赖 A/B）

1. HTTP 在同一事务写 Snapshot、`QUEUED` Run 和 minimal intent 后返回；无 Git、FS 或 submit 外部调用。
2. 第二个 Worker 无法获取全局 session advisory lock并立即退出/NotReady；主 Worker 进程退出后新 Worker 可获取锁恢复。
3. schema 不含 per-Run lease、heartbeat、fencing、submission-attempt history 或多 Worker claim 字段。
4. 分别在 arm 后 HTTP 前、Scheduler 接受后 response 前、job id CAS 前终止 Worker；恢复严格执行 correlation 0/1/多/incomplete 规则并证明最多一个 Job。
5. 分别在 Scheduler 终态观察后、Artifact rename 后、DB finalize 前终止 Worker；恢复后 Artifact 不覆盖，Run 终态和摘要一致。
6. 删除 FastAPI `_sync_loop`、同步 `_submit`、旧 Worker wrapper 和全部调用方；无 `SUBMITTED`，Snapshot 全程不变。

### D — Single-profile slurmrestd / Slurm（顺序 4，依赖 C）

1. 本地 fixture 覆盖单 profile 的 submit/find/poll/cancel、完整 correlation、UNKNOWN、协议错误和 Secret 去敏。
2. `nodes>1`、runtime 非 Native或 cluster mismatch 在 HTTP 前拒绝；不实现多节点分配、Apptainer 或 router。
3. HTTP non-2xx/timeout/invalid success 均 Uncertain；未知 pagination/metadata/filter/schema 均 correlation incomplete。
4. profile 不把 v0.0.40 或历史 v0.0.41 当目标事实；未完成人工核验时 Slurm 配置 fail-fast。
5. D 不写 Run DB、FS、Log 或 Artifact，不保留临时同步 consumer。

### 真实环境 human gate

用户明确禁用 `ustc-107-runner`。Agent 不为本 ADR 登录 107、启动 SSH bridge、访问真实 Shared FS、获取 token 或提交/查询真实 Job。由获授权的人在新窗口逐项确认：

1. 真实 Slurm/slurmrestd 版本、单 API profile、Bearer 或其他认证 header、target ClusterName、Account/Partition/QoS；
2. 完整 correlation 字段容量、精确查询权限、filter 和分页完整性；
3. `/public`、`/home` 或其他 canonical Shared FS 路径在 API/Worker/compute 的一致映射；
4. service UID、compute UID、`shared_gid`、目录权限和同目录 atomic rename；
5. Native 环境与最小无 Input Binding 命令。

充分证据是：经产品 API 创建无 Input Binding Run，返回 `QUEUED`；独立 Worker执行明确 Version marker；平台 job id 与权威查询一致；stdout/stderr、状态时间、exit code和一个 Artifact通过产品 API读回；在批准窗口验证一次响应丢失/落库前退出且恢复后最多一个关联 Job。evidence bundle 必须脱敏，不含 token、Secret、内部 endpoint 或用户凭据。

没有 fresh human evidence 时，只能称本地实现候选，不得声明真实 M1 链路通过。

## 非目标与风险边界

M1 明确不实现：

- 多 Worker 扩缩、热备 takeover、滚动双活；
- 任意数据库网络分区下继续执行；advisory-lock 连接丢失时 Worker 必须 fail-stop；
- 节点/内核掉电或通用 Shared FS power-loss durability；
- 消息队列、provider registry、通用 saga/补偿框架；
- 多 cluster、多 profile、多 node、Apptainer；
- Shared Resource、完整 Input Binding 和 M3 数据管理。

接受的窄风险是 public 不可见 Git orphan 可能占用存储；它不得成为正式 Version。发现真实生产数据保留、Worker 多副本或滚动部署义务时，必须重新决策，不能静默扩大本设计。

## 后果

- 好：四个 seam 保留，A/B/C 内部状态显著减少，审计集中在真实不变量。
- 好：应用进程重启和 submit ambiguity 仍完整处理，避免重复 Slurm Job。
- 好：单 writer/单 Worker 作为部署契约，比持续 lease/fencing 更容易运行和排障。
- 好：Shared Resource 保持 M3，M1 可用最小无输入 Run 验收。
- 坏：M1 Worker 吞吐受单进程串行限制；这是当前明确接受的范围。
- 坏：Git orphan 需在未来有真实容量压力时再评估清理，不在 M1 自动治理。
- **反悔成本：低到中**。窄 A/B/D seam 和 minimal intent 可在真实多副本需求出现时保留语义、替换内部协调；public RunStatus/Snapshot 不受影响。

## 未决人类决策

1. 真实 target cluster、slurmrestd 地址、认证方式及 Account/Partition/QoS。
2. correlation 字段、容量、精确查询与分页完整性。
3. `/public`、`/home` 或其他 Shared FS canonical mount mapping。
4. service UID、compute UID 与 `shared_gid` 的真实值和权限配置。
5. Native 验收命令、human gate 执行者、窗口和脱敏 evidence bundle 保存位置。

## 重新评估条件

- 产品或部署真实需要两个 active Worker、滚动双活或独立伸缩；
- 单 Worker 吞吐成为已测瓶颈；
- Git orphan 形成真实容量或合规义务；
- Shared FS 不支持所需原子 rename、权限隔离或 canonical path；
- Slurm 无法按稳定 correlation 做完整精确查询；
- 产品要求区分“待处理/已提交”或 M3 Input Binding 出现新的真实变化轴。

---
> 决策变更时新增 ADR，并将本记录标为被取代，不重写历史。
