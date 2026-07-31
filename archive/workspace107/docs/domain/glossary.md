# 领域语言

同一概念在产品文档、代码、接口和数据库中必须使用一致名称。
代码中一律使用英文名，中文名只出现在面向用户的界面和文档里。

完整定义见 [产品设计最终稿 §3.1](../product/design-final.md)。
本文只保留实现约定，并标注当前实现状态。

状态说明：`已实现` = M1 中有对应代码；`已建模` = 有数据结构但能力未完整；
`未实现` = 仅在设计稿中定义。

## 一. 身份与空间

| 英文名 | 中文名 | 代码位置 | 状态 |
| :--- | :--- | :--- | :--- |
| `User` | 用户 | `domain/models.py` | 已实现 |
| `Workspace` | 空间 | `domain/models.py` | 已实现 |
| `Membership` | 成员关系 | `domain/models.py` | 已实现 |
| `WorkspaceRole` | 成员角色 | `domain/enums.py` | 已实现（Owner / Admin / Member / Viewer） |
| `Capability` | 操作许可 | `domain/capabilities.py` | 已实现 |
| `Activity` | 活动 | `domain/models.py` | 已实现 |
| `Notification` | 通知 | `domain/models.py` | 已实现 |

`Workspace` 分为 `personal` 和 `collaborative` 两种 `WorkspaceKind`，
共享同一套对象模型，差异只在成员管理方式。

**角色本身不携带权限语义**——它只是一组能力的命名集合：

```text
Viewer   能看，不改，不花算力
Member   能建项目、跑作业，不碰空间配置也不管人
Admin    能管人和配置，日常运营不用惊动所有者
Owner    比 Admin 只多一样：转让所有权
```

判断权限时永远问「有没有这个能力」，不要问「是不是某个角色」。
完整矩阵和理由见 [ADR-0008](../decisions/0008-capability-based-authorization.md)。

**活动和通知是两条独立的数据流**：

```text
活动 Activity      面向对象（Workspace / Project），回答「这里发生了什么」
                   一次操作产生一条，写完不改，没有已读状态
通知 Notification  面向人，回答「有什么需要我关注」
                   一次操作产生 0~N 条，有未读 / 已读状态
```

活动里的 `actor_name` 和 `target_name` 是**写入时抄下来的快照**，不是外键。
活动是历史事实：对象改名或删除之后，那句话仍然要读得通，而且要说当时的名字。
理由见 [ADR-0003](../decisions/0003-activity-and-notification.md)。

Course **不是**第三种 Workspace 类型：

```text
Course Workspace = 启用了 Course Profile 的 Collaborative Workspace
```

## 二. Project 与版本

| 英文名 | 中文名 | 说明 | 状态 |
| :--- | :--- | :--- | :--- |
| `Project` | 项目 | Workspace 下可编辑、可版本化、可运行的计算项目 | 已实现 |
| `ProjectFile` | 项目文件 | 组成 Project Working Tree 的当前可编辑内容 | 已实现 |
| `ProjectVersion` | 项目版本 | 正式保存的不可变内容快照 | 已实现 |
| `ProjectBranch` | 分支 | 指向某个 Project Version 的可变引用 | 未实现（V1） |
| `RunConfiguration` | 运行方案 | 可编辑、可命名、可复用的执行配置 | 已实现 |
| `ForkRelation` | 派生关系 | 新 Project 与来源 Project Version 的来源记录 | 已实现 |
| `Template` | 模板 | 对可复用 Project Version 的目录入口 | 未实现（V1） |

**Project Working Tree 与 Project Version 必须区分。**
前者可变，后者创建后不可修改。

## 三. 运行环境与输入

| 英文名 | 中文名 | 说明 | 状态 |
| :--- | :--- | :--- | :--- |
| `Environment` | 运行环境 | 可被多个 Project 复用的独立运行基础 | 已实现 |
| `EnvironmentVersion` | 环境版本 | Environment 已发布的不可变版本 | 已实现 |
| `SharedResource` | 共享资源 | 独立于 Project、可版本化和授权的内容资源 | 未实现 |
| `Artifact` | 运行产物 | 某次 Run 产生并被保存的不可变结果 | 已实现 |
| `InputBinding` | 输入绑定 | 把一份确定内容绑定到 Run 中指定访问路径 | 已建模 |

