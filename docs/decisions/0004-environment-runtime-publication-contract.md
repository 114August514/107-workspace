# 0004. Environment 版本只发布 Modules 或受控 Apptainer SIF

- 状态：已接受
- 日期：2026-08-29

## 背景

107 平台当前运行 Ubuntu 24.04.3，节点共享 `/public` 与 `/home`，使用 Environment Modules，普通用户无 sudo。`docs/references/platform/` 中的平台 PDF 是本决定的平台事实来源。真实 Apptainer CLI 成功发布证据仍由 #46 负责；#7 只负责下游 Workspace 身份、共享挂载、独立 Worker 与 Slurm 执行接缝。

旧模型把任意 `image` 和 `setup_command` 当作 Environment Version。它既不能证明运行基础确实存在，也允许把任意 shell 注入调度脚本，无法提供可重放的精确运行语义。

## 选项

1. **通用 provider/validator registry 与组合图** —— 扩展性高，但引入当前没有消费者的抽象，也无法收紧任意 shell。
2. **两个显式 runtime kind** —— `modules` 与 `apptainer_sif` 分别拥有封闭定义、验证和执行策略；不支持任意组合。

## 决定

Environment publication 使用持久 `EnvironmentPublicationAttempt`，状态仅为 `pending -> processing -> succeeded|failed`。成功在一个事务中创建且仅创建一个不可变 `EnvironmentVersion`；失败不创建 Version，并保留结构化原因、验证摘要与证据。

`modules` 定义固定为 cluster profile `107`、module system `environment_modules`、activation policy `purge_then_ordered_load_v1` 和有序精确 allowlist。V1 用户运行 allowlist 包含 Python、Miniconda、CUDA、Apptainer、Go 与 oneAPI 计算模块；不接受任意 setup shell、用户或 home modulefiles。

`apptainer_sif` 定义固定记录平台控制、内容寻址的 SIF SHA-256、字节数和 locator，来源 URI/摘要、架构、launcher module `apptainer/1.4.5` 与固定 exec policy。launcher 是基础设施前提，不是用户 modules 组合。发布必须对真实 CAS 字节调用已安装的 Apptainer CLI，并从 `inspect --json` 的 `data.attributes.labels["org.label-schema.build-arch"]` 取得实际 SIF 架构；只把 `amd64` 与 `x86_64` 归一为固定 `x86_64`，元数据缺失、格式错误或其他架构均失败。CLI 不可用时同样明确失败，不伪造成功，也不手写 SIF 解析器。Version 和 Run Snapshot 只保存 CAS locator；提交调度器前通过 StoragePort 解析 scheduler-visible 文件路径并重新计算摘要，绝不把绝对路径作为版本身份。

不可变定义与验证证据和可变 availability 分开。availability 为 `available|unavailable|deprecated`，带原因、详情与检查时间。显式 refresh 复用 Modules allowlist 或 SIF CAS/CLI 校验，只更新这四个可变字段并返回新 projection。Run Snapshot 冻结精确 Version ID、canonical execution spec 和 definition hash；保存、preflight 与执行读取当前 projection 并重新检查 availability 与 USE，绝不 fallback。

当前处理器采用单 API durable loop。授权的 attempt history/list 让重载后的页面恢复 pending、processing 和 failed 原因。它不是多副本或生产 Worker。

## 后果

- 好：发布结果可审计、可重放；调度脚本不再执行 Environment 任意 shell；Run 精确语义没有隐式回退。
- 坏：新增 runtime kind 必须形成新的产品决定；本地缺少 Apptainer 时 SIF publication 只能得到真实失败证据。
- **反悔成本**：高 —— 涉及持久 schema、OpenAPI、Run Snapshot 和调度执行协议。

## 重新评估的条件

平台正式支持第三种运行基础，或 #7 建立独立 Worker/Slurm 边界并证明当前单 API loop 不再满足时，以新 ADR 取代本决定。

---
> 决策变了不要改这份文件；新写一份并把本决定标记为被取代。
