# 第五章：后端开发入门

107 Workspace 后端使用 Python 3.12、FastAPI 和异步 SQLAlchemy。本章不系统讲这些框架，
而是沿一次真实的“提交 Run”请求说明开发中必须认识的部分。

## 5.1 应用入口与路由

`backend/src/workspace107/main.py` 中的 `create_app()` 创建 FastAPI 应用，注册中间件、错误
处理和总路由。所有业务接口都有 `/api/v1` 前缀，这个前缀定义在
`api/routes/__init__.py`。启动后可以在 <http://127.0.0.1:8000/docs> 查看 FastAPI 自动生成
的交互式接口文档。

一个路由由 HTTP 方法、路径、输入 Schema 和输出 Schema 构成。下面是
`api/routes/runs.py` 中提交接口的简化形式：

```python
@router.post(
    "/projects/{project_id}/runs",
    response_model=RunOut,
    status_code=201,
)
async def create_run(
    project_id: str,
    payload: RunDraftIn,
    user: CurrentUser,
    services: ServicesDep,
) -> RunOut:
    result = await services.runs.create(user.id, project_id, _to_draft(payload))
    return run_out(result.run)
```

`project_id` 来自 URL，`payload` 是 JSON 请求体，`CurrentUser` 和 `ServicesDep` 由 FastAPI
依赖注入。路由只完成协议转换：把 Pydantic 输入模型转为用例参数，再用 Presenter 转成响应
模型。权限、数据库写入和调度提交都不应写在这里。

请求与响应模型集中在 `api/schemas.py`。字段可省略时要准确写成 `X | None = None`；状态等
固定集合使用领域枚举；结构固定的数据应定义模型而非自由 `dict`。这些类型会进入 OpenAPI，
继而成为前端类型，所以 Schema 既是校验器，也是跨组件契约。

## 5.2 一次请求中的依赖与事务

`api/deps.py` 负责请求级装配。`get_services()` 打开一个 `AsyncSession`，构造 Repository 和
Application Service，然后在请求成功时提交事务，异常时回滚，最后关闭 Session：

```python
session = context.session_factory()
try:
    yield build_services(context, session)
    await session.commit()
except Exception:
    await session.rollback()
    raise
finally:
    await session.close()
```

因此一般路由不需要手动 `commit()`。一次 HTTP 请求就是一个事务边界。后台 Run 状态同步也
会创建自己的 Session 和事务，相关入口在 `main.py` 的 `_sync_loop()`。

开发身份目前由 `get_current_user()` 解析：本地开发通过 `X-User` 请求头识别用户，不传时是
`student`，首次出现会自动创建用户和 Personal Workspace。这只是当前开发实现，不是正式
认证方案；不要把它当成生产安全机制，也不要在新业务代码中自行读取 `X-User`。

## 5.3 Application Service 如何编排用例

`application/run_service.py` 的 `RunService.create()` 是提交 Run 的主要用例。它按顺序完成：

```text
检查用户对 Project 的提交能力
→ 处理幂等键，避免重试产生两次计算
→ 锁定资源权益并执行 preflight
→ 根据已解析结果创建不可变 Run Snapshot
→ 创建 Run 和事件记录
→ 准备运行目录、在执行边界解析 Secret
→ 调用 SchedulerPort.submit()
→ 保存调度任务 ID 或提交失败事实
```

这里的关键不是记住每个函数名，而是理解 Application 层负责“顺序”。例如权限校验通过、
算力方案存在、资源额度足够、环境版本可用等条件必须全部成立，才能固定快照。调度器提交
失败时，代码不会把整个 Run 删除，而是把状态改为 `submit_failed`，保留可排查的历史记录。

访问控制集中在 `application/access.py` 的 `AccessGuard`。读取 Project 时，它会继续检查所属
Workspace 和 Membership；用户没有发现权限时返回 404，避免泄露对象是否存在；用户能看见
对象但没有操作能力时才返回 403。新增或重写资源接口时，不能只按资源 ID 查询后就直接使用，
必须经过归属和能力检查，并补“使用别人的 ID”测试。

## 5.4 Domain 保护核心规则

领域对象和规则在 `domain/`。最典型的是 `domain/run_snapshot.py` 中的 `RunSnapshot`：它是
`frozen=True` 的 dataclass，构造时还会拒绝绝对工作目录和包含 `..` 的路径。对应仓储端口
`RunSnapshotRepository` 只有 `add()` 和 `get()`，没有 `update()`。要改变执行内容，只能创建
新的 Run 与 Snapshot。

Secret 也遵循清晰边界。Snapshot 只保存“环境变量名到 Secret 名称”的引用；
`RunService._submit()` 在最后提交任务时才从 `SecretVault` 解析明文并放入进程环境。明文不得
进入 Snapshot、API、日志或事件。调试时也不要打印完整环境变量字典。

Domain 还包含算力请求校验、路径规范化、枚举和错误类型。规则只依赖传入的数据，不直接访问
数据库、HTTP、文件和当前时间。若一条规则从多个入口都必须成立，应优先放在领域对象或领域
函数中，而不是在每个路由各写一次。

## 5.5 `async` 和异常处理的最低知识

项目中数据库、存储和调度调用大多是异步操作，需要使用 `await`。`async def` 不代表内部所有
代码自动并发；它只是允许函数在等待 IO 时把执行机会交出去。不要在路由或异步用例中直接做
长时间同步网络请求、阻塞等待或大量 CPU 计算，否则会阻塞其他请求。外部 IO 应通过已有 Port
或合适的 Adapter 完成。

领域错误定义在 `domain/errors.py`，`api/errors.py` 将它们统一转换为 HTTP 错误信封。
`api/routes/__init__.py` 的 `COMMON_ERRORS` 同时把常见 400、403、404、409、422 和 502 响应
写入契约。新代码应抛已有的语义异常，不要在 Application Service 中拼 `JSONResponse`，也
不要捕获所有异常后假装成功。

## 5.6 修改后端功能的最短路线

以增加一个 Run 响应字段为例：

1. 在领域模型或用例结果中确认该数据真实存在，且允许暴露。
2. 修改 `api/schemas.py` 的输出 Schema 和 `api/presenters.py` 的转换。
3. 若涉及规则，先在 `backend/tests/unit/domain/` 或 `unit/application/` 添加失败测试。
4. 若涉及数据库，按下一章的迁移流程处理，不能只改 ORM 表定义。
5. 运行 `make contract`，检查生成的 OpenAPI 和前端类型差异。
6. 运行 `make check`，并手工验证接口成功、错误和无权限场景。

不要直接编辑 `contracts/openapi.json` 或前端生成类型来“修正”接口。它们只是后端路由和 Schema
的生成结果，真正的修改源头在 `api/`。
