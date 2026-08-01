# 补齐 OpenAPI 接口说明

- 状态：已完成
- 认领：August / Codex
- 上下文：补齐公开 API operation 的中文摘要与说明
- 开始：2026-08-01 11:48 +0800
- 结束：2026-08-01 12:05 +0800

## 意图

让生成的 OpenAPI 契约直接呈现可读、准确的中文接口文档，并通过契约测试防止后续新增接口遗漏摘要或说明。

## 预期改动

- `backend/src/workspace107/api/routes/`
- `backend/tests/contract/test_api_contract.py`
- `contracts/openapi.json`
- `frontend/src/api/schema.d.ts`

## 仓外副作用

无。

## 回退方式

回退本任务提交后重新运行 `make contract`。

## 验收

- 接口文档契约测试先失败后通过
- `make contract`
- `make contract-check`
- `make check`

## 禁区

- 不改路由路径、HTTP 方法、DTO、响应模型或业务逻辑
- 不给缺少可靠语义来源的字段批量填充占位文案
- 不加依赖

## 结果

- 63 个 `/api/v1` operation 均使用显式中文 `summary`，并从路由函数 docstring 生成准确的
  中文 `description`；说明覆盖权限、不可变性、幂等、截断、Secret 可见性和关键副作用。
- 新增契约测试，逐个检查 GET、POST、PUT、PATCH、DELETE operation 的摘要和说明均包含
  中文；测试在补齐文档前失败，完成后通过。
- 重新生成 `contracts/openapi.json` 和 `frontend/src/api/schema.d.ts`；结构化比对确认
  OpenAPI 只改变 `summary` / `description`，TypeScript 只改变注释，接口与类型没有漂移。
- `make contract-check` 通过；`make check` 通过，包含工作流 12 项、后端 272 项、前端
  61 项，以及 lint、格式、类型检查、构建和契约比对。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次接口文档补齐未处理该既有性能事项。
- 未新增依赖，未修改路由、DTO、响应模型、权限规则或业务行为。
