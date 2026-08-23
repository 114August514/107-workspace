# issue-37-config-scopes

- 状态：待复审
- 分支：`refactor/37-config-scopes`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-37`
- Reviewed code HEAD: `af9a012678f24046391f86d1badaa16b5c6ad02a1`
- PR #60 open/non-draft；no push this journal step；primary 未触碰。

## 当前真相
- User/UserGroup/Project scoped Variable/Secret、exact SecretReference、Project-first/owner/user resolver、snapshot freeze、current Secret execution/rerun、Fork expression isolation、显式 CRUD 与 #58 Asset Ownership/#56 AppShell 同步均保留。
- f37 是开发环境的 destructive structural schema cutover：创建 current scoped tables/redaction table，删除 legacy Workspace config tables；现有开发数据库需要 reset。不存在 legacy Workspace data/Snapshot/backfill compatibility 或历史数据恢复承诺。
- 新 Run 在执行前 retain 注入 Secret 值用于历史日志脱敏；submitted 且含 Secret refs 但缺 retention 时，read_logs fail closed；未提交 Run 不触发该 invariant。
- #67 is synchronized on main; Viewer was removed per main-authoritative roles/UI/tests. Scoped config authorization retains Owner/Admin/Member semantics unchanged; #36 OwnerReference seam and #38 entitlement overlap remain coordination boundaries.

## 证据
- `make check`：Backend **256 passed / 4 skipped**；Frontend **116 passed**；format/lint/typecheck/build/workflow/API contract pass。
- `make smoke`：合并后的 exact-owner default Environment 隔离 HTTP Core Run pass。
- PostgreSQL current-schema structural roundtrip pass；merged asset/config targeted tests **21 passed**；independent reviews PASS。

## 回滚
使用 `git revert <commit>`；不使用 stash/reset/clean/force push。
