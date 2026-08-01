# 设计决策记录

这里记录**需要解释理由、且改起来代价很大**的决策：领域语义、边界划分、
端口设计、部署形态。

不记录：日常实现细节、能从代码直接读出来的事、还没想清楚的想法。

## 为什么要写

设计稿说「应该是什么」，代码说「现在是什么」，两者中间缺一层：
「当时为什么这么选，放弃了什么」。半年后有人想改这块，没有这一层就只能靠猜。

一条记录写清楚四件事：

```text
背景      当时面对什么问题
决策      最后选了什么
理由      为什么是它，放弃的方案差在哪
影响      带来什么约束，以后要注意什么
```

## 约定

- 文件名用 ASCII：`NNNN-english-slug.md`，正文用中文
- 编号只增不减，不复用
- 决策被推翻时**不删旧记录**，新写一条并在旧记录顶部标注「已被 ADR-NNNN 取代」
- 新增或修改决策要经过 Pull Request 评审

## 目录

| 编号 | 标题 | 状态 | 相关阶段 |
| :--- | :--- | :--- | :--- |
| [0001](0001-fork-semantics.md) | Fork 的复制语义与来源追踪 | 已接受 | M2 |
| [0002](0002-shared-resource-grants.md) | Shared Resource 的归属、版本与跨空间授权 | 已接受 | M2 |
| [0003](0003-activity-and-notification.md) | 活动与通知是两条独立的数据流 | 已接受 | M2 |
| [0004](0004-runtime-backend.md) | RuntimeBackend：Native / Conda / Apptainer | 已接受 | M2 |
| [0005](0005-deployment-topology.md) | 容器化部署形态 | 已接受 | M1 |
| [0006](0006-dependency-injection-and-api-contract.md) | 依赖注入与接口契约 | 已接受 | M1 |
| [0007](0007-submission-correctness-and-observability.md) | 提交路径的正确性与可观测性 | 已接受 | M1.5 |
| [0008](0008-capability-based-authorization.md) | 权限基于能力，以及四个角色的能力矩阵 | 已接受 | M2 |
| [0009](0009-visual-tokens.md) | 界面样式集中到令牌，视觉取向借鉴开发者工具 | 已接受 | M2 |
