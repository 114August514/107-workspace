# 文档

## 阅读地图

**改哪块之前先读什么。** 直接照着代码改容易漏掉当初为什么这么设计——
这张表就是为了让那些理由能被找到。

| 你要改的东西 | 先读 | 再检查 |
| :--- | :--- | :--- |
| 产品范围、能力优先级 | [产品设计最终稿](product/design-final.md) | [当前 Milestone](milestones/README.md) |
| 领域对象、归属关系、命名 | [领域语言](domain/glossary.md) | [全局不变量](domain/invariants.md) |
| 权限判断、可见性 | [GR-001 / GR-013](domain/invariants.md) | `application/access.py`、`tests/unit/test_access_guard.py` |
| 版本、快照类不可变对象 | [GR-003 / GR-009](domain/invariants.md) | `tests/unit/test_run_snapshot.py` |
| Secret、凭据 | [GR-012](domain/invariants.md) | `tests/security/test_secret_redaction.py` |
| 分层、依赖注入、新增端口 | [ADR-0006](decisions/0006-dependency-injection-and-api-contract.md) | `tests/unit/test_layering.py`、[后端说明](../backend/README.md) |
| 接口 DTO、前端类型 | [ADR-0006](decisions/0006-dependency-injection-and-api-contract.md) | `scripts/sync-api-contract.sh`、CI 的 `api-contract-check` |
| 列表接口要不要分页 | [ADR-0007 第 4 节](decisions/0007-submission-correctness-and-observability.md) | `domain/pagination.py` 的注释 |
| Run 提交、并发、幂等 | [ADR-0007](decisions/0007-submission-correctness-and-observability.md) | `tests/integration/test_concurrency.py`、`test_idempotency.py` |
| 调度适配器、作业脚本 | [GR-015](domain/invariants.md)、[ADR-0004](decisions/0004-runtime-backend.md) | [平台参考材料](references/README.md) |
| 部署、环境变量、集群对接 | [ADR-0005](decisions/0005-deployment-topology.md) | [部署说明](../deploy/README.md) |
| 协作功能（角色、Fork、共享资源、通知） | [M2 Milestone](milestones/M2-collaborative-workspace.md) | [ADR-0001~0003](decisions/README.md) |
| 界面样式、配色、布局组件 | [ADR-0009](decisions/0009-visual-tokens.md) | `frontend/src/theme.ts`、`src/theme.test.ts` |
| Git 流程、Commit、评审 | [Git 工作流](development/git-workflow.md) | [贡献指南](../CONTRIBUTING.md)、[评审规范](development/code-review.md) |

## 目录

```text
docs/
├── product/       产品设计最终稿，范围和优先级的事实来源
├── domain/        领域语言与全局不变量，评审时逐条对照
├── decisions/     需要解释理由、改起来代价大的决策（ADR）
├── milestones/    阶段目标、非目标与完成标准
├── development/   Git 流程、Commit 规范、评审规范、问题处理
├── references/    塑造了架构边界的外部材料
└── api/           由后端导出的 OpenAPI Contract，不要手改
```

## 三类文档的分工

```text
产品设计稿    用户可以做什么，做到什么程度
领域文档      这些操作作用于什么对象，必须满足什么规则
决策记录      当时为什么这么选，放弃了什么，以后要注意什么
```

代码回答「现在是什么」，设计稿回答「应该是什么」，
决策记录填的是中间那层：**当时为什么这么选**。
半年后有人想改某块，没有这一层就只能靠猜。

## 什么时候该写新文档

```text
定了一个改起来代价很大的选择        -> 写 ADR
开始一个新阶段                      -> 写 Milestone，重点是非目标
发现一条必须长期遵守的规则          -> 加进 domain/invariants.md，并配一个测试
只是实现细节                        -> 写代码注释，不要写文档
```

约定如果没有对应的可执行检查，迟早会烂掉。写规则的同时想清楚：
**谁来发现有人违反了它。**
