# 107 Workspace Backend Design

**Date:** 2026-07-13
**Status:** Approved for implementation planning
**Scope:** Backend only

## 1. Purpose

107 Workspace is a low-friction collaborative computing layer for undergraduate
teaching, student projects, and competition teams. It turns cluster concepts
such as Slurm scripts, partitions, QoS values, shared paths, and result
collection into workspace-level projects, datasets, run templates, runs, logs,
and artifacts.

This design reinitializes the repository around an independent backend. It uses
the [initial backend bootstrap guide](../../references/engineering/initial-backend-bootstrap-guide.md)
and [product vision](../../references/product/107-workspace-product-vision.md)
as design inputs, preserves useful behavior from the existing RunBox, and
selectively internalizes proven ideas from `submit107` and `hpc-helper`. The
resulting backend has no runtime dependency on any sibling repository.

## 2. Goals

The first backend release must:

1. Provide a FastAPI service managed with `uv` and Python 3.12.
2. Persist users, workspaces, memberships, projects, dataset versions, run
   templates, runs, run events, transfer state, and artifacts with SQLAlchemy 2
   and Alembic.
3. Support all six workspace kinds from the product brief: personal, course,
   experiment, team, project, and public.
4. Enforce workspace membership roles in the application layer without adding
   a production login system.
5. Execute the complete project-to-result workflow through a durable mock
   cluster adapter.
6. Provide a layered Slurm adapter assembled from the useful scheduling ideas
   in `submit107` and `hpc-helper`, without requiring a live cluster for the
   first release.
7. Provide independent project scanning and transfer ports for local and SSH
   operation.
8. Preserve the useful RunBox source as an archive while moving reusable
   behavior into tested backend modules.
9. Pass migrations, unit tests, adapter contract tests, API integration tests,
   static analysis, formatting checks, and a live HTTP smoke test.

## 3. Non-goals

The first release does not implement:

- A frontend or static web application.
- Dockerfiles, Compose files, Kubernetes manifests, or deployment automation.
- Password login, OAuth, SSO, token issuance, or production identity proof.
- Production quota accounting, billing, notifications, or automatic grading.
- A production-grade multi-tenant security boundary.
- SCOW replacement or direct SCOW UI integration.
- Destructive remote mirroring or automatic remote deletion.
- Interactive GPU holder sessions as a primary run mode.
- A live-cluster acceptance test, because Slurm and credentials are not part of
  the local development environment.

## 4. Evidence From Existing Projects

### 4.1 Existing RunBox

The current RunBox proves several useful interaction patterns:

- FastAPI can expose cluster operations and one-way live output through SSE.
- Blocking cluster calls must not block the application event loop.
- Cluster failures benefit from stable categories such as configuration,
  authentication, allocation, synchronization, and run failures.
- A run must support explicit stop semantics and structured completion data.

The active RunBox code is not a suitable backend base because it uses a single
399-line route module, untyped dictionary request bodies, process-global active
run state, a bundled frontend, and an undeclared `hpc_helper.api` dependency.
The checked-in `hpc-helper` does not contain that API module, so the old RunBox
cannot be reproduced from its declared dependencies.

### 4.2 submit107

The sibling `submit107` project has 127 passing tests and useful, separable
behavior:

- Project entry-point detection.
- Dependency-based environment and resource inference.
- Layered configuration concepts.
- Strict sbatch generation.
- Slurm preflight and submit-output parsing.
- Clear separation between local-side transfer concerns and cluster-side job
  concerns.

The backend will not import `submit107`. CLI prompts, Rich output, Markdown run
records, notebook rewriting, Git/Pan orchestration, and CLI configuration files
do not belong inside a multi-user HTTP service.

### 4.3 hpc-helper

The local reference is commit `dedae742e7fa8f8ebb103b9eb62e8cbe8d28dbf3`.
It has no tests, lock file, license file, or `hpc_helper.api` module. Its most
valuable implementation ideas are:

- Reliable SSH options with connection timeout and keepalive.
- PAX tar streaming for Unicode paths.
- Correct cleanup of both processes in a transfer pipeline.
- `.hpcignore` parsing and directory pruning.
- Manifest-based incremental scanning.
- Queue reconciliation that detects stale cached jobs.
- Local-login-node and SSH-driven execution modes.
- Batch groups with shared and per-group resource overrides.

