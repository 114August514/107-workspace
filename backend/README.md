# 107 Workspace Backend

The independent FastAPI backend for 107 Workspace. It is a layered modular
monolith for collaborative projects, versioned data, and local or Slurm-backed
run execution.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- `curl` for the live smoke workflow
- A filesystem location writable by the backend

Slurm is optional. Local Slurm mode requires `sinfo`, `sbatch`, `squeue`,
`sacct`, and `scancel` on the backend host. SSH mode additionally requires the
system `ssh` client and a preconfigured SSH host alias. The default Mock adapter
needs neither Slurm nor SSH.

## Quick Start

Run all commands in this section from `backend/`:

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn workspace107.main:create_app --factory --reload
```

The defaults create a SQLite database and runtime data beneath `backend/var/`.
The server does not run migrations automatically, so apply them before the
first start and after pulling a migration.

Use these endpoints to inspect a running service:

- Health: `http://127.0.0.1:8000/health`
- OpenAPI UI: `http://127.0.0.1:8000/docs`
- OpenAPI document: `http://127.0.0.1:8000/openapi.json`

Application endpoints use the `/api/v1` prefix. `POST /api/v1/users` creates a
development identity; authenticated endpoints currently expect its UUID in
the `X-User-Id` header. This header is an explicit backend-stage identity
boundary, not a production authentication mechanism.

## Architecture

```text
workspace107.api -> workspace107.application -> workspace107.domain
                                                   ^
                                                   |
                              workspace107.infrastructure
```

The layers have distinct responsibilities:

| Layer | Responsibility |
| --- | --- |
| `domain` | Standard-library-only values, policies, state transitions, models, and ports |
| `application` | Use cases, permission checks, immutable run snapshots, and transaction boundaries |
| `infrastructure` | SQLAlchemy, local storage, project transfer, Mock, Slurm, SSH, and reconciliation implementations |
| `api` | FastAPI dependencies, request/response schemas, routes, SSE, and Problem Details mapping |

[`workspace107.main:create_app`](src/workspace107/main.py) is the composition
root. Infrastructure implements domain ports, so application services do not
depend on SQLAlchemy, Slurm commands, SSH, or FastAPI. Adapter calls are kept
outside database transactions, and run state is reconciled with compare-and-set
updates.

The backend contains no active imports from RunBox, `submit107`, or
`hpc-helper`. Their useful behavior is represented by local policies and
adapters rather than runtime dependencies.

## Runtime Adapters

### Mock

`WORKSPACE107_CLUSTER_ADAPTER=mock` is the default. Each submitted external job
is stored as an atomic JSON record under `WORKSPACE107_MOCK_CLUSTER_ROOT`, with
logs and result data beside it. This external state survives API process
restarts; durable domain run state remains in the configured database.

The background reconciler polls non-terminal runs, records state events,
collects terminal logs and results into object storage, and continues after a
transient adapter failure. Mock runs exercise the same domain port and HTTP
workflow as Slurm runs.

### Slurm

Select Slurm explicitly:

```bash
export WORKSPACE107_CLUSTER_ADAPTER=slurm
export WORKSPACE107_CLUSTER_TRANSPORT=local
```

Local transport executes argument arrays on the backend host. This mode is
appropriate when the API runs on a Slurm login node and the configured project,
log, and storage roots are local paths.

For SSH transport:

```bash
export WORKSPACE107_CLUSTER_ADAPTER=slurm
export WORKSPACE107_CLUSTER_TRANSPORT=ssh
export WORKSPACE107_SSH_HOST=ustc-cluster
export WORKSPACE107_SLURM_REMOTE_ROOT=project/workspace107/runs
export WORKSPACE107_SLURM_LOG_ROOT=project/workspace107/logs
export WORKSPACE107_SLURM_STORAGE_ROOT=project/workspace107/storage
```

`WORKSPACE107_SSH_HOST` is a trusted service-side host or SSH alias, never a
request value. Configure credentials and host keys outside this repository.
Selecting SSH also selects the SSH project-transfer adapter, keeping project
sync and run submission on the same transport.

Slurm scripts are rendered with strict Jinja values and validated paths.
Commands use argument arrays; only the SSH transport constructs a quoted remote
command. Contract tests use scripted runners and do not require a cluster.

## Configuration

Settings use the `WORKSPACE107_` prefix and may be provided through the
environment or `backend/.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE107_DATABASE_URL` | `sqlite+aiosqlite:///./var/workspace107.db` | SQLAlchemy async database URL |
| `WORKSPACE107_STORAGE_ROOT` | `var/storage` | Content-addressed dataset and artifact storage |
| `WORKSPACE107_TRANSFER_ROOTS` | `source`, `cluster`, and `downloads` under `var/transfer` | JSON object of named project-transfer roots |
| `WORKSPACE107_MOCK_CLUSTER_ROOT` | `var/mock-cluster` | Durable Mock scheduler state, logs, and results |
| `WORKSPACE107_CLUSTER_ADAPTER` | `mock` | `mock` or `slurm` |
| `WORKSPACE107_CLUSTER_TRANSPORT` | `local` | `local` or `ssh`; shared by project transfer and cluster commands |
| `WORKSPACE107_SSH_HOST` | unset | Required service-configured host when the transport is `ssh` |
| `WORKSPACE107_SLURM_REMOTE_ROOT` | `var/slurm` | Slurm run working root |
| `WORKSPACE107_SLURM_LOG_ROOT` | `var/slurm/logs` | Slurm stdout/stderr root |
| `WORKSPACE107_SLURM_STORAGE_ROOT` | `var/slurm/storage` | Slurm-side dataset and collected-output root |
| `WORKSPACE107_RECONCILE_INTERVAL_SECONDS` | `0.2` | Background reconciliation and SSE polling interval |

Complex settings use JSON. For example:

```bash
export WORKSPACE107_TRANSFER_ROOTS='{"source":"/srv/workspace107/source","cluster":"/srv/workspace107/cluster","downloads":"/srv/workspace107/downloads"}'
```

For SSH transport, `source` and `downloads` are local allowed roots while
`cluster` is a remote POSIX root. All configured roots are validated before
transfer.

## Migrations

Apply, inspect, or reverse migrations with Alembic:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

The downgrade command removes the backend schema and is intended for migration
verification against disposable data. SQLite connections enable foreign keys
and WAL mode.

## Tests and Quality Gates

Run the normal test suite and focused checks from `backend/`:

```bash
uv run pytest -q
uv run pytest tests/integration/api -q
uv run pytest --cov=workspace107 --cov-report=term-missing --cov-fail-under=90
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv lock --check
```

The live HTTP smoke test is skipped by the normal pytest suite because it needs
an external server. Run its isolated harness from the repository root:

```bash
./scripts/smoke-backend.sh
```

The script creates a temporary database and all runtime roots, applies
migrations, starts Uvicorn on `127.0.0.1:8760`, and runs a complete workflow
over TCP. It creates users and a course workspace, adds a member, pushes a
project, uploads a dataset version, creates a run template, preflights and
submits a Mock run, observes queued/running/succeeded states, reads logs, and
verifies a downloaded result against its SHA-256 metadata. Set
`WORKSPACE107_SMOKE_PORT` to use another local port.

See the repository-level [backend design](../docs/superpowers/specs/2026-07-13-workspace107-backend-design.md)
and [implementation plan](../docs/superpowers/plans/2026-07-13-workspace107-backend.md)
for the full domain model, API inventory, security decisions, and acceptance
criteria.
