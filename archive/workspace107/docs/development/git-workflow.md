# Git 工作流

本文是完整的命令参考。快速上手看 [`CONTRIBUTING.md`](../../CONTRIBUTING.md)。

## 一. 分支模型

只保留一个长期分支 `main`。

> `main` 始终代表：
>
> - 可以正常安装
> - 可以通过测试
> - 可以启动基本服务
> - 不会泄露敏感信息

所有开发工作都在短期分支上完成，命名为 `<类型>/<Issue编号>-<简短描述>`：

```text
feat/123-create-workspace
fix/207-run-status-sync
refactor/231-slurm-adapter
docs/256-git-workflow
test/278-workspace-service
chore/301-update-ci
```

禁止使用 `zxb_branch`、`backend-new`、`zxb_final`、`临时分支` 这类命名，
也不要让每个人永久维护一个个人分支——长期个人分支非常容易与 `main` 严重分叉。

## 二. 创建分支

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/123-create-workspace
```

其中 `--ff-only` 表示只允许本地 `main` 沿着远程提交历史直接向前移动；
如果本地和远程已经分叉就停止，不自动生成合并提交。

## 三. 开发中查看状态

```bash
git status           # 当前分支、修改文件和暂存文件
git diff             # 尚未暂存的具体修改
git diff --staged    # 已 git add、准备下次 commit 的修改
```

`git status` 是最重要的命令。遇到不确定的情况先执行它。

## 四. 暂存与提交

```bash
git add backend/src/workspace107/application/workspace_service.py
git add backend/tests/unit/test_workspace_service.py
git diff --staged
git commit -m "feat(workspace): 支持创建协作空间"
```

需要逐块检查时用 `git add -p`。不建议每次直接 `git add .`，
它容易把日志、临时文件、密钥或无关修改一起加入提交。

## 五. 推送

```bash
git push -u origin feat/123-create-workspace   # 第一次
git push                                        # 之后
```

## 六. 同步最新 main

开发过程中 `main` 发生变化时：

```bash
git status
git checkout main
git pull --ff-only origin main
git checkout feat/123-create-workspace
git merge main
```

没有冲突就直接 `git push`。

出现冲突时先 `git status` 看冲突文件，打开后会看到：

```text
<<<<<<< HEAD
开发分支中的内容
=======
main 中的内容
>>>>>>> main
```

手动决定保留什么、删除标记，然后：

```bash
git add <已解决的文件>
git commit
git push
```

想取消这次合并：

```bash
git merge --abort
```

本项目目前统一使用 `merge` 处理同步。理解 `rebase` 影响之后也可以使用，
但不要在已推送的共享分支上 rebase。

## 七. 合并后清理

仓库配置为**仅允许 Squash merging**，并在合并 PR 后自动删除远程分支。
GitHub 删除的是远程分支，本地仍需手动清理：

```bash
git checkout main
git pull --ff-only origin main
git branch -D feat/123-create-workspace
git fetch --prune
```

## 八. 版本发布

阶段性成果完成后，由维护者从最新 `main` 打 Tag：

```bash
git checkout main
git pull --ff-only origin main
git tag -a v0.1.0 -m "完成核心运行闭环"
git push origin v0.1.0
```

然后在 GitHub 创建 Release，写明本版本目标、主要功能、不兼容变化、
已知问题、部署方式和对应 Milestone。

Tag 创建后不移动、不覆盖。发现问题时发布新版本。

## 九. 日常八条命令

```bash
git status
git diff
git checkout
git pull
git add
git commit
git push
git log --oneline
```

查看提交图：

```bash
git log --oneline --graph --decorate --all
```

## 十. 危险命令

在未理解影响前，禁止自行使用：

```bash
git reset --hard
git clean -fd
git push --force
```

确实需要覆盖远程历史时，优先考虑 `git push --force-with-lease`，
并先与维护者确认。
