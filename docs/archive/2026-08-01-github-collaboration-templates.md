# 整理 GitHub 协作入口与手动发布流程

- 状态：已完成
- 认领：August / Codex
- 上下文：GitHub Issue、Pull Request 与 Release 工作流整理
- 开始：2026-08-01 09:05 +0800
- 结束：2026-08-01 09:44 +0800

## 意图

让 `.github/` 的 Issue、Pull Request 和 Release 入口与
`docs/contributing/git-workflow.md` 保持一致，并在默认分支迁移期间继续兼容
`main` 与 `master`。

## 预期改动

- 将 Issue 入口拆成缺陷、功能请求和工程任务三类，并统一覆盖五项核心责任。
- 将 Pull Request 模板收敛为固定信息与按需检查项。
- 将镜像发布改为维护者手动触发，并显式选择源码引用、版本和 `latest` 标签。
- 同步贡献入口与 Git 协作指南中的模板、标签、验证、分支过渡和发布说明。

## 仓外副作用

无。不 push，不修改 GitHub 默认分支、标签、规则集或仓库设置。

## 回退方式

git revert <commit>

## 验收

- `.github/` YAML 语法检查与格式检查
- `make doctor`
- `make check`

## 禁区

- 不重命名远端 `master`，不取消 CI 的双分支兼容。
- 不发布镜像、不创建或移动 Tag。
- 不新增依赖，不修改产品行为。

## 结果

- 新增独立工程任务表单；缺陷、功能与工程任务均要求背景、目标、范围、验收条件和
  非目标，缺陷表单另收集复现、环境与影响。
- Pull Request 模板保留关联 Issue、修改内容、验证证据、影响范围和按需界面截图，
  API、迁移、权限、Secret 等检查只在实际涉及时保留。
- Release 改为手动触发，只接受与版本匹配的 annotated Tag；工作流先验证输入，再将
  Tag 固定为 Commit SHA，预发布版本不能更新 `latest`，build metadata 被明确拒绝。
- Git 指南记录三类标签、手动发布顺序与 `master` 到 `main` 的过渡状态；根贡献入口
  改为引用 GitHub 当前默认分支。
- YAML、Issue Form 核心字段、Release Bash 语法与 SemVer 边界检查通过；`.github`
  全部通过 Prettier。
- `make doctor` 通过，确认 Node 24.18.0 与 pnpm 11.18.0；仅提示可选 hooks 未启用。
- `make check` 通过：workflow 10 项、后端 270 项、前端 61 项，以及 lint、格式、类型、
  构建和 API Contract 全部通过。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次协作配置整理未处理该既有性能事项。
- 未实际触发 Release、发布镜像或核对远端 `type: bug`、`type: feature`、`type: task`
  标签；这些操作留给仓库侧手动执行。
