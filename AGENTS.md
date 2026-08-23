# 107 Workspace

本文件是 Coding Agent 在 107 Workspace 中工作的项目入口。

这里只保存 Agent 的工程行为和仓库级工作边界。

产品规则、领域模型、测试规范、部署语义和长期设计决定等已经有权威文档的内容，
不要复制到本文件。

支持 Lean Harness 的运行环境通过 `.omp/AGENTS.md`
获得完整 Policy 和 Skills。

其他环境至少遵循本文件中的工程原则和项目索引。

## 工程原则

如果当前环境能够使用 Lean Harness，
以 `.omp/AGENTS.md` 引入的完整 Policy 和 Skills 为准。

否则至少遵循以下原则：

- 优先推进真实、可验证的结果，不用流程、检查或汇报动作本身冒充进度。
- 实现前先调查现有代码、标准能力、已有依赖和项目模式；
  优先复用已经正确解决的问题，不重复造轮子。
- 选择满足当前目标且整体复杂度最低的方案，
  不为假设中的未来提前建设抽象、兼容层或基础设施。
- 局部、可逆、影响可控的普通工程决定直接完成。
  技术未知优先通过代码、文档和实验自行收敛。
- 用户可见但需求未定义的行为、public contract、权限与安全边界、
  破坏性持久状态变化、发布部署及其他高影响且难以逆转的决定，
  请求相应的人类判断。
- 测试保护值得长期维护的可观察行为、业务规则、契约和重要风险，
  不保护施工过程或偶然实现细节。
- 默认需要与风险相称的 fresh evidence，但不默认要求新增永久测试。
  迁移、旧语义清理和机械重构可以使用 targeted check、搜索、
  临时脚本或一次性测试完成验证。
- 检查、Review 和重新确认由真实风险、技术不确定性或决策价值触发。
  不要在正常推进的每一步机械停下来确认“目前还没出问题”。
- 完成声明必须与实际证据一致；未验证的部分明确说明。

## 查找项目事实

开始任务后：

1. 根据需要了解项目概况和当前实现；
2. 查看 `docs/README.md`，找到当前问题对应的权威来源；
3. 阅读与任务直接相关的文档和当前代码；
4. 在这些事实基础上继续实现。

不要机械加载所有文档。

`archive/`、`docs/archive/` 和 `docs/references/`
不是当前产品或实现规则的默认事实来源。

不要因为搜索命中了历史材料，就把它当作当前规范。

## 仓库边界

判断代码位置和职责时，优先阅读当前实现和相关 ADR，
不要从本文件推导详细架构。

主要工作区域：

- `backend/`
- `frontend/`
- `contracts/`
- `deploy/`
- `scripts/`

遇到 generated file 时，先找到正式 source-of-truth 和生成入口，
不要直接修改生成物绕过生成流程。

不得提交 Secret、token、private key 或其他敏感凭据。

涉及 authentication、authorization、ownership、持久状态、
API contract、scheduler / Slurm、部署或真实共享环境时，
提高风险判断强度，并先读取对应权威文档。

这些区域本身不是停止工作的理由；
是否升级取决于实际影响和可逆性。

## 验证

完整项目验证入口：

`make check`

开发与验证支持 Linux，或在 Windows 主机上使用 Linux toolchain 与 Linux filesystem
的 WSL2 环境；不支持原生 Windows / PowerShell runtime。

开发过程中选择能够证明当前 Claim 的最小有效验证，
不要求每次局部修改都机械运行完整检查。

测试策略、测试粒度和长期测试资产规则见：

`docs/testing/README.md`

未运行的相关验证必须明确说明。

## 在途工作

`docs/journal/` 是本项目的 durable work state。

只有工作确实需要跨会话、并行 ownership、handoff、恢复，
或存在无法仅通过 Git 安全重建的仓外状态时，才使用 journal。

简单、单会话、局部工作不要求创建 journal。

具体格式和生命周期见：

`docs/journal/README.md`

不要为同一项工作建立平行的项目级持久状态系统。

## 完成

完成以当前目标、实际修改和 fresh evidence 为依据。

支持 Lean Harness 的环境可以使用其 Review 和 finish 方法增强检查。

如果验证只覆盖 mock、本地或其他受限环境，
明确说明证据范围。

没有验证过的内容不要宣称已经完成。
