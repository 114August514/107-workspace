# workspace107 source archive

This directory is an immutable source snapshot kept for migration review and
historical comparison.

- Source repository: `workspace107`
- Source commit: `293c8d8b0ff6a43be4b31d62447fb332779862d5`
- Archived on: 2026-08-01
- Snapshot method: `git archive` of the source commit

Apart from `ARCHIVE.md` and `MIGRATION.md`, only files tracked by the source
repository are present. The source `.git/` directory, virtual environments,
dependency directories, build output, caches, runtime databases, and other
ignored files were not copied. `MIGRATION.md` records how this snapshot became
the active baseline; it is metadata, not part of the source tree.

The archive is reference material. It is excluded from active builds, tests,
formatting, linting, type checking, and generated-contract checks. Do not make
feature changes here; migrate an implementation into the active tree and adapt
it to this repository instead.

The archived `docs/product/design-final.md` records the source repository's
historical design baseline. The active repository's root `DESIGN-final.md` is
the authoritative product and domain specification.

The snapshot intentionally preserves source defects as evidence. In
particular, two archived development documents contain merge-marker examples
that Git's whitespace checker reports as conflict markers, and the archived
design document contains one trailing space. These files are unchanged from
the source commit and are not active project guidance.

At the time of migration, the source backend passed Ruff lint and format
checks. The original all-in-one `scripts/check.sh` run was interrupted while
its quiet pytest phase was still running, so this archive does not claim a
complete green verification receipt. The migrated active tree must pass the
repository-level `make check` before delivery.
