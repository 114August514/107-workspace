# 文档索引

## 活动指导

| 问题 | 文档 |
| :--- | :--- |
| 产品能力、术语、规则和 Roadmap | [`product/design.md`](product/design.md) |
| 延后设计事项与已接受的实现妥协登记 | [`product/deferred.md`](product/deferred.md) |
| Git、Issue、分支、提交和 PR | [`contributing/git-workflow.md`](contributing/git-workflow.md) |
| Coding Agent 项目入口、工程原则和工作路由 | [`../AGENTS.md`](../AGENTS.md) |
| 测试策略、测试粒度和验证边界 | [`testing/`](testing/README.md) |
| 前端实现、Primer 使用与迁移边界 | [`../frontend/README.md`](../frontend/README.md) |
| API、生成类型和跨组件机器契约 | [`../contracts/`](../contracts/README.md) |
| 部署方式与生产边界 | `operations/deployment.md`，可执行清单见 [`../deploy/`](../deploy/README.md) |
| 长期工程决策及其取舍 | [`decisions/`](decisions/README.md) |
| 在途工作、跨会话恢复、并行协作和交接 | [`journal/`](journal/README.md) |

## 证据与历史

[`references/`](references/README.md)
只保存仍有价值的外部输入和来源记录，不自动成为当前产品或工程事实。

[`archive/`](archive/README.md)
解释已经退出活动文档树的过程材料；

源码与迁移前实现快照位于仓库根目录的
[`archive/`](../archive/README.md)。

历史材料不能覆盖当前活动事实。

涉及产品能力、领域术语和业务规则时，
以当前 `product/design.md` 为权威来源。

涉及已经形成的长期工程决定及其原因时，
读取当前适用的 [`decisions/`](decisions/README.md)。

跨前后端的生成式 API 契约属于机器契约，
统一保存在 [`contracts/`](../contracts/README.md)，
不要从历史文档或手写说明推断其当前形状。
