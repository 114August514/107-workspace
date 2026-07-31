# ADR-0008 权限判断基于能力，以及四个角色各自能做什么

状态：已接受 · 阶段：M2 · 相关：GR-001、GR-013

## 背景

设计稿 §2.2 C 规定了四个角色：

```text
[Core] Owner / Member 基础角色
[V1]   Admin / Viewer 扩展角色
[V1]   修改成员角色
```

但它**没有规定每个角色能做什么**。这是必须由实现来定的，而且定错了很难改——
用户会按已有的权限安排工作，收紧权限等于打断别人正在做的事。

M1 的权限判断长这样：

```python
async def workspace_as_owner(...):
    if not access.is_owner:
        raise PermissionDenied(...)
```

加两个角色意味着把每一处 `is_owner` 翻出来重新判断「Admin 算不算」「Viewer 算不算」。
一共十几处，**漏掉的那一处就是一个越权**。

## 决策

### 1. 判断的对象是能力，不是角色

```python
# 之前
if not access.is_owner:
    raise PermissionDenied(...)

# 现在
access = await guard.workspace(user_id, workspace_id, needs=Capability.MEMBER_MANAGE)
```

角色只是能力的一个命名集合。加新角色时只改一张表，不碰任何判断点；
新增能力时只在需要它的地方标注一次。

能力命名统一为 `对象.动作`（`member.manage`、`run.submit`），
这样它出现在日志和错误信息里就能直接读。

`needs=` 放在 `guard` 的调用里而不是分成两步，是为了让「取对象」和「查权限」
不容易被拆开——拆开之后就有人会忘掉第二步。

### 2. 角色能力矩阵

| 能力 | Owner | Admin | Member | Viewer |
| :--- | :--: | :--: | :--: | :--: |
| 查看空间 / 成员 / 权益 / 配置 | ✓ | ✓ | ✓ | ✓ |
| 查看 Project / 文件 / 版本 / Run / 日志 / 产物 | ✓ | ✓ | ✓ | ✓ |
| 创建和修改 Project、改文件、存版本 | ✓ | ✓ | ✓ | — |
| 管理运行方案 | ✓ | ✓ | ✓ | — |
| 提交 Run、重跑、取消 | ✓ | ✓ | ✓ | — |
| 修改空间设置与默认环境 | ✓ | ✓ | — | — |
| 邀请、移除成员、修改成员角色 | ✓ | ✓ | — | — |
| 管理配置变量与 Secret | ✓ | ✓ | — | — |
| 转让空间所有权 | ✓ | — | — | — |

四个角色对应四种真实的人：

```text
Viewer   旁听的人：助教、评委、来观摩的同学。能看，不花算力，不改东西
Member   干活的人：能建项目、跑作业，但不碰空间配置也不管人
Admin    管事的人：能管人和配置，日常运营不需要惊动所有者
Owner    负责人：比 Admin 只多一样——转让所有权
```

**能力是逐级包含的**：Viewer ⊂ Member ⊂ Admin ⊂ Owner。不是所有权限模型都该这样，
但这个项目里角色就是「权限逐级增加」，出现交叉说明有人加错了地方。
有一条测试守着这个关系。

### 3. 所有权是一件独立的事

两条限制都从这里来：

```text
不能修改 Owner 的角色      要换所有者就走转让流程，那是一次明确的交接
不能把成员直接设成 Owner   否则一个 Admin 就能自己造出一个所有者来
```

**「不能设成 Owner」约束的是全部产生路径，不是某一个接口。** 这条当初只写了
「不能把成员**设成** Owner」，实现就只在改角色那条路上落地，邀请接口没管——
一个 Admin 可以直接 `POST /members {"role":"owner"}` 造出第二个所有者，
对方接受邀请后拿到 `ownership.transfer`，转手把空间拿走。审查时实跑复现过。

所以规则要按**路径**列全，写规则时就把口子堵死，而不是等实现去猜：

| 产生路径 | 允许写入 owner？ |
| :--- | :--- |
| 邀请成员 `POST /workspaces/{id}/members` | **不允许**，409 |
| 修改成员角色 `PATCH .../members/{uid}` | **不允许**，409 |
| 重新邀请已退出/已移除的成员（复用旧 membership） | **不允许**，409 |
| 转让所有权 `POST .../transfer-ownership/{uid}` | 唯一允许的路径 |

