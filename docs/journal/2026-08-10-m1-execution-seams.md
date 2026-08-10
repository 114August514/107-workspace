# M1 Executable Skeleton 架构接缝

- 状态：已更新
- 认领：m1-architecture
- 上下文：`docs/decisions/`、`docs/journal/`
- 开始：2026-08-10
- 最近更新：2026-08-10
- 分支：`docs/m1-execution-seams`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-m1-architecture`

## 意图

在不实现业务代码的前提下，明确 M1 从确定 Project Version 到真实 Slurm 执行及结果回写的最小架构接缝，并把后续工作拆成 Git Version、Shared FS、Worker、Slurm 四个可独立审计的 Issue。

## 最新人类决定

- 系统整体简单性优先于自治能力，不因候选代码已经复杂而迁就它。
- M1 采用单 Project writer、单 active Worker；功能最小但必须形成真实完整闭环。
- 只要求应用进程重启恢复、绝不重复 Slurm Job、Version 不漂移和 Artifact 不覆盖。
- 多 Worker 扩缩、任意网络分区、节点掉电一致性和通用 provider/saga 不属于 M1。
- Shared Resource 仍属于 M3；M1 以无 Input Binding Run 验收。

## 预期改动

- `docs/decisions/0003-m1-execution-seams.md`
- `docs/journal/2026-08-10-m1-execution-seams.md`

## 审计输入

- Lean Harness `working-contract.md` 的简单性、持续设计、开发收敛与兼容规则。
- ADR-0003 原提案、当前 `main@74a41f9` 与 A/B/C/D 候选 branch tip/diff 结构。
- `docs/references/platform/` 原始材料：历史 `/public`/`/home` 共享路径与 Slurm v0.0.41/Bearer 示例。
- A/B/C/D targeted review：DB/Git、Shared FS、Worker 提交歧义和 Slurm profile 风险。

原始平台材料只用于触发 human gate。材料中的 Slurm 25.11、v0.0.41、Bearer 与当前 v0.0.40/X-SLURM-header 候选冲突，不作为实现默认值。

## clean replace 结果

### A Git Version

- 使用 PostgreSQL transaction advisory lock 或等价最小生产锁保证单 Project writer。
- immutable Version ref 先于正式 DB row；DB 失败允许留下 public 不可见 orphan。
- 删除 DB/Git pending saga、pending ref、`main` 一致性和重复 manifest 状态。

### B Shared FS

- 单 active Worker 是唯一 writer；删除 per-Run/Artifact locks、claims 和多 owner takeover。
- 保留 identity marker、staging/atomic rename、进程重启恢复、openat 路径安全和 first-installed Artifact evidence。
- 明确 service UID、compute UID 与 `shared_gid` 权限；Artifact store/control 只对 service UID 开放。

### C Worker

- 一个 PostgreSQL session advisory lock 保证单 active Worker；获取失败退出，连接丢失 fail-stop。
- execution intent 只保留 correlation、attempt、next action、cancel/uncertainty 和 terminal observation。
- 删除 per-Run lease/heartbeat/fencing、submission-attempt history 和双 Worker自治测试。
- 保留 submit 前 arm、job id CAS 与 correlation 0/1/多/incomplete 恢复。

### D Slurm

- 只保留 Native、nodes=1、single cluster、single profile。
- 所有未经人工 allowlist 证明的 HTTP non-2xx/transport/invalid success 都是 Uncertain。
- 真实 version、认证、profile、correlation 与 cluster 只能由 human gate 确认。

## 四个 Issue 顺序

1. A — 发布不可漂移的 Git-backed Project Version。
2. B — 在单 writer 下准备可恢复 Shared FS workspace 和不可覆盖 Artifact。
3. C — 以全局 advisory lock 运行独立 Worker，并完整恢复 submit ambiguity。
4. D — 接入单 target cluster/profile 的 slurmrestd / Slurm，并执行人类验收。

## 仓外副作用

仅更新本地 ADR、journal 并创建普通 commit；不 push、不创建或修改 Issue/PR，不访问真实 Shared FS/Slurm，不调用 `ustc-107-runner`。

## 回退方式

已形成 commit 后使用普通 `git revert <commit>` 保留审计历史；不 amend、不重写历史。

## 验收

- ADR 保持“提议中”，区分产品事实、技术决定与历史参考事实。
- A/B/C/D ownership、禁区、删除清单、非目标和机器可判定验收已按简单性决定 clean replace。
- ADR 不把 Shared Resource、具体 Shared FS 路径、历史 Slurm version/header、消息队列或 `SUBMITTED` 写成 M1 前置实现事实。
- 文档检查通过后创建一个新 commit；不 amend、不 push。

## 文档检查

- `git diff --check`：通过。
- 变更范围：仅 ADR-0003 与本 journal。
- 语义自检：ADR 状态仍为“提议中”；A/B/C/D 决定、删除清单、非目标、Shared Resource M3 边界和历史平台事实 human gate 均已出现。
- 仓库没有独立 Markdown checker；未用项目全量测试替代文档检查。

## 实际结果

- ADR-0003 已改为单 Project writer、单 active Worker 的最小集成架构。
- 保留四个窄 seam 和真实 submit ambiguity 恢复，删除提前多副本自治设计。
- 历史 `/public`/`/home` shared 与 v0.0.41/Bearer 被明确标为 human-gate 输入。
- Shared Resource 保持 M3；未修改业务代码、GitHub 或真实集群状态。
