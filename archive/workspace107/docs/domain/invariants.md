# 全局产品不变量

以下规则适用于所有模块，后续领域规则不得与之冲突。
定义出自 [产品设计最终稿 §3.4](../product/design-final.md)，本文补充**实现位置与测试位置**，
供代码评审时逐条对照。

`M1` 列说明当前状态：`强制` = 代码层面拒绝违反；`部分` = 已建模但仅覆盖部分路径；
`待实现` = 相关能力尚未开发。

| 编号 | 规则 | M1 | 实现位置 |
| :--- | :--- | :--- | :--- |
| GR-001 | Workspace 是基础归属边界 | 强制 | `application/access.py` |
| GR-001a | 权限按能力判断，不按角色比较 | 强制 | `domain/capabilities.py`、`application/access.py` |
| GR-002 | 对象归属与资源记账相互独立 | 部分 | `domain/models.py` |
| GR-002a | 资源权益的并发上限必须真的生效 | 强制 | `application/run_service.py`（提交前锁权益行） |
| GR-003 | 可变对象与不可变版本必须分离 | 强制 | `domain/models.py` |
| GR-004 | 引用不会复制内容 | 强制 | `domain/run_snapshot.py` |
| GR-005 | 复制产生独立内容 | 强制 | `application/project_service.py` |
| GR-006 | Fork 不传播权限和权益 | 强制 | `application/project_service.py` |
| GR-007 | 所有外部引用在使用时重新校验 | 强制 | `application/run_service.py` |
| GR-008 | 历史事实与当前访问权分离 | 强制 | `application/run_service.py` |
| GR-009 | Run Snapshot 创建后不可修改 | 强制 | `domain/run_snapshot.py` |
| GR-010 | Artifact 可以直接作为后续输入 | 部分 | `domain/models.py` |
| GR-011 | 输入默认只读 | 强制 | `infrastructure/storage/local.py` |
| GR-012 | Credential 不得通过普通对象传播 | 强制 | `domain/secrets.py` |
| GR-013 | 无发现权限时对象视为不存在 | 强制 | `application/access.py` |
| GR-014 | 平台管理员权限不等于内容访问权 | 待实现 | — |
| GR-015 | Slurm 是实际调度状态的事实来源 | 强制 | `domain/ports/scheduler.py` |
| GR-016 | 删除不能重写历史事实 | 部分 | `domain/models.py` |
| GR-017 | 产生外部副作用之前必须先完成去重登记 | 强制 | `application/run_service.py` |

---

## 重点条款的实现说明

### GR-001 Workspace 是基础归属边界

```text
1. Project 必须且只能属于一个 Workspace
2. Run 必须属于一个 Project
3. Log 和 Artifact 必须属于产生它们的 Run
4. Run、Log、Artifact 的归属 Workspace 由 Project 决定
5. Membership 只在对应 Workspace 内生效
```

实现方式：所有读写路径都必须先经过 `AccessGuard`，由它根据 `Membership`
解析当前用户在目标 Workspace 中的角色。API 层不允许直接用 `project_id`
查询而跳过归属校验。

测试：`tests/unit/test_access_guard.py`、`tests/integration/test_isolation.py`

### GR-001a 权限按能力判断

写成 `role is OWNER` 的话，每加一个角色都要把所有判断点翻一遍，
**漏掉的那一处就是一个越权**。所以判断的对象是能力，角色只是能力的命名集合。

前端也按能力判断（后端在响应里给出 `capabilities`），不要自己按角色推导——
推导意味着规则有两份，早晚不一致。

矩阵见 [ADR-0008](../decisions/0008-capability-based-authorization.md)。

测试：`tests/unit/test_capabilities.py`、`tests/integration/test_roles.py`

### GR-002a 并发上限在并发下也要成立

**额度的口径是「Workspace × 算力方案」，不是整个 Workspace。**

这条必须先说死，否则实现无从对齐。`ResourceEntitlement` 的定义就是
「Workspace 使用**某个算力方案**的资格及期限」，`max_concurrent_runs`
是这条权益上的字段，那么它约束的就只能是这个方案上的 Run：

