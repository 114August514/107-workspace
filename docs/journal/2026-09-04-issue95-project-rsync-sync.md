# issue95-project-rsync-sync

- 状态：本地实现与真实 SSH/rsync 传输已验证；待在共享存储部署上完成 API apply 闭环
- 写入边界：`/home/august/Projects/ustc_107/107-workspace-95`
- 分支：`feat/95-project-rsync-sync`
- 起始底座：`main` `3755e345de353754911f1343ee305265d680983a`
- 关联：Issue #95；Related #47、#20、#79

## 意图与完成边界

提供 `107 project sync <local-directory> <project>`，用真实 `rsync + SSH` 把本地目录增量
传入受控暂存区，再经现有 Project capability、路径 namespace、CAS 与 Working State 语义
apply。默认不删除 Project 中仅远端存在的文件，也不自动创建 Project Version。

## 冻结决策

- API 签发按 Project 与发起 User 隔离的稳定暂存 key；CLI 不接受远端路径参数。稳定目录让
  rsync 的 quick check 与 partial 文件可在重复执行时复用。
- rsync 对暂存区使用 `--delete --delete-excluded`，清理本地已删除或新近忽略的旧暂存内容；
  apply 只创建或覆盖 Working State 路径，不把该镜像删除语义扩散到 Project。
- `.107ignore` 由 `pathspec` 按 gitignore-style 规则求出 exact 忽略文件；`.git/`、`.venv/`、
  `node_modules/`、`__pycache__/` 与常见构建目录始终默认排除。
- apply 前一次性校验权限、规范路径、保留名、单文件大小、file/directory namespace、符号链接
  与特殊文件；内容未变化时不 upsert、不 touch Project。
- 暂存区不新增数据库 session/token 模型。授权事实仍由每次 prepare/apply 的现有 Project
  capability 决定，文件传输继续由 SSH 身份与部署目录权限负责。

## 验证证据

- 定向：`uv run pytest tests/integration/test_project_sync.py tests/unit/test_cli.py -q`，
  `4 passed`。覆盖稳定暂存 key、权限复核、Working State 不删除额外文件、重复 apply 为零变化、
  Version 不自动创建、`.107ignore`、默认排除、保留名/符号链接拒绝和真实本机 rsync 两轮增量。
- 完整：候选实现首次 `make check` 通过。workflow `15 tests`；后端 `355 passed, 3 skipped`；
  前端 `28 files / 185 tests`；格式、lint、typecheck、production build 与 API contract 均通过。
  SSH 实测后仅调整 rsync itemized 测试兼容 `<f`/`>f` 并补本文；其后的两次压力复跑中，
  同两个未修改的前端异步用例偶发在默认等待/超时边界失败。两个测试文件及 4.1 秒的临界用例
  分别独立复跑均通过；最终后端全量、前端格式/lint/typecheck/build 与 API contract 仍全部通过。
- CLI：`uv run 107 project sync --help` 可用；首次真实 rsync 的 CLI 进度输出包含扫描文件数、
  百分比、吞吐和 ETA。
- 真实 SSH：通过现有 `ustc-cluster` SSH alias 连接 Linux x86_64，远端 rsync `3.2.7`。
  在两端独立 `/tmp` 目录执行首次同步后，`.107ignore`、`change.txt`、`stable.txt` 到达远端，
  `ignored.tmp` 未出现。少量修改后的第二轮 itemized 输出只包含
  `<f.st...... change.txt` 与 `<f+++++++++ final-new.txt`，未包含稳定文件 `stable.txt`。
  本地与远端五个有效文件的 SHA-256 完全一致；测试目录随后已在两端清理。

## 尚缺证据

- 当前开发机没有 SSH daemon，本地 API 的 `storage_root` 也没有挂载为 `ustc-cluster` 可见的
  同一共享目录。因此上述真实 SSH 证据只闭合 transport；本地 API 集成测试闭合 apply，二者
  尚未在同一真实部署中串成一次完整 `107 project sync`。
- Ready 前需要在一个 API 与 SSH 入口共享 `project-sync` 物理目录的部署上配置
  `WORKSPACE107_PROJECT_SYNC_SSH_TARGET` / `WORKSPACE107_PROJECT_SYNC_REMOTE_ROOT`，执行首次同步、
  少量修改后的第二次同步，并从 Project API 核对 Working Changes 与 Version 数量。
