# 整理仓库文档与本地参考目录

- 状态：已完成
- 认领：August / Codex
- 上下文：repository documentation topology
- 开始：2026-08-01 02:43 +0800
- 结束：2026-08-01 02:59 +0800

## 意图

减少仓库根目录噪声，区分活动规范、外部参考和历史过程材料；移除不构成运行时依赖的
本地 `hpc-helper` checkout，同时留下可复核的来源与吸收范围。

## 预期改动

- 将活动设计、Git 协作规范、延后事项和部署说明归入 `docs/` 的稳定分类。
- 将已经结束的后端重建资料与完成 journal 移入 `docs/archive/`。
- 记录 `hpc-helper` 上游、固定提交和非依赖关系，不归档无许可证源码。
- 更新活动引用、Doctor、文档引用测试与 GitHub 协作模板。
- 内联 `stack.mk` 的薄变量定义并删除该单独文件。

## 仓外副作用

- 删除根目录下被忽略的干净 `hpc-helper/` 独立 checkout；可从记录的上游提交恢复。
- 不 push，不修改远程分支或 tag。

## 回退方式

已提交变化使用 `git revert <commit>`；本地 `hpc-helper` 使用来源记录中的固定提交重新
clone/checkout。

## 验收

- `make check`
- `make doctor`
- 活动 Markdown 链接检查
- `git diff --check`

## 禁区

- 不改产品规则和实现行为。
- 不修改历史源码快照内容。
- 不归档第三方无许可证源码或 `.git/` 历史。
- 不新增依赖。

## 结果

- 根目录被跟踪文件由 14 个收敛为 10 个；活动长文档进入 `docs/` 的稳定分类。
- 旧后端规格、计划、审阅和已失效参考从 HEAD 淘汰，由 `374aa9f` 与历史索引取回。
- 完成/放弃的迁移 journal 进入对应归档，活动 journal 只保留进行中工作与说明。
- `hpc-helper/` 在确认工作区干净且与固定上游提交一致后删除；来源和吸收边界已记录。
- 本地 `IDEA.md`、`PLAN.md`、`myself.md`、`todo.md` 移入被忽略的 `.local/notes/`。
- `make doctor` 通过，仅提示可选 hooks 尚未启用。
- `make check` 通过：工作流 10 项、后端 270 项、前端 61 项，以及格式、lint、类型、
  构建和 API Contract 全部通过。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次文档整理未处理该既有性能事项。
