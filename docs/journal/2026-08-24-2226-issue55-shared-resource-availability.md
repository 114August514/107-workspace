# issue55-shared-resource-availability

- 状态：进行中
- 认领：Chongan Wang
- 上下文：未指定
- 开始：2026-08-24 22:26 +0800

## 意图
完成 GitHub Issue #55：Shared Resource 列表/详情展示当前 User 的可用状态
（Owner scope / User Grant / UserGroup Grant / 不可用）与 USE Grant 摘要，
前端只消费后端 contract，不猜测 Membership；语义与 asset_use / Run preflight 对齐。

## 预期改动
- `backend/src/workspace107/domain/grant.py`（availability source 枚举）
- `backend/src/workspace107/application/asset_use.py`（availability 计算）
- `backend/src/workspace107/application/shared_resource_service.py`（view 携带 availability）
- `backend/src/workspace107/api/schemas.py`、`api/presenters.py`、`api/routes/shared_resources.py`
- `contracts/openapi.json`、`frontend/src/api/schema.d.ts`（生成物，经 `make contract` / `generate:api`）
- `frontend/src/components/sharedresource/*`、`frontend/src/pages/SharedResourcePage.tsx`
- 后端 integration / 前端 component tests

## 仓外副作用
无。

## 回退方式
git revert <commit>

## 验收
make check；后端 integration 覆盖四态与 Grant 撤销；浏览器证据（列表/详情可用与不可用两态）。
浏览器证据：`docs/evidence/issue-55/`（bob 的列表三态、user grant 与
group grant 详情、alice 的 owner 详情）；「不可用」态在发现边界外不可达，
由组件测试覆盖（SharedResourcePage.test.tsx）。

## 禁区
- ~~不扩展发现边界（不新增 Grant-based discovery）~~ 已解除：四态展示要求
  Grant 可用的资源对 grantee 可见，经用户确认后把 Shared Resource 的发现边界
  扩展到 USE Grant 可用的资源（grantor 必须等于当前 Owner，符合 GR-408）
- 不实现 Grant 创建/撤销界面（V1）
- 不动 Run preflight 逻辑本身
- 不加依赖

## 决策记录
- 2026-08-24：#40 journal 冻结了发现边界，但 #55 的四态展示在 grantee 看
  不到资源时不可达；经用户确认，扩展 `_shared_resource_discovery_predicate`
  （repositories.py）允许 USE Grant 命中。原「授权不带来管理权限」语义保留：
  grant-only 用户 role=None、无 capability，管理操作返回 403。
