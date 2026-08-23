# Git 与协作工作流

## 一. Git vs. Github

```text
Git
├── 在本地管理文件版本
├── commit、branch、merge、diff
└── 没有网络也能使用

GitHub
├── 保存远程 Git 仓库
├── Issue 管理任务
├── Pull Request 评审代码
├── Actions 自动运行测试
└── 管理团队权限和发布版本
```

可以把整个过程理解为：

```text
本地修改
   ↓ git add
暂存区
   ↓ git commit
本地仓库
   ↓ git push
GitHub 远程仓库
   ↓ Pull Request
评审、测试、合并到默认分支
```

---

## 二. 从零开始的 Git 使用

### 2.1 配置 Git 身份

Git 会在每次 Commit 中记录提交者的姓名和邮箱。

首次使用 Git 时需执行：

```bash
git config --global user.name "你的名字"
git config --global user.email "你的 GitHub 邮箱"
```

> 若已有配置不正确，再次对同一个配置项执行命令，会覆盖原有配置。

查看全部全局配置

```bash
git config --global --list
```

查看配置来自哪个配置文件：

```bash
git config --show-origin --get user.name
git config --show-origin --get user.email
```

如需仅为当前仓库设置不同的提交身份，应进入仓库目录后执行：

```bash
git config user.name "你的名字"
git config user.email "你的邮箱"
```

没有 `--global` 的配置只对当前仓库生效，并且优先于全局配置。

### 2.2 克隆仓库

```bash
git clone <仓库地址>
cd 107-workspace
```

`git clone` 会完成以下操作：

```text
下载远程仓库中的代码和提交历史
创建本地仓库
自动添加名为 origin 的远程仓库
切换到远程仓库的默认分支
```

克隆完成后进行检查：

```bash
git status
git branch
git remote -v
```

其中：

```text
git status
查看当前仓库和工作区状态

git branch
查看本地分支，带 * 的是当前分支

git remote -v
查看已经配置的远程仓库名称及地址
```

### 2.3 修改或增加远程仓库

一般开发者克隆项目后，不需要修改远程仓库配置。只有在仓库迁移、使用 Fork 或配置镜像仓库时才需要以下操作。

#### 2.3.1 修改现有远程仓库地址

当仓库地址发生变化，但仍将主要远程仓库命名为 `origin` 时：

```bash
git remote set-url origin <新的仓库地址>
```

修改后检查：

```bash
git remote -v
```

#### 2.3.2 增加另一个远程仓库

需要同时连接多个远程仓库时：

```bash
git remote add upstream <另一个仓库地址>
```

例如在 Fork 工作流中：

```text
origin
自己的 Fork，拥有推送权限

upstream
项目的官方仓库，主要用于获取更新
```

查看所有远程仓库：

```bash
git remote -v
```

#### 2.3.3 其他远程仓库操作

修改远程仓库名称：

```bash
git remote rename <旧名称> <新名称>
```

删除本地记录的远程仓库：

```bash
git remote remove <远程仓库名称>
```

删除 Remote 只会删除当前本地仓库中的远程配置，不会删除 GitHub 上的真实仓库。

---

## 三. 分支模型

项目最终只保留一个长期分支 `main`。当前远程默认分支仍为 `master`；在 GitHub 默认
分支、保护规则和协作者设置完成迁移前，`master` 仍是共享主分支，本文命令中的
`main` 应替换为 `master`。

CI 暂时同时监听 `main` 和 `master`，只用于覆盖改名窗口，不表示并行维护两条主线。
迁移完成后应删除 `master` 监听和本段过渡说明。

无论主分支当前叫什么，它始终代表：

> 可以正常安装
> 可以通过测试
> 可以启动基本服务
> 不会泄露敏感信息

所有开发工作都在短期分支上完成。

### 3.1 分支命名

统一采用：

```text
<类型>/<Issue编号>-<简短描述>
```

以下是格式示例，不代表当前产品尚未实现对应能力：

```text
feat/123-create-workspace
feat/145-submit-run
fix/207-run-status-sync
refactor/231-slurm-adapter
docs/256-git-workflow
test/278-workspace-service
chore/301-update-ci
```

允许的类型：

| 类型 | 用途 |
| :----------: | :----------: |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 不改变行为的重构 |
| `test` | 测试 |
| `docs` | 文档 |
| `chore` | 工程配置、依赖、CI |