The backend will reimplement these behaviors behind explicit interfaces rather
than copying the CLI structure. This avoids inheriting global single-user
session files, `sys.exit`, terminal output, unchecked path composition, shell
argument interpolation, silently ignored state corruption, and stale remote
files.

## 5. Repository Layout

```text
107-workspace/
├── archive/
│   └── runbox-v0/
│       ├── README.md
│       ├── DESIGN.md
│       ├── pyproject.toml
│       └── runbox/
├── backend/
│   ├── src/workspace107/
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   └── infrastructure/
│   ├── migrations/
│   ├── tests/
│   ├── .python-version
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── README.md
│   └── uv.lock
├── deploy/
├── docker/
├── docs/
├── frontend/
├── scripts/
├── .gitignore
└── README.md
```

`frontend`, `docker`, and `deploy` contain only short scope markers in this
release. They contain no implementation.

The nested local `hpc-helper/` checkout remains an untracked reference and is
ignored by the parent repository. Generated `runbox.egg-info` and
`__pycache__` directories are removed rather than archived.

## 6. Package Architecture

The backend is a modular monolith with four dependency layers:

```text
workspace107.api
        |
        v
workspace107.application
        |
        v
workspace107.domain  <--- defines ports
        ^
        |
workspace107.infrastructure  --- implements ports
```

Rules:

1. `domain` imports only the Python standard library.
2. `application` imports `domain`, never FastAPI, SQLAlchemy, SSH, or Slurm
   implementations.
3. `infrastructure` implements domain ports and may import SQLAlchemy, Jinja,
   filesystem, subprocess, and transport libraries.
4. `api` maps HTTP requests to application commands and application results to
   HTTP responses.
5. Cross-feature collaboration goes through domain ports or application DTOs,
   not through another feature's database model.
6. API schemas and SQLAlchemy models are separate from domain values.

The package layout is:

```text
src/workspace107/
├── api/
│   ├── dependencies.py
│   ├── errors.py
│   ├── router.py
│   └── routes/
├── application/
│   ├── datasets.py
│   ├── inference.py
│   ├── projects.py
│   ├── runs.py
│   ├── templates.py
│   ├── users.py
│   └── workspaces.py
├── domain/
│   ├── errors.py
│   ├── models.py
│   ├── permissions.py
│   ├── state_machine.py
│   ├── values.py
│   └── ports/
│       ├── cluster.py
│       ├── repositories.py
│       ├── storage.py
│       └── transfer.py
├── infrastructure/
│   ├── cluster/
│   │   ├── mock.py
│   │   └── slurm/
│   │       ├── adapter.py
│   │       ├── command_runner.py
│   │       ├── parser.py
│   │       ├── renderer.py
│   │       └── transports/
│   │           ├── local.py
│   │           └── ssh.py
│   ├── db/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── session.py
│   ├── storage/local.py
│   ├── transfer/
│   │   ├── local.py
│   │   ├── manifest.py
│   │   ├── scanner.py
│   │   ├── ssh.py
│   │   └── tar_stream.py
│   └── workers/reconciler.py
├── config.py
└── main.py
```

## 7. Domain Model

All primary identifiers are UUIDs generated by the application. Timestamps are
UTC. Referenced historical records are archived, not physically deleted.

### 7.1 User

- `id`
- `username`, unique and immutable
- `display_name`
- `email`, optional
- `created_at`
- `archived_at`, optional

The backend stores no password or authentication secret.

### 7.2 Workspace

- `id`
- `kind`: `personal`, `course`, `experiment`, `team`, `project`, or `public`
- `name`
- `slug`, globally unique
- `description`
- `parent_id`, required only for an experiment nested under a course
- `created_by`
- `created_at`
- `archived_at`, optional

### 7.3 WorkspaceMember

- `workspace_id`
- `user_id`
- `role`: `owner`, `manager`, `member`, or `viewer`
- `joined_at`

The creator becomes owner in the same transaction that creates the workspace.
A workspace always retains at least one owner.

### 7.4 Project

- `id`
- `workspace_id`
- `name`
- `slug`, unique within the workspace
- `description`
- `storage_key`
- `created_by`
- `created_at`
- `archived_at`, optional

### 7.5 Dataset and DatasetVersion

