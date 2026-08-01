# Milestone

Milestone 不是一组功能分类，而是一段**可以被演示和验收的阶段性成果**。
每个 Milestone 必须写清楚四件事：

```text
目标        这个阶段最终让用户完成什么
范围        包含哪些能力
非目标      明确不做什么
完成标准    怎么判断已经完成
```

其中「非目标」最重要，它防止开发过程中不断把别的能力顺手塞进当前阶段。

## 规划

| Milestone | 名称 | 状态 |
| :--- | :--- | :--- |
| [M0](M0-engineering-foundation.md) | Engineering Foundation | 已完成 |
| [M1](M1-core-run-loop.md) | Core Run Loop | 已完成 |
| — | M2 前置加固（并发、幂等、分页、可观测） | 已完成，见 [ADR-0007](../decisions/0007-submission-correctness-and-observability.md) |
| [M2](M2-collaborative-workspace.md) | Collaborative Workspace | 已规划，未开工 |
| M3 | Competition MVP | 未开始 |

开工前的设计决策记录在 [docs/decisions/](../decisions/README.md)。

## 过程中出现新想法时

```text
属于当前目标，且不做会阻断闭环
→ 加入当前 Milestone

重要，但不阻断当前闭环
→ 放入后续 Milestone 或 Backlog

改变了领域边界或产品定位
→ 先更新产品能力图并进行设计评审
```

## 开始一个 Milestone 前的短评审

1. 这个阶段最终要让用户完成什么？
2. 是否形成完整闭环？
3. 哪些能力明确不做？
4. 是否与 [产品设计最终稿](../product/design-final.md) 冲突？
5. 完成后是否能被实际演示和验收？

需要解释理由、改起来代价又很大的选择，评审时写成
[设计决策记录](../decisions/README.md)，不要只留在聊天记录里。
