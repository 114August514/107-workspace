# issue54-project-config-surface

- 状态：已完成
- 认领：Chongan Wang
- 上下文：未指定
- 开始：2026-09-03 23:24 +0800

## 意图
完成 GitHub Issue #54：Project Variable / Secret 管理表面与运行配置
引用能力。Variable/Secret 面板做成自包含组件（props 只接 projectId 与
access），当前挂在 ProjectPage 新「设置」tab；PR #86（Project IA）合并后
迁移到其 settings 路由，只需替换占位符。

## 预期改动
- `frontend/src/api/client.ts`（variable/secret upsert/delete 方法）
- `frontend/src/components/project/*`（Variables / Secrets 自包含面板）
- `frontend/src/pages/ProjectPage.tsx`（新增「设置」tab 挂载面板）
- `frontend/src/components/runconfig/*`（user.* 引用提示、引用摘要、
  设为默认运行方案动作）
- component tests

## 仓外副作用
无。

## 回退方式
git revert <commit>

## 验收
`workspace.py check` 全链路；component tests 覆盖权限空态与 Secret
不回显明文；浏览器证据（桌面 / 375px / 键盘）。
浏览器证据：`docs/evidence/issue-54/`（Variables / Secrets 桌面清单、
新建 Variable 弹窗、替换 Secret 弹窗、删除确认、375px、键盘焦点）。

## 禁区
- 不重复实现 #37 的后端 scope / Secret Provider（契约已就绪，纯前端）
- 不重复实现 #44 的 Input Binding 编辑器（引用摘要只读展示）
- 不实现 Secret 明文回读、前端缓存或错误信息泄露明文
- 同名 Variable 解析结果由后端确认，前端不模拟

## 决策记录
- 2026-09-03：面板放「设置」tab 是对 #86 目标 IA（Files/Runs/Activity/
  Settings）的预对齐——其 settings 视图是显式占位符，本工作的面板组件
  直接迁入即可。
- 2026-09-04：设计评审四轮后定稿——分区切换用 Primer SegmentedControl
  （同 #94 RunSummary / RunLogPanel 的运行结果 Tab），清单用 #94
  FileBrowser 的表格式样（无外框、muted 分隔线、body-small 字号、
  固定列宽保证值的显隐不移动「最近更新」列），并增加「最近更新」列。
  为此后端把 Variable.updated_at 落库（迁移 b3d8e2a64c19：SQLite 不能
  直接加 NOT NULL 列，走 加列 → 回填 → 收紧），Secret 经 vault 暴露
  只含名称与更新时间的元数据列表（明文仍不出 vault，SecretOut 无值
  字段）。契约同步重导出。
- 2026-09-04：面板从 antd 重写为 Primer（SegmentedControl / Dialog /
  FormControl / RelativeTime / IconButton / ConfirmationDialog），与
  #94 的设计语言一致；删除确认用 ConfirmationDialog（注意 v38 没有
  open 受控 prop，必须条件挂载，否则一挂载就弹空框）。预览页
  /design/project-settings 完成使命后删除。
- 2026-09-04：窄屏（≤544px）操作列两枚图标按钮放不下，媒体查询把
  操作列放宽到 28% 并收紧 actions 单元格内边距；覆盖规则必须放在
  .td 简写之后才生效。
