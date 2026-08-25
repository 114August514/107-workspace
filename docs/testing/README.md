# 测试策略

测试服务于需要长期保护的可观察行为、业务规则、契约和重要风险。

测试以 `docs/product/design.md` 的当前目标设计为产品语义依据，
不把当前旧实现的 API、进程边界、权限矩阵、UI 结构或其他施工状态
自动固化为未来兼容契约。

实现功能或修改行为时，根据当前变化的实质风险判断是否需要新增永久测试。

默认要求获得与风险相称的验证证据，
但不默认要求每次修改都新增测试文件。

普通缺陷和尚未被接受为当前实现妥协的未完成能力记录在 Issue 中。有意保留的代码妥协还必须登记到 [`../product/deferred.md`](../product/deferred.md)，并由引入该妥协的 PR 引用登记 ID。不要为了表达未来计划提交 skip、xfail 或占位测试。

## 永久测试与一次性验证

永久测试用于长期防止有价值的行为或风险回归，例如：

- 业务规则和状态转换；
- 用户可观察行为；
- public API 和跨组件契约；
- 权限、安全和数据一致性；
- 重要失败路径；
- 已经发生且值得防止再次出现的回归。

新增永久测试前，应先确认：

- 测试保护的是行为或契约，而不是当前实现细节；
- 该风险没有被现有测试充分覆盖；
- 测试失败时能够指出有意义的产品或工程回归；
- 长期维护成本与被保护风险相称。

以下检查通常属于当前工作的验证证据，
不默认沉淀为永久测试：

- 文档和普通配置修改；
- 文件移动、重命名和机械重构；
- 简单 wiring；
- private helper 或内部调用方式变化；
- 实现迁移过程中确认旧代码、旧字段、旧入口或旧 fallback 已经清除；
- 对一次性数据转换或施工状态的检查。

这类工作可以使用：

- targeted test；
- 搜索；
- 静态检查；
- 临时脚本；
- 一次性测试；
- 手动或自动的针对性实验。

如果“旧行为不得再次出现”本身属于长期产品契约、安全不变量
或已经发生且可能复发的重要回归，则应留下行为导向的永久测试，
而不是测试旧实现文件或旧函数是否存在。

不要为了“更安全”在 unit、integration、system 等多个层级
重复完整验证同一条规则。

## 粒度

```text
backend/tests/
├── unit/domain/          纯领域规则和不变量
├── unit/application/     使用 Fake Port 的用例编排
├── unit/observability/   请求上下文和日志格式化
├── integration/          API、DB、Storage、Scheduler 或 Worker Adapter
├── contract/             OpenAPI、错误信封和外部协议
├── architecture/         依赖方向与仓库治理
└── system/               少量 API + Worker + PostgreSQL 核心闭环

frontend/tests/
├── unit/                 纯函数、状态判断和边界降级
├── component/            用户可观察的组件行为
├── feature/              在 API 边界替换外部依赖的页面流程
└── e2e/                  少量真实浏览器核心闭环
```

目录只在存在对应长期测试资产时创建。

安全是测试主题，不是独立粒度。
安全断言放在实际规则或执行边界所在的最低有效层级，
例如 Domain、API integration 或 system test。

优先在最接近规则归属、成本最低且稳定的层级保护行为；
只有跨组件连接本身存在重要风险时，才增加更高层测试。

## 当前测试资产

当前仓库已有测试只代表它们实际保护的行为和工程边界，
不因为测试已经存在就自动获得永久兼容地位。

当前较稳定的保护包括：

- 后端领域规则：算力校验、路径规范化、Run Snapshot 相关规则、
  Variable 与 Secret 解析；
- 后端横切行为：请求标识上下文与日志格式化；
- Adapter 行为：本地存储、文件权限和 Mock Scheduler；
- 架构治理：Domain / Application 依赖方向，以及活动文档和引用关系；
- 前端边界行为：API 错误降级与环境变量引用解析。

