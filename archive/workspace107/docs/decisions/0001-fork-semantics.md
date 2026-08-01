# ADR-0001 Fork 的复制语义与来源追踪

状态：已接受 · 阶段：M2 · 相关：GR-005、GR-006、GR-007、GR-012

## 背景

设计稿 §2.4 A 要求「从已有 Project 的确定版本创建新 Project」，§3.2.20 定义了
Fork Relation。这里有几个必须先定死的问题：

1. Fork 出来的是新 Project，还是源 Project 的一个分支？
2. 复制哪些东西？源空间的权益、凭据、Run 历史算不算？
3. 跨 Workspace Fork 时，引用（环境、共享资源、Secret）怎么处理？
4. 内容真的要复制一份字节吗？数据集几十 GB 的话怎么办？

## 决策

### 1. Fork 产生新 Project，不产生分支

设计稿 §3.2.7 已经写死了：

> Fork 创建的是新 Project，不是源 Project 中的新分支。

新 Project 归属于**目标 Workspace**，从此与源 Project 没有任何持续关系。

### 2. 复制内容，不建立同步

按 GR-005，复制之后：

```text
源内容后续变化    不影响副本
副本后续变化      不影响源内容
```

Fork Relation 只是一条**不可变的来源记录**，不是同步通道。
「查看来源是否产生新版本」「与来源新版本比较」属于 V2，即使做了也是
用户主动发起的一次性比较，不是自动跟随。

### 3. 复制清单

按 GR-006 明确列出，实现时对着这张表写测试：

| 复制 | 不复制 |
| :--- | :--- |
| Project Version 的全部文件内容 | 源 Workspace 的成员与权限 |
| Run Configuration（工作目录、命令、环境变量表达式） | Resource Entitlement |
| Environment 选择信息 | Environment Grant / Shared Resource Grant |
| Input Binding 的引用信息 | Workspace Credential 与 Secret 的**值** |
| Compute Request 与算力方案选择 | Run 历史、Log、Artifact |
| Artifact 收集规则 | Fork Relation 本身（新 Project 有自己的那条） |

Secret 的处理最容易搞错，单独写清楚（GR-012 规则 4）：

```text
${{ secrets.HF_TOKEN }}   → 表达式复制过去
HF_TOKEN 的值             → 不复制

目标 Workspace 没有同名 Secret
  → Run Configuration 显示为「未解析」
  → 提交前检查拦下，提示用户在本空间配置同名 Secret
```

### 4. 所有复制来的引用，在目标空间重新校验

按 GR-007，Fork 完成的那一刻不做校验（Fork 本身只是复制），
但**创建 Run 时**必须重新解析：环境版本是否可用、算力方案是否在目标空间权益内、
共享资源是否对目标空间授权、Secret 是否存在。

这意味着 Fork 可能产生一个「暂时跑不起来」的 Project——这是正确行为，
比静默降级或偷偷授权要好。前端应该在 Project 页面提示还缺什么。

### 5. 内容复制是元数据复制，不是字节复制

存储层已经是内容寻址的（`blobs/<hash 前两位>/<hash>`）。
Project Version 是一组 `(path, size, content_hash)`。所以 Fork 只需要：

```text
新建 Project 行
新建 Project Version 行（sequence 从 1 开始）
复制 N 条 (path, size, content_hash) 记录
```

一个字节都不用搬。几十 GB 的数据集 Fork 一百次也只占一份存储。

代价是**删除必须谨慎**：blob 被多少对象引用不再显而易见。
M2 的数据清理（§2.12 B）只清理 Run 日志和 Artifact，不做 blob 回收；
真正的垃圾回收需要引用计数或标记清除，留到后续阶段，
到时候要单独写一条 ADR。

### 6. 配额记账归目标 Workspace

按 GR-002，对象归属和资源记账相互独立。Fork 出的 Project 归目标 Workspace，
它的存储占用也记在目标 Workspace 上——即使物理上和源 Workspace 共享同一份 blob。

这是**逻辑记账**：按 Project Version 里 `sum(size)` 计算，不按实际磁盘占用。
这样用户看到的数字稳定可解释，不会因为别人删了个 Project 就突然涨。

## 放弃的方案

**把 Fork 做成源 Project 的分支。** 直接违反 §3.2.7，而且会让权限彻底混乱：
分支属于源 Project，源 Project 属于源 Workspace，那么 Fork 的人凭什么能写？

**Fork 时立刻校验所有引用并拒绝。** 想法是「不让用户拿到跑不起来的东西」，
但实际会让跨空间复用几乎不可用——目标空间通常就是缺东西，用户 Fork 过来
正是为了在本空间补齐。把校验放到创建 Run 时更符合真实使用顺序。

**Fork 时把源空间的授权一并复制过去。** 这等于让任何人通过 Fork 就能拿到
别人的数据访问权，是明确的越权。

## 影响

- `ForkRelation` 是不可变对象，加入 GR-003 的不可变清单
- `AccessGuard` 需要同时校验**源 Project Version 可读**和**目标 Workspace 可写**
- 前端 Fork 入口需要选择目标 Workspace，并展示「目标空间可用性检查结果」（§2.4 A）
- 数据清理不能简单地「删 Project 就删 blob」，M2 的清理范围要写清楚
- 之后做模板（§2.4 C/D）时，「从模板创建 Project」复用同一套复制逻辑，
  区别只在来源是 Template Revision 引用的 Project Version
