# 第二章：从一次 Run 看懂系统

如果只选择一条路径认识仓库，应该选择 Run。它会经过前端、API、业务规则、数据库、文件
存储和调度器，几乎串起项目的全部开发领域。

## 2.1 总体链路

```text
用户在浏览器提交
        |
        v
React 组件调用 /api/v1/... 接口
        |
        v
FastAPI 路由解析 HTTP 请求
        |
        v
Application Service 校验权限并编排用例
        |
        +----> Domain 规则创建不可变 Run Snapshot
        +----> Repository 写入数据库
        +----> Storage 准备运行目录和文件
        +----> Scheduler 提交作业
                              |
                         Mock 或 Slurm
                              |
        <---- 轮询状态、读取日志、收集 Artifact
        |
前端定时刷新并展示结果
```

每一层只负责一类问题。路由不应该判断业务权限，领域层不应该读数据库，前端也不应该自己
猜测 Slurm 状态。

## 2.2 提交之前：用户编辑的是运行方案

用户在 Project 页面中创建 Run Configuration。它描述命令、环境变量、资源需求等可复用
选择。它仍然可以编辑，因此不能直接作为历史执行证据。

提交弹窗会收集本次运行需要的选择，然后通过前端 API Client 发送给后端。前端请求类型来自
后端导出的 OpenAPI，而不是由组件手写。字段拼错或漏传路径参数时，TypeScript 应尽量在构建
前发现问题。

## 2.3 API 层：把 HTTP 转成用例调用

FastAPI 路由负责：

- 读取路径参数、查询参数和 JSON 请求体；
- 通过依赖获得当前用户和 Application Service；
- 把请求 Schema 转换成用例参数；
- 把成功结果或领域错误转换成 HTTP 响应。

路由不应直接取得 Repository，也不应自己写“成员是否有权限”“算力是否可用”等判断。否则
同一个用例从别的入口调用时，规则很容易被绕过。

## 2.4 Application 层：编排一次提交

Application Service 是用例的负责人。一次 Run 提交通常需要协调多个能力：

1. 根据当前用户和 Workspace 检查访问权限；
2. 读取 Project、Run Configuration、Environment 和算力权益；
3. 调用领域逻辑校验并创建 Run Snapshot；
4. 保存 Run 和相关事实；
5. 让 Storage 准备运行目录；
6. 生成调度脚本并调用 Scheduler；
7. 记录状态或活动信息。

这些步骤涉及事务和失败处理，不能随意拆到路由或基础设施中。Application 层依赖的是端口
协议，因此单元测试可以用 Fake Repository、Fake Scheduler 等替代真实外部系统。

## 2.5 Domain 层：固定执行事实

创建 Run 时，系统把真正会影响复现的内容固定为 Run Snapshot。之后即使用户修改了 Run
Configuration，已创建的 Run 也不能重新读取新配置。

可以把二者理解为：

```text
Run Configuration = 可以继续修改的模板
Run Snapshot      = 某次提交时拍下的不可修改照片
```

Domain 层负责这类不变量。它不能 import FastAPI、SQLAlchemy、文件系统或 HTTP Client。
时钟和随机数也属于外部输入，应通过参数或端口传入，使测试能够给出确定结果。

## 2.6 Infrastructure 层：接触真实世界

基础设施层实现领域端口：

- Repository 使用 SQLAlchemy 访问数据库；
- Storage 在本地或共享目录中准备文件、读取日志和收集 Artifact；
- Secret Vault 保存和解析敏感值；
- Mock Scheduler 或 Slurm Adapter 提交、查询和取消作业；
- Clock 提供当前时间。

Application 只知道“需要一个 Scheduler”，不应依赖具体是 Mock 还是 Slurm。这让本地开发和
真实集群可以复用同一套业务流程。

## 2.7 作业脚本和运行目录

提交前，平台会根据快照和资源选择渲染作业脚本。Mock 模式下可以在
`var/storage/runs/<run_id>/job.sh` 看到它。脚本包含实际命令、工作目录以及调度所需信息。

运行目录同时承担 API 与计算任务之间的数据交换：API 准备输入，计算任务写入日志和结果，
API 再读取它们。真实 Slurm 环境中，API 和每个计算节点必须以同一个绝对路径看到同一份
内容；Docker 本机命名卷不能自动满足这一条件。

## 2.8 状态只能来自调度器

Scheduler 端口只暴露 `submit`、`poll` 和 `cancel`。系统没有“直接把 Run 标为成功”的入口。
Run 状态由轮询结果驱动：

```text
已创建 → 已提交/排队 → 运行中 → 成功或失败
                       \→ 取消中 → 已取消
```

具体状态名称以代码中的枚举和接口契约为准，不要在前端硬编码另一套状态机。取消与任务结束
可能同时发生，因此轮询和取消逻辑还要考虑重复调用与状态竞争。

## 2.9 页面如何看到变化

Run 页面在任务未结束时定时触发状态同步并重新读取 Run，当前间隔约为两秒。随后组件分别
展示状态、事件时间线、日志、Artifact 和复现快照。

调试一个“状态没有更新”的问题时，可以按链路逐层确认：

1. 浏览器是否发出了同步和查询请求；
2. API 是否返回错误，响应中的 `request_id` 是什么；
3. Scheduler 的 `poll` 返回了什么；
4. Run 是否成功写入新状态；
5. 前端是否把该状态映射为正确展示。

沿数据流查找通常比在整个仓库中盲目搜索“状态”更有效。

