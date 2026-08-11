# M1 Executable Skeleton 本地候选交接

- 状态：BLOCKED/HANDOFF
- 认领：integration/m1-executable-skeleton
- 上下文：A/B/C/D 集成、本地验收、GitHub Issue 与真实 107 human gate
- 开始：2026-08-10
- 最近更新：2026-08-11
- 分支：`feat/7-m1-executable-skeleton`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-m1-integration`
- PR8 pre-checkpoint HEAD（本次文档修改前）：`12f1722aba7ea7d1e7cb8401eb5f341aa353da8e`
- Journal refresh base HEAD（本次文档修改前）：`12f1722aba7ea7d1e7cb8401eb5f341aa353da8e`
- MCP：新会话已实际挂载并验证 `get_me`、`issue_write`、`create_pull_request`；认证用户为 `114August514`

## 当前状态

本地 executable skeleton 候选已经完成并通过独立评审，GitHub Issue [#7](https://github.com/114August514/107-workspace/issues/7) 已创建；真实 107 环境验收尚未完成。因此当前状态仍是 **BLOCKED/HANDOFF**，不是 M1 真实环境 `DONE`。

A Git Version、B Shared FS、C Worker、D Slurm 已集成到同一 vertical slice。最终 independent review 为 **PASS**。切片范围较广，但耦合评估为 **PASS**：A/B/C/D ownership 已收敛；取消与轮询的不确定性合并只存在于 `RunWorker` 与 `ExecutionStore` seam，没有新增 public 状态、lease、history 或 schema。

## 仍有效的架构决定

- M1 采用单 Project writer、单 active Worker；不为多 Worker 扩缩、任意网络分区或节点掉电一致性增加通用 saga/provider。
- Project Version 对应不可漂移的完整 Git commit 和 immutable ref；数据库失败允许留下 public 不可见 orphan。
- Run workspace 由单 active Worker 独占写入；保留 identity marker、staging/atomic rename、进程重启恢复、openat 路径安全和 first-installed Artifact evidence。
- execution intent 只保留 correlation、attempt、next action、cancel/uncertainty 和 terminal observation；不引入 per-Run lease/heartbeat/fencing 或 submission-attempt history。
- Worker 在 submit 前 arm；响应不确定时必须按完整 correlation 做 0/1/多/incomplete 恢复，不能盲目重提。
- poll failure/`UNKNOWN` 是比同轮 cancel failure 更权威的 Scheduler 观察；`PENDING`/`RUNNING` 才保留未解决的 cancel uncertainty；terminal 清除 uncertainty 并 finalize。该语义由 Worker 与 ExecutionStore 单字段、短事务 seam 承担。
- Slurm 候选只保留 Native、`nodes=1`、single cluster、single profile。真实 version、认证、profile、correlation 与 mount mapping 只能由 human gate 确认。
- Shared Resource 仍属于 M3；M1 以无 Input Binding Run 验收。

## 本地候选证据

- `make check`：PASS；Backend `234 passed, 0 skipped`；workflow `19 passed`；Frontend `14 passed`；OpenAPI contract comparison 与 production build PASS。
- PostgreSQL ExecutionStore integration：`7 passed, 0 skipped`。
- Worker targeted verification：`6 passed, 0 skipped`。
- 官方 `make smoke`：连续两次 PASS；每次隔离运行并完成清理，无数据库、进程或存储残留。
- `make compose-config`：PASS；独立 Worker 为单副本，Scheduler/Slurm 配置只属于 Worker。
- Final independent review：PASS。
- Code candidate `12f1722aba7ea7d1e7cb8401eb5f341aa353da8e`（pre-document checkpoint）。

这些证据只证明本地候选及其 Mock/PostgreSQL/Compose 行为，不证明真实 Shared FS、slurmrestd 或 Slurm 已验收。

## GitHub MCP blocker：已解除

新 OMP 会话已实际挂载 `get_me`、`issue_write` 与 `create_pull_request`。`get_me` 确认认证用户为 `114August514`；`issue_write` 已创建 M1 Issue [#7](https://github.com/114August514/107-workspace/issues/7)；本地分支已按项目流程重命名并 push 为 `feat/7-m1-executable-skeleton`；`create_pull_request` 已创建 PR [#8](https://github.com/114August514/107-workspace/pull/8)。PR 使用 `Refs #7`，因为真实 107 human gate 尚未完成；本流程不 merge。

## Blocker 2：真实 107 M1 human gate（2026-08-11 fresh evidence）

可复用事实与 runbook 见 [`107-cluster.md`](../operations/107-cluster.md)。

本次获授权 probe 已访问 107：先运行一次 `sbatch --test-only`（不产生 job），再提交
一次实际最小 batch job 36100；没有执行真实 M1 Worker/REST submit，也没有证明
submit ambiguity/restart 恢复。当前仍需：

