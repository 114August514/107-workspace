# 测试策略

测试以 `docs/product/design.md` 的目标设计为依据，不把当前旧实现的 API、进程边界、
权限矩阵或 UI 组件写成未来兼容契约。一个功能切片进入实现时，同步补齐对应粒度的测试；
尚未实现的能力记录在 Issue 中，不提交 skip、xfail 或占位测试。

## 粒度

```text
backend/tests/
├── unit/domain/          纯领域规则和不变量
├── unit/application/     使用 Fake Port 的用例编排
├── unit/observability/   请求上下文和日志格式化
├── integration/          单个 API、DB、Storage、Scheduler 或 Worker Adapter
├── contract/             OpenAPI、错误信封和外部协议
├── architecture/         依赖方向与仓库治理
└── system/               少量 API + Worker + PostgreSQL 核心闭环

frontend/tests/
├── unit/                 纯函数、状态判断和边界降级
├── component/            用户可观察的组件行为
├── feature/              在 API 边界替换外部依赖的页面流程
└── e2e/                  少量真实浏览器核心闭环
```

目录只在有对应测试时创建。安全是测试主题，不是独立粒度；安全断言放在实际执行边界中，
例如 Domain 不变量、API 集成或系统测试。

## 当前基线

当前只保留以下已实现且不绑定旧产品流程的基础保护：

- 后端单元规则：算力校验、路径规范化、Run Snapshot 序列化与路径约束、Variable 与
  Secret 解析。
- 后端横切单元：请求标识上下文与日志格式化。
- 后端 Adapter：本地存储配置、文件权限和 Mock Scheduler 平台行为。
- 架构治理：Domain 与 Application 依赖方向，以及活动文档、GR、ADR 和本地链接引用。
- 前端单元边界：API 错误降级与环境变量引用解析。

旧 ASGI / SQLite 工作流、进程内 `/runs/sync` 驱动、`X-User` 自动建号、固定 seed 数据、
旧角色矩阵和 Ant Design 视觉偏好不构成新基线。对应功能按目标架构重新实现时再写测试。

## 断言边界

- Unit 不访问真实数据库、HTTP、子进程或共享文件系统。
- Integration 每次只证明一个真实 Adapter 或入口，不称为端到端测试。
- Contract 只验证跨组件可观察的形状和语义，不直接调用私有函数。
- Component 通过可访问角色、可见文案和用户结果断言，不依赖组件库私有 class 或 DOM。
- System 必须经过独立 API、Worker 和 PostgreSQL；缺少这些边界时不伪造通过。
- 测试文件围绕一项能力或一个边界组织，不按每个函数机械拆分。

## 运行

```bash
make test
make check
make coverage
```

原生 Windows 没有 Make 时使用相同任务实现：

```powershell
uv run --no-project python scripts/workspace.py test
uv run --no-project python scripts/workspace.py check
uv run --no-project python scripts/workspace.py coverage
```

`make coverage` 在测试基线重建期间只生成报告，不设全仓百分比门槛。新模块形成稳定边界后，
再按模块风险和可测试性建立门槛，不能用旧实现覆盖率代表目标架构质量。

仓库根 `pytest.ini` 只收集 `backend/tests/`，防止 IDE 或裸 pytest 把
`archive/workspace107/` 的来源快照当成活动测试。统一入口仍是协作和 CI 的权威方式。
