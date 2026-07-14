# Documentation Responsibilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move repository source materials into responsibility-based reference directories, repair navigation, and preserve both PDFs as unchanged Git LFS objects.

**Architecture:** Treat `docs/references/` as the home for informative design inputs and platform source material, grouped into product, engineering, and platform subjects. Keep reviews and accepted workflow records in their existing locations, and make authority explicit through focused indexes rather than rewriting source documents.

**Tech Stack:** Markdown, Git, Git LFS, POSIX shell utilities

**Source specification:** `docs/superpowers/specs/2026-07-14-document-responsibilities-design.md`

---

## File Map

- `docs/references/README.md`: reference navigation and normative-status rules.
- `docs/references/product/107-workspace-product-vision.md`: preserved product and domain input formerly stored as `foo.md`.
- `docs/references/engineering/initial-backend-bootstrap-guide.md`: preserved early initialization guidance formerly stored as `ref.md`.
- `docs/references/platform/README.md`: titles, roles, and usage caveats for platform source materials.
- `docs/references/platform/107-cluster-competition-training.pdf`: unchanged 59-page cluster training source.
- `docs/references/platform/computing-platform-track-introduction.pdf`: unchanged 8-page platform introduction source.
- `docs/references/platform/workspace-slurm-apptainer-context.md`: preserved explanation of product, scheduler, and runtime responsibilities.
- `.gitattributes`: exact-path Git LFS rules for the two new PDF paths.
- `README.md`: repository-level entry points.
- `docs/superpowers/specs/2026-07-13-workspace107-backend-design.md`: current links to the two design inputs.
- `docs/superpowers/plans/2026-07-13-workspace107-backend.md`: historical-path note without falsifying recorded commands.
- `docs/reviews/2026-07-14-backend-reinitialization/README.md`: platform reference entry point.
- `docs/reviews/2026-07-14-backend-reinitialization/01-change-phases.md`: links to the named design inputs.
- `docs/reviews/2026-07-14-backend-reinitialization/06-commit-index.md`: links to the named design inputs.

### Task 1: Classify And Move Reference Sources

**Files:**
- Create: `docs/references/README.md`
- Create: `docs/references/platform/README.md`
- Move: `foo.md` -> `docs/references/product/107-workspace-product-vision.md`
- Move: `ref.md` -> `docs/references/engineering/initial-backend-bootstrap-guide.md`
- Move: `docs/archive/2026-07-14-platform-materials/training-107-competition.pdf` -> `docs/references/platform/107-cluster-competition-training.pdf`
- Move: `docs/archive/2026-07-14-platform-materials/算力平台及算力平台赛道介绍.pdf` -> `docs/references/platform/computing-platform-track-introduction.pdf`
- Move: `docs/archive/2026-07-14-platform-materials/流程参考.md` -> `docs/references/platform/workspace-slurm-apptainer-context.md`
- Delete after migration: `docs/archive/2026-07-14-platform-materials/README.md`

- [x] **Step 1: Create the responsibility directories and move source files**

Run:

```bash
mkdir -p docs/references/product docs/references/engineering docs/references/platform
mv foo.md docs/references/product/107-workspace-product-vision.md
mv ref.md docs/references/engineering/initial-backend-bootstrap-guide.md
mv docs/archive/2026-07-14-platform-materials/training-107-competition.pdf docs/references/platform/107-cluster-competition-training.pdf
mv docs/archive/2026-07-14-platform-materials/算力平台及算力平台赛道介绍.pdf docs/references/platform/computing-platform-track-introduction.pdf
mv docs/archive/2026-07-14-platform-materials/流程参考.md docs/references/platform/workspace-slurm-apptainer-context.md
```

Expected: all five sources exist at their new paths; `foo.md` and `ref.md` no
longer exist at the repository root.

- [x] **Step 2: Write the top-level reference index**

Create `docs/references/README.md` with a short introduction that states:

```text
These files are informative source material, not current backend requirements.
Product inputs explain intended value and domain language. Engineering inputs
record early setup direction. Platform references document the environment on
which the product runs. Accepted specifications and current development guides
take precedence when sources disagree.
```

Link directly to the product vision, initialization guide, platform index,
accepted backend specification, implementation plan, backend guide, and backend
review package.

- [x] **Step 3: Write the platform source index**

Create `docs/references/platform/README.md` and list the exact source titles:

```text
中国科大“一〇七杯”算力与智能体开发大赛算力平台赛道培训
算力平台及算力平台赛道介绍
107 Workspace、Slurm 与 Apptainer 职责说明
```

For each item, state what question it helps answer. Mark both PDFs as original,
unchanged source files collected on 2026-07-14 and operational details as
time-sensitive rather than normative product behavior.

- [x] **Step 4: Remove the superseded archive index and inspect the tree**

Remove `docs/archive/2026-07-14-platform-materials/README.md`, then run:

```bash
find docs -maxdepth 4 -type f -print | sort
test ! -e foo.md
test ! -e ref.md
test ! -e docs/archive/2026-07-14-platform-materials
```

Expected: the target tree matches the specification and all three commands
checking old locations exit successfully.

### Task 2: Repair Navigation And Git LFS Rules

