# M1 Executable Skeleton 本地候选交接

- 状态：BLOCKED/HANDOFF
- 认领：integration/m1-executable-skeleton
- 上下文：A/B/C/D 集成、本地验收、GitHub Issue 与真实 107 human gate
- 开始：2026-08-10
- 最近更新：2026-08-11
- 分支：`integration/m1-executable-skeleton`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-m1-integration`
- Code candidate：`72cf12b526e2eedea8891bc2c6c767923cdb4c4f`
- Journal refresh base HEAD：`79ec0b69ce438e74f3220692f71cfa71ff6ac6a4`
- MCP config：root 与 integration worktree 的 `.omp/mcp.json` 均已允许 `issue_write`，并包含 `create_pull_request`

## 当前状态

本地 executable skeleton 候选已经完成并通过独立评审，但外部 Issue 流程和真实 107 环境验收尚未完成。因此当前状态是 **BLOCKED/HANDOFF**，不是 M1 真实环境 `DONE`。

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

## Blocker 1：当前延续会话未加载 GitHub MCP tools

root 与 integration worktree 的 `.omp/mcp.json` 均已允许 `issue_write`，并包含 `create_pull_request`；但当前延续 OMP 会话的实际 tool inventory 只有 `functions` 与 `multi_tool_use`。全部 GitHub tools 均不可用并返回 `Unknown tool`，因此配置文件事实不等于本会话已获得 GitHub capability。

必须完全退出当前 OMP process，再从 integration worktree 启动一个全新的 OMP session；只 reload shell、重载 terminal 或继续旧会话均不满足恢复条件。新会话必须同时确认实际 inventory 包含 `issue_write`、`create_pull_request`，且 native Git 可运行，才能继续。禁止以 `gh`、直接 REST 或其他 GitHub 写入口替代官方 GitHub MCP。

## Blocker 2：真实 107 Shared FS/Slurm human gate

真实环境验收需要用户提供或确认：

- Account、Partition、QoS；
- 最小 nodes/tasks/CPU/memory/GPU/time limit；
- Shared FS canonical mount mapping、service/compute UID/GID；
- slurmrestd version/profile、认证方式、correlation 查询能力；
- 明确的真实执行授权和验收窗口。

在这些输入和授权具备前，不访问 107、不运行真实作业、不使用 `ustc-107-runner` Skill。当前没有真实 107 证据，不能声称 M1 真实环境 `DONE`。

## 仓外副作用

- 未创建或修改 GitHub Issue/PR。
- 未执行 branch rename。
- 未 push。
- 未访问 107、Shared FS、slurmrestd 或 Slurm。
- 未删除 Docker volume。
- 本次 handoff 只更新现有 journal 并创建本地普通 commit；不记录本机 Secret。

## 恢复后的下一步顺序

1. 完全退出当前 OMP process；不得以 reload shell、重载 terminal 或继续旧会话代替。
2. 从 `/home/august/Projects/ustc_107/107-workspace-m1-integration` 启动一个全新的 OMP session，并回到 `integration/m1-executable-skeleton`。
3. 确认实际 tool inventory 同时包含 `issue_write` 与 `create_pull_request`，且 native Git 可运行；任一条件不满足就保持 BLOCKED/HANDOFF。
4. 用 native Git 只读确认 journal checkpoint、code candidate、branch/HEAD 和 worktree clean。
5. Inspect `issue_write` 的实际 schema 后使用它创建 M1 Issue，引用本 journal、ADR-0003、code candidate、本地证据和两个 blocker；不得猜参数。
6. Issue 创建成功后关联现有工作；仅在项目流程确有需要且 native Git 安全条件满足时，将 branch rename 为 Issue 关联名称。
7. 把 Issue 关联和必要的 branch 事实写回本 journal，创建普通 journal commit。
8. 获得相应授权后记录 intended commit ID，再 push 对应 branch。
9. 确认 push 后使用 `create_pull_request` 创建 PR；不得使用 `gh` 或 REST 替代 GitHub MCP。
10. 向用户收集并确认真实 107 human gate 参数与执行授权。
11. 在新授权窗口执行 Shared FS/Slurm 验收并保存脱敏 evidence；只有 fresh evidence 满足验收后，才重新判断 M1 状态。

## 回退方式

本次 journal checkpoint 使用普通 commit。需要撤销时执行 `git revert <本次 handoff commit>`，保留审计历史；不 amend、不 rebase、不重写历史。
