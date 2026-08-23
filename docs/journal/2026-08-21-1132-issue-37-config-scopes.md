# issue-37-config-scopes

- 状态：待复审
- 分支：`refactor/37-config-scopes`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-37`
- Reviewed code HEAD: `565492253622b2e63ca66534ca1d2f5870140110`
- PR #60 open/non-draft；未 push 本次 journal；primary 未触碰。

## 当前真相
- User/UserGroup/Project scoped Variable/Secret、exact SecretReference、Project-first/owner/user resolver、snapshot freeze、current Secret execution/rerun、Fork expression isolation、显式 CRUD 与 #58 Asset Ownership/#56 AppShell 同步均保留。
- f37 是开发环境的 destructive structural schema cutover：创建 current scoped tables/redaction table，删除 legacy Workspace config tables；现有开发数据库需要 reset。不存在 legacy Workspace data/Snapshot/backfill compatibility 或历史数据恢复承诺。
- 新 Run 在执行前 retain 注入 Secret 值用于历史日志脱敏；submitted 且含 Secret refs 但缺 retention 时，read_logs fail closed；未提交 Run 不触发该 invariant。
- #67 未合并，Viewer 语义保持不变；#36 OwnerReference seam 与 #38 entitlement overlap 仍是协调边界。

## 证据
- `make check`：Backend **250 passed / 3 skipped**；Frontend **116 passed**；format/lint/typecheck/build/workflow/API contract pass。
- `make smoke`：合并后的 exact-owner default Environment 隔离 HTTP Core Run pass。
- PostgreSQL current-schema structural roundtrip pass；merged asset/config targeted tests pass；independent reviews PASS。

## 回滚
使用 `git revert <commit>`；不使用 stash/reset/clean/force push。
