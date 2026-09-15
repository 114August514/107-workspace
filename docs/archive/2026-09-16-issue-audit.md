# 多仓库任务审计结果

日期：2026-09-16。范围：清理旧任务、组件归属、遗漏实现切片和文档事实对齐。
审计基线：索引 13b96bc、后端 7131295、前端 f4329b3。
本次没有补做产品实现、执行真实集群操作或把远期设计提升为近期承诺。

## 已转移的 6 项任务

| 原索引仓库 Issue | 当前归属 | 结果 |
|---|---|---|
| #16 | [frontend #1](https://github.com/114August514/107-frontend/issues/1) | Primer 总迁移；修正已完成切片和过期依赖 |
| #20 | [frontend #2](https://github.com/114August514/107-frontend/issues/2) | Project/Version 仍含 Ant Design，继续 open |
| #22 | [frontend #3](https://github.com/114August514/107-frontend/issues/3) | 最终删除依赖与旧主题，继续 open |
| #79 | [frontend #4](https://github.com/114August514/107-frontend/issues/4) | 预览已有部分实现，统一 Markdown/语言覆盖及验收仍未完整 |
| #95 | [backend #1](https://github.com/114August514/107-backend/issues/1) | CLI 已实现；收窄为 rsync 与 API apply 的同部署真实验收 |
| #96 | [backend #2](https://github.com/114August514/107-backend/issues/2) | 尚缺资源上传 CLI 到 publication 闭环 |

转移保留原讨论，正文中的历史 Issue/PR 已改为跨仓明确引用。

## 新补的 6 个具体任务

前四项是已有跨仓总任务缺少的可执行拆分，后两项是设计与实现间的具体遗漏。

| 任务 | 现有证据与范围 |
|---|---|
| [backend #4：Git Version](https://github.com/114August514/107-backend/issues/4) | 当前 Version 仍为文件 manifest，缺正式 Git commit/tree 身份；归总任务 #7 |
| [backend #5：独立 Worker/Shared FS](https://github.com/114August514/107-backend/issues/5) | 当前 Run 生命周期仍由 API 驱动；归总任务 #7，与模块化母题 #3 分工 |
| [backend #6：Terminal 会话](https://github.com/114August514/107-backend/issues/6) | PTY、用户执行身份、Project 文件与权限边界；归总任务 #97 |
| [frontend #6：Terminal 面板](https://github.com/114August514/107-frontend/issues/6) | xterm、连接状态、焦点/尺寸和真实后端联调；归总任务 #97 |
| [frontend #7：组级配置入口](https://github.com/114August514/107-frontend/issues/7) | 组级 Variable/Secret API 已有，但缺管理 UI；先协调现行设置入口决定 |
| [workspace #128：组默认环境](https://github.com/114August514/107-workspace/issues/128) | design.md §2.5 B 有 Core 要求，但模型仅有 Project 默认环境；先收敛默认值规则 |

已有 [backend #3](https://github.com/114August514/107-backend/issues/3) 和
[frontend #5](https://github.com/114August514/107-frontend/issues/5) 保持原范围，不重复创建。

## 关闭与保留

- [通知 #50](https://github.com/114August514/107-workspace/issues/50) 按已实现 Core 范围关闭：读/未读、偏好、mandatory、Run/成员/资产/调度异常通知具备实现和测试。平台公告后台、邮件和生产验收不在关闭声明内。
- [#7](https://github.com/114August514/107-workspace/issues/7) 保留整体真实执行验收；旧候选通过不代表当前 main 已有 Worker/Git/Shared FS。
- [#52](https://github.com/114August514/107-workspace/issues/52) 保留指定演示环境、持久化重启、排障与 runbook 复现验收。
- [#97](https://github.com/114August514/107-workspace/issues/97) 保留 Terminal 的跨仓真实用户流程验收。
- [PR #77](https://github.com/114August514/107-workspace/pull/77) 保留分支与证据，转为 Draft；后续按 backend #4/#5 适配，不直接把旧 monorepo 分支合入索引仓库。

## 索引和治理

- [Core 索引 #43](https://github.com/114August514/107-workspace/issues/43) 区分已交付、仍待实现、已选 V1 与工程母题。
- [V1/Optional 索引 #53](https://github.com/114August514/107-workspace/issues/53) 移出已实现认证、Admin 治理和资源发布等伪缺口，保留未选能力；不批量创建 V2/Future 任务。
- 新任务和相关迁移任务建立原生父子关系，组件任务使用统一功能/工程类型标签；未设置未经选择的期限或 Milestone。
- 修正 design.md 的旧 Monorepo 目录及 M0 描述、契约文档索引和跨仓文档测试归属。

## 最新验证与限制

- 后端现有通知/API/配置执行/环境发布/同步定向测试：23 passed。
- 前端 NotificationBell/FileViewer/ReadmePanel：17 passed，其中通知 13 项。
- 跨仓文档引用检查：4 passed。
- 原主分支完整 CI 的证据来自迁移 PR #127；本次产品源码没有变化。
- 本次未进行新的浏览器视觉验收、真实 SSH/Slurm 或演示服务器操作；这些仍按各任务的剩余条件验收。