禁止使用：

```text
zxb_branch
backend-new
zxb_final
临时分支
```

也不要让每个人永久维护一个个人分支。长期个人分支非常容易与 `main` 严重分叉。

### 3.2 开发分支如何同步最新 main

标准开发流程见**第四节**，本节仅讲述在一个 Issue 开发过程中，如何应对 `main`
已经发生变化的同步问题。

开发分支需要获取最新 `main` 时，执行：

```bash
git status
git checkout main
git pull --ff-only origin main
git checkout feat/123-create-workspace
git merge main
```

含义：

```text
先更新本地 main
再切回开发分支
把最新 main 合并进开发分支
```

如果没有冲突，继续：

```bash
git push
```

如果出现冲突：

```bash
git status
```

Git 会列出冲突文件。打开文件后会看到：

```text
 <<<<<<< HEAD
开发分支中的内容
 =======
main 中的内容
 >>>>>>> main
```

手动决定保留什么，删除这些标记，然后执行：

```bash
git add <已解决的文件>
git commit
git push
```

尚未解决并希望取消本次合并时：

```bash
git merge --abort
```

如果会使用 `rebase` 处理的话，也可以考虑使用 `rebase`，此处暂时仅介绍 `merge`。

---

## 四. 标准开发流程

本项目采用以下路径：

```text
Issue
  ↓
创建分支
  ↓
本地开发
  ↓
Commit
  ↓
Push
  ↓
Pull Request
  ↓
Review + CI
  ↓
Squash Merge
  ↓
GitHub 删除远程开发分支
  ↓
本地切回并更新 main
  ↓
删除本地开发分支
```

### 4.1 领取 Issue

所有正式工作原则上先建立 Issue。

GitHub 已关闭空白 Issue。按工作性质选择最具体的入口：

| 模板     | 使用场景                               | 额外信息                             |
| -------- | -------------------------------------- | ------------------------------------ |
| 缺陷报告 | 已有行为不符合预期                     | 复现步骤、期望与实际行为、环境、影响 |
| 功能请求 | 新增或改变用户可观察的能力             | 产品设计、原型或依赖 Issue（如有）   |
| 工程任务 | 重构、测试、文档、CI、依赖维护或技术债 | 任务类型、风险与回退（如有）         |

无论选择哪种入口，Issue 都至少写清楚：

```text
背景
目标
范围
验收条件
非目标（不做什么）
```

这三类问题要分清去向：

- **普通缺陷**：已有行为不符合预期，是需要修复的 Bug。用缺陷 Issue 跟踪，不写入 `docs/product/deferred.md`。
- **尚未决定接受的技术债**：发现实现不理想，但还没决定是否在比赛阶段保留。同样只开 Issue 调查或安排修复，不写入登记。
- **明确决定暂时保留的实现妥协**：团队知道当前实现未达到目标设计，但为优先交付功能决定暂不修。例如比赛阶段用开发身份代替 CAS 接入、用 Mock Scheduler 代替真实集群。这类妥协必须登记到 [`../product/deferred.md`](../product/deferred.md)，写清风险、适用范围和退出条件，并在引入该妥协的 PR 中填写登记 ID。

例如：

```markdown
## 背景

Workspace Owner 目前无法在平台内邀请协作者，只能由维护者直接修改数据。

## 目标

支持 Owner 在 Collaborative Workspace 中邀请成员。

## 范围

- 邀请已有平台用户加入 Workspace
- 提供邀请入口、接口和活动记录

## 验收条件

- Owner 可以填写用户名发送邀请
- 已存在的成员不能重复邀请
- 非 Owner 返回 403
- 邀请操作写入活动记录

## 非目标

- 邮件通知
- 批量邀请
- 自定义角色
```

一个 Issue 尽量控制在半天到三天内完成。过大的任务应拆成多个 Issue。

### 4.2 从最新 main 创建分支

所有开发任务应该在分支进行，创建分支方式如下：

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/123-create-workspace
```

含义：

```text
git checkout <分支名>
切换到对应分支

git pull --ff-only origin main
从 GitHub 获取最新的 main，并更新本地 main。
只允许本地 main 沿着远程提交历史直接向前移动；
如果本地和远程已经出现分叉，则停止，不自动生成合并提交。