`Dataset` is mutable catalog metadata. `DatasetVersion` is immutable content.

Dataset fields:

- `id`, `workspace_id`, `name`, `slug`, `description`
- `created_by`, `created_at`, `archived_at`

Dataset version fields:

- `id`, `dataset_id`, `version`, unique within the dataset
- `storage_key`
- `size_bytes`
- `sha256`
- `created_by`, `created_at`

Existing versions cannot be overwritten. A new upload creates a new version.

### 7.6 RunTemplate

- `id`, `workspace_id`, `name`, `description`
- `entrypoint`
- `environment_spec`: typed JSON validated by Pydantic
- `resource_spec`: typed JSON for CPU, memory, GPU, wall time, account,
  partition, and QoS
- `output_spec`: typed JSON containing allowed relative output paths
- `created_by`, `created_at`, `updated_at`, `archived_at`

Template mutation does not affect existing runs because submission creates a
complete snapshot.

### 7.7 Run and RunDataset

Run fields:

- `id`, `workspace_id`, `project_id`, `template_id`
- `submitted_by`
- `status`
- `external_job_id`, optional until submission succeeds
- `submission_snapshot`: immutable JSON containing template, resources,
  environment, entrypoint, mounts, and outputs
- `exit_code`, optional
- `failure_code` and `failure_message`, optional
- `submitted_at`, `started_at`, `finished_at`, optional as appropriate
- `created_at`, `updated_at`

`RunDataset` links a run to an exact dataset version and a normalized relative
mount path. Mount paths are unique within a run.

### 7.8 RunEvent

- `id`, `run_id`
- `event_type`
- `from_status`, optional
- `to_status`, optional
- `message`, optional
- `details`, typed JSON
- `created_at`

Every state transition creates an event in the same database transaction.

### 7.9 Artifact

- `id`, `run_id`
- `kind`: `log`, `result`, or `report`
- `name`
- `storage_key`
- `media_type`
- `size_bytes`
- `sha256`
- `created_at`

### 7.10 ProjectSync

- `id`, `project_id`
- `transport`: `local` or `ssh`
- `target_uri`
- `manifest`, typed JSON mapping relative paths to signatures
- `last_synced_at`
- `created_at`, `updated_at`

Transfer manifests belong to projects and targets, not to a process-global user
directory.

## 8. Identity and Permissions

Production authentication is deferred. Protected endpoints require an
`X-User-Id` header containing an existing user UUID. This is a trusted identity
placeholder, not a security claim.

Application services enforce permissions:

- Owner: workspace lifecycle, member roles, and all content.
- Manager: member invitations except owner changes, plus all content.
- Member: create and modify projects, datasets, templates, and runs.
- Viewer: read workspace resources, logs, and artifacts.

Only owners can archive a workspace. Managers and owners can archive shared
resources. A future authentication adapter will replace header parsing without
changing application service signatures.

## 9. Domain Ports

### 9.1 ClusterPort

The application depends on these operations:

`RunSubmission` contains an opaque resolved `project_uri`. Each dataset mount
contains its dataset version ID, opaque resolved `source_uri`, and normalized
relative mount path. The API accepts resource IDs; the application resolves
these URIs before calling the adapter, so cluster implementations never query
application repositories.

```python
preflight(spec: RunSubmission) -> list[PreflightCheck]
submit(spec: RunSubmission) -> SubmittedJob
status(external_job_id: str) -> JobObservation
cancel(external_job_id: str) -> None
read_log(external_job_id: str, offset: int) -> LogChunk
collect_artifacts(external_job_id: str) -> list[CollectedArtifact]
open_artifact(external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]
```

`collect_artifacts` returns immutable metadata with opaque adapter keys;
`open_artifact` streams one selected object. The port uses domain values only.
It does not expose subprocess objects, Slurm-specific states, filesystem paths,
or transport details.

### 9.2 ProjectTransferPort

```python
scan(source: TransferSource, ignore: IgnoreRules) -> ProjectSnapshot
push(plan: TransferPlan) -> TransferResult
pull(request: PullRequest) -> TransferResult
```

Scanning and transfer are separate from cluster scheduling. This keeps project
collaboration usable even when the scheduler is unavailable.

### 9.3 StoragePort

