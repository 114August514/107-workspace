# 文档历史索引

这里索引已经退出活动文档树的过程材料。历史文件不构成当前产品、架构或工程规范。

## 2026-07-14 后端重建

旧 `docs/reviews/`、`docs/superpowers/`、早期产品愿景、后端初始化指南和派生的平台说明
记录了迁移前后端重建过程。它们包含已失效的领域模型、测试数量、目录、脚本链接和
“Approved”状态，因此不再复制到 HEAD。

完整内容保存在本分支祖先提交
[`374aa9fab36b1f047b5648a4dd1bd3c0817dc472`](https://github.com/114August514/107-workspace/tree/374aa9fab36b1f047b5648a4dd1bd3c0817dc472/docs)：

```bash
git show 374aa9f:docs/reviews/2026-07-14-backend-reinitialization/README.md
git show 374aa9f:docs/superpowers/specs/2026-07-13-workspace107-backend-design.md
git show 374aa9f:docs/references/product/107-workspace-product-vision.md
```

活动设计见 [`../product/design.md`](../product/design.md)，当前实现状态见仓库
[`README.md`](../../README.md)。

## 完成记录

- [`2026-08-01-ci-runtime-provisioning.md`](2026-08-01-ci-runtime-provisioning.md)：
  由 GitHub Actions 显式配置 Python 3.12 与 Windows UTF-8，并撤掉任务脚本的 PATH 推断。
- [`2026-08-01-ci-portability.md`](2026-08-01-ci-portability.md)：
  记录首轮 Alembic 配置修复及随后被替代的 PATH 推断方案。
- [`2026-08-01-pre-publish-test-review.md`](2026-08-01-pre-publish-test-review.md)：
  修正发布前复核发现的假断言、依赖方向解析漏洞和无断言测试。
- [`2026-08-01-test-baseline-reset.md`](2026-08-01-test-baseline-reset.md)：
  删除绑定旧实现的测试，并建立重构期测试边界、收集范围和覆盖率报告口径。
- [`2026-08-01-active-guidance-alignment.md`](2026-08-01-active-guidance-alignment.md)：
  清理旧工具链与协作口径，并明确目标设计和当前旧实现的边界。
- [`2026-08-01-openapi-operation-docs.md`](2026-08-01-openapi-operation-docs.md)：
  为全部公开 API operation 补齐中文摘要与说明，并加入契约回归测试。
- [`2026-08-01-openapi-descriptions.md`](2026-08-01-openapi-descriptions.md)：
  修复 Pydantic 字段说明未进入 OpenAPI 与前端生成类型的问题。
- [`2026-08-01-api-contract-location.md`](2026-08-01-api-contract-location.md)：
  生成的 OpenAPI 从人工文档树迁入根 `contracts/`，前后端契约链路保持不变。
- [`2026-08-01-deploy-layout.md`](2026-08-01-deploy-layout.md)：
  Compose 编排迁入 `deploy/`，并保持服务构建文件与原有相对路径语义。
- [`2026-08-01-github-collaboration-templates.md`](2026-08-01-github-collaboration-templates.md)：
  Issue、Pull Request、分支过渡与手动镜像发布入口的整理结果。
- [`2026-08-01-repository-documentation-reorganization.md`](2026-08-01-repository-documentation-reorganization.md)：
  活动文档、历史材料、根目录与外部参考 checkout 的整理结果。
