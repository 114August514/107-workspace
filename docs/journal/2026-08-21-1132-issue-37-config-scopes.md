# issue-37-config-scopes

- 状态：待复审
- 认领：August / Codex
- 分支：`refactor/37-config-scopes`
- Worktree：`/home/august/Projects/ustc_107/107-workspace-37`
- Reviewed code/evidence HEAD: `e9d3e07ff60ac0652a128abc87ea402b6bd80397`.
- PR #60 `https://github.com/114August514/107-workspace/pull/60` is open, non-draft, base `main`; publication journal commit follows; primary worktree 未触碰。

## 当前完成范围
- User/UserGroup/Project scoped Variable/Secret、严格 scope repository/vault、显式 CRUD/API、Project-first/owner/user resolver、typed exact SecretReference、snapshot freeze、execution/rerun current Secret、no-fallback failure、log redaction、Fork expression isolation。
- Per-run `run_secret_redactions` retention boundary：SecretVault retains injected values by digest before execution side effects; historical logs use retention first and bounded legacy fallback. Values never enter Snapshot/API/UI.
- Workspace Variable/Secret public routes and LegacyWorkspaceService config methods removed. Seed, smoke task, frontend RunConfiguration availability and client consumers use explicit Project/UserGroup scope routes. Unrelated Workspace compatibility remains for #36–#42.
- Alembic f37 migration covers scoped config, Snapshot JSON exact refs, redaction table/FK, deterministic legacy mapping and refusal safety; PostgreSQL job runs existing identity test then scoped config test.

## 最终证据
- Reviewed code/evidence HEAD `e9d3e07ff60ac0652a128abc87ea402b6bd80397` `make check` PASS: backend Ruff lint/format; backend **241 passed, 4 skipped**; frontend **60 passed** with format/lint/typecheck/build; workflow/API contract pass。
- `make smoke` PASS: isolated HTTP core Run completed with Project-scoped seed path.
- Targeted #37 suite: 107 passed; migration suite: 7 passed; focused Fork/execution/rerun and historical-redaction tests passed.
- PostgreSQL 17 fresh Docker evidence: scoped test **2 passed, 0 skipped**; JSON object/exact refs, scoped rows, redaction PK/FK cascade, downgrade/re-upgrade and refusal preservation verified. Container `workspace107-pg17-37` removed; post-cleanup container listing empty.
- Independent targeted re-reviews: PASS (both); no live 107 activity。

## Known boundaries
- PostgreSQL evidence is fixture-scoped and separate from the standard local SQLite `make check`; PR is published but not merged.
- Private #36 ownership contract and active #38/#39 overlap remain coordination risks; their worktrees were not modified.

## Rollback
Use `git revert <commit>` per exact commit; no stash/reset/clean used.

## Review remediation evidence
- `3805a99` restored rerun concurrency/plan checks, fixed submit-failure notification `run_id`, removed stale frontend scope-availability heuristic, and added name-pattern validation.
- `ec28a46` added real rerun-limit and scheduler-submit-failure regressions and removed dead unresolved helper/test files.
- Remediation commits `3805a99`, `ec28a46`, `5a40e40` and backfill commits `118ad9b`, `ecf2966`, `3276153`, `e9d3e07` record the reviewed behavior; independent targeted re-reviews PASS。

## Historical redaction backfill
- f37 backfills only submitted Runs with legacy Secret `updated_at <= submitted_at`; it deduplicates `(run_id, sha256(value))` and skips empty, missing, malformed, later-rotated, or unsubmitted refs without guessing.
- SQLite migration fixture proves duplicate TOKEN dedupe, digest/value retention, LATE/MISSING skip, unsubmitted Run skip, plaintext-free Snapshot, and downgrade/re-upgrade safety.
- PostgreSQL 17 fresh evidence: `test_scoped_config_postgres.py` 2 passed/0 skipped; JSON object/exact refs, scoped rows, redaction schema, refusal preservation verified; container cleanup confirmed.
- Frontend wrappers were already absent; `resolve_env` and Workspace semantics are removed. Pre-migration rotations cannot be reconstructed.

## Final historical backfill evidence
- Reviewed code HEAD: `e9d3e07ff60ac0652a128abc87ea402b6bd80397` (backfill implementation `118ad9b`, SQLite cutoff fixture `e9d3e07`, PostgreSQL fixture `3276153`).
- Final targeted migration/domain set: 101 passed, 2 PostgreSQL URL-absent skips; SQLite migration suite 7 passed; frontend 60 tests/typecheck/format/lint/build pass; contract check and `make smoke` pass.
- Final `make check`: backend **241 passed/4 skipped**; all backend/frontend/workflow/API contract checks pass. Historical limitation: pre-migration Secret rotations/deletions without timestamp-provable current values cannot be reconstructed.
- PostgreSQL 17 fresh evidence remains 2 passed/0 skipped with container cleanup verified.

## Main merge / cutoff follow-up
- Merged `origin/main` at `e35043b4d3831db41444df0560939c0cb93a7f92`; main-authoritative #58 asset-owner and #56 AppShell/Home/Primer changes were retained, while scoped config/exact Secret behavior remained.
- Reparented f37 directly after `c471ac39f002`; Alembic has one head. Generated contracts were regenerated canonically after conflict resolution.
- Historical backfill cutoff is conservative: submitted Run required and `legacy Secret updated_at <= run.created_at`; the in-window `created_at < updated_at <= submitted_at` case is skipped. Pre-migration lost rotations cannot be reconstructed.