```python
put(stream: AsyncIterator[bytes], metadata: ObjectMetadata) -> StoredObject
open(storage_key: str) -> AsyncIterator[bytes]
delete_unreferenced(storage_key: str) -> None
```

Storage keys are opaque identifiers. API callers never supply backend absolute
paths.

## 10. Cluster Implementations

### 10.1 Durable MockClusterAdapter

The mock adapter is the default development and acceptance implementation. It
stores external scheduler state as atomic JSON records under a configured mock
root and writes mock logs and results beneath the same root. State therefore
survives an API process restart.

The adapter supports:

- Submission with a unique external job ID.
- Configurable queued and running durations.
- Deterministic success or failure for test scenarios.
- Cancellation from submitting, queued, or running states.
- Incremental log reads by byte offset.
- Result and log collection after a terminal state.
- An injected clock for deterministic tests.

The mock state directory represents an external scheduler. Domain run state
remains in the database and is reconciled through the same port used by Slurm.

### 10.2 SlurmClusterAdapter

The Slurm implementation is present and contract-tested, but not selected by
default. It contains no Click or Rich dependency.

The backend internalizes the source-project entry detection and resource
inference ideas from `submit107` in `application/inference.py`; these policies
remain independent of Slurm. The Slurm adapter itself absorbs:

- `submit107` strict script behavior, Slurm preflight, and submit-output
  parsing.
- `hpc-helper` account support, resource overrides, queue recovery concepts,
  batch grouping, and local/SSH execution modes.

The renderer uses Jinja with `StrictUndefined`, validated values, normalized
relative paths, and shell quoting. Scripts include `set -euo pipefail`, an
explicit working directory, log destinations, environment activation, and
resource directives.

Active states come from `squeue`; terminal states and exit codes come from
`sacct --parsable2`. Cancellation uses `scancel`. Unknown external states map to
a typed adapter error instead of silently becoming failed runs.

`CommandRunner` returns structured stdout, stderr, exit code, and timing data.
It never calls `sys.exit` and never invokes `shell=True`.

### 10.3 Explicit Transports

`WORKSPACE107_CLUSTER_TRANSPORT` is either `local` or `ssh`. The backend never
guesses based on installed commands.

- Local transport uses async subprocess APIs on a cluster login node.
- SSH transport invokes the system `ssh` executable with ControlMaster
  disabled, a connection timeout, and keepalive settings derived from
  `hpc-helper`.

Both implementations satisfy the same command-runner tests. SSH host values
come from trusted service configuration, not request bodies.

## 11. Project Transfer

The scanner combines useful `.hpcignore` behavior with mandatory built-in
exclusions for `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`,
and `.ipynb_checkpoints`.

Manifest signatures contain size and nanosecond modification time. The scanner
returns added, changed, unchanged, and locally removed paths. Push is
upload-only in this release: removed local paths are reported but never deleted
remotely.

SSH transfer uses PAX tar streams for Unicode names. File lists are passed via a
temporary file or stdin rather than command-line expansion. Both processes in a
pipeline are terminated and awaited on error or cancellation. Every local and
remote path passes normalization and allowed-root checks before execution.

Large-file warnings are structured results rather than terminal output. The API
can show them without parsing strings.

## 12. Run State Machine

The legal state graph is:

```text
SUBMITTING -> QUEUED -> RUNNING -> SUCCEEDED
     |          |          |
     +----------+----------+-> FAILED
     |          |          |
     +----------+----------+-> CANCELLING -> CANCELLED
```

Rules:

- A run is created as `SUBMITTING` only after preflight passes.
- Adapter submission failure moves it to `FAILED` and records the adapter
  error.
- Terminal states are immutable.
- Cancellation is idempotent for `CANCELLING` and `CANCELLED`.
- Illegal transitions raise `invalid_run_transition`.
- State updates use a compare-and-set database update so two reconciler passes
  cannot both apply the same transition.
- Artifact collection happens once after a successful terminal observation.

The reconciler runs from the FastAPI lifespan, polls only non-terminal runs,
and exposes `reconcile_once()` for deterministic integration tests.

## 13. Run Submission Flow

1. Resolve `X-User-Id` and verify workspace membership.
2. Load active project, template, and exact dataset versions.
3. Validate entrypoint, mount paths, output paths, environment, and resources,
   then resolve the project and dataset storage URIs.
