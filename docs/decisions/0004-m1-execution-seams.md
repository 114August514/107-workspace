# 0004. 以四个窄接缝打通最小 M1 执行链路

- 状态：提议中
- 日期：2026-08-26

## 背景

Issue #7 要把 Git Project Version、POSIX Run workspace、独立 Worker 和单一 Slurm REST
profile 接成最薄可执行闭环。当前 main 已包含 #41 的执行授权修复，因此旧 PR #8 中任何以
`workspace_id` 代替授权、Secret scope、entitlement、Input access 或执行身份的路径都不能恢复。

执行 authority 固定为：持久化的 `Run.initiated_by_user_id`、该 Run 的 exact immutable
`RunSnapshot`，以及 Worker 推进前重新执行的当前授权校验。Snapshot 是唯一执行配置；Project
Version 绑定完整 immutable commit OID。Run workspace identity 是
`(run_id, snapshot_id, project_version_id, commit_oid)`。

HTTP 事务不能和 Scheduler submit 原子提交。若 Scheduler 已接受但 job id 尚未持久化，盲目
重试会创建重复作业。另一方面，多 Worker、lease/heartbeat/fencing、消息队列和 provider
framework 都不是当前产品义务，只会扩大失败面。

## 决定

采用四个窄 seam 和一个 active Worker：

```text
HTTP API -> PostgreSQL: exact Snapshot + QUEUED Run + durable execution intent
                                      |
                                      v
single active Worker -- current authorization revalidation
        |-- ProjectVersionExporter -> exact Git commit
        |-- RunWorkspace            -> canonical POSIX shared path
        `-- SchedulerPort           -> submit/find/poll/cancel
                                      |
                                      v
                         terminal Run + Log + Artifact
```

### A. Git Project Version

- DB 可见 Version 必须绑定完整 commit OID 和不可变 ref；Worker 不接受 branch、HEAD、latest
  或 Working State。
- Git ref 先发布，DB row 后可见；失败允许留下 public 不可见 orphan，不建立通用 DB/Git saga。
- 导出必须逐项核对固定 commit；后续 Working State 变化不得影响已保存 Version。

### B. POSIX Run workspace

- identity 精确包含 run、snapshot、version 和 commit；同 identity 可恢复，不同 identity 冲突。
- canonical storage root 由 API 与 Worker 以同一路径和同一 `storage_gid` 挂载；两进程必须加入该组，
  Worker 当前的 Run-tree `shared_gid` 必须与它相同。
- 当前全局 group 只解决 local seam 的 compute 写入，不构成 cross-Run isolation；同组 identity
  能遍历其他 Run，因此真实 Slurm/native Worker 必须 fail-closed。
- 启用真实 compute 前必须实现并验证 per-job identity、per-Run group/ACL 或 mount namespace 中的一种
  最小隔离 contract，使 Run A 不能访问 Run B、Project Git、blob store 或 Artifact control state。
- canonical root 的 ancestor、owner、GID 和 mode 必须在 API/Worker composition 前 fail-closed；
  `projects/`、`blobs/` 和 Artifact control area 保持 service-private，Run Input 保持只读。
- 单 Worker 是唯一 service writer；不增加 per-run lease、heartbeat、claim 或 fencing。

### C. 独立 Worker

- API 只提交事务内 intent，不持有 Scheduler 或 Slurm credential/config，也不在 FastAPI
  lifespan 内 submit、poll 或推进执行。
- Worker 启动时取得 PostgreSQL session advisory lock；部署副本数固定为一。锁连接丢失时
  fail-stop，不自动变成多 Worker 协议。
- 每次 materialize 或 submit 前调用从 #41 提取的
  `ExecutionContextService.validate(run, snapshot)`，用 initiated user 和当前授权重新校验。
- Snapshot 是唯一执行配置；持久 intent 只保存恢复必需事实，不复制可漂移配置。

### D. 单目标 Scheduler profile

- adapter 只实现一个 fixture-backed target/schema profile 和 Native payload；不提供多 profile、
  多 cluster、Apptainer fallback 或兼容探测。真实 Slurm Worker 在 filesystem isolation 落地前拒绝启动。
- correlation 使用完整稳定值。submit 前持久 arm；job id 用 compare-and-set 关联。
- 响应丢失、timeout、HTTP non-2xx、invalid success 或 job id 未落库时必须先按 correlation reconcile。
- 只有查询完整且零匹配才可再次 submit；唯一匹配关联原 job；多匹配或 incomplete 必须停止，
  绝不重提。只有 HTTP 前本地拒绝能确定为未提交。

## 运行与配置边界

- 完整开发、Worker/Shared FS/smoke/deploy 目标是 Linux 与 WSL2；原生 Windows /
  PowerShell runtime 不受支持，详见 ADR-0005。
- Compose 只有一个 Worker，API 与 Worker 共享 canonical storage；Scheduler/Slurm 配置与 JWT
  只注入 Worker。
- MockScheduler 只用于 local/test，并在 Worker 主机真实执行命令，不是沙箱。
- Worker 必须使用 PostgreSQL。官方 smoke 为每次调用创建独立数据库和临时 storage，同时启动
  API 与外部 Worker，结束后终止进程并删除隔离数据库/目录。

## 真实 107 人工门

本 ADR 和本地 smoke 不授权访问 107，也不证明真实部署。当前 `scheduler=slurm` 会在 Worker 启动时
机械失败；它不能通过填写环境变量解除。解除该代码门之前，获授权的人必须确认：

1. 能机械保证 Run A 不可访问 Run B、Project Git、Shared Resource blob 和 Artifact control state 的
   per-job identity、per-Run group/ACL 或 mount isolation contract，并用 distinct compute identity 验证；
2. service identity、compute identity、canonical mount mapping、setgid/ACL 与只读 Input 权限；
3. slurmrestd version、单 profile、target cluster、路径、响应 schema 与状态映射；
4. correlation 字段容量、精确过滤权限和分页完整性；
5. credential issuer、签发方式、TTL、注入、renewal、revocation 与进程重启策略；JWT 必须只进入
   Worker 内存，不能进入 API、命令行、数据库、日志或 evidence；
6. Account/Partition/QoS/resources、Native setup 和 authorized submit/restart 验收窗口。

完成 filesystem isolation 的实现、测试和重新评审之后，才允许删除 startup fail-closed。随后真实验收
还必须覆盖一次获授权最小 submit，以及一次 ambiguous response/restart 恢复并证明不会重复作业。

## 非目标

- 多 Worker、热备、lease/heartbeat/fencing、队列或 provider registry；
- 多 cluster/profile、兼容 fallback、Apptainer 或多节点资源框架；
- 未经授权的 107 probe、mapping、认证或 submit；
- 修改 `/me`、Home、Activity、Notification、前端路由/类型或 Workspace projection cleanup。

## 后果

执行责任从 API 清晰移到一个独立 Worker；恢复和 submit ambiguity 有持久事实，但系统不承担尚未
出现的分布式协调义务。代价是吞吐受单 Worker 限制，且真实 107 仍需人工验收。出现真实多 Worker
义务、Shared FS 不满足语义或 correlation 无法完整精确查询时，必须新增 ADR 重新决策。

---
> 决策变更时新增 ADR，并将本记录标为被取代，不重写历史。
