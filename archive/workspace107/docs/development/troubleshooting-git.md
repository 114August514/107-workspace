# Git 常见问题处理

## 一. 撤销尚未暂存的修改

```bash
git restore path/to/file
```

## 二. 把文件移出暂存区（保留修改）

```bash
git restore --staged path/to/file
```

## 三. 最近一次 Commit 尚未推送

修改提交信息：

```bash
git commit --amend
```

把遗漏文件加入最近一次提交：

```bash
git add <文件>
git commit --amend --no-edit
```

## 四. Commit 已经推送到共享分支

**不要**使用：

```bash
git reset --hard
git push --force
```

应创建一个反向提交：

```bash
git revert <commit-id>
git push
```

`git revert` 不删除历史，而是增加一个用于撤销旧修改的新 Commit，更适合共享仓库。

## 五. 合并冲突

```bash
git status                  # 列出冲突文件
# 手动编辑，删除 <<<<<<< ======= >>>>>>> 标记
git add <已解决的文件>
git commit
```

想放弃这次合并：

```bash
git merge --abort
```

不要盲目复制网上的命令。先用 `git status` 弄清楚当前处在什么状态。

## 六. 不小心提交了密钥

正确顺序是：

```text
1. 立即撤销或轮换密钥
2. 通知仓库维护者
3. 清理 Git 历史
4. 检查 CI 日志、Release 和缓存中是否仍有泄露
```

**第一步永远是轮换密钥**，而不是先研究怎么改 Git 历史。
仅删除文件或重新 Commit 不够——密钥仍然存在于历史中，
任何 clone 过仓库的人都拿得到。

历史清理会重写提交，由维护者统一处理，普通开发者不要自行执行。

## 七. 不小心把大文件提交进了普通 Git

文件只存在于当前尚未合并的开发分支时，可以重新暂存：

```bash
git lfs track "docs/demo/*.mp4"
git add .gitattributes
git rm --cached docs/demo/demo.mp4
git add docs/demo/demo.mp4
git lfs ls-files
git diff --staged
```

如果大文件已经进入共享提交历史，需要 `git lfs migrate` 或其他历史清理工具，
该操作会重写历史，交由维护者处理。

在此之前先问一句：这个文件真的需要版本管理吗？
数据集、模型 checkpoint 和 Run 产物应存入算力平台存储，而不是仓库。

## 八. 本地 main 和远程分叉了

```bash
git pull --ff-only origin main
```

报错说明本地 `main` 上有远程没有的提交——通常是不小心直接在 `main` 上开发了。
把这些提交救到新分支上：

```bash
git checkout -b feat/123-补救分支
git checkout main
git reset --hard origin/main    # 确认 main 上没有要保留的东西之后再执行
```

`git reset --hard` 会丢弃工作区修改，执行前务必确认已经把要保留的内容
放到了别的分支上。不确定就先问维护者。

## 九. 找回「弄丢」的提交

```bash
git reflog
```

它记录了 HEAD 的移动历史。找到目标 commit 后：

```bash
git checkout -b rescue <commit-id>
```

大多数「提交丢了」的情况都能靠 reflog 找回，先别慌。