4. Ask the selected cluster adapter to perform implementation-specific
   preflight where required.
5. Create the run, dataset links, immutable snapshot, and initial event in one
   transaction.
6. Submit outside the database transaction.
7. Store the external job ID and transition to `QUEUED`, or record a typed
   failure.
8. Let the reconciler observe subsequent states.
9. On terminal completion, enumerate adapter artifact metadata, stream each
   object through `ClusterPort.open_artifact` into `StoragePort`, then create
   artifact records.

`POST /runs/preflight` runs steps 1 through 4 without creating persistent run
state. `POST /runs` repeats preflight to avoid trusting a stale client result.

## 14. HTTP API

The API prefix is `/api/v1`. Health is intentionally unversioned.

### 14.1 Health and users

- `GET /health`
- `POST /api/v1/users`
- `GET /api/v1/users/{user_id}`

### 14.2 Workspaces and members

- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`
- `PATCH /api/v1/workspaces/{workspace_id}`
- `POST /api/v1/workspaces/{workspace_id}/archive`
- `GET /api/v1/workspaces/{workspace_id}/members`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}`
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`

### 14.3 Projects

- `POST /api/v1/workspaces/{workspace_id}/projects`
- `GET /api/v1/workspaces/{workspace_id}/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/archive`
- `POST /api/v1/projects/{project_id}/scan`
- `POST /api/v1/projects/{project_id}/push`
- `POST /api/v1/projects/{project_id}/pull`

### 14.4 Datasets

- `POST /api/v1/workspaces/{workspace_id}/datasets`
- `GET /api/v1/workspaces/{workspace_id}/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `POST /api/v1/datasets/{dataset_id}/versions`
- `GET /api/v1/datasets/{dataset_id}/versions`
- `GET /api/v1/dataset-versions/{version_id}/download`
- `POST /api/v1/datasets/{dataset_id}/archive`

### 14.5 Run templates

- `POST /api/v1/workspaces/{workspace_id}/run-templates`
- `GET /api/v1/workspaces/{workspace_id}/run-templates`
- `GET /api/v1/run-templates/{template_id}`
- `PATCH /api/v1/run-templates/{template_id}`
- `POST /api/v1/run-templates/{template_id}/archive`

### 14.6 Runs and artifacts

