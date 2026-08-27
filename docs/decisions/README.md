# 设计决策记录

这里记录反悔成本较高、不能只从代码看出理由的活动工程决策。

- 文件名使用 `NNNN-english-slug.md`。
- 编号只增不减，不复用。
- 决策改变时新增 ADR，并把旧记录标为被取代，不重写历史。
- 尚未决定的想法放 Issue 或 journal，不提前写成已接受决策。

| 编号 | 决策 | 状态 |
| :--- | :--- | :--- |
| [0001](0001-workspace107-migration-baseline.md) | 以 workspace107 已实现部分替换活动开发基线 | 已接受 |
| [0002](0002-documentation-topology.md) | 区分活动文档、参考材料与历史归档 | 已接受 |
| [0003](0003-competition-delivery-and-portable-capability-slices.md) | 比赛优先可见切片，并保持能力可由原 107 独立消费 | 已接受 |
| [0004](0004-m1-execution-seams.md) | 以四个窄接缝打通最小 M1 执行链路 | 提议中 |
| [0005](0005-platform-support-matrix.md) | 完整开发与运行只支持 Linux / WSL2 | 已接受 |

`archive/workspace107/docs/decisions/` 中的文件属于来源快照，只解释来源实现的历史，
不是当前仓库的活动 ADR。
