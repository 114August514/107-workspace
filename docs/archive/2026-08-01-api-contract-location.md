# 收敛 API 机器契约目录

- 状态：已完成
- 认领：August / Codex
- 上下文：将生成的 OpenAPI 契约从 docs/ 迁入根 contracts/
- 开始：2026-08-01 11:18 +0800
- 结束：2026-08-01 11:26 +0800

## 意图

把生成的 OpenAPI 从人工文档树中分离，明确后端生成、根目录共享契约、前端派生类型
三者的所有权，同时保持 `make contract` 和 `make check` 的行为不变。

## 预期改动

- 将 `docs/api/openapi.json` 迁移为 `contracts/openapi.json`。
- 新增中文 `contracts/README.md`，说明生成、消费、提交和禁止手改规则。
- 同步脚本、Doctor、审计信号、前后端说明和活动目录索引。
- 补充契约产物所有权的工作流回归测试。

## 仓外副作用

无。

## 回退方式

git revert <commit>

## 验收

- 契约路径测试先失败后通过
- `make contract-check`
- `make doctor`
- `make check`

## 禁区

- 不修改 OpenAPI Schema 内容或前端生成类型。
- 不调整应用 API、路由或 DTO。
- 不新增依赖。

## 结果

- `docs/api/openapi.json` 迁移为 `contracts/openapi.json`，迁移前后的 Git 对象哈希均为
  `73bd3dd85547a929f655f8b7cfc244efaeaa1a7a`，契约内容未改变。
- 新增中文 `contracts/README.md`，明确后端生成、共享契约和前端派生类型的责任边界；
  `docs/` 不再混放机器生成物。
- `make contract`、前端 `generate:api`、Doctor、审计信号、Git 属性、活动索引和产品设计
  目录图均使用新路径；前端生成类型仍保留在服务目录。
- 契约产物所有权测试先在旧路径下失败，完成迁移后通过；工作流测试增至 12 项。
- `make contract-check` 和前端 `pnpm run generate:api` 均通过，重新生成结果与已提交契约
  和类型一致；活动文档引用测试 4 项通过。
- `make doctor` 通过，确认 Node 24.18.0 与 pnpm 11.18.0；仅提示可选 hooks 未启用。
- `make check` 通过：工作流 12 项、后端 270 项、前端 61 项，以及 lint、格式、类型、
  构建和 API Contract 全部通过。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次契约目录整理未处理该既有性能事项。
- 未新增依赖，未修改 API Schema、路由、DTO 或远端仓库状态。
