# ADR-0003 活动与通知是两条独立的数据流

状态：已接受 · 阶段：M2 · 相关：设计稿 §2.10

## 背景

设计稿 §2.10 在开头就特意提醒过：

```text
通知
→ 面向特定用户，需要用户关注或处理

活动
→ 面向 Workspace 或 Project，说明最近发生了什么
```

实现时很容易图省事把两者合成一张表——反正都是「谁在什么时候对什么做了什么」。
但两者的读取方式、生命周期和扩展方向完全不同，合在一起早晚要拆。

## 决策

### 1. 两条独立的数据流，不用一张表凑合

| | 活动 Activity | 通知 Notification |
| :--- | :--- | :--- |
| 面向 | 对象（Workspace / Project） | 人（User） |
| 回答 | 这里最近发生了什么 | 有什么需要我关注 |
| 数量 | 一次操作产生一条 | 一次操作产生 0~N 条（每个相关的人一条） |
| 状态 | 无。写完就不改 | 有。未读 / 已读 / 归档 |
| 生命周期 | 跟随对象 | 跟随用户，可以单独归档删除 |
| 扩展方向 | 筛选、订阅（V2） | 邮件、免打扰、摘要（V1/V2） |

关键区别在数量关系：一次操作产生**一条活动**，但可以产生 **0~N 条通知**。
用一张表表达不了这种一对多，硬凑就得加 `recipient_id` 然后对活动重复存 N 份。

> **订正（实现 Issue 4 之后）**：这里原本举的例子是「移除成员产生两条通知：
> 被移除的人要知道，Owner 要有记录」。那个例子是错的，而且和本文档
> 第 4 节的产生点表、以及「不给自己发通知」这条规则互相矛盾——
> 移除操作正是 Owner 或 Admin 自己发起的，再给他发一条就是通知自己。
> **Owner 要回顾「这个空间发生过什么」，那是活动流的职责，不是通知。**
> 移除成员实际产生一条活动、一条通知（给被移除的人）。
>
> 一次操作产生多条通知的真实例子是「引用的共享资源被撤销授权」：
> 受影响的可能是多个 Project 的负责人，一条活动、N 条通知。
> 这个场景在 M2 Issue 6~8 才会出现。

### 2. 活动在用例成功后由 ActivityRecorder 写入

```text
application 层用例成功
        ↓
ActivityRecorder.record(workspace_id, project_id?, actor, action, target)
        ↓
活动表
```

放在 application 层而不是仓储层，理由是：**只有用例知道这次操作在业务上叫什么**。
仓储只看到「往 runs 表插了一行」，分不清这是「提交 Run」还是「重跑」。

失败的操作不记活动。活动流是「发生了什么」，不是审计日志——
管理审计（§2.12 E）是另一件事，M2 不做。

### 3. 通知统一走 NotificationPublisher 端口

```text
domain/ports/notification.py
    class NotificationPublisher(Protocol):
        async def publish(self, notification: Notification) -> None
```

M2 只有一个实现：写进数据库，前端轮询未读数。
V1 加邮件时新增一个组合实现（站内 + 邮件），**用例代码一行都不用改**。

这是 M2 就要留好接口的唯一理由。如果现在到处直接 `repos.notifications.add(...)`，
将来加邮件就得把每个产生点都找出来改一遍，还容易漏。

### 4. 产生点集中，不下沉

通知只在这些地方产生，每处都要能说清「为什么这个人需要知道」：

| 事件 | 产生点 | 接收者 |
| :--- | :--- | :--- |
| Run 结束 / 失败 | `RunLifecycleService` | Run 创建人 |
| 提交失败 | `RunService._submit` | Run 创建人 |
| 收到 Workspace 邀请 | `WorkspaceService.invite_member` | 被邀请人 |
| 被移除 / 角色变更 | `WorkspaceService` | 被操作的成员 |
| 引用的环境或共享资源不可用 | 资源状态变更用例 | 受影响 Project 的 `created_by` |

「Project 的所有者」这个角色在领域模型里**不存在**——Project 归属于
Workspace，不归属于人（GR-001）。这里指的是 `Project.created_by`，
也就是当初建它的人。M2 Issue 6~8 做共享资源时按这个字段发。
如果将来一个 Project 需要多个负责人，那是新增一个概念，不是复用这句话。

**Run 结束通知只能由 `RunLifecycleService` 发出**，因为按 GR-015 它是唯一
知道终态的地方——状态来自调度系统的轮询结果，别处都是猜。

