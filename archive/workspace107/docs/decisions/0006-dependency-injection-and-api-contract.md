# ADR-0006 依赖注入与接口契约

状态：已接受 · 阶段：M1 · 相关：GR-001、GR-013

## 背景

M1 交付后复查，发现两处「一改要改一堆」的隐患。它们表现不同，根子是同一个：
**边界只写在文档里，没有变成机器能检查的东西。**

### 后端：用例层被绕过去了

`Services` 容器把仓储、存储和调度器一起交给了路由，而且 `repos` 的类型
直接写成了具体的 `SqlRepositories`：

```python
class Services:
    repos: SqlRepositories        # 具体实现，不是端口
    guard: AccessGuard
    storage: StoragePort
    scheduler: SchedulerPort
    ...
```

于是有 7 处路由直接查仓储、直接读存储。后果不只是「不好看」：

- 绕过用例层就绕过了权限校验、事务边界和领域规则
- 换存储实现要改路由，而路由本来不该知道存储是什么
- 同一个操作在路由和服务里各写一遍，两边会慢慢长歪

### 前端：类型是手抄的

`frontend/src/api/types.ts` 是 295 行手写 TypeScript，照着后端 schema 抄。
CI 里检查了 `openapi.json` 与后端一致，但**没人检查前端类型与 openapi.json 一致**。
GitGuideline 第八节写的链路里，「重新生成前端 API 类型」这一环当时并没有落地。

结果就是：后端把 `exit_code` 改个名，前端编译照样通过，跑起来才发现是 undefined。
而且改一个字段要人肉找出所有引用它的组件——这正是「改一个要改一堆」。

## 决策

### 1. 依赖注入：具体实现只在两个地方出现

```text
domain/ports/     用协议描述「需要什么能力」
application/      只认这些协议，构造函数注入
infrastructure/   实现这些协议
main.py           进程级装配：数据库、存储、调度器、时钟
api/deps.py       请求级装配：仓储、Secret 保管、各用例服务
```

具体实现类只能在 `main.py` 和 `api/deps.py` 里被构造。换数据库、换调度器、
换存储，改动范围就是这两个文件。

### 2. Services 容器只暴露用例服务

```python
class Services:
    workspaces: WorkspaceService
    projects: ProjectService
    run_configurations: RunConfigurationService
    runs: RunService
    catalog: CatalogService
    lifecycle: RunLifecycleService
```

路由拿不到仓储和端口，也就**没有办法**绕过用例层。这不是洁癖，是一条安全边界：
权限校验（GR-001 / GR-013）都在服务里，绕过服务等于绕过它们。

需要新能力时加用例服务或给现有服务加方法，不要往容器里塞端口。

### 3. 前端类型必须从契约生成，禁止手写

```text
后端 DTO / 路由
       ↓  workspace107.tools.export_openapi
docs/api/openapi.json
       ↓  openapi-typescript
frontend/src/api/schema.d.ts        （生成物，不手改）
       ↓  派生并改成领域语言的短名字
frontend/src/api/types.ts
       ↓
组件
```

一条命令同步：

```bash
./scripts/sync-api-contract.sh
```

HTTP 调用走 `openapi-fetch`，泛型参数就是生成的 `paths`。
路径写错、路径参数漏传、query 名字拼错、请求体字段不对，全是编译期错误。

### 4. 契约必须说实话

生成的类型只有在契约本身准确时才有意义。为此做了四处修正：

| 原来 | 现在 | 差别 |
| :--- | :--- | :--- |
| `status: str` | `status: RunStatus` | 前端拿到联合类型，`Record` 少写分支会报错 |
| `scheduler: dict[str, object]` | `scheduler: ResolvedSchedulerOut` | 前端不用猜字典里有哪些 key |
| `name: str = ""` | `name: str \| None = None` | 「可以不传」在契约里如实表达 |
| 错误响应未声明 | 路由统一声明 `ErrorOut` | 前端解析错误体不再靠猜 |

框架自己的参数校验错误也统一成同一种错误体——两种形状意味着前端要写两套解析。

### 5. 表格列名也要接受检查

antd 的 `dataIndex` 声明成 `string`，不检查字段是否存在。字段改名后表格会安静地
渲染成空列，是最难发现的一类问题。用 `field<T>('exit_code')` 把它约束回类型上，
运行时零开销。

### 6. 生成物提交进仓库

`openapi.json` 和 `schema.d.ts` 都提交，CI 重新生成后比对差异。

这样做的好处：改动在代码评审里看得见——contract 变了，diff 里就有；
而且新成员 clone 下来直接能编译，不需要先跑后端。

代价是每次改 DTO 要多跑一次同步脚本。CI 会提醒，忘不了。

## 放弃的方案

**靠代码评审保证分层。** 试过了，M1 就是这么漏的。人会累，检查不会。

**前端类型在构建时生成、不提交。** 那么 contract 变化在 PR diff 里看不见，
评审时无从判断「这个改动会不会影响前端」；新成员还得先把后端跑起来才能编译前端。

**用 axios / fetch 手写请求函数，只用生成的类型标注返回值。** 只挡住了返回值，
挡不住路径和参数。路径拼错依然要到运行时才发现。

**在前端做运行时响应校验（zod 之类）。** 能挡住运行时不一致，但代价是每个 schema
再写一遍，又回到了手工同步。编译期检查加上 CI 的契约比对已经够了。

**放松 `--default-non-nullable` 让带默认值的字段都变成可选。** 那会让**响应**类型
也全变成可选，前端到处要判空，反而更弱。正确做法是让后端的请求 DTO 如实表达可选。

## 影响

这些约定都有对应的可执行检查，不靠自觉：

| 约定 | 检查它的东西 |
| :--- | :--- |
| domain 不依赖框架和基础设施 | `tests/unit/test_layering.py` + ruff 的 banned-api |
| application 只依赖端口 | `tests/unit/test_layering.py` |
| 路由不直接碰基础设施 | `tests/unit/test_layering.py` |
| Services 只暴露用例服务 | `tests/unit/test_layering.py` |
| 具体实现只在两个组合根构造 | `tests/unit/test_layering.py` |
| 前端类型与后端一致 | CI 的 `api-contract-check` |
| 前端调用与契约一致 | `npm run typecheck` |

新增一层或一类端口时，记得同步更新 `test_layering.py` 里的规则——
规则漏了，边界就等于没有。
