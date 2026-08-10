# M1 Executable Skeleton 架构接缝

- 状态：已完成
- 认领：m1-architecture
- 上下文：`docs/decisions/`、`docs/journal/`
- 开始：2026-08-10
- 分支：`docs/m1-execution-seams`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-m1-architecture`

## 意图

在不实现业务代码的前提下，明确 M1 从确定 Project Version 到真实 Slurm 执行及结果回写的最小架构接缝，并把后续工作拆成 Git Version、Shared FS、Worker、Slurm 四个可独立审计的 Issue。

## 预期改动

- `docs/decisions/0003-m1-execution-seams.md`
- `docs/journal/2026-08-10-m1-execution-seams.md`

## 并行接缝检查

- 当前 `main`：核对 Run / Snapshot、`StoragePort`、`SchedulerPort`、FastAPI 内同步循环与本地存储实现。
- PR #3：只读核对其对 `run_service.py`、`StoragePort`、本地存储、Input Binding 和仓储容器的修改；不修改 GitHub。

## 仓外副作用

仅创建本地 linked worktree、短期分支和 commit；不 push、不创建或修改 Issue / PR，不访问真实 Shared FS / Slurm，不调用 `ustc-107-runner`。

## 回退方式

在确认 worktree 没有需保留内容后，由工作负责人按 Git contract 移除 linked worktree 和本地短期分支；已形成 commit 时可使用普通 `git revert <commit>` 保留审计历史。

## 验收

- ADR 区分产品事实、当前代码事实和技术决定。
- ADR 不把 Shared Resource、具体 Shared FS provider、消息队列或 `SUBMITTED` 状态写成 M1 前置条件。
- 四个 Issue 的 ownership、依赖、禁区、clean cutover 和机器可判定验收完整。
- 提交前完成 Markdown / repository 文档检查。

## 禁区

- 不修改业务代码、API 契约、数据库迁移或部署配置。
- 不合并、复制或改写 PR #3。
- 不 push、不创建 PR、不修改 GitHub。

## 实际结果

- 新增 ADR-0003，确定 A Git Version、B Shared FS、C Worker、D Slurm 的责任、顺序、依赖和禁区。
- 明确同步 Run 实现 clean cutover、Worker submit 幂等与歧义处理，以及 `QUEUED` / `scheduler_job_id` 语义。
- Shared Resource 保持 M3；真实 Shared FS / Slurm 验收被设为 human gate，Agent 不执行。
- 未修改业务代码、GitHub 或任何真实集群状态。
