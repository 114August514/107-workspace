# M1 - Core Run Loop

## 目标

让单个用户在 107 Workspace 中完成一次端到端算力运行。

## 用户结果

用户不需要直接执行 `sbatch`、`squeue` 等命令，即可提交作业、查看状态、
读取日志并获取输出。

```text
创建 Project
→ 准备代码
→ 保存 Project Version
→ 配置运行方案
→ 提交 Run
→ 查看状态
→ 查看日志
→ 获取 Artifact
```

## 范围

对应 [产品设计最终稿](../product/design-final.md) 中标记为 `[Core]` 的能力子集：

| 设计稿章节 | M1 覆盖内容 |
| :--- | :--- |
| 2.1 用户与全局导航 | 识别当前用户、查看自己的 Workspace / Project / Run |
| 2.2 Workspace | Personal Workspace、Collaborative Workspace 创建与成员基础操作 |
| 2.3 Project | Project 创建、文件浏览与增删改、Project Version 保存与历史 |
| 2.3.F 运行方案 | 工作目录、执行命令、环境变量、Artifact 收集规则 |
| 2.5 运行环境 | 环境列表、Workspace 默认环境、Project 环境选择 |
| 2.7 算力配置 | Compute Plan 列表、Compute Request、权益与平台限制校验 |
| 2.8 Run 生命周期 | 提交前检查、创建 Run 与 Run Snapshot、状态时间线、取消、重跑 |
| 2.9 日志与产物 | stdout / stderr、平台事件、Artifact 收集与下载、复现快照 |

领域对象：

```text
User            Workspace       Membership      ComputePlan
Project         ProjectVersion  ProjectFile     ResourceEntitlement
Environment     EnvironmentVersion              WorkspaceVariable
RunConfiguration                RunSnapshot     WorkspaceSecret
Run             RunEvent        RunLog          Artifact
```

调度：定义 `SchedulerPort`，提供 `mock` 适配器（本机进程真实执行）
和 `slurm` 适配器骨架。

## 非目标

- Collaborative Workspace 的完整角色体系（Admin / Viewer 属于 V1）
- Fork、模板、Course Profile、Assignment 与 Submission
- Shared Resource 的创建、授权和跨 Workspace 共享
- 权益申请与审批流程
- 分支、Merge Request、外部 Git 仓库同步
- 本地同步客户端、远程 VS Code、浏览器内 IDE
- 高级资源推荐、指标看板、Run 批量执行
- 平台管理与运维后台

## 完成标准

- [x] 演示环境可以创建 Workspace 和 Project
- [x] 可以上传 / 编辑文件并保存 Project Version
- [x] 可以配置运行方案并通过提交前检查
- [x] 可以提交一个 Run，状态从 `queued` 更新到 `running` 和 `succeeded`
- [x] 可以查看 stdout 和 stderr，以及平台产生的执行事件
- [x] 可以查看并下载 Artifact
- [x] 可以从历史 Run 查看完整复现快照并重新运行
- [x] Run Snapshot 的不可变性、输入只读、Secret 不落明文有测试覆盖
- [x] 前端控制台可以完成上述全部操作
- [x] `scripts/check.sh` 全绿
- [x] README 已更新

验收方式：

```bash
./scripts/demo.sh     # 端到端跑通闭环，不需要连接集群
./scripts/check.sh    # 与 CI 相同的全部检查
```

## 目前的取舍

这些是 M1 有意留下的边界，不是遗漏：

| 现状 | 说明 |
| :--- | :--- |
| 调度默认走 `mock` 适配器 | 在本机以子进程真实执行，状态来自真实退出码。`slurm` 适配器按 REST API v0.0.40 编写，接入前需按目标集群实际启用的 API 版本核对 |
| 新 Workspace 自动获得全部算力方案 | 权益申请与审批属于 V1，M1 先保证闭环可用 |
| 只有 Owner / Member 两种角色 | Admin / Viewer 属于 V1 |
| Input Binding 只支持 Artifact 来源 | Shared Resource 已建模，能力属于后续阶段 |
| 身份用 `X-User` 请求头 | 对接学校统一身份认证只需替换 `api/deps.py` 的 `get_current_user` |
| Secret 存在数据库表中 | 接口已按外部密钥服务设计，生产部署应替换为 KMS 或 Vault |