### 5. M2 只做站内，但不可关闭的通知要区分出来

设计稿 §2.10 C 提到「查看不可关闭的重要系统通知」。M2 虽然还没有偏好设置，
但通知对象上要先带 `mandatory` 标记，否则 V1 加偏好时会发现历史数据分不出来。

## 放弃的方案

**一张 events 表两边共用，通知靠 `recipient_id` 是否为空区分。**
活动会被重复存 N 份（每个接收者一份），Workspace 活动流查询要先去重，
而且「未读」状态挂在活动上语义很怪——活动是客观事实，没有读没读一说。

**从活动流实时推导通知。** 需要在读取时算「哪些活动与我有关」，
逻辑复杂而且没法表达「已读」。更要命的是活动是对象级的，
而通知的接收者可能根本不在那个对象的可见范围里
（比如被移除的成员，移除之后他已经看不到这个 Workspace 了）。

**直接在仓储层写活动。** 见第 2 条，仓储分不清业务动作。

## 影响

- 新增领域对象：`Activity`、`Notification`
- 新增端口：`NotificationPublisher`
- `RunLifecycleService` 需要注入 publisher——它现在的构造参数已经有四个，
  再加就该考虑打包成一个上下文对象了
- 前端需要一个轮询未读数的入口；和 Run 状态轮询共用同一套 `usePolling`
- 活动写入失败**不能**让主用例失败：记日志、继续。用户提交 Run 成功了，
  不该因为活动表写不进去而看到报错

## 补充：「记日志、继续」不等于 try/except

*（实现 Issue 3 时补，这条当初写得太简略，照字面做是错的。）*

事务边界是一次请求（`api/deps.py`：整个请求共用一个 session，最后统一 commit）。
在这个前提下，光把异常吞掉是**不够**的：

```python
try:
    await repos.activities.add(activity)   # ORM add + flush
except Exception:
    logger.warning(...)                    # 看起来「继续」了
```

仓储走的是 ORM 的 `add` + `flush`。flush 失败会把整个 session 标记成需要回滚，
请求结束时的 `session.commit()` 抛 `PendingRollbackError`——
**主用例的数据跟着一起丢**，正好是这条规则想避免的事。

正确做法是把活动写入包在 SAVEPOINT 里，失败只回滚这一小段：

```python
async with session.begin_nested():
    await repos.activities.add(activity)
```

两种写法的差别实测过（同样的失败注入）：

```text
不用嵌套事务    活动写入失败 → 外层 PendingRollbackError → 最终落库 []
用嵌套事务      活动写入失败 → 外层提交成功           → 最终落库 [主用例写的行]
```

有一条测试守着这个行为：`tests/integration/test_activity.py::test_活动写不进去也不能让用例失败`。
把 `begin_nested()` 去掉，它立刻变红。

顺带一个容易被误导的地方：用 Core 的 `session.execute(insert(...))` 做同样的实验，
不加 SAVEPOINT 也能提交成功——**所以别用 Core 写法去验证 ORM 路径的行为**。

同一个坑对 Issue 4 的通知写入一样适用，实现时按同样的方式处理了
（`application/notifier.py`），也有对应的测试：
`tests/integration/test_notifications.py::test_通知发不出去也不能让用例失败`。

## 补充：实现 Issue 4 时定下的两条

*（ADR 原文没写，但实现时必须回答。）*

**不给自己发通知。** 自己做的事自己知道。不加这条判断的话，
一个人邀请五个成员就会给自己攒五条通知，未读数变成噪音，
真正需要关注的反而被淹掉。判断放在 `Notifier._publish` 里统一兜底。

例外是 Run 结束和提交失败：那不是谁「做」的，是调度系统的结果，
**提交者正是需要知道的那个人**。这两处显式传 `actor_id=None` 跳过判断。

**读通知不做 Workspace 权限校验，只按收件人过滤。** 这正是 ADR 第 4 节
「被移除的成员移除之后已经看不到这个 Workspace」那句话的落地：
按 Workspace 过滤会把「你被移除了」这条一起挡掉，那这条通知等于没发。
`member_removed` 因此也不带跳转目标——他已经看不到那个空间，链过去只会是 404。

对应的是仓储层的一条硬性要求：**每个查询都要带 `recipient_id` 条件，
包括标记已读**。少一个条件就是「能标记别人的通知」这种越权，
有测试守着（`test_不能标记别人的通知`）。