```text
数的范围        该 Workspace 在**该算力方案**上未结束的 Run
比的对象        该 Workspace 在**该算力方案**上的 max_concurrent_runs
锁的对象        同一条权益行
```

三者必须是同一个粒度。**锁的粒度小于计数的粒度，等于没锁**：
两个请求提交到不同方案时锁的是两条不同的行，谁都不会阻塞谁，
却都在读同一个更大范围的计数，双双通过。

这也符合直觉：CPU 作业不该占掉 GPU 的名额。集群资源本身就是分区的。

> **放弃的方案：额度按整个 Workspace 计。** 那样 `max_concurrent_runs`
> 就不该长在 per-plan 的权益行上，而应该是 Workspace 自己的字段，
> 锁也要改成锁 Workspace 行。真需要「一个空间总共不许超过 N 个」这种
> 总量控制时，它是**另一条独立的规则**加另一个字段，不要和 per-plan
> 额度混在一起——混在一起就是现在这种口径不一致。

**串行化**：「数一数还有几个名额 -> 创建 Run」中间会被别的请求插进来。
不串行化的话两个请求同时读到「还没到上限」，然后都创建成功。
实现方式：提交前对该 Workspace 在目标算力方案上的权益行做
`SELECT ... FOR UPDATE`，锁持有到事务结束。**创建和重跑两条路径都要走**——
重跑是最容易被反复触发的路径，漏掉它等于没做。

严格保证只在 PostgreSQL 上成立；SQLite 忽略 `FOR UPDATE`，
开发和测试环境依赖它自身的写串行化。详见
[ADR-0007](../decisions/0007-submission-correctness-and-observability.md)。

测试：`tests/integration/test_concurrency.py`，其中必须有一条
**跨算力方案**的用例——只测同方案的话，口径不一致这个错误检查不出来。

### GR-003 / GR-009 不可变性

**要区分「内容不可变」和「记录不可变」，两者不是一回事。**

```text
记录整体不可变    ProjectVersion、EnvironmentVersion、RunSnapshot
                  Python 层 frozen，数据库层没有 UPDATE，要改就建新对象

只有内容不可变    Artifact
                  字节写进 blob 之后永不改动，但记录上的状态字段会变：
                  status、cleaned_at 由清理流程写（GR-016），
                  name、description 允许在展示范围内修改
```

早先这条把 Artifact 和前三者并列，还断言「数据库层没有对应的 UPDATE 语句」——
那和 GR-016 直接冲突：清理**必须** UPDATE 才能置 `cleaned_at`。
实现上 `Artifact` 也从来不是 `frozen`。规则和实现对不上时，
**先想清楚规则想守的到底是什么**：这里想守的是「已经产生的字节不会被改写」，
不是「这一行永远不许 UPDATE」。

Run 创建后不允许修改代码版本、执行命令、工作目录、环境版本、输入来源、
算力请求、最终调度配置和 Artifact 收集规则。要改任何一项都必须创建新 Run。

Run 创建后不允许修改代码版本、执行命令、工作目录、环境版本、输入来源、
算力请求、最终调度配置和 Artifact 收集规则。要改任何一项都必须创建新 Run。

测试：`tests/unit/test_run_snapshot.py`

### GR-005 / GR-006 Fork 复制什么、不复制什么

```text
复制                                    不复制
Project Version 的全部文件内容          源 Workspace 的成员与权限
Run Configuration（命令、变量表达式）    Resource Entitlement
Environment 选择信息                    Workspace Secret 的**值**
Input Binding 的引用信息                Run 历史、Log、Artifact
Compute Request 与算力方案选择          Fork Relation 本身
Artifact 收集规则
```

**右边那列比左边重要**：复制多了就是越权，而越权不会自己报错。
Secret 只复制 `${{ secrets.X }}` 表达式，值留在源空间——目标空间缺同名 Secret 时
提交前检查拦下（GR-012 规则 4），这是正确行为，比静默降级成空字符串好。