旧 ASGI / SQLite 工作流、进程内 `/runs/sync` 驱动、
`X-User` 自动建号、固定 seed 数据、旧角色矩阵和 Ant Design 视觉实现
不因历史实现或历史测试而成为新的产品兼容契约。

相关代码发生迁移时，应先明确目标设计和需要长期保护的行为，
再决定保留、重写或删除对应测试。

删除旧测试前，需要获得足够证据证明：

- 它保护的行为已经失效；或
- 对应行为已经在新的权威边界得到保护；或
- 它只是在约束已经被废弃的实现细节。

## 断言边界

### Unit

Unit 应聚焦单一规则或局部行为，
不依赖真实数据库、HTTP、子进程或其他外部服务。

不要为了测试 private implementation 而构造脆弱的调用次数、
内部函数或 mock interaction 断言。

### Integration

Integration 验证真实 Adapter、持久化边界或协议入口之间的连接行为。

不要因为使用了多个真实组件就自动把它称为端到端测试。

### Contract

Contract 验证跨组件可观察的形状和语义。

不要通过直接调用 private function 来证明 public contract。

### Component

Component 通过用户可观察结果断言：

- 可访问角色；
- 可见内容；
- 交互结果；
- 状态变化。

不要依赖组件库私有 class、内部 DOM 结构或其他实现细节。

### System

System 用于保护少量真正重要的跨进程核心闭环。

需要真实证明 API、Worker 和 PostgreSQL 边界的场景，
不能通过把这些边界 mock 掉之后宣称 system 行为已经验证。

官方 executable smoke 使用真实 API 进程、独立 Worker、PostgreSQL 和 MockScheduler；每次创建
唯一数据库与临时 storage，结束后隔离清理。它证明本地进程/持久化/文件系统接缝，不证明真实
107 service identity、mount、REST profile、credential lifecycle 或 authorized submit/restart。

### 组织

测试文件围绕一项能力、规则或边界组织，
不按每个函数机械拆分测试文件。

## 验证选择

开发过程中，根据当前 Claim 和风险选择最小有效验证。

例如：

- 修改纯领域规则，优先运行对应 domain tests；
- 修改某个 Adapter，优先运行相关 integration tests；
- 修改 OpenAPI 或跨组件接口，运行 contract 验证；
- 修改前端用户行为，选择最接近该行为的 unit / component / feature 测试；
- 机械迁移或清理旧实现，可以使用搜索、临时检查或 targeted test；
- 高风险跨组件流程才需要 system / e2e 级证据。

不要因为“还可以再测一个情况”就持续增加测试。
当当前 Claim 和实质风险已经获得充分证据时，应停止。

## 运行

Linux / WSL2 运行完整测试与工程验证：

```bash
make test
make check
make coverage
make smoke
```

`make smoke` 需要 `WORKSPACE107_DATABASE_URL` 指向 PostgreSQL 管理连接；它启动 API 与独立
Worker 并使用 Mock Scheduler。已有栈可运行
`uv run --no-project python scripts/workspace.py smoke --base-url <.../api/v1>`，该模式不接管
栈生命周期或数据清理。

原生 Windows / PowerShell runtime 不在支持矩阵内。统一 Python task 实现不构成跨平台承诺；
完整验证与 smoke 必须在 Linux 或使用 Linux toolchain/filesystem 的 WSL2 运行。权威边界见
[ADR-0005](../decisions/0005-platform-support-matrix.md)。

`make test` 是 Linux/WSL2 完整项目测试入口；`make check` 是完整工程验证入口，但局部改动不
要求机械运行全套。`make coverage` 当前只生成报告，不设置全仓百分比门槛。

如果未来需要 coverage gate，
应根据模块风险、稳定边界和可测试性决定，
不能用旧实现的覆盖率代表目标架构质量。

仓库根 `pytest.ini` 只收集 `backend/tests/`，
避免 IDE 或裸 pytest 把 `archive/workspace107/`
中的历史来源快照当作活动测试。

协作和 CI 仍使用项目统一任务入口。
