# 第十章：Git 与团队协作

本章只保留本项目日常开发主路径。完整 Git 教程、LFS 和故障恢复说明见
[`../../contributing/git-workflow.md`](../../contributing/git-workflow.md)。

## 10.1 Git 和 GitHub 的分工

Git 在本地记录文件版本、分支和 Commit；GitHub 保存远程仓库，并提供 Issue、Pull Request、
Review 和 CI。一次改动通常经过：

```text
工作区 → git add → 暂存区 → git commit → 本地历史
      → git push → GitHub 分支 → Pull Request → 评审和 CI → 合并
```

## 10.2 项目开发流程

```text
Issue
→ Journal（跨会话或并行工作）
→ 开发分支
→ 测试先失败
→ 实现
→ make check
→ Commit 和 Push
→ Pull Request
→ Review 与 CI
→ 合并
```

Issue 至少写清背景、目标、范围、验收条件和非目标。跨会话、多人并行或有仓外副作用的工作还要
建立 `docs/journal/` 记录，使中断后能够恢复。

## 10.3 创建分支

先确认工作区没有意外修改，再从共享主分支创建短期分支。主分支实际名称以远程仓库设置和当前
协作文档为准；以下以 `main` 为例：

```bash
git status
git checkout main
git pull --ff-only origin main
git checkout -b feat/123-show-run-exit-code
```

分支格式为 `<类型>/<Issue编号>-<简短描述>`。常用类型包括 `feat`、`fix`、`refactor`、`test`、
`docs` 和 `chore`。一个分支解决一个主要问题，不维护长期个人分支。

## 10.4 经常查看差异

```bash
git status
git diff
git diff --staged
```

只暂存准备提交的文件：

```bash
git add path/to/file
```

或逐块选择：

```bash
git add -p
```

不要习惯性 `git add .`。它可能加入无关改动、日志、运行结果或敏感文件。已有未提交改动可能
来自其他协作者，不能为了让工作区“干净”而擅自覆盖或删除。

## 10.5 Commit 和 Pull Request

Commit 使用：

```text
<类型>(<范围>): <一句话说明>
```

例如：

```bash
git commit -m "feat(web): 展示 Run 退出码"
git push -u origin feat/123-show-run-exit-code
```

Pull Request 应说明关联 Issue、修改内容、实际验证证据、影响范围和故意没有处理的内容。界面
改动附截图；调度改动明确使用的是 Mock 还是真实集群。不要用“应该通过”代替实际命令结果。

实现、对应测试、必要文档和契约更新可以在一个 PR 中，但无关重构、依赖升级和格式化不应混入。

## 10.6 Review 关注什么

评审不只是看代码风格，建议按风险顺序检查：

1. 行为是否满足 Issue 和产品规则；
2. 是否存在跨 Workspace 越权；
3. Snapshot、Version 和 Secret 边界是否被破坏；
4. 错误、并发、取消和重试路径是否合理；
5. 数据库、API 契约和前端是否同步；
6. 测试是否验证真实结果；
7. 代码是否放在正确层并容易维护。

## 10.7 同步与冲突

开发期间主分支有更新时，可以按协作规范合并最新主分支。冲突出现后，先用 `git status` 查看
文件，理解两边意图，再编辑冲突标记并测试。不能确定时应请求原作者协助，不要只选择“ours”
或“theirs”让冲突消失。

合并完成后更新本地主分支并清理已经合并的开发分支。仓库使用何种合并方式以 GitHub 设置和
协作规范为准。

## 10.8 撤销和 Secret 泄露

共享历史中的错误通常使用：

```bash
git revert <commit-id>
```

不要对共享分支使用 `git reset --hard` 或强制推送。尚未推送的个人 Commit 可以按完整 Git
指南处理，但操作前仍要确认不会丢失工作区内容。

误提交密钥时，删除文件再提交并不足够，因为旧 Commit 仍包含密钥。正确顺序是：

1. 立即撤销或轮换密钥；
2. 通知维护者；
3. 按维护者方案清理历史；
4. 检查 CI 日志、Release 和缓存中的副本。

`.env`、Slurm JWT、Token、SSH 私钥、用户数据、Run 输出和数据库 Dump 都不能进入仓库。

