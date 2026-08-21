# issue-37-config-scopes

- 状态：待复审
- 认领：August / Codex
- 分支：`refactor/37-config-scopes`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-37`
- Exact published HEAD: `68869657569136d3896656ec052e7694b76ee636`; remote `origin/refactor/37-config-scopes` matches.
- Issue #37；PR #60 `https://github.com/114August514/107-workspace/pull/60` is open, non-draft, base `main`; primary worktree 未触碰。

## 当前完成范围
- User/UserGroup/Project scoped Variable/Secret、严格 scope repository/vault、显式 CRUD/API、Project-first/owner/user resolver、typed exact SecretReference、snapshot freeze、execution/rerun current Secret、no-fallback failure、log redaction、Fork expression isolation。
- Per-run `run_secret_redactions` retention boundary：SecretVault retains injected values by digest before execution side effects; historical logs use retention first and bounded legacy fallback. Values never enter Snapshot/API/UI.
- Workspace Variable/Secret public routes and LegacyWorkspaceService config methods removed. Seed, smoke task, frontend RunConfiguration availability and client consumers use explicit Project/UserGroup scope routes. Unrelated Workspace compatibility remains for #36–#42.
- Alembic f37 migration covers scoped config, Snapshot JSON exact refs, redaction table/FK, deterministic legacy mapping and refusal safety; PostgreSQL job runs existing identity test then scoped config test.

## 最终证据
- Exact published HEAD `68869657569136d3896656ec052e7694b76ee636` `make check` PASS: backend Ruff lint/format; backend **238 passed, 4 skipped**; frontend format/lint/typecheck; frontend **68 passed**; frontend build; API contract sync/check.
- `make smoke` PASS: isolated HTTP core Run completed with Project-scoped seed path.
- Targeted #37 suite: 107 passed; migration suite: 7 passed; focused Fork/execution/rerun and historical-redaction tests passed.
- PostgreSQL 17 fresh Docker evidence: scoped test **2 passed, 0 skipped**; JSON object/exact refs, scoped rows, redaction PK/FK cascade, downgrade/re-upgrade and refusal preservation verified. Container `workspace107-pg17-37` removed; post-cleanup container listing empty.
- Independent targeted re-reviews: PASS. No live 107 activity.

## Known boundaries
- PostgreSQL evidence is fixture-scoped and separate from the standard local SQLite `make check`; PR is published but not merged.
- Private #36 ownership contract and active #38/#39 overlap remain coordination risks; their worktrees were not modified.

## Rollback
Use `git revert <commit>` per exact commit; no stash/reset/clean used.