实现方式：内容复制只搬 `(path, size, content_hash)`，不搬字节——
存储按内容寻址，几十 GB 的数据集 Fork 一百次也只占一份。

两侧都要校验：**源版本可读**且**目标空间可写**。少任何一边都是越权——
只查源就是「谁都能往别人空间里塞项目」，只查目标就是「Fork 一下就能读到看不见的内容」。

测试：`tests/integration/test_fork.py`，按上面这张表分成「复制什么」和
「不复制什么」两组。

### GR-007 / GR-008 引用重新校验

创建 Run、重新运行历史 Run 时，必须重新检查：

```text
Environment Version 当前是否可用
Artifact 当前是否仍然存在且有权访问
Compute Plan 是否仍在 Workspace 权益范围内
引用的 Variable / Secret 是否存在
```

**历史上曾经成功使用，不代表当前仍然可以使用。**
历史 Run 可以继续显示曾经使用的标识，但不因此授予当前访问权。

测试：`tests/integration/test_rerun.py`

### GR-011 输入默认只读

Artifact 作为 Run 输入时以只读方式挂载到 `access_path`。
Run 不得原地修改输入对象；程序需要修改时先复制到工作目录。

实现方式：`infrastructure/storage/local.py` 在准备 Run 工作目录时，
把输入内容以只读权限（`0o555` 目录 / `0o444` 文件）放置到访问路径下。

测试：`tests/integration/test_run_inputs.py`

### GR-012 Secret 不落明文

```text
1. Project 文件和 Run Configuration 不得保存 Secret 明文
2. Secret 必须显式引用后才能被 Run 使用
3. Run Snapshot、日志和页面不得展示 Secret 明文
4. Fork 或使用模板时可以复制引用表达式，但不能复制 Secret 值
```

实现方式：

- `WorkspaceSecret` 的值只有写入接口，没有读取接口
- `RunSnapshot.environment_variables` 中 Secret 项保存的是
  `SecretReference(name=...)`，不是值
- 执行阶段由 `SecretResolver` 在进程边界注入，值不进入数据库和日志
- 日志写入前经过 `redact()` 过滤已知 Secret 值

测试：`tests/security/test_secret_redaction.py`

### GR-013 无发现权限时对象视为不存在

```text
搜索结果中不出现
列表中不出现
直接访问时不泄露对象信息
```

实现方式：无权访问时统一返回 `404`，**不返回 `403`**，
否则错误码本身会泄露对象是否存在。

测试：`tests/security/test_object_discovery.py`

### GR-017 副作用之前先去重

提交作业、发通知、调第三方这类**平台外部的副作用**一旦发生就收不回来。
事务回滚能撤销数据库写入，撤销不了已经提交给集群的作业。

所以带幂等键的请求必须按这个顺序：

```text
登记幂等键并落库   <- 唯一约束在这一刻生效
      ↓
准备数据、创建对象
      ↓
产生外部副作用     <- 到这一步才不可逆
```

顺序反了的话，并发的第二个请求会先把作业提交出去，再因为键冲突回滚——
数据库干净了，集群上却多跑了一个没人认领的作业，而且平台侧没有任何记录。

测试：`tests/integration/test_idempotency.py::test_登记在提交调度任务之前落库`

### GR-015 Slurm 是实际调度状态的事实来源

```text
107 Workspace 负责：产品对象、权限校验、Run Snapshot、调度请求解析、状态映射
Slurm 负责：      排队、资源分配、节点选择、任务执行、底层任务状态
```

107 不重新实现调度算法。平台记录与调度系统状态不一致时，
保留异常状态并执行同步或人工处置，**不能直接伪造成功状态**。

实现方式：`SchedulerPort` 只暴露 `submit` / `poll` / `cancel`，
不暴露任何「设置状态」的方法。Run 状态只能由 poll 结果驱动。

### GR-016 删除不能重写历史事实

Artifact 内容被清理后，历史 Run 仍保留标识、名称、内容摘要、原始大小、
产生时间、来源 Run 和清理状态。

实现方式：Artifact 有 `cleaned_at` 字段，清理只删除存储文件并置位该字段，
不删除数据库记录。
