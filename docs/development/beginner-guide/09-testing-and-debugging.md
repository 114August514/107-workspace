# 第九章：测试、质量检查与调试

测试的目标不是证明某个函数“被调用过”，而是证明用户可观察的结果和重要规则正确。测试数量
也不是目的；选择与风险相匹配的粒度更重要。

## 9.1 测试粒度

```text
backend/tests/
├── unit/domain/          纯领域规则
├── unit/application/     使用 Fake Port 的用例编排
├── unit/observability/   请求上下文和日志格式
├── integration/          单个 DB、Storage、Scheduler 等 Adapter
├── contract/             API 和外部协议
├── architecture/         依赖方向与仓库规则
└── system/               少量完整核心闭环

frontend/tests/
├── unit/                 纯函数和边界判断
├── component/            用户可观察的组件行为
├── feature/              替换 API 边界后的页面流程
└── e2e/                  少量真实浏览器闭环
```

目录只在有对应测试时创建。上图同时包含目标粒度，并不表示当前每一层都已经完整覆盖。功能切片
进入实现时再补需要的测试，不提交 skip、xfail 或只占位置的文件。

## 9.2 怎样选择测试

| 改动 | 优先选择 |
| --- | --- |
| 纯计算、状态判断、路径校验 | Domain 或前端 Unit |
| 用例的权限和调用顺序 | Application Unit，使用 Fake Port |
| 数据库、Storage、Scheduler 行为 | Integration |
| API 字段和错误信封 | Contract |
| 按钮、表单、错误和空状态 | Component |
| 一段页面操作 | Feature |
| 最关键跨进程流程 | 少量 System/E2E |

安全不是独立的测试目录。越权、不可变性、Secret 泄露等断言应放在真正执行这些边界的测试中。

## 9.3 先看到测试失败

仓库要求先写测试并亲眼看到它红，再实现功能。一个可靠的小循环是：

```text
写一个能表达预期的测试
→ 运行它并确认因缺少功能而失败
→ 写最小实现
→ 运行相关测试
→ 整理代码
→ 运行更大范围检查
```

如果新测试一开始就通过，可能测试了已有行为、没有到达目标分支，或断言过弱。先弄清原因，
不要把“绿”自动当成好消息。

## 9.4 Arrange、Act、Assert

多数测试可以按三个阶段阅读：

```text
Arrange  准备输入、用户和依赖
Act      执行被测行为
Assert   验证返回值、状态或外部可观察结果
```

有效测试必须有有意义的断言。不要只调用函数；也不要把全部依赖 Mock 掉后只断言某个 Mock
被调用。Application 测试可以用 Fake Repository 和 Scheduler，但应验证业务结果、保存的快照
或状态变化。

前端组件测试按角色、可见文案和用户操作查询元素，不绑定 Ant Design 私有 class 或内部 DOM。

## 9.5 权限和不可变性怎么测

权限测试至少准备两个用户或 Workspace：

```text
用户 A 创建资源
用户 B 带着 A 的资源 ID 请求
断言得到 403 或 404，且没有产生写入或调度副作用
```

只用自己的 ID 测成功路径无法发现越权。不可变对象则应验证不存在更新入口，或修改尝试会失败，
同时旧 Snapshot 仍保持原值。

Secret 测试既要检查 API 响应，也要检查 Snapshot、事件和日志中没有明文。不要在测试失败消息
里打印真实 Secret，可使用明显的假值。

## 9.6 统一检查入口

日常可以运行较小范围：

```bash
make test
make check-backend
make check-frontend
make coverage
```

声称完成之前运行：

```bash
make check
```

它统一执行格式检查、Lint、类型检查、测试、构建和契约核对。`make coverage` 当前生成后端报告，
重构期不设置失真的全仓百分比门槛。

CI 调用同一任务实现，并额外覆盖迁移升降级、Windows 无 Make 入口以及 Compose 构建和 Smoke。
不要自己发明另一套检查链，也不要通过 skip、注释测试或放宽断言换取绿色结果。

## 9.7 调试先缩小范围

遇到页面问题时按数据链逐层确认：

1. 页面是否完成加载；
2. 浏览器 Network 中是否发出请求；
3. HTTP 状态码和错误体是什么；
4. 响应的 `request_id` 是什么；
5. 后端同一 `request_id` 的日志发生了什么；
6. 如果是 Run，再检查调度 ID、状态事件、日志和退出码。

健康检查有两个层次：

```text
GET /api/v1/health   进程是否响应
GET /api/v1/ready    数据库是否可用
```

`health` 成功但 `ready` 失败，通常说明 API 进程存在而数据库连接有问题。

## 9.8 常见现象

| 现象 | 优先检查 |
| --- | --- |
| 前端字段突然为空 | OpenAPI 是否更新，TypeScript 类型检查是否通过 |
| 请求返回 403/404 | 当前开发用户和 Workspace 归属 |
| 请求返回 422 | 请求体是否符合 Pydantic Schema |
| Run 状态不更新 | 后台同步、Scheduler `poll` 和终态判断 |
| 日志不完整 | 接口是否返回尾部且标记 `truncated` |
| 本机通过但 CI 失败 | 具体失败平台、迁移或 Compose Job |
| 构建报告契约漂移 | 运行 `make contract` 并检查生成差异 |

调试时保留证据：输入条件、实际命令、状态码、`request_id` 和最小复现步骤。不要只写“页面坏了”
或“Slurm 不工作”。