**Files:**
- Modify: `.gitattributes`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-13-workspace107-backend-design.md`
- Modify: `docs/superpowers/plans/2026-07-13-workspace107-backend.md`
- Modify: `docs/reviews/2026-07-14-backend-reinitialization/README.md`
- Modify: `docs/reviews/2026-07-14-backend-reinitialization/01-change-phases.md`
- Modify: `docs/reviews/2026-07-14-backend-reinitialization/06-commit-index.md`

- [x] **Step 1: Move the exact-path LFS attributes**

Replace `.gitattributes` with:

```gitattributes
docs/references/platform/107-cluster-competition-training.pdf filter=lfs diff=lfs merge=lfs -text
docs/references/platform/computing-platform-track-introduction.pdf filter=lfs diff=lfs merge=lfs -text
```

- [x] **Step 2: Update current navigation and design references**

Use these mappings in repository navigation, the accepted backend design, and
the review package:

```text
foo.md -> docs/references/product/107-workspace-product-vision.md
ref.md -> docs/references/engineering/initial-backend-bootstrap-guide.md
docs/archive/2026-07-14-platform-materials/README.md -> docs/references/platform/README.md
```

Use relative Markdown links from each containing document. Name the targets
"Product vision", "Initial backend bootstrap guide", and "Platform reference
materials" rather than the old generic labels.

- [x] **Step 3: Preserve and annotate historical command paths**

At the start of `docs/superpowers/plans/2026-07-13-workspace107-backend.md`, add
a historical-path note linking `ref.md` and `foo.md` to their new locations.
State that command blocks retain the paths that existed when the plan was
executed. Do not rewrite those command blocks, because that would make the
recorded repository-reset procedure inaccurate.

- [x] **Step 4: Scan for stale active references**

Run:

```bash
rg -n '\]\([^)]*archive/2026-07-14-platform-materials|\]\((?:\.\./)*foo\.md\)|\]\((?:\.\./)*ref\.md\)' . --glob '*.md'
```

Expected: no active Markdown links target the old locations. Plain-text old
paths may remain only in the migration mapping and the explicitly annotated
historical backend plan.

### Task 3: Verify And Commit The Reorganization

**Files:**
- Verify: all paths listed in Tasks 1 and 2

- [x] **Step 1: Verify all local Markdown links**

Run this Bash-compatible checker to extract relative inline link targets from
every tracked Markdown file, ignore external URLs and anchors, and resolve each
path relative to its containing file with `realpath -e`:

```bash
status=0
while IFS= read -r -d '' file; do
  [ -f "$file" ] || continue
  while IFS= read -r target; do
    case "$target" in
      http://*|https://*|mailto:*|'#'*) continue ;;
    esac
    target="${target%%#*}"
    if ! realpath -e "$(dirname "$file")/$target" >/dev/null; then
      printf '%s -> %s\n' "$file" "$target"
      status=1
    fi
  done < <(perl -ne 'while (/\[[^]]*\]\(([^ )#]+)(?:#[^) ]*)?(?:\s+"[^"]*")?\)/g) { print "$1\n" }' "$file")
done < <(git ls-files -co --exclude-standard -z -- '*.md')
exit "$status"
```

Expected: every checked local target exists and the checker exits zero.

- [x] **Step 2: Verify worktree PDF identity and LFS attributes**

Run:

```bash
git check-attr filter diff merge -- docs/references/platform/*.pdf
sha256sum docs/references/platform/*.pdf
wc -c docs/references/platform/*.pdf
```

Expected: both paths report `filter: lfs`, `diff: lfs`, and `merge: lfs`;
the content hashes are
`6cbdb7db2a3294746f9c1eca077f643edb20715eace85d2f7f74fa515f9c99eb`
and `d09a75c373809fa8b8bff3df55f291cbe29742e4df89aa32008464f7bc050d0a`;
the byte sizes are `1103398` and `276026`.

- [x] **Step 3: Verify scope and formatting**

Run:

```bash
git diff --check
git status --short
git diff --stat
git diff --name-status
```

Expected: only the planned documentation, `.gitattributes`, and navigation
paths changed. Git detects the source documents as moves where similarity
permits; no application source, test, generated file, or ignored local note is
included.

- [x] **Step 4: Stage and verify LFS pointers**

Stage only the planned paths and inspect both staged PDF blobs:

```bash
git add .gitattributes README.md foo.md ref.md \
  docs/archive/2026-07-14-platform-materials \
  docs/references \
  docs/reviews/2026-07-14-backend-reinitialization \
  docs/superpowers/specs/2026-07-13-workspace107-backend-design.md \
  docs/superpowers/plans/2026-07-13-workspace107-backend.md \
  docs/superpowers/plans/2026-07-14-document-responsibilities.md
git show :docs/references/platform/107-cluster-competition-training.pdf
git show :docs/references/platform/computing-platform-track-introduction.pdf
git lfs ls-files --long
git lfs fsck
```

Expected: each staged blob is a three-line Git LFS pointer with version URL,
the expected SHA-256 object ID, and the original byte size (`1103398` and
`276026`). `git lfs ls-files --long` reports both new paths with those object
IDs, and `git lfs fsck` exits successfully.

- [x] **Step 5: Commit without pushing**

Run:

```bash
git commit -m "docs: organize project reference materials"
git status --short --branch
git log -2 --oneline
```

Expected: the implementation commit follows the documentation-responsibilities
specification and plan commits, the worktree is clean, and the local branch is
ahead of `origin/master`. Do not run `git push`.
