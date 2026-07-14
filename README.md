# 107 Workspace

107 Workspace is a backend-first collaborative computing workspace for
undergraduate teaching, student projects, and competition teams.

The active implementation is an independent, layered FastAPI service in
[`backend/`](backend/README.md). It covers collaborative workspaces, projects,
versioned datasets, run templates, project transfer, Mock and Slurm scheduling,
logs, and result artifacts.

Frontend, container, and deployment implementation remains intentionally
deferred. The corresponding directories contain scope markers only.

## Architecture

The backend is a modular monolith with dependency direction:

```text
api -> application -> domain ports <- infrastructure
```

The active package does not import RunBox, `submit107`, or `hpc-helper`.
Reusable behavior from those projects was reimplemented behind domain ports.
The original RunBox remains available as an isolated source snapshot under
[`archive/runbox-v0/`](archive/runbox-v0/ARCHIVE.md).

## Development

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn workspace107.main:create_app --factory --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. See the
[`backend/README.md`](backend/README.md) for configuration, migrations, adapter
selection, tests, and the live HTTP acceptance workflow.

Run the isolated end-to-end smoke workflow from the repository root:

```bash
./scripts/smoke-backend.sh
```

## References

- [Backend design](docs/superpowers/specs/2026-07-13-workspace107-backend-design.md)
- [Implementation plan](docs/superpowers/plans/2026-07-13-workspace107-backend.md)
- [Backend reinitialization review](docs/reviews/2026-07-14-backend-reinitialization/README.md)
- [Backend development guide](backend/README.md)
- [RunBox v0 archive](archive/runbox-v0/ARCHIVE.md)
- [Platform source materials](docs/archive/2026-07-14-platform-materials/README.md)
- [Product reference](ref.md)
- [Architecture notes](foo.md)
