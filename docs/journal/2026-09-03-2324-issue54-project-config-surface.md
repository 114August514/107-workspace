# issue54-project-config-surface

- 状态：进行中
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
浏览器证据：`docs/evidence/issue-54/`（设置 tab 桌面与 375px、键盘
焦点、Secret 密码输入模态）。

## 禁区
- 不重复实现 #37 的后端 scope / Secret Provider（契约已就绪，纯前端）
- 不重复实现 #44 的 Input Binding 编辑器（引用摘要只读展示）
- 不实现 Secret 明文回读、前端缓存或错误信息泄露明文
- 同名 Variable 解析结果由后端确认，前端不模拟

## 决策记录
- 2026-09-03：面板放「设置」tab 是对 #86 目标 IA（Files/Runs/Activity/
  Settings）的预对齐——其 settings 视图是显式占位符，本工作的面板组件
  直接迁入即可。
