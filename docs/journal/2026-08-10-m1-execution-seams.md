# M1 Executable Skeleton 本地候选交接

- 状态：BLOCKED/HANDOFF
- 认领：integration/m1-executable-skeleton
- 上下文：A/B/C/D 集成、本地验收、GitHub Issue 与真实 107 human gate
- 开始：2026-08-10
- 最近更新：2026-08-11
- 分支：`feat/7-m1-executable-skeleton`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-m1-integration`
- Code candidate：`72cf12b526e2eedea8891bc2c6c767923cdb4c4f`
- Journal refresh base HEAD：`79ec0b69ce438e74f3220692f71cfa71ff6ac6a4`
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

- `make check`：PASS；Backend `232 passed, 0 skipped`；workflow `17 passed`；Frontend `14 passed`；OpenAPI contract comparison 与 production build PASS。
- PostgreSQL ExecutionStore integration：`7 passed, 0 skipped`。
- Worker targeted verification：`6 passed, 0 skipped`。
- 官方 `make smoke`：连续两次 PASS；每次隔离运行并完成清理，无数据库、进程或存储残留。
- `make compose-config`：PASS；独立 Worker 为单副本，Scheduler/Slurm 配置只属于 Worker。
- Final independent review：PASS。
- Code candidate `72cf12b526e2eedea8891bc2c6c767923cdb4c4f` 验证后 worktree clean。

这些证据只证明本地候选及其 Mock/PostgreSQL/Compose 行为，不证明真实 Shared FS、slurmrestd 或 Slurm 已验收。

## GitHub MCP blocker：已解除

新 OMP 会话已实际挂载 `get_me`、`issue_write` 与 `create_pull_request`。`get_me` 确认认证用户为 `114August514`，`issue_write` 已创建 M1 Issue [#7](https://github.com/114August514/107-workspace/issues/7)。本地分支已按项目流程从 `integration/m1-executable-skeleton` 重命名为 `feat/7-m1-executable-skeleton`；push 与 PR 仍需在本 checkpoint commit 后完成。

## Blocker 2：真实 107 Shared FS/Slurm human gate

真实环境验收需要用户提供或确认：

- Account、Partition、QoS；
- 最小 nodes/tasks/CPU/memory/GPU/time limit；
- Shared FS canonical mount mapping、service/compute UID/GID；
- slurmrestd version/profile、认证方式、correlation 查询能力；
- 明确的真实执行授权和验收窗口。

在这些输入和授权具备前，不访问 107、不运行真实作业、不使用 `ustc-107-runner` Skill。当前没有真实 107 证据，不能声称 M1 真实环境 `DONE`。

## 仓外副作用

- 已创建 GitHub Issue [#7](https://github.com/114August514/107-workspace/issues/7)。
- 本地分支已从 `integration/m1-executable-skeleton` 重命名为 `feat/7-m1-executable-skeleton`。
- 尚未 push，尚未创建或 merge PR。
- 未删除 Docker volume。
- 本次 handoff 只更新现有 journal 并创建本地普通 commit；不记录本机 Secret。

## 下一步顺序

1. 将本 journal 的 Issue 与 branch 事实创建为普通 commit。
2. 记录 intended commit ID，push `feat/7-m1-executable-skeleton` 并用远端 ref 核对结果。
3. push 确认后使用 `create_pull_request` 创建关联 Issue #7 的 PR；不得使用 `gh` 或 REST 替代 GitHub MCP，不 merge。
4. 向用户收集并确认真实 107 human gate 参数与执行授权。
5. 在新授权窗口执行 Shared FS/Slurm 验收并保存脱敏 evidence；只有 fresh evidence 满足验收后，才重新判断 M1 状态。

## 回退方式

本次 journal checkpoint 使用普通 commit。需要撤销时执行 `git revert <本次 handoff commit>`，保留审计历史；不 amend、不 rebase、不重写历史。
