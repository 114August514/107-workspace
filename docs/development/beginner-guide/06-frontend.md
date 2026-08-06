# 第六章：React 前端开发

前端位于 `frontend/`，使用 React、TypeScript、Vite 和 Ant Design。本章不会系统教授 React，
只介绍阅读和修改当前页面必须掌握的概念。

## 6.1 四个基本概念

- **组件（Component）**：返回界面的函数，可以组合和复用。
- **属性（Props）**：父组件传给子组件的数据。
- **状态（State）**：组件内部会变化、变化后会触发重新渲染的数据。
- **Hook**：让组件保存状态、加载数据或执行副作用的函数，例如 `useState`、`useEffect`。

TypeScript 会检查 Props、State 和 API 数据的形状。它不能替代测试，但能在字段改名、漏传参数
等常见错误进入浏览器之前给出提示。

## 6.2 目录和页面

```text
frontend/src/
├── api/          API 客户端、生成类型和异步 Hook
├── components/   可复用界面和交互
├── pages/        顶层页面
├── utils/        格式化、状态判断等纯函数
├── App.tsx       路由和应用外壳
└── main.tsx      React 启动入口
```

当前页面主要包括首页、Workspace、Project 和 Run。页面负责组合组件，具体的数据加载和交互
尽量留在 `components/` 与 `api/` 中。例如 Run 页面组合状态、日志、事件、Artifact 和快照组件，
而不是把所有逻辑写进一个巨大文件。

找界面代码时，可以先从地址对应的 `pages/` 文件开始，再跟随组件名称进入
`components/workspace`、`project`、`runconfig` 或 `run`。

## 6.3 开发服务器与 API 代理

`make dev` 启动 Vite。浏览器向 `/api` 发出的请求会代理到 `http://127.0.0.1:8000`。前端代码
只使用 `/api/v1/...` 相对路径，不硬编码后端主机和端口。部署时 nginx 也按同源方式转发，前端
代码因此不需要按环境切换地址。

开发身份由右上角用户切换控件控制。选择保存在 `localStorage`，API Client 把它放入
`X-User` 请求头。切换身份很适合验证越权场景，但这只是本地机制，不是真实登录系统。

## 6.4 API 调用只有一套类型来源

前端不能手写后端 DTO。类型从后端一路生成：

```text
FastAPI 路由与 Schema
        → contracts/openapi.json
        → frontend/src/api/schema.d.ts
        → frontend/src/api/types.ts
        → API Client 和组件
```

`schema.d.ts` 是生成文件，`types.ts` 只为生成类型起短名字。HTTP 请求集中通过
`frontend/src/api/client.ts` 中的 `openapi-fetch` 客户端发出。路径、路径参数、query 或请求体
字段写错时，TypeScript 应报告错误。

后端接口变化后，在根目录运行：

```bash
make contract
```

然后根据类型错误修改调用方。不要编辑生成文件，也不要用宽泛的 `any` 或类型断言压掉真实
不一致。

## 6.5 加载、失败和空状态

网络请求不是立即完成的，而且可能失败。`src/api/useAsync.ts` 帮助组件表达常见状态：

```text
loading    正在加载
data       加载成功
error      加载失败
```

一个完整界面至少要考虑加载中、错误、空数据和成功四种情况。跨页面的通用处理应使用已有的
`AsyncSection` 等公共组件，避免每个页面用不同文案和不同判断重复实现。

API 错误会转换为 `ApiError`。排查问题时记录 `requestId`，它来自错误体中的 `request_id` 或
响应头 `X-Request-Id`，可以对应到服务端同一次请求的日志。

## 6.6 Run 为什么会轮询

作业提交后不会在一个 HTTP 请求内完成。Run 页面在任务未结束时周期性触发后端状态同步，再
读取最新 Run。轮询需要满足：

- Run 进入终态后停止；
- 组件卸载或切换到其他 Run 后停止旧轮询；
- 一次请求失败时展示错误，而不是假装状态未变化；
- 状态名称和终态判断复用公共工具，不在多个组件复制。

轮询只是当前实现。未来若改为事件推送，用户可观察行为可以保持不变，组件不应依赖调度器
内部细节。

## 6.7 表单和展示的基本原则

本项目使用 Ant Design。新增交互时优先复用已有表单、表格、Modal 和状态标签模式。需要注意：

- 表单提交期间禁用重复提交，并展示明确成功或失败结果；
- 展示后端返回的 GPU、Partition、QoS 等事实，不在前端硬编码平台配置；
- 表格字段使用项目的 `field<T>()` 帮助函数，减少字段改名后静默空列；
- 日期、容量和状态使用 `utils/` 中的公共格式化函数；
- 不依赖 Ant Design 私有 class 或内部 DOM 结构实现业务逻辑。

## 6.8 修改前端功能的最短路线

以“在 Run 列表显示后端已有字段”为例：

1. 从 `RunTable.tsx` 找到列定义和数据类型；
2. 确认字段已存在于 `api/types.ts` 派生的类型中；
3. 先为格式化或可观察组件行为添加测试；
4. 使用公共格式化函数实现展示，并处理空值；
5. 在窄窗口、加载、错误、空列表和正常数据下检查布局；
6. 运行 `make check-frontend`。

如果类型中没有字段，应回到后端确认接口语义，再按契约链更新，不能只在前端假造字段。

## 6.9 前端最低检查

```bash
make check-frontend
```

它覆盖格式检查、ESLint、TypeScript 类型检查、Vitest 和生产构建。接口发生变化时还需要运行：

```bash
make contract
make check
```

“开发服务器能显示”不是完成证据。生产构建、类型检查和测试发现的问题往往不会直接出现在
手工点击的那条路径中。

