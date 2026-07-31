<!--
PR 标题格式与 Commit 一致：
    <类型>(<范围>): <一句话说明>
例如：
    feat(workspace): 支持创建协作空间
-->

## 关联 Issue

Closes #

## 修改内容

-
-

## 验证方式

<!-- 写实际执行过的命令和结果，不要写“应该没问题”。 -->

- [ ] `cd backend && uv run ruff check .`
- [ ] `cd backend && uv run ruff format --check .`
- [ ] `cd backend && uv run pytest`
- [ ] `cd frontend && npm run lint`
- [ ] `cd frontend && npm run typecheck`
- [ ] `cd frontend && npm run build`
- [ ] 手动验证：

## 影响范围

- 数据库迁移：无 / 有（迁移文件：）
- API 变化：无 / 有（已执行 `./scripts/sync-api-contract.sh` 并提交两个生成物）
- 前端接口类型：由契约生成，未手写
- 领域不变量：未触及 / 涉及 GR-0xx

## 截图

<!-- 涉及界面时必须提供。 -->

## 自检

- [ ] 一个 PR 只解决一个主要问题
- [ ] 没有提交 `.env`、密钥、Token、用户数据或运行产物
- [ ] 新增或修改的行为有对应测试
- [ ] 变更的动态平台事实（GPU 型号、分区、配额等）没有被写成固定结论
