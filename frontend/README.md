# 前端

107 Workspace 控制台。React + TypeScript + Vite；目标组件系统使用 Primer React、
Primer Primitives、Primer Octicons 与 CSS Modules。当前 Ant Design 界面是迁移期间的
旧实现，不是新页面继续扩展的默认方案。
工具链统一使用 Node.js 24 LTS 与 pnpm 11；版本约束同时记录在 `.node-version`、
`package.json` 和 CI 中。

## 运行

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

打开 <http://127.0.0.1:5174>。开发服务器把 `/api` 转发到 `http://127.0.0.1:8000`，
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
├── pages/              HomePage / UserGroupPage / ProjectPage / RunPage
└── utils/format.ts     展示格式化

tests/
└── unit/               当前保留的 API 错误降级与引用解析单元测试
```

页面只做编排，数据获取和交互细节都在组件里。跨页面复用的展示逻辑
（状态标签、加载与错误处理、时长与容量格式化）只定义一次。

## 组件系统与迁移边界

目标前端技术选型以 [`docs/product/design.md`](../docs/product/design.md) 为准。
Primer 迁移由 [GitHub Issue #16](https://github.com/114August514/107-workspace/issues/16)
统一跟踪，但迁移进度不改变产品设计或 API 契约。
用户可见术语、状态反馈和操作文案统一遵循
[`docs/product/ui-copy.md`](../docs/product/ui-copy.md)，页面不得自行定义竞争规则。

迁移遵守以下边界：

1. 按完整用户表面迁移，不按 Button、Tag、Modal 等组件类别横切全仓；
2. 迁移期间允许未迁移页面继续使用 Ant Design，但同一个已迁移表面不得混用两套组件；
3. 已迁移文件不得继续导入 `antd` 或 `@ant-design/icons`；
4. 新增页面默认使用 Primer；只在真实切片出现复用需求时提取公共组件；
5. 视觉迁移不顺便修改领域术语、API、权限判断或状态管理架构；
6. 最后一个清理切片删除 Ant Design Provider、主题、专属 helper 和直接依赖，不保留兼容别名。

### 样式与组件

- 颜色、间距、圆角和字体优先使用 Primer Primitives，不在项目里复制一套 GitHub 色值；
- 107 Workspace 特有的高密度文件、版本、Run、日志和 Artifact 布局使用 CSS Modules；
- 页面不通过行内样式堆叠长期视觉规则，也不使用组件库私有 class；
- 可交互组件必须覆盖 `default`、`hover`、`active`、`focus`、`disabled`、`loading`、
  `selected` 和 `error` 中适用的状态；
- 网络数据必须区分加载、成功但为空、成功有数据和失败，空态和错误态都提供下一步操作；
- 语义元素、关联表单标签、可见键盘焦点和正文对比度是最低可访问性要求。

迁移基础切片应提供 `/design-system` 页面，展示实际采用的 token、组件状态、数据四态和
常用文案。该页面是可运行的实现参考，不替代产品设计。

### UI 验证

UI 改动除类型检查和生产构建外，还必须在真实浏览器中检查：

- 桌面宽度和 375 px 窄屏；
- 键盘完成主要交互且焦点可见；
- 加载、空数据和请求失败；
- 发生变更的表单、浮层或下载等关键交互。

PR 提供与改动范围相称的关键状态截图。组件测试断言用户可观察行为，不绑定 Primer 或
Ant Design 的私有 DOM 和 class。

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

仍未迁移的 Ant Design 表格列名使用 `field<T>('exit_code')` 而不是裸字符串：
其 `dataIndex` 声明成 `string`，字段改名后可能安静地渲染成空列。最终删除
Ant Design 时同时复核并清理这个专属 helper。

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

当前 Ant Design UI 是后续迁移的旧实现，因此不保留绑定组件库私有 class 或视觉偏好的
测试。新组件和页面切片进入实现时，按 [`../docs/testing/README.md`](../docs/testing/README.md)
定义的 unit、component、feature 和 e2e 粒度保护用户可观察行为。

## 关于展示内容

GPU 型号、分区、QoS、配额这些是会变的平台事实。界面上只展示后端返回的值，
不在前端硬编码，也不写成固定结论。