git checkout -b <新分支名>
创建并切换到新分支
```

禁止直接在 `main` 上开发，确保 `main` 上代码的稳定性。

### 4.3 开发前后查看状态

在分支开发过程中，可以执行以下命令查看分支状态：

```bash
git status
git diff
```

其中：

```text
git status
查看当前分支、修改文件和暂存文件

git diff
查看尚未暂存的具体修改

git diff --staged
查看已经执行过 git add，准备下一次 commit 的具体修改内容
```

`git status` 是最重要的 Git 命令。遇到不确定情况时，可以先执行该命令。

---

### 4.4 只暂存准备提交的文件

推荐：

```bash
git add backend/src/workspace107/application/workspace_service.py
git add backend/tests/unit/domain/test_compute.py
```

或者逐块检查：

```bash
git add -p
```

不建议每次都直接：

```bash
git add .
```

因为它容易把日志、临时文件、密钥或无关修改一起加入提交。

随后确认：

```bash
git diff --staged
```

### 4.5 提交

```bash
git commit -m "feat(workspace): 支持创建协作空间"
```

提交格式统一为：

```text
<类型>(<范围>): <一句话说明>
```

推荐范围：

```text
workspace
project
run
storage
slurm
resource
auth
api
web
cli
docs
ci
```

示例：

```text
feat(workspace): 支持邀请空间成员
fix(run): 修复取消作业后状态未更新
refactor(slurm): 提取统一命令执行接口
test(project): 补充项目归档服务测试
docs: 补充本地开发环境说明
chore(ci): 增加后端 Ruff 检查
```

不要写：

```text
update
修改一下
fix bug
final
提交代码
完成工作
```

一个 Commit 应只表达一个逻辑变化。实现一个功能、完成一次独立重构、补充一组对应测试，都适合各自形成 Commit。

### 4.6 推送分支

第一次推送：

```bash
git push -u origin feat/123-create-workspace
```

后续继续推送只需：

```bash
git push
```

---

### 4.7 创建 Pull Request

PR 标题也采用相同格式：

```text
feat(workspace): 支持创建协作空间
```

PR 描述保留模板中的固定信息，并填写实际证据。以下内容继续使用上面的虚构场景：

```markdown
## 关联 Issue

Closes #123

## 修改内容

- 新增 Workspace 创建接口
- 新增名称和所有者校验
- 新增 service 单元测试

## 验证证据

- `make check`：通过
- 手动调用 `POST /api/v1/workspaces`：返回 201，响应不包含 Secret 明文

## 影响范围

- 数据库新增 workspace 表
- 新增 API endpoint
- 前端暂未接入

## 延后事项与实现妥协

- Deferred ID：无

## 截图（仅界面改动）