- PR8 从 v0.0.40 clean replace 到目标 API profile；目标 advertise `v0.0.41-44`，当前兼容性 **FAIL**。
- v0.0.44 correlation 查询没有 comment 精确过滤，且无法证明查询完整性；
  `correlation_query_complete` 不能设为 `true`。
- service image `10001:10001` 与 probe compute identity `66703:66703` 的权限、
  `shared_gid`、专用 storage root 及 `/var/lib/workspace107/storage` 到 compute 的
  canonical mapping 未验；当前只验证同一 compute UID。
- Native M1 Worker/REST 端到端、submit ambiguity/restart 窗口仍未验。

因此状态仍为 **BLOCKED/HANDOFF**，不能宣称 M1 真实环境 `DONE`。

## 仓外副作用

- 已创建 GitHub Issue [#7](https://github.com/114August514/107-workspace/issues/7)。
- 本地分支已从 `integration/m1-executable-skeleton` 重命名为 `feat/7-m1-executable-skeleton`。
- `feat/7-m1-executable-skeleton` 已 push，GitHub PR [#8](https://github.com/114August514/107-workspace/pull/8) 已创建但未 merge。
- 2026-08-11 在授权窗口登录并访问 107；先执行 `sbatch --test-only`（无 job side effect），
  再运行一次实际最小 batch job 36100，这是一次外部副作用。
- 最小作业事实：平台 job id `36100`，脱敏 correlation/name `w107-probe-20260811T044406Z-fdf170`，
  account `stu`，partition `Students`，省略 QoS 后生效 `qos_stu_medium_2gpu`，
  nodes=1/task=1/cpu=1/mem=64M/time=1m，节点 `anode16`，ReqTRES 为
  `cpu=1,mem=64M,node=1,billing=1`；04:44:21Z 提交一次，04:44:22Z 开始并结束，
  `COMPLETED 0:0`，test-only 通过，队列已清空。
- 初始查询截至 04:47:20Z 为 rc=0、无行；fresh read-only follow-up 截至 `2026-08-11T05:05:23Z`
  按 job id，以及按 own user + jobname + UTC day 两种 `sacct -X` 边界查询均 rc=0、empty；
  queue clean，无新 job 或文件修改。accounting gap 仍未补写或推断状态。
- 远端脱敏证据位于 `~/project/107-workspace-probes/20260811T044406Z-fdf170/`，
  包含 evidence.txt、script、markers、stdout/stderr；stderr 为空，logs 保留。
- Shared FS：login/compute 对 canonical HOME 与 `/public` 可见同 backend/inodes，
  login marker read compute PASS；同目录 staging→final rename inode 保持且 login 可见 PASS。
  仅同一 probe compute UID `66703:66703`，不能据此升级为 service identity、shared_gid、
  专用 storage root 或 `/var/lib/workspace107/storage` mapping PASS。
- REST endpoint 仅记录为可达且未认证返回 401；一次 120s token 只在远端单进程内存生成，
  通过 `X-SLURM-USER-NAME`/`X-SLURM-USER-TOKEN` 访问 OpenAPI（200），未打印、落盘、
  export 或放入 argv，进程退出后不保留。不得记录 token 或 endpoint 细节。
- 探针期间与后续文档收敛均未删除 Docker volume；无 Docker volume 变化。

## 下一步顺序

1. 保持 Issue #7 与 PR #8 打开，不在本流程 merge。
2. 先为目标 v0.0.41-44 重新核验并实现单一 profile；在 correlation 精确查询和完整性
   证明前，不设 `correlation_query_complete=true`。
3. 以 service/compute 双身份完成 shared_gid、专用 storage root 和固定
   `/var/lib/workspace107/storage` mapping 验收。
4. 在新的明确授权窗口执行真实 M1 Worker/REST submit，并单独验证 submit ambiguity/restart；
   只有 fresh evidence 满足全部验收后，才重新判断 M1 状态。

## 回退方式

本次 checkpoint 更新 operations 与 journal，未创建 commit；如需撤销应使用受控、可审计的
文档变更，不 amend、不 rebase、不重写 Git 历史。

## 2026-08-11 Competition Demo 轨道调整 checkpoint

产品近期目标已调整为受信任本地环境中的 Competition Demo，交付与验收权威口径见
[`docs/product/design.md`](../product/design.md) §0.2。真实 107 M1 human gate 转为赛后
集成轨，仍保持 **BLOCKED/HANDOFF**；本地候选可以支持 Competition Demo，但不因此成为
真实 M1 `DONE`。上文记录的外部 probe、FAIL / INSUFFICIENT 结论、仓外副作用和后续
human-gate 验收项均未改变。

外部 ChatGPT 分享只作为带归属的设计输入记录在
[`platform-positioning-chat.md`](../references/engineering/platform-positioning-chat.md)，
不作为产品动机、用户研究、目标 107 事实或比赛规则的权威来源。
