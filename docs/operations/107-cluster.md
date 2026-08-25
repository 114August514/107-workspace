# 107 集群运行事实与 M1 人工验收

这里记录目标 107 的可复用、脱敏事实以及仍未通过的人工门。通用容器与共享存储拓扑见
[`deployment.md`](deployment.md)；架构责任见 [ADR-0004](../decisions/0004-m1-execution-seams.md)。

## 证据边界

当前 Issue #7 v2 没有访问 SCOW、SSH、真实 mount、token 或 Scheduler，也没有提交真实作业。
本地 Mock/PostgreSQL/Compose 结果即使通过，也只能证明本地 executable skeleton。

旧 PR #8 在 **2026-08-11** 的获授权 probe 留下以下脱敏事实；它们是带日期的历史环境证据，
不是本次实现验收，也不能直接成为默认配置：

| fact | 2026-08-11 evidence | 当前结论 |
| :--- | :--- | :--- |
| Slurm/client/local slurmrestd | 25.11.2，cluster `training` | 版本、cluster 或 endpoint 变化后必须复验 |
| API profile | 目标 advertise `v0.0.41-44` | 当前 adapter 的单 profile 必须单独核对；不得 fallback |
| correlation query | v0.0.44 未证明 comment 精确过滤或查询完整性 | **未通过**；不得把 complete 配为 true |
| Shared FS | login/compute 对部分 canonical HOME 与 `/public` 可见同 backend/inode | 只证明 probe identity；未证明 service/compute/mount mapping |
| identity | probe compute identity 已观察 | 不是 service identity，也不是部署 UID/GID 验收 |
| credential probe | 一次短时 token 仅在远端单进程内使用 | 不证明 issuer、TTL policy、renewal、revocation 或 restart lifecycle |

任何未复验事实都不得写成 `.env` 默认值或“107 已接受”的结论。

## 启用 Slurm 前的停止门

先在脱敏验收记录中逐项标为“已确认”；任一未确认即停止并保持
`WORKSPACE107_SCHEDULER=mock`：

1. **服务与存储身份**：API/Worker service UID/GID、compute UID/GID、shared GID、setgid 与
   directory modes；API、Worker 和 compute 对 canonical storage path 的同内容映射；同目录
   atomic rename、只读 input、Log 与 Artifact 权限。
2. **REST profile**：单 target cluster、slurmrestd/Slurm version、API version、submit/job/list/
   cancel path、request/response schema、状态和错误映射。不同 profile 必须 clean replace，不能探测
   或兼容 fallback。
3. **correlation**：完整稳定 correlation 的字段、最大字节、无截断保存、server-side exact filter、
   权限和分页完整性。权限、filter、schema、metadata 或 pagination 任一不确定都必须返回
   `complete=false`。
4. **credential lifecycle**：issuer、签发主体与流程、允许的 TTL、Worker-only 注入、renewal 时机与
   失败行为、revocation、进程重启后的重新获取/失效策略。JWT 不进入 API、命令行、`.env`、DB、
   日志、异常、Scheduler script 或 evidence。仓库当前不替站点发明这些策略。
5. **资源与 runtime**：获批 Account、Partition、QoS、nodes/tasks/CPU/memory/GPU/time limit，
   以及 Native setup/command。当前只接受 Native 和单节点；Apptainer 或多节点需求必须停止。
6. **执行授权**：明确的操作人、时间窗口、最小作业内容、允许的 submit/query/cancel/restart 动作、
   停止条件和 evidence 保存位置。

## 最小真实验收（仅在新授权窗口）

1. 经产品 API 创建最小 Run；确认返回 `QUEUED`、job id 为空，且执行 authority 为持久化
   `initiated_by_user_id` + exact Snapshot + 当前授权。
2. Worker 在 materialize/submit 前重新校验 execution context；固定 Project Version marker 必须来自
   Snapshot 绑定的完整 commit OID。命令只写少量 stdout/stderr 和批准的 Artifact。
3. 比对平台 job id、完整 correlation、原始/映射状态、exit code 和时间；Log 与 Artifact 必须能从
   产品 API 读回。没观察到的中间状态不能补写。
4. 在另一个明确批准的窗口制造 submit response 丢失或 job id 落库前退出。恢复只能按完整查询
   得到 0/1/多匹配；唯一匹配关联原 job，多匹配或 incomplete 停止，绝不盲目重提。
5. 单独验证 credential expiry/renewal/revocation 与 Worker restart 行为；没有站点 policy 和 fresh
   evidence 就保持未通过。

## 歧义和停止条件

在目标 allowlist 未核验前，submit 的 HTTP non-2xx、timeout、transport failure、invalid success 或
2xx 缺 job id 一律视为 ambiguous；只有发 HTTP 前的本地校验失败能确定为 Rejected。poll 404、
未知状态、correlation 权限不足或结果不完整都不能伪造成成功或权威零匹配。

evidence 只能保存日期、版本、配置项名称、脱敏值、correlation/job id、状态/时间、marker 摘要和
结论；不得保存 token、认证 header 值、Secret、内部 endpoint/IP、用户凭据或个人绝对路径。