<关键状态截图>
```

验证证据写出实际命令、环境和关键结果，不需要粘贴整段日志。涉及集群行为时注明使用
`mock` 还是真实集群；未执行的验证必须明确说明。截图只在界面发生变化时提供。

“延后事项与实现妥协”固定保留。没有有意代码妥协时填写“无”；存在妥协时，必须先在
[`../product/deferred.md`](../product/deferred.md) 登记，并在合并前填写对应 ID。普通
缺陷和未接受的技术债只关联 Issue，不使用登记 ID。

模板末尾的按需检查项只保留本 PR 实际涉及的 API 契约、数据库迁移、认证授权、
Secret 或界面证据，并在验证完成后勾选；没有适用项时删除该小节。

### 4.8 评审并合并 PR

建议只使用如下方式进行合并：

```text
Squash and merge
```

在一个 PR 合并后，`main` 中就只会形成一个提交：

```text
feat(workspace): 支持创建协作空间 (#123)
```

这样允许协作者在开发分支中出现若干类似：

```text
补测试
修复 lint
调整命名
处理 review
```

的中间提交，但不会污染主分支历史。

GitHub 仓库已配置：

```text
仅允许 Squash merging
合并 PR 后自动删除远程开发分支
```

> 注意：
>
> GitHub 自动删除的是远程开发分支，本地开发分支仍需开发者手动清理。

### 4.9 同步 main 并删除本地开发分支

确认 PR 已经成功合并后，在本地执行：

```bash
git checkout main
git pull --ff-only origin main
git branch -D feat/123-create-workspace
git fetch --prune
```

含义：

```text
git checkout main
离开已经完成的开发分支，切换回 main

git pull --ff-only origin main
获取包含刚才 PR 的最新 main

git branch -D feat/123-create-workspace
删除已经完成的本地开发分支

git fetch --prune
清除本地保存的、远程已经删除的分支引用
```

---

## 五. Git LFS 与文件存储策略

Git 仓库主要用于保存源代码、配置、文档和少量测试资源，不应被当作用户文件存储、数据集仓库或运行结果仓库。

### 5.1 文件存储决策

| 文件类型 | 存放位置 |
| :--- | :--- |
| 源代码、配置模板、文档、小型测试数据 | 普通 Git |
| 必须随项目版本管理的大型二进制资源 | Git LFS |
| 用户文件、原始数据集、训练数据 | 算力平台存储 |
| 模型 checkpoint、作业日志、运行结果 | 算力平台存储 |
| 可发布的软件包、镜像等制品 | 制品仓库或容器镜像仓库 |
| 密钥、Token、密码 | 本地环境变量或密钥管理系统 |
| 构建产物、缓存、依赖目录、虚拟环境 | 不保存，写入 `.gitignore` |

107 Workspace 中的用户文件、训练数据、模型 checkpoint 和 Run 产物，默认都不应进入 Git 仓库或 Git LFS。

> 实际上跑实验的设备都可被认为是算力平台？

### 5.2 Git LFS 的适用范围

Git LFS，即 Git Large File Storage，用于管理必须跟随仓库版本进行追踪的大型二进制文件。

使用 Git LFS 后：

```text
普通 Git 仓库
保存体积较小的 LFS 指针文件

Git LFS 存储
保存真实的二进制文件内容
```

适合使用 Git LFS 的文件包括：

```text
比赛演示所需的视频
必须随版本发布的二进制资源
较大的设计源文件
无法通过脚本重新生成、且确实需要版本管理的测试资源
```

不应使用 Git LFS 保存：

```text
用户上传文件
原始数据集
训练数据
模型 checkpoint
每次 Run 的输出
运行日志
数据库备份
依赖目录
构建产物
```

这些文件应存入 `/public` 等算力平台存储、对象存储或制品存储，而不是 GitHub。

> Git LFS 仍然属于版本控制系统的一部分，也可能受到托管平台的存储量和流量限制，因此不能将其当作通用的大文件存储服务。

### 5.3 安装和使用 Git LFS

#### 5.3.1 初始化 Git LFS

每位需要处理 LFS 文件的开发者，都需要先在自己的开发环境中安装 Git LFS。

安装完成后执行：

```bash
git lfs install
```

该命令通常只需要在一台开发环境中执行一次。

确认是否安装成功：

```bash
git lfs version
```

#### 5.3.2 指定需要由 LFS 管理的文件

例如，只将 `docs/demo/` 目录下的 MP4 演示视频交给 Git LFS 管理：

```bash
git lfs track "docs/demo/*.mp4"
```

该命令会创建或修改仓库根目录下的：

```text
.gitattributes
```

其中会生成类似规则：

```gitattributes
docs/demo/*.mp4 filter=lfs diff=lfs merge=lfs -text
```

这表示：

> 当文件路径匹配 `docs/demo/*.mp4`，并执行 `git add` 时，Git 会自动通过 Git LFS 管理该文件。

随后提交 `.gitattributes` 和对应文件：

```bash
git add .gitattributes
git add docs/demo/demo.mp4
git diff --staged
git commit -m "docs(demo): 添加产品演示视频"
```

`.gitattributes` 必须提交到仓库，否则其他成员无法获得相同的 LFS 规则。

---

#### 5.3.3 查看和拉取 LFS 文件

查看当前配置的 LFS 跟踪规则：

```bash
git lfs track
```

查看仓库中已经由 LFS 管理的文件：

```bash
git lfs ls-files
```

拉取当前版本所需的真实 LFS 文件：

```bash
git lfs pull
```

正常情况下，使用支持 Git LFS 的环境执行 `git clone` 或 `git pull` 时，会自动下载相应的 LFS 文件。文件未正确下载时，可以手动执行 `git lfs pull`。

### 5.4 `.gitattributes`

`.gitattributes` 用于定义 Git 应如何处理不同路径下的文件，包括：

```text
Git LFS 跟踪规则
文本文件的换行符
二进制文件识别
diff 和 merge 行为
```

它和 `.gitignore` 的职责不同：

```text
.gitignore
决定哪些未跟踪文件不应加入 Git

.gitattributes
决定已经由 Git 管理的文件应如何处理
```

例如，项目可以使用以下基础配置：

```gitattributes
# 自动识别文本文件，并在仓库中统一使用 LF 换行符
* text=auto eol=lf

# 明确常用文本文件
*.sh text eol=lf
*.py text eol=lf
*.toml text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.json text eol=lf
*.md text eol=lf

# 常见二进制文件
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.pdf binary

# 仅对指定目录中的演示视频启用 Git LFS
docs/demo/*.mp4 filter=lfs diff=lfs merge=lfs -text
```

统一使用 LF 换行符可以减少 Windows、WSL 和 Linux 环境之间的换行差异，并避免 Shell 脚本在 Linux 环境中因 CRLF 换行而无法执行。

检查某个文件实际匹配到的属性：

```bash
git check-attr -a -- path/to/file
```

### 5.5 注意事项

1. 应先配置 LFS 规则，再执行 `git add`：

   ```bash
   git lfs track "docs/demo/*.mp4"
   git add .gitattributes
   git add docs/demo/demo.mp4
   ```

2. `git lfs track` 只负责修改 `.gitattributes`，不会自动把文件加入暂存区，也不会自动创建 Commit。

3. `.gitattributes` 必须提交到仓库，并和对应的 LFS 文件放在同一个 Pull Request 中。

4. 不要因为某种扩展名可能产生大文件，就在整个仓库范围内盲目启用 LFS。

   例如不建议：

   ```bash
   git lfs track "*.pt"
   git lfs track "*.ckpt"
   ```

   这会使仓库中所有匹配的训练产物都进入 Git LFS。

   107 Workspace 中的模型 checkpoint 默认应保存在算力平台存储中，而不是 Git LFS。

5. 更推荐使用限定目录的规则：

   ```bash
   git lfs track "docs/demo/*.mp4"
   git lfs track "tests/fixtures/binary/*.zip"
   ```

6. `git lfs track` 不会自动迁移已经以普通 Git 方式提交的大文件。

   如果文件只存在于当前尚未合并的开发分支，可以重新暂存：

   ```bash
   git rm --cached docs/demo/demo.mp4
   git add docs/demo/demo.mp4
   ```

   然后检查：

   ```bash
   git lfs ls-files
   git diff --staged
   ```

7. 如果大文件已经进入共享提交历史，则可能需要使用 `git lfs migrate` 或其他历史清理工具。该操作会重写 Git 历史，不应由普通开发者自行执行，应交由仓库维护者统一处理。

8. 新增或修改 LFS 跟踪规则应经过 Pull Request 评审。

9. 删除工作区中的大文件前，应先确认它是否是可以重新获取的 LFS 文件、平台存储文件，或唯一存在的本地文件。

---

## 六. GitHub 上如何管理项目

### 6.1 Issue 是任务的唯一来源

不要同时在聊天记录、口头讨论、笔记软件和 GitHub 中各维护一份任务。

最终决定落实为：

```text
要实现的功能 → Issue
发现的 Bug → Issue
需要讨论的重构 → Issue
文档缺失 → Issue
```

聊天可以讨论，但讨论结果应回写 Issue。

### 6.2 Milestone 用以确定阶段性成果

#### 6.2.1 Milestone 不能只是一组 Issue

错误的 Milestone：

```text
MVP
├── 文件管理
├── 项目管理
├── 作业管理
├── 用户管理
└── 权限管理
```

这只是功能分类，没有说明做到什么程度，也很难判断是否完成。

更好的 Milestone 应有四项内容：

```text
目标
范围
不包含什么
完成标准
```

Milestone 的产品范围和名称以 [`../product/design.md`](../product/design.md) 的 Roadmap
为准，不在 Git 指南中维护另一套阶段定义。

#### 6.2.2 每个 Milestone 建议固定一个描述模板

```markdown
# <阶段编号> - <可验收结果>

## 目标

说明这个阶段最终让用户完成什么。

## 用户结果

用用户可观察的结果描述价值。

## 范围

- <本阶段包含的能力>

## 非目标

- <明确延后的能力>

## 完成标准

- [ ] <可重复验证的用户结果>
- [ ] 统一检查通过
- [ ] 文档与实际状态一致
```

其中“非目标”非常重要。它能够防止开发过程中不断把别的能力顺手塞进当前阶段。

#### 6.2.3 如何用 Milestone 确认方向

每次准备开始一个 Milestone 时，只需要做一次短评审：

1. 这个阶段最终要让用户完成什么？
2. 是否形成完整闭环？
3. 哪些能力明确不做？
4. 是否与产品能力图冲突？
5. 完成后是否能被实际演示和验收？

过程中遇到新想法时，不立即加入当前 Milestone，而是判断：

```text
属于当前目标且不做会阻断闭环
→ 加入当前 Milestone

重要，但不阻断当前闭环
→ 放入后续 Milestone 或 Backlog

改变了领域边界或产品定位
→ 先更新产品能力图并进行设计评审
```

### 6.3 标签说明

推荐三组标签。

类型：

```text
type: feature
type: bug
type: task
```

三类 Issue 表单会申请对应的类型标签；仓库维护者需要预先创建这些标签。工程任务的
具体性质在表单中选择，不再为重构、测试、文档和调研各维护一组互斥类型标签。

模块：

```text
area: workspace
area: project
area: run
area: storage
area: resource
area: entitlement
area: profile
area: identity
area: platform
area: frontend
area: infrastructure
```

优先级：

```text
priority: P0 - 阻塞级
priority: P1 - 应在当前实现
priority: P2 - 可以延后
```

模块和优先级标签由维护者在 Issue triage 时补充，Issue 表单中的普通字段不会自动
转换成 GitHub 标签。

阶段名称和顺序从产品设计的 Roadmap 建立到 GitHub Milestone，不在这里硬编码副本。

### 6.4 版本发布和 Tag

在完成阶段性成果后，应由维护者从最新 `main` 创建 **Tag** :

```bash
git checkout main
git pull --ff-only origin main
git tag -a v0.1.0 -m "完成核心运行闭环"
git push origin v0.1.0
```

推送 Tag 本身不会发布镜像。确认 Tag 与 CI 后，在 GitHub Actions 中手动运行
`Release` workflow：

```text
source_ref: v0.1.0
version: 0.1.0（不带 v，不使用 +build metadata）
publish_latest: 仅稳定版本按需选择
```

`source_ref` 必须是与 `version` 匹配的 `v<SemVer>` annotated Tag。工作流显式检出
`refs/tags/<source_ref>` 并解析为不可变提交，再为 API 与 Web 构建并发布带版本号的
GHCR 镜像；只有显式选择时才更新 `latest`，预发布版本不能更新 `latest`。为避免不同
版本折叠到同一个 OCI Tag，发布版本不接受 SemVer build metadata。工作流不会创建或
移动 Tag，也不会代替 GitHub Release notes。

镜像发布成功后，在 GitHub 创建 Release，填写：

```text
本版本目标
主要功能
不兼容变化
已知问题
部署方式
对应 Milestone
```

Tag 创建后原则上不移动、不覆盖。发现问题时发布新版本，而不是修改已有 Tag。

---

## 七. PR 规模与评审规范

### 7.1 一个 PR 只解决一个主要问题

可以包含：

```text
实现
对应测试
必要文档
API Contract 更新
```

但不要混合：

```text
新功能 + 无关目录重构 + 依赖大升级 + 全项目格式化
```

建议普通 PR 控制在大约 300～500 行人工修改以内。

生成的 OpenAPI 文件或 lock 文件可以单独说明，不计入主要评审规模。

### 7.2 评审检查顺序

Reviewer 按以下顺序检查：

```text
1. 是否真正满足 Issue 的验收条件
2. 是否破坏现有行为
3. 模块边界是否正确
4. 是否有必要测试
5. 权限和输入校验是否完整
6. 是否泄露密钥或用户数据
7. 命名和可读性是否合理
```

不应在 Review 中只讨论格式，而忽略业务正确性。

### 7.3 Draft PR

任务尚未完成，但希望提前同步设计或接口时，直接创建 Draft Pull Request。不要等所有代码写完才让其他成员第一次看到。

---

## 八. 针对 107 Workspace 的 CI

共享主分支的本地与 CI 统一入口是：

```bash
make check
```

支持 Linux 开发环境；Windows 主机上的开发必须使用 WSL2 的 Linux toolchain，并将
仓库放在 WSL2 的 Linux filesystem。原生 Windows / PowerShell runtime 不受支持。

统一检查至少覆盖：

```text
workflow lint / tests
backend lint / format / tests
frontend format / lint / typecheck / tests / build
OpenAPI 与前端类型契约
```

接口发生变化时：

```text
后端修改 DTO/Route
        ↓
重新生成 openapi.json
        ↓
重新生成前端 API 类型
        ↓
CI 检查生成文件是否存在未提交差异
```

CI 还单独验证数据库 migration 的升级、回退和再升级、PostgreSQL 行为，以及 Compose
构建与 HTTP smoke。不要在 workflow 中复制另一套检查命令；新的质量门应先进入
`scripts/workspace.py`，再由本地与 CI 共同调用。

---

## 九. 撤销、恢复与密钥泄露处理

### 9.1 最近一次 Commit 尚未推送

修改提交信息：

```bash
git commit --amend
```

把遗漏文件加入最近一次提交：

```bash
git add <文件>
git commit --amend --no-edit
```

### 9.2 Commit 已经推送到共享分支

不要使用：

```bash
git reset --hard
git push --force
```

应创建一个反向提交：

```bash
git revert <commit-id>
git push
```

`git revert` 不会删除历史，而是增加一个用于撤销旧修改的新 Commit，更适合共享仓库。

### 9.3 不小心提交了密钥

仅删除文件或重新 Commit 不够，因为密钥仍可能存在于 Git 历史中。

正确处理顺序：

```text
1. 立即撤销或轮换密钥
2. 通知仓库维护者
3. 清理 Git 历史
4. 检查 CI 日志、Release 和缓存中是否仍有泄露
```

第一步永远是轮换密钥，而不是先研究怎么改 Git 历史。

---

## 十. 常用命令说明

### 10.1 日常开发八条命令

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

### 10.2 安全撤销

撤销工作区中尚未暂存的修改：

```bash
git restore path/to/file
```

把文件移出暂存区，但保留修改：

```bash
git restore --staged path/to/file
```

修改最近一次 Commit 信息：

```bash
git commit --amend
```

查看提交图：

```bash
git log --oneline --graph --decorate --all
```

### 10.3 后续

```text
merge
rebase
stash
cherry-pick
reflog
bisect
```

在未理解影响前，禁止自行使用：

```bash
git reset --hard
git clean -fd
git push --force
```

确实需要覆盖远程历史时，也应先理解原因，并优先考虑：

```bash
git push --force-with-lease
```

---

## A1 附录

```text
1. 不在 main 上开发
2. 开始工作和提交前都执行 git status
3. 只 add 自己确认过的文件
4. 一个 PR 只解决一个主要问题
5. 遇到冲突先停下来理解，不盲目复制命令
```

### 应当提交的工程文件

通常应提交：

```text
uv.lock
前端包管理器 lock 文件
数据库迁移文件
.env.example
Dockerfile
Compose 编排文件
CI workflow
必要的 OpenAPI Contract
.gitattributes
.editorconfig
```

通常不提交：

```text
.venv/
node_modules/
dist/
build/
coverage/
.pytest_cache/
.mypy_cache/
.ruff_cache/
__pycache__/
```

同一种前端包管理器只保留一种锁文件。例如使用 `pnpm` 时提交：

```text
pnpm-lock.yaml
```

不要同时保留：

```text
package-lock.json
yarn.lock
pnpm-lock.yaml
```

### 绝对不能提交的内容

107 Workspace 会接触 Slurm、用户文件和运行结果，因此 `.gitignore` 和密钥纪律必须严格。

禁止提交：

```text
.env
.env.local
真实数据库密码
SLURM_JWT
GitHub Token
SSH 私钥
校园认证 Cookie
用户上传文件
用户数据集
模型权重
checkpoint
运行日志
Run 输出目录
数据库 dump
本地虚拟环境
缓存目录
IDE 临时文件
```

仓库中只放：

```text
.env.example
```

例如：

```dotenv
DATABASE_URL=
SLURM_API_BASE_URL=
SLURM_JWT=
```

只保留变量名和说明，不填写真实值。

培训材料明确指出，Slurm JWT 等价于密码，不应明文写入代码，更不能提交到 Git，应通过环境变量传入。

大型数据集和模型结果也不应通过普通 Git 保存。确实需要版本化的少量二进制资源可以后续评估 Git LFS，但 HPC 数据、模型 checkpoint 和 Run 产物应由平台存储系统管理。

**Issue 说明要做什么，分支隔离修改，Commit 记录过程，PR 完成评审，CI 保证基本质量，默认分支保存可信版本。**