判断依据只有一条：**`memberships.role == owner` 这个值，只能由转让流程写入。**
新增任何写 role 的接口时，先回答它属于上表哪一行。

推论：`workspace.owner_id` 和「role 为 owner 的 membership」必须始终一一对应。
转让流程要保证降级的是**在册的那个所有者**，而不是碰巧发起调用的人——
否则会留下一个 role=owner 但不是 owner_id 的成员，他照样能再转让一次。

**转让之后原所有者留在 Admin，不是 Member。** 交出的是所有权，不是团队；
新所有者觉得不合适可以再降级。M1 的实现降到 Member，那是因为当时没有 Admin。

### 4. 能力清单由后端算好交给前端

`GET /workspaces/{id}` 的响应里带 `capabilities`，前端据此决定显不显示入口：

```ts
{can(workspace, 'member.manage') && <Button>邀请成员</Button>}
```

**前端不要按角色推导**（`role === 'owner'`）。推导意味着规则有两份，
后端改了矩阵前端不会跟着变，然后就会出现「按钮在但点了报 403」，
或者更糟——「按钮不在但其实能做」。

分工是清楚的：

```text
前端权限 = 用户体验，决定看得见什么
后端权限 = 安全边界，决定做得成什么
```

前端判断永远是「顺带的」，删掉它系统仍然安全。

## 放弃的方案

**继续用角色比较，只是多几个分支。** 每处判断都要写
`role in (OWNER, ADMIN)`，加第五个角色时要再翻一遍全部判断点。
M1 只有十几处就已经不好数了。

**Viewer 也能提交 Run。** 想法是「反正有权益上限兜着」。但 Viewer 的语义就是
旁听，让旁听的人能花掉这个空间的算力配额，和角色名字直接矛盾。

**Admin 也能转让所有权。** 转让不可逆，而且会把原所有者降级。
这种事应当由所有者本人做——否则一个 Admin 可以在所有者不知情时把空间交出去。

**做成可配置的自定义角色。** 设计稿把它标为 V2。现在做会让权限模型复杂一大截，
而四个固定角色已经覆盖了课程、竞赛队、课题组这几个真实场景。
真要做的时候，这套能力枚举就是它的基础——自定义角色无非是「自选一组能力」。

**把能力细到 Project 级别**（某人只能改某个 Project）。设计稿标为 V2。
现在做的话每个判断点都要多带一个对象参数，而 M2 的场景还不需要。

## 影响

- `WorkspaceRole` 增加 `ADMIN` 和 `VIEWER` 两个取值，契约里的枚举跟着变，
  前端类型自动传导（ADR-0006 那条链路）
- `AccessGuard.workspace_as_owner` 移除，调用方改用 `needs=`
- `WorkspaceService.list_for_user` / `get` / `create_collaborative` 返回
  `WorkspaceView`（带角色和能力），不再返回裸 `Workspace`
- 新增 `PATCH /workspaces/{id}/members/{user_id}` 修改角色
- 前端四处 `role === 'owner'` 换成 `can(workspace, ...)`

**没有数据迁移**：`memberships.role` 本来就是字符串列，新取值直接可用。
已有数据里只有 owner 和 member，语义不变。

## 守住它的测试

| 约定 | 测试 |
| :--- | :--- |
| 矩阵每一格都符合预期 | `tests/unit/test_capabilities.py::test_角色能力与矩阵一致` |
| 能力逐级包含 | `tests/unit/test_capabilities.py::test_能力是逐级包含的` |
| Owner 只比 Admin 多转让 | `tests/unit/test_capabilities.py::test_owner_只比_admin_多一样转让所有权` |
| Viewer 建不了 Project、提交不了 Run | `tests/integration/test_roles.py` |
| Member 管不了人和配置 | `tests/integration/test_roles.py::test_member_能干活但管不了人` |
| Admin 不能转让所有权 | `tests/integration/test_roles.py` |
| 不能造出第二个所有者 | `tests/integration/test_roles.py::test_不能把成员直接设成_owner` |
| 转让后原所有者留在 Admin | `tests/integration/test_roles.py::test_转让之后原所有者留在_admin` |
| 前端按能力而不是角色判断 | `frontend/src/api/capabilities.test.ts` |

矩阵测试**故意把每个角色的能力全部列出来**，而不是用集合运算推导。
推导出来的期望值看不出「谁比谁多了什么」，而那正是评审这类改动时要看的东西。