- `POST /api/v1/runs/preflight`
- `POST /api/v1/runs`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/runs/{run_id}/logs`
- `GET /api/v1/runs/{run_id}/logs/stream`
- `GET /api/v1/runs/{run_id}/artifacts`
- `GET /api/v1/artifacts/{artifact_id}/download`

List endpoints use `limit` and `offset` with stable creation-time ordering.
SSE log events contain an offset and data; reconnecting clients send the last
offset and do not drain a shared in-memory queue.

## 15. Error Contract

Errors use `application/problem+json` with these fields:

```json
{
  "type": "https://workspace107.local/problems/preflight-failed",
  "title": "Run preflight failed",
  "status": 422,
  "detail": "One or more run checks failed.",
  "code": "preflight_failed",
  "errors": []
}
```

Stable codes include:

- `workspace_access_denied`
- `resource_not_found`
- `resource_archived`
- `invalid_run_transition`
- `preflight_failed`
- `path_outside_allowed_root`
- `transfer_failed`
- `cluster_unavailable`
- `external_command_failed`

Infrastructure exceptions are translated once at the application boundary.
Raw commands, credentials, environment values, and unrestricted filesystem
paths are never returned to API clients.

## 16. Configuration

`pydantic-settings` loads `WORKSPACE107_*` environment variables. Important
settings include:

- Database URL.
- Storage root.
- Mock-cluster state root.
- Cluster adapter: `mock` or `slurm`.
- Cluster transport: `local` or `ssh`.
- SSH alias and remote root.
- Slurm account, partition, QoS, and log root.
- Reconciler interval.
- Allowed local project roots.

Defaults select SQLite, local storage, and the mock cluster. No hostname,
username, student identifier, credential, or absolute personal path is committed
to the repository.

## 17. Security and Data Integrity

- Normalize paths with `Path.resolve()` or `PurePosixPath` before allowed-root
  checks.
- Reject absolute mount, entrypoint, and output paths from API payloads.
- Reject `..`, NUL bytes, empty path segments, and mount collisions.
- Construct local processes with argument arrays and `shell=False`.
- Quote the unavoidable remote-shell boundary in exactly one transport module.
- Restrict SSH hosts and remote roots to service configuration.
- Store uploaded objects under generated storage keys, never user filenames.
- Compute SHA-256 while streaming uploads and artifact collection.
- Enable SQLite foreign keys and WAL mode.
- Use unique constraints for slugs, memberships, dataset versions, and run
  mount paths.
- Prevent removal of the final workspace owner.
- Preserve immutable submission snapshots and dataset versions.

## 18. Testing Strategy

### 18.1 Unit tests

- Workspace role matrix and final-owner invariant.
- Run state machine and compare-and-set transitions.
- Run preflight checks and immutable snapshot creation.
- Entry detection and dependency/resource inference.
- Strict sbatch rendering for CPU, GPU, uv, conda, and system environments.
- Slurm output parsers for queued, running, completed, failed, cancelled,
  timeout, node failure, and unknown states.
- Ignore matching, directory pruning, manifest diffs, and large-file warnings.
- Local and POSIX path normalization and injection attempts.
- Tar pipeline cancellation and error propagation.

### 18.2 Adapter contract tests

One reusable suite verifies submit, observe, cancel, logs, terminal artifacts,
and error normalization. It runs against:

- Durable `MockClusterAdapter`.
- `SlurmClusterAdapter` with a scripted fake `CommandRunner`.

Transfer contracts run against local transfer and SSH transfer with scripted
processes.

### 18.3 Integration tests

- Alembic upgrade from an empty database and downgrade to base.
- User, workspace, membership, project, dataset, template, and run APIs.
- Authorization failures for every workspace role.
- Dataset upload and artifact download streaming.
- Full mock workflow through queued, running, and succeeded states.
- Failure and cancellation workflows.
- Mock job recovery after recreating the FastAPI application.
- SSE reconnect from a known log offset.
- Archived resources rejected for new runs.

### 18.4 Quality gates

From `backend/`:

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
uv run pytest --cov=workspace107 --cov-report=term-missing --cov-fail-under=90
uv run ruff format --check .
uv run ruff check .
uv run pyright
```

A final smoke test starts Uvicorn, verifies `GET /health`, submits a complete
mock workflow over HTTP, waits for success, reads logs, downloads an artifact,
and then shuts the server down.

## 19. Acceptance Criteria

The backend release is complete only when all of the following are true:

1. A clean clone can install the backend using only its own `pyproject.toml` and
   `uv.lock`.
2. No active backend import resolves through RunBox, `submit107`, or
   `hpc-helper`.
3. The old RunBox is available under `archive/runbox-v0` without generated
   caches or package metadata.
4. Migrations create every model and enforce documented uniqueness and foreign
   keys.
5. An API client can create a user, course workspace, member, project, dataset
   version, and run template.
6. The client can preflight and submit a mock run, observe queued/running/
   succeeded states, read logs, and download a verified result artifact.
7. Failure, cancellation, invalid transitions, unauthorized access, archived
   resources, path traversal, and command-injection inputs are covered by
   passing tests.
8. Mock external state survives application recreation.
9. The Slurm adapter passes the common cluster contract with a fake command
   runner.
10. Project scanning and local transfer pass the common transfer contract; SSH
    command construction and pipeline behavior are tested without credentials.
11. Ruff, strict Pyright, pytest coverage, migration checks, and the live HTTP
    smoke test all pass.
12. Root and backend documentation explain the architecture, local development,
    API discovery, and deferred frontend/container work.

## 20. Reinitialization Sequence

Implementation will proceed in dependency order:

1. Archive RunBox and establish the root layout.
2. Scaffold the independent backend toolchain and quality gates.
3. Implement domain values, state machine, and ports with tests.
4. Implement database models, repositories, and migrations.
5. Implement users, workspaces, projects, datasets, and templates.
6. Implement local storage and project scanning/transfer.
7. Implement the durable mock cluster and reconciler.
8. Implement run APIs, logs, artifacts, cancellation, and SSE reconnection.
9. Implement the layered Slurm adapter and SSH transport from the absorbed
   behavior.
10. Run the full verification and live HTTP acceptance workflow.

Each step leaves a working, testable backend state. Frontend and container work
begin only after this acceptance list is satisfied.
