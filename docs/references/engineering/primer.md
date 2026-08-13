# Primer 来源与吸收边界

本文件记录 107 Workspace 采用 Primer 时核验过的官方来源和吸收边界，不是产品或实现规范。
产品技术选型以 [`docs/product/design.md`](../../product/design.md) 为准，前端实施规则见
[`frontend/README.md`](../../../frontend/README.md)。

- 核验日期：2026-08-13
- 上游维护者：GitHub / Primer
- 许可证：下列三个 npm 包的核验版本均声明为 MIT

## 官方来源

| 能力 | 官方来源 | 核验时 npm `latest` |
| :--- | :--- | :--- |
| React 组件与 ThemeProvider | [Primer React 入门](https://primer.style/product/getting-started/react/)、[`primer/react`](https://github.com/primer/react) | `@primer/react@38.35.1` |
| 颜色、间距、字体与主题变量 | [`primer/primitives`](https://github.com/primer/primitives) | `@primer/primitives@11.10.0` |
| React 图标 | [Primer Octicons](https://primer.style/octicons)、[`primer/octicons`](https://github.com/primer/octicons) | `@primer/octicons-react@19.33.0` |

版本号只记录本次核验事实。实际安装版本和完整性由 `frontend/package.json` 与
`pnpm-lock.yaml` 决定，不从本文推断。

`@primer/react@38.35.1` 的 npm 元数据显示其 React、React DOM 及对应类型 peer dependency
支持 18.x 或 19.x；这覆盖本仓库当前 React 19。Primer 官方入门要求应用根部使用
`ThemeProvider` 与 `BaseStyles`，并导入所需的 Primitives 主题 CSS。

## 吸收边界

采用：

- Primer React 的稳定基础组件和主题入口；
- Primer Primitives 提供的语义化颜色、间距、圆角、字体和亮暗主题变量；
- Primer Octicons 中与操作含义一致的图标；
- Primer 的 GitHub 风格信息层级、边框分区和高密度数据展示模式。

不自动采用：

- GitHub 品牌、商标、站点文案或与 107 Workspace 无关的产品导航；
- 未经真实切片证明需要的 experimental / deprecated 组件；
- 完整 `@primer/css` 全局样式；官方说明它是可选能力，只有确认不会扩大现有页面的全局样式影响后才引入；
- Primer 对业务对象的命名或权限假设；Workspace、User Group、Project、Run 等语义只来自当前产品设计和 API 契约；
- 为每个 Primer 组件再建立一层无业务价值的通用 wrapper。

107 Workspace 特有的文件、版本、Run、日志和 Artifact 布局使用 CSS Modules 实现，
但不得复制一套与 Primer Primitives 竞争的基础 token。源码直接导入的 Primer 包应声明为
项目直接依赖，不能只依赖其他包的传递安装结果。
