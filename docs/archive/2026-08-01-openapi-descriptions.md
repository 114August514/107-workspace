# 修复 OpenAPI 字段说明生成

- 状态：已完成
- 认领：August / Codex
- 上下文：修复已编写字段说明未进入 OpenAPI 的生成缺陷
- 开始：2026-08-01 11:32 +0800
- 结束：2026-08-01 11:37 +0800

## 意图

让 API Schema 中已经编写的字段说明进入生成的 OpenAPI 和前端类型，同时区分生成缺陷
与尚未编写的 operation、模型和字段说明。

## 预期改动

- 为字段说明生成补充失败优先的契约测试。
- 启用 Pydantic attribute docstring 采集。
- 重新生成 `contracts/openapi.json` 和 `frontend/src/api/schema.d.ts`。
- 记录当前 description 覆盖情况，不自动拼接或伪造缺失说明。

## 仓外副作用

无。

## 回退方式

git revert <commit>

## 验收

- 字段 description 契约测试先失败后通过
- `make contract`
- `make contract-check`
- `make check`

## 禁区

- 不修改 API 路由、DTO 字段或业务行为。
- 不为尚未写说明的接口生成占位文案。
- 不新增依赖。

## 结果

- 确认顶层 `info.description` 一直正常生成；缺陷位于 Pydantic 字段元数据，而非导出器
  写文件或契约目录迁移。
- 5 个字段已经在源码中使用 attribute docstring 编写说明，但基础 `Model` 未启用
  `use_attribute_docstrings`，导致生成的 315 个属性此前没有任何 description。
- 契约测试先以 `KeyError: description` 失败；启用 Pydantic 配置后通过，并同时覆盖
  `WorkspaceOut.capabilities`、`FileWriteIn.content`、`PreflightOut.secret_references`、
  `NotificationOut.mandatory` 和 `ForkIn.name`。
- 重新生成的 `contracts/openapi.json` 只新增上述 5 个 description；
  `frontend/src/api/schema.d.ts` 只新增对应 JSDoc，TypeScript 类型没有改变。
- 当前 OpenAPI 共 63 个 operation、74 个 Schema 和 315 个属性；其中已有说明分别为
  8、21 和 5。其余缺口是源码尚未编写说明，不是生成失败，本次没有生成占位文案。
- API 契约测试 22 项、`make contract-check` 和 `make check` 均通过；完整检查包含工作流
  12 项、后端 271 项、前端 61 项，以及 lint、格式、类型、构建和契约比对。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次 OpenAPI 元数据修复未处理该既有事项。
- 未新增依赖，未修改路由、DTO 字段、API 类型或业务行为。
