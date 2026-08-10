# 107 Workspace OMP 上下文

本项目使用 Lean Harness 作为工程方法与可复用 Skills 的来源。

Lean Harness 固定版本目录：

`~/.local/share/lean-harness/v0.1.0-dogfood`

## 工程原则

对于非简单的工程判断，以 Lean Harness Policy 作为方法指导：

@~/.local/share/lean-harness/v0.1.0-dogfood/policy/index.md

当当前任务与某个 Lean Harness Skill 匹配时，优先使用通过 `.omp/config.yml`
加载的对应 Skill。

Lean Harness 负责提供通用工程方法、风险判断与可复用能力；
具体项目规则以本仓库定义为准。

## 项目权威

@../AGENTS.md

## 工作连续性

本仓库拥有自己的持久化工作状态机制。

以下情况使用 `docs/journal/`：

- 工作需要跨会话继续；
- 存在多人或多个 Agent 并行，需要明确工作归属；
- 需要暂停、交接或之后恢复；
- 存在仓库外副作用，需要记录当前真实状态。

GitHub Issue 负责记录任务目标、范围、验收条件和正式任务决策。

Git 负责记录当前仓库和代码的真实状态。

ADR 与产品文档负责记录需要长期保留的设计和产品决策。

不要为同一项工作再建立一套并行的 Lean Harness Continuity 工作日志。

OMP 会话历史和上下文压缩仅属于临时运行时上下文，
不能作为项目持久状态的事实来源。

Lean Harness Continuity 可以作为工作连续性设计的参考，
但除非本项目以后明确采用，否则不作为 107 Workspace 的持久工作状态权威。