`Environment Version` 决定代码在什么软件基础上运行；
`Input Binding` 决定 Run 能读取哪些确定内容、通过什么路径读取。两者职责不同。

`InputBinding` 统一引用一份确定内容，不针对来源类型设计不同结构：

```text
InputBinding
├── source_type      shared_resource_version | artifact
├── source_id
├── source_subpath   可选
└── access_path      在 Run 中暴露的路径
```

M1 只支持 `artifact` 来源。

## 四. 配置变量与 Secret

| 英文名 | 中文名 | 归属 | 状态 |
| :--- | :--- | :--- | :--- |
| `WorkspaceVariable` | 配置变量 | Workspace，可直接查看 | 已实现 |
| `WorkspaceSecret` | Secret | Workspace，值不可读出 | 已实现 |
| `EnvironmentVariable` | 环境变量 | Run Configuration，运行时提供给用户程序 | 已实现 |

Run Configuration 使用与 GitHub Actions 类似的表达式引用：

```yaml
env:
  LOG_LEVEL: ${{ vars.LOG_LEVEL }}
  BATCH_SIZE: "32"
  HF_TOKEN: ${{ secrets.HF_TOKEN }}
```

Variable 或 Secret 的名称不必与最终环境变量名相同。

创建 Run 时：

```text
字面值和 Variable  → 解析后固定到 Run Snapshot
Secret             → Run Snapshot 只保存引用表达式，执行时由平台注入
```

## 五. 算力与调度

| 英文名 | 中文名 | 说明 | 状态 |
| :--- | :--- | :--- | :--- |
| `ComputePlan` | 算力方案 | 平台提供的命名资源与限制组合 | 已实现 |
| `ResourceEntitlement` | 资源权益 | Workspace 使用算力方案的资格及期限 | 已实现 |
| `ComputeRequest` | 算力请求 | 一次运行声明的具体资源需求 | 已实现 |
| `SchedulerMapping` | 调度映射 | 转换为底层调度参数的平台规则 | 已实现 |
| `ResolvedSchedulerConfiguration` | 已解析调度配置 | 创建 Run 时固定的最终调度参数 | 已实现 |
| `EntitlementRequest` | 权益申请 | 请求开通或调整权益的记录 | 未实现（V1） |

解析链路：

```text
ResourceEntitlement + ComputePlan + ComputeRequest + SchedulerMapping
        ↓
ResolvedSchedulerConfiguration
        ↓
提交并执行 Run
```

## 六. Run 与执行过程

| 英文名 | 中文名 | 说明 | 状态 |
| :--- | :--- | :--- | :--- |
| `Run` | 运行 | 一次独立执行实例及其生命周期记录 | 已实现 |
| `RunSnapshot` | 运行快照 | 创建时固定、用于执行和复现的不可变配置 | 已实现 |
| `SchedulerJob` | 调度任务 | 底层调度系统创建的任务 | 已实现 |
| `RunLog` | 日志 | stdout 和 stderr | 已实现 |
| `RunEvent` | 执行事件 | 平台产生的状态变化和错误信息 | 已实现 |
| `ArtifactCollectionRule` | 产物收集规则 | 结束后把哪些输出保存为 Artifact | 已实现 |
| `Metric` | 指标 | Run 可选上报的结构化结果 | 未实现（V1） |

核心区别：

```text
Run Configuration → 描述以后准备怎样运行，可编辑、可复用
Run Snapshot      → 记录本次实际按什么配置运行，创建后不可修改
Run               → 一次独立执行及其完整生命周期
```

`Run` 保留对来源 `RunConfiguration` 的引用，但该引用**不作为执行依据**。
执行时只读 `RunSnapshot`。

## 七. 命名约定

- 数据库表名使用复数下划线形式：`project_versions`、`run_snapshots`
- API 路径使用复数连字符形式：`/api/v1/workspaces/{id}/projects`
- Python 类名与领域名一致：`ProjectVersion`、`RunSnapshot`
- 前端类型名与 API schema 一致，不另起别名
- 状态枚举使用小写下划线：`queued`、`running`、`succeeded`、`failed`
