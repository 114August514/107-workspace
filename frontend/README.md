# 前端

107 Workspace 控制台。React + TypeScript + Vite，组件库使用 Ant Design。
工具链统一使用 Node.js 24 LTS 与 pnpm 11；版本约束同时记录在 `.node-version`、
`package.json` 和 CI 中。

## 运行

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

打开 <http://127.0.0.1:5173>。开发服务器把 `/api` 转发到 `http://127.0.0.1:8000`，
所以代码里不出现后端地址。需要先按 [`backend/README.md`](../backend/README.md)
启动后端并载入种子数据。

## 目录

```text
src/
├── api/
│   ├── schema.d.ts     由 contracts/openapi.json 生成，不要手改
│   ├── types.ts        从 schema.d.ts 派生，只负责起短名字
│   ├── client.ts       基于 openapi-fetch 的类型安全调用
│   └── useAsync.ts     加载与轮询钩子
├── components/
│   ├── common/         AsyncSection、RunStatusTag 等跨页面复用组件
│   ├── layout/         AppShell、开发身份切换
│   ├── workspace/      成员、变量与 Secret、资源权益、默认环境
│   ├── project/        文件浏览与编辑、版本历史
│   ├── runconfig/      运行方案列表与表单
│   └── run/            提交弹窗、Run 列表、事件时间线、日志、产物、复现快照
├── pages/              HomePage / WorkspacePage / ProjectPage / RunPage
└── utils/format.ts     展示格式化
```

页面只做编排，数据获取和交互细节都在组件里。跨页面复用的展示逻辑
（状态标签、加载与错误处理、时长与容量格式化）只定义一次。

## 接口类型来自契约，不是手写的

```text
后端 DTO / 路由 → contracts/openapi.json → src/api/schema.d.ts → src/api/types.ts → 组件
```

**不要在前端手写任何接口类型。** 需要新字段先改后端，然后：

```bash
make contract                       # 在仓库根目录执行
```

HTTP 调用走 `openapi-fetch`，泛型参数就是生成的 `paths`：

```ts
await http.GET('/api/v1/projects/{project_id}/files/content', {
  params: { path: { project_id: id }, query: { path } },
})
```

路径写错、路径参数漏传、query 名字拼错、请求体字段不对，都是编译期错误。

表格列名用 `field<T>('exit_code')` 而不是裸字符串——antd 的 `dataIndex`
声明成 `string`，不检查字段是否存在，字段改名后表格会安静地渲染成空列。

仓库的统一检查会重新生成并比对差异，所以前端类型不能悄悄和后端脱节。

## 页面对应的核心闭环

Project 页面的四个标签页呈现当前迁移实现已有的本地 Mock 闭环：

```text
① 项目文件  →  ② 版本  →  ③ 运行方案  →  ④ Run 历史
```

Run 页面提供状态、日志、执行事件、Artifact 和复现快照。
Run 未结束时每 2 秒轮询一次：先触发后端状态同步，再读取 Run——
状态只能来自调度系统的轮询结果。

## 身份

后端 `auth_mode=dev` 时用 `X-User` 请求头识别身份，右上角的下拉框就是它的界面，
选择结果存在 localStorage。接入学校统一身份认证后，这个控件会被真正的登录态替换。

## 检查

```bash
pnpm run lint
pnpm run typecheck        # 同时也在检查前端调用与后端契约是否一致
pnpm run test --run
pnpm run build
pnpm run generate:api     # 仅重新生成类型；平时在根目录用 make contract
```

仓库根目录执行 `make check-frontend` 会跑与 CI 相同的前端检查。

## 关于展示内容

GPU 型号、分区、QoS、配额这些是会变的平台事实。界面上只展示后端返回的值，
不在前端硬编码，也不写成固定结论。
