# issue-37-config-scopes

- 状态：待复审
- 分支：`refactor/37-config-scopes`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-37`
- Reviewed synchronized code HEAD: `7a328aad78e034ccd095f3ee5b69a17935acdb68`
- PR #60 open, non-draft, base `main`; no push in this journal step; primary untouched。

## 交付与同步
- User/UserGroup/Project scoped Variable/Secret、exact SecretReference、Project-first/owner/user resolver、snapshot freeze、current Secret execution/rerun、historical redaction retention、Fork expression isolation and explicit CRUD are implemented。
- Merged main `e35043b4d3831db41444df0560939c0cb93a7f92`; retained #58 Asset Ownership and #56 AppShell/Home/Primer. f37 directly follows `c471ac39f002`; Alembic has one head。
- Workspace Variable/Secret API and controlled consumers were removed; generated OpenAPI/frontend types were regenerated canonically。

## Migration safety
- Historical redaction backfill requires submitted Run and legacy Secret `updated_at <= Run.created_at`; duplicate values use `(run_id, sha256(value))` and missing, empty, malformed, later-updated, or unsubmitted refs are skipped without guessing。
- The cross-dialect regression `created_at < updated_at <= submitted_at` is skipped. Pre-migration lost rotations/deletions cannot be reconstructed。
- PostgreSQL 17 evidence: 2 passed/0 skipped; JSON, scoped rows, redaction PK/FK cascade, downgrade/re-upgrade and refusal preservation verified; container cleaned。

## 最终证据
- `make check` pass: backend suite green, frontend **116 tests**, format/lint/typecheck/build, workflow and API contract pass。
- `make smoke` pass with merged exact-owner default Environment。
- Targeted asset/config/migration/run tests pass；independent targeted reviews PASS。
- #36 OwnerReference seam remains upstream coordination; #38 entitlement overlap remains coordination risk. No live 107 activity。

## Rollback
Use `git revert <commit>`; no stash/reset/clean/force push。
