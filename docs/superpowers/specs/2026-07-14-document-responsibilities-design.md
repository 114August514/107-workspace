# Documentation Responsibilities Design

**Date:** 2026-07-14

**Status:** Approved under the user's delegated approval for safe follow-up work

**Scope:** Repository documentation organization only

## 1. Purpose

The repository currently mixes product inputs, an early backend setup guide,
platform source materials, implementation specifications, and review records.
This change gives each document an explicit responsibility without rewriting
its source content or presenting historical inputs as current requirements.

## 2. Chosen Organization

Source materials belong under `docs/references/`, grouped by the subject they
inform:

```text
docs/
├── references/
│   ├── README.md
│   ├── product/
│   │   └── 107-workspace-product-vision.md
│   ├── engineering/
│   │   └── initial-backend-bootstrap-guide.md
│   └── platform/
│       ├── README.md
│       ├── 107-cluster-competition-training.pdf
│       ├── computing-platform-track-introduction.pdf
│       └── workspace-slurm-apptainer-context.md
├── reviews/
└── superpowers/
    ├── plans/
    └── specs/
```

The categories have distinct responsibilities:

- `references/product/` preserves product and domain inputs.
- `references/engineering/` preserves engineering inputs and early guidance.
- `references/platform/` preserves source material about the 107 platform,
  cluster operation, Slurm, SCOW, and Apptainer.
- `reviews/` contains evidence-based snapshots intended for human review.
- `superpowers/specs/` and `superpowers/plans/` contain accepted design and
  implementation records. Their paths remain unchanged because the workflow
  treats them as conventional locations.

## 3. Source Mapping

| Existing path | New path | Role |
| --- | --- | --- |
| `foo.md` | `docs/references/product/107-workspace-product-vision.md` | Early product vision and domain model input |
| `ref.md` | `docs/references/engineering/initial-backend-bootstrap-guide.md` | Early backend initialization guide |
| `docs/archive/2026-07-14-platform-materials/training-107-competition.pdf` | `docs/references/platform/107-cluster-competition-training.pdf` | Cluster and competition-track training reference |
| `docs/archive/2026-07-14-platform-materials/算力平台及算力平台赛道介绍.pdf` | `docs/references/platform/computing-platform-track-introduction.pdf` | Computing-platform and track introduction |
| `docs/archive/2026-07-14-platform-materials/流程参考.md` | `docs/references/platform/workspace-slurm-apptainer-context.md` | Explanatory platform workflow context |

The old dated archive directory is removed after all tracked content moves.
`archive/` remains reserved for retired implementations and complete historical
snapshots, such as RunBox v0.

## 4. Authority And Navigation

The reference index must state that source materials are informative and
non-normative. The product vision and initialization guide remain useful design
evidence, but the accepted backend specification, implementation plan, backend
guide, and review package supersede them where they disagree.

The repository README links to the new reference index and names the product
and engineering inputs accurately. Existing design, plan, and review documents
use the new paths when referring to the files. Commands recorded as historical
evidence may retain their original command text only when the surrounding text
explicitly identifies it as a historical snapshot; otherwise paths are updated.

## 5. Binary Preservation

The two PDFs remain byte-for-byte unchanged and tracked by Git LFS. Exact-path
rules in `.gitattributes` move to the new filenames. Their expected LFS object
IDs are:

- `6cbdb7db2a3294746f9c1eca077f643edb20715eace85d2f7f74fa515f9c99eb`
- `d09a75c373809fa8b8bff3df55f291cbe29742e4df89aa32008464f7bc050d0a`

## 6. Acceptance Criteria

The reorganization is complete when:

1. The target tree exists and the old root and archive paths do not.
2. Each reference category and authority level is explained by an index.
3. All live Markdown links resolve from their containing document.
4. Searches find no unintended stale references to the old paths.
5. Both PDFs are still LFS pointers with the expected object IDs and pass
   `git lfs fsck`.
6. Only the intended documentation, navigation, and LFS attribute changes are
   committed, and no commit is pushed.
