"""Project-specific development, migration, demo, and workflow tasks."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from .common import (
    BACKEND_ROOT,
    FRONTEND_ROOT,
    NODE_MAJOR,
    PNPM_MAJOR,
    REPO_ROOT,
    TaskError,
    backend_uv,
    command_text,
    ensure_backend_dependencies,
    ensure_frontend_dependencies,
    git,
    heading,
    merged_environment,
    require_commands,
    require_major_version,
    resolve_executable,
    run,
)

TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "submit_failed"}
DEMO_USER_GROUP_ID = "grp_demo"
JOURNAL_FIELD = re.compile(r"^-\s*([^:：]+)[:：]\s*(.*)$")
COMPOSE_FILE = REPO_ROOT / "deploy" / "compose.yaml"


def migrate(direction: str) -> None:
    heading("Database migration")
    ensure_backend_dependencies(quiet=True)
    revision = "head" if direction == "up" else "-1"
    backend_uv("run", "alembic", "upgrade" if direction == "up" else "downgrade", revision)


def coverage() -> None:
    heading("Backend coverage report")
    ensure_backend_dependencies(quiet=True)
    backend_uv(
        "run",
        "pytest",
        "--cov=workspace107",
        "--cov-report=term-missing",
    )


def _backend_python_executable() -> str:
    """Resolve the project interpreter for directly managed server processes."""
    result = backend_uv(
        "run",
        "--no-sync",
        "python",
        "-c",
        "import sys; print(sys.executable)",
        capture=True,
        quiet=True,
    )
    executable = result.stdout.strip()
    if not executable:
        raise TaskError("uv did not report the backend Python executable")
    return executable


def run_dev(component: str = "all") -> None:
    heading(f"Development server ({component})")
    if component in {"all", "backend"}:
        ensure_backend_dependencies(quiet=True)
    if component in {"all", "frontend"}:
        ensure_frontend_dependencies(quiet=True)

    commands: list[tuple[list[str], Path]] = []
    if component in {"all", "backend"}:
        commands.append(
            (
                [
                    _backend_python_executable(),
                    "-m",
                    "uvicorn",
                    "workspace107.main:create_app",
                    "--factory",
                    "--reload",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                BACKEND_ROOT,
            )
        )
    if component in {"all", "frontend"}:
        commands.append(
            (
                [resolve_executable("pnpm"), "run", "dev", "--", "--host", "127.0.0.1"],
                FRONTEND_ROOT,
            )
        )

    processes: list[subprocess.Popen[str]] = []
    try:
        for command, cwd in commands:
            print(f"$ {command_text(command)}", flush=True)
            processes.append(subprocess.Popen(command, cwd=cwd, text=True))
        while processes:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    if return_code != 0:
                        raise TaskError(
                            f"Development process exited with code {return_code}",
                            exit_code=return_code,
                        )
                    return
            time.sleep(0.2)
    finally:
        _stop_processes(processes)


def ship() -> None:
    raise TaskError(
        "Production deployment is not configured. Use `workspace.py compose up` only for the "
        "documented single-host Compose topology."
    )


def compose(action: str) -> None:
    require_commands("docker")
    arguments: dict[str, list[str]] = {
        "build": ["build"],
        "config": ["config", "--format", "json"],
        "up": ["up", "--build"],
        "down": ["down"],
    }
    command = [
        "docker",
        "compose",
        "--project-directory",
        REPO_ROOT,
        "--file",
        COMPOSE_FILE,
        *arguments[action],
    ]
    if action != "config":
        run(command)
        return
    result = run(
        command,
        env={"POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD") or "compose-config-only"},
        capture=True,
    )
    try:
        rendered = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TaskError("Docker Compose returned invalid JSON configuration") from error
    _validate_compose_config(rendered)
    print(result.stdout, end="")


def _validate_compose_config(rendered: dict[str, Any]) -> None:
    services = rendered.get("services", {})
    api = services.get("api", {})
    worker = services.get("worker", {})
    if not api or not worker:
        raise TaskError("Compose config must define separate api and worker services")

    api_environment = api.get("environment", {})
    forbidden_api = {
        name
        for name in api_environment
        if name in {"WORKSPACE107_SCHEDULER", "WORKSPACE107_SHARED_GID"}
        or name.startswith("WORKSPACE107_SLURM_")
        or name.startswith("WORKSPACE107_WORKER_")
    }
    if forbidden_api:
        raise TaskError(
            "API service contains Worker-only configuration: " + ", ".join(sorted(forbidden_api))
        )

    required_api = {"WORKSPACE107_STORAGE_GID"}
    missing_api = sorted(required_api - set(api_environment))
    if missing_api:
        raise TaskError("API service is missing storage configuration: " + ", ".join(missing_api))

    worker_environment = worker.get("environment", {})
    required_worker = {
        "WORKSPACE107_SCHEDULER",
        "WORKSPACE107_STORAGE_GID",
        "WORKSPACE107_SHARED_GID",
        "WORKSPACE107_SLURM_API_USER",
        "WORKSPACE107_SLURM_JWT",
        "WORKSPACE107_SLURM_API_SCHEMA_PROFILE",
    }
    missing_worker = sorted(required_worker - set(worker_environment))
    if missing_worker:
        raise TaskError("Worker service is missing configuration: " + ", ".join(missing_worker))
    storage_gid = str(api_environment["WORKSPACE107_STORAGE_GID"])
    if str(worker_environment["WORKSPACE107_STORAGE_GID"]) != storage_gid:
        raise TaskError("API and Worker must use the same canonical storage GID")
    if str(worker_environment["WORKSPACE107_SHARED_GID"]) != storage_gid:
        raise TaskError("Current local Run-tree shared GID must equal the canonical storage GID")
    for service_name, service in (("API", api), ("Worker", worker)):
        if storage_gid not in {str(value) for value in service.get("group_add", [])}:
            raise TaskError(f"{service_name} service must join the canonical storage GID")

    dependencies = worker.get("depends_on", {})
    if "db" not in dependencies or "api" in dependencies:
        raise TaskError("Worker must depend on PostgreSQL directly, not API health")
    health_command = json.dumps(worker.get("healthcheck", {}).get("test", []))
    if "8000" in health_command or "workspace107.worker" not in health_command:
        raise TaskError("Worker healthcheck must probe the Worker process, not API port 8000")


def install_hooks() -> None:
    heading("Git hooks")
    git("config", "core.hooksPath", ".githooks")
    print("Configured core.hooksPath=.githooks for this clone.")


class ApiClient:
    def __init__(self, base_url: str, user: str = "demo") -> None:
        self.base_url = base_url.rstrip("/")
        self.user = user

    def request(
        self,
        method: str,
        path: str,
        payload: object | None = None,
        *,
        binary: bool = False,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"X-User": self.user}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise TaskError(f"{method} {path} returned HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise TaskError(f"{method} {path} failed: {error.reason}") from error
        if binary:
            return content
        if not content:
            return None
        return json.loads(content)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return cast(int, listener.getsockname()[1])


def _selected_demo_port(smoke: bool) -> int:
    names = ["WORKSPACE107_SMOKE_PORT"] if smoke else ["WORKSPACE107_DEMO_PORT", "PORT"]
    for name in names:
        value = os.environ.get(name)
        if value:
            try:
                return int(value)
            except ValueError as error:
                raise TaskError(f"{name} must be an integer, got {value!r}") from error
    return _free_port()


def _wait_until_ready(url: str, process: subprocess.Popen[str], log_path: Path) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            log = log_path.read_text(encoding="utf-8", errors="replace")
            raise TaskError(f"Backend exited with code {return_code}:\n{log}")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    raise TaskError(f"Backend did not become ready at {url}:\n{log}")


def _stop_processes(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextmanager
def _smoke_admin_database() -> Iterator[str]:
    configured = os.environ.get("WORKSPACE107_DATABASE_URL", "")
    if configured.startswith("postgresql+"):
        yield configured
        return

    require_commands("docker")
    name = f"workspace107-smoke-postgres-{uuid.uuid4().hex}"
    port = _free_port()
    password = uuid.uuid4().hex
    run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--env",
            f"POSTGRES_PASSWORD={password}",
            "--publish",
            f"127.0.0.1:{port}:5432",
            "postgres:17-alpine",
        ],
        capture=True,
        quiet=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            probe = run(
                ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                capture=True,
                quiet=True,
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise TaskError("Temporary PostgreSQL container did not become ready")
        yield f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/postgres"
    finally:
        run(["docker", "rm", "--force", name], capture=True, quiet=True, check=False)


@contextmanager
def _temporary_smoke_database(admin_url: str) -> Iterator[str]:
    name = f"workspace107_smoke_{uuid.uuid4().hex}"
    environment = merged_environment(
        {
            "WORKSPACE107_SMOKE_ADMIN_DATABASE_URL": admin_url,
            "WORKSPACE107_SMOKE_DATABASE_NAME": name,
        }
    )
    created = backend_uv(
        "run",
        "python",
        "-m",
        "workspace107.tools.smoke_database",
        "create",
        env=environment,
        capture=True,
        quiet=True,
    ).stdout.strip()
    try:
        if not created.startswith("postgresql+"):
            raise TaskError("Smoke database helper did not return a PostgreSQL URL")
        yield created
    finally:
        backend_uv(
            "run",
            "python",
            "-m",
            "workspace107.tools.smoke_database",
            "drop",
            env=environment,
            capture=True,
            quiet=True,
        )


def _validated_api_base_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    try:
        parsed = urlsplit(candidate)
        valid_port = parsed.port is None or parsed.port > 0
    except ValueError:
        valid_port = False
        parsed = urlsplit("")
    valid = (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and valid_port
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.rstrip("/").endswith("/api/v1")
    )
    if not valid:
        raise TaskError("External smoke requires an HTTP(S) API URL ending in /api/v1")
    return candidate


def external_smoke(base_url: str) -> None:
    """Exercise a running API/Worker stack without owning its lifecycle or data."""
    heading("External stack core run smoke")
    evidence = _exercise_core_run(
        ApiClient(_validated_api_base_url(base_url), user="student"),
        verbose=False,
    )
    print("ok  external HTTP core run completed: " + json.dumps(evidence, sort_keys=True))


def demo(*, smoke: bool = False) -> None:
    heading("Isolated core run smoke" if smoke else "Core run demo")
    ensure_backend_dependencies(quiet=True)
    port = _selected_demo_port(smoke)
    base_url = f"http://127.0.0.1:{port}/api/v1"

    with (
        _smoke_admin_database() as database_url,
        tempfile.TemporaryDirectory(prefix="workspace107-demo-") as directory,
        _temporary_smoke_database(database_url) as isolated_database_url,
    ):
        workdir = Path(directory)
        server_log = workdir / "uvicorn.log"
        worker_log = workdir / "worker.log"
        environment = merged_environment(
            {
                "WORKSPACE107_ENV": "local",
                "WORKSPACE107_DATABASE_URL": isolated_database_url,
                "WORKSPACE107_STORAGE_ROOT": str((workdir / "storage").resolve()),
                "WORKSPACE107_SCHEDULER": "mock",
            }
        )
        backend_uv("run", "alembic", "upgrade", "head", env=environment, quiet=smoke)
        backend_uv(
            "run",
            "python",
            "-m",
            "workspace107.tools.seed",
            "--demo",
            env=environment,
            quiet=smoke,
        )

        server_command = [
            _backend_python_executable(),
            "-m",
            "uvicorn",
            "workspace107.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]
        worker_command = [_backend_python_executable(), "-m", "workspace107.worker"]
        with (
            server_log.open("w", encoding="utf-8") as server_output,
            worker_log.open("w", encoding="utf-8") as worker_output,
        ):
            server_process = subprocess.Popen(
                server_command,
                cwd=BACKEND_ROOT,
                env=environment,
                stdout=server_output,
                stderr=subprocess.STDOUT,
                text=True,
            )
            worker_process = subprocess.Popen(
                worker_command,
                cwd=BACKEND_ROOT,
                env=environment,
                stdout=worker_output,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                _wait_until_ready(f"{base_url}/health", server_process, server_log)
                _exercise_core_run(ApiClient(base_url, user="student"), verbose=not smoke)
            except Exception as error:
                server_output.flush()
                worker_output.flush()
                raise TaskError(
                    f"{error}\nAPI log:\n{server_log.read_text(errors='replace')}"
                    f"\nWorker log:\n{worker_log.read_text(errors='replace')}"
                ) from error
            finally:
                _stop_processes([worker_process, server_process])

    if smoke:
        print("ok  isolated HTTP core run completed")
    else:
        print("\nDemo complete: Project -> Version -> Run Snapshot -> logs -> Artifact.")


def _exercise_core_run(client: ApiClient, *, verbose: bool) -> dict[str, Any]:
    def say(label: str) -> None:
        if verbose:
            print(f"\n{label}")

    say("1. Resolve explicit demo User Group")
    home = client.request("GET", "/me")
    demo_group = next(
        (group for group in home["user_groups"] if group["id"] == DEMO_USER_GROUP_ID),
        None,
    )
    if demo_group is None:
        raise TaskError(f"Demo User Group {DEMO_USER_GROUP_ID!r} is not visible to the demo user")
    user_group_id = demo_group["id"]
    if verbose:
        print(f"User Group: {user_group_id}")

    say("2. Create Project and source file")
    project = client.request(
        "POST",
        "/projects",
        {
            "owner": {"kind": "user_group", "id": user_group_id},
            "name": "Demo Project",
            "description": "Isolated workflow demo",
        },
    )
    project_id = project["id"]
    source = (
        "import json, os, pathlib\n"
        "pathlib.Path('outputs').mkdir(exist_ok=True)\n"
        "epochs = int(os.environ['EPOCHS'])\n"
        "print(f'epochs={epochs}', flush=True)\n"
        "pathlib.Path('outputs/metrics.json').write_text("
        "json.dumps({'epochs': epochs, 'accuracy': 0.93}), encoding='utf-8')\n"
    )
    client.request("PUT", f"/projects/{project_id}/files", {"path": "train.py", "content": source})
    if verbose:
        print(f"Project: {project_id}")

    say("3. Save immutable Project Version")
    version = client.request(
        "POST", f"/projects/{project_id}/versions", {"message": "Initial version"}
    )
    if verbose:
        print(f"Version: {version['label']}")

    say("4. Create Run Configuration")
    client.request(
        "PUT",
        f"/projects/{project_id}/variables",
        {"name": "EPOCHS", "value": "3"},
    )
    environments = client.request("GET", "/catalog/environments")
    environment_version_id = next(
        version["id"]
        for environment in environments
        if environment["owner"]["id"] == user_group_id
        for version in environment["versions"]
        if version["available"]
    )
    configuration = client.request(
        "POST",
        f"/projects/{project_id}/run-configurations",
        {
            "name": "Default run",
            "command": "python train.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "environment_variables": {"EPOCHS": "${{ vars.EPOCHS }}"},
            "artifact_rules": [{"path": "outputs", "name": "Training result", "optional": False}],
        },
    )

    say("5. Preflight and submit Run")
    preflight = client.request(
        "POST",
        f"/projects/{project_id}/runs/preflight",
        {"run_configuration_id": configuration["id"]},
    )
    if not preflight["ok"]:
        raise TaskError(f"Run preflight failed: {preflight}")
    run = client.request(
        "POST",
        f"/projects/{project_id}/runs",
        {"run_configuration_id": configuration["id"], "name": "Demo run"},
    )
    run_id = run["id"]

    say("6. Wait for scheduler reconciliation")
    deadline = time.monotonic() + 30
    status = "queued"
    detail: dict[str, Any] = {}
    while time.monotonic() < deadline:
        detail = client.request("GET", f"/runs/{run_id}")
        status = detail["run"]["status"]
        if verbose:
            print(f"status: {status}")
        if status in TERMINAL_RUN_STATUSES:
            break
        time.sleep(0.2)
    if status != "succeeded":
        raise TaskError(f"Demo Run did not succeed; final status is {status!r}")

    say("7. Verify logs and Artifact")
    logs = client.request("GET", f"/runs/{run_id}/logs")
    log_text = "\n".join(chunk["content"] for chunk in logs)
    if "epochs=3" not in log_text:
        raise TaskError("Run logs did not contain the expected output")
    artifact_id = detail["artifacts"][0]["id"]
    files = client.request("GET", f"/artifacts/{artifact_id}/files")
    metric_file = next((item for item in files if item["path"] == "metrics.json"), None)
    if metric_file is None:
        raise TaskError("Artifact does not contain metrics.json")
    downloaded = client.request(
        "GET", f"/artifacts/{artifact_id}/download?path=metrics.json", binary=True
    )
    metrics = json.loads(downloaded)
    if metrics != {"epochs": 3, "accuracy": 0.93}:
        raise TaskError(f"Unexpected Artifact content: {metrics}")
    if metric_file["size"] != len(downloaded):
        raise TaskError("Artifact size does not match the file listing")
    if verbose:
        print(log_text.rstrip())
        print(f"Artifact metrics.json: {metrics}")
        print(f"Run Snapshot: {detail['snapshot']}")
    return {
        "run_id": run_id,
        "status": status,
        "artifact_id": artifact_id,
        "artifact_path": metric_file["path"],
        "artifact_size": metric_file["size"],
        "artifact": metrics,
    }


def _journal_fields(path: Path) -> tuple[str, dict[str, str]]:
    title = path.stem
    fields: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line_number == 0 and line.startswith("#"):
            title = line.lstrip("# ")
        match = JOURNAL_FIELD.match(line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return title, fields


def journal(
    *, include_all: bool = False, new_slug: str | None = None, context: str = "未指定"
) -> None:
    journal_dir = REPO_ROOT / "docs" / "journal"
    if new_slug is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", new_slug):
            raise TaskError("Journal slug must contain only letters, digits, `_`, or `-`.")
        journal_dir.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now().astimezone()
        owner_result = git("config", "user.name", capture=True, check=False)
        owner = owner_result.stdout.strip() or "unknown"
        path = journal_dir / f"{now:%Y-%m-%d-%H%M}-{new_slug}.md"
        if path.exists():
            raise TaskError(f"Journal entry already exists: {path.relative_to(REPO_ROOT)}")
        path.write_text(
            f"# {new_slug}\n\n"
            f"- 状态：进行中\n- 认领：{owner}\n- 上下文：{context}\n"
            f"- 开始：{now:%Y-%m-%d %H:%M %z}\n\n"
            "## 意图\n<要达成什么；关联 Issue 或规则标识>\n\n"
            "## 预期改动\n- <文件路径>\n\n"
            "## 仓外副作用\n无。\n\n"
            "## 回退方式\ngit revert <commit>\n\n"
            "## 验收\nmake check\n\n"
            "## 禁区\n- 不动 <其他上下文>\n- 不加依赖\n",
            encoding="utf-8",
        )
        print(path.relative_to(REPO_ROOT))
        return

    heading("Work journal")
    paths = (
        sorted(path for path in journal_dir.glob("*.md") if path.name != "README.md")
        if journal_dir.is_dir()
        else []
    )
    if not paths:
        print("No journal entries.")
        return
    now = time.time()
    visible = 0
    for path in paths:
        title, fields = _journal_fields(path)
        status = fields.get("状态", "未知")
        if not include_all and status not in {"进行中", "未知"}:
            continue
        visible += 1
        age_hours = max(0, int((now - path.stat().st_mtime) / 3600))
        owner = fields.get("认领", "unknown")
        context = fields.get("上下文", "未指定")
        stale = " STALE" if status == "进行中" and age_hours >= 24 else ""
        print(
            f"- [{status}{stale}] {title} | {owner} | {context} | "
            f"{age_hours}h | {path.relative_to(REPO_ROOT)}"
        )
    if visible == 0:
        print("No in-progress journal entries.")


def _git_base(explicit: str | None) -> str:
    if explicit:
        result = git("rev-parse", "--verify", explicit, capture=True, check=False)
        if result.returncode != 0:
            raise TaskError(f"Unknown audit base: {explicit}")
        return explicit
    for candidate in ("origin/main", "origin/master", "main", "master", "HEAD~1"):
        if git("rev-parse", "--verify", candidate, capture=True, check=False).returncode == 0:
            return candidate
    raise TaskError("Could not determine an audit base")


def audit(*, base: str | None = None, max_lines: int = 400) -> None:
    selected = _git_base(base)
    names = git("diff", "--name-only", f"{selected}...HEAD", capture=True).stdout.splitlines()
    numstat = git("diff", "--numstat", f"{selected}...HEAD", capture=True).stdout.splitlines()
    changed_lines = 0
    for line in numstat:
        added, deleted, path = line.split("\t", 2)
        if any(token in path for token in ("lock", ".generated.")):
            continue
        if added.isdigit() and deleted.isdigit():
            changed_lines += int(added) + int(deleted)

    heading("Review audit")
    print(f"Base: {selected}")
    print(f"Changed files: {len(names)}; review lines: {changed_lines}/{max_lines}")
    flags: list[str] = []
    sensitive_patterns = {
        "API contract": ("contracts/", "frontend/src/api/schema.d.ts"),
        "database migration": ("backend/migrations/",),
        "authentication or authorization": (
            "auth",
            "permission",
            "role",
            "token",
            "session",
        ),
        "dependency manifest": ("pyproject.toml", "package.json"),
        "secret/config boundary": (".env", "secret", "credential", ".pem", ".key"),
        "architecture decision": ("docs/decisions/",),
    }
    lowered = [name.lower() for name in names]
    for label, patterns in sensitive_patterns.items():
        if any(any(pattern.lower() in name for pattern in patterns) for name in lowered):
            flags.append(label)
    if changed_lines > max_lines:
        flags.append("diff exceeds the review-size budget")
    if flags:
        print("Human review required for:")
        for flag in flags:
            print(f"  - {flag}")
        raise TaskError("Audit found review-gate signals; inspect them before merge.")
    print("No automatic review-gate signal found. Human review is still required.")


def review() -> None:
    heading("Milestone review signals")
    roots = [BACKEND_ROOT / "src", BACKEND_ROOT / "tests", FRONTEND_ROOT / "src"]
    skip_pattern = re.compile(r"@pytest\.mark\.skip|\.(?:skip|todo)\(")
    todo_pattern = re.compile(r"\b(?:TODO|FIXME|HACK)\b")
    skipped: list[Path] = []
    todos: list[Path] = []
    large: list[tuple[int, Path]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            if skip_pattern.search(text):
                skipped.append(path)
            if todo_pattern.search(text):
                todos.append(path)
            if len(lines) > 400:
                large.append((len(lines), path))
    print(f"Skipped-test files: {len(skipped)}")
    print(f"TODO/FIXME/HACK files: {len(todos)}")
    print(f"Source files over 400 lines: {len(large)}")
    for count, path in sorted(large, reverse=True)[:8]:
        print(f"  - {path.relative_to(REPO_ROOT)} ({count} lines)")
    print("Human review must still check product scope, recorded debt, and the next major risk.")


def doctor() -> None:
    heading("Engineering baseline doctor")
    required_files = [
        "AGENTS.md",
        "docs/product/design.md",
        "docs/product/deferred.md",
        "docs/contributing/git-workflow.md",
        "docs/operations/deployment.md",
        "docs/operations/107-cluster.md",
        "deploy/README.md",
        "deploy/compose.yaml",
        "docs/README.md",
        "docs/decisions/README.md",
        "docs/journal/README.md",
        "docs/references/README.md",
        "docs/archive/README.md",
        "archive/README.md",
        "Makefile",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".env.example",
        ".github/workflows/ci.yml",
        "scripts/workspace.py",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "frontend/pnpm-workspace.yaml",
        ".node-version",
        "contracts/README.md",
        "contracts/openapi.json",
        "frontend/src/api/schema.d.ts",
    ]
    failures: list[str] = []
    for relative in required_files:
        if (REPO_ROOT / relative).exists():
            print(f"ok    {relative}")
        else:
            failures.append(relative)
            print(f"FAIL  {relative}")
    for command in ("git", "uv", "node", "pnpm"):
        try:
            resolved = resolve_executable(command)
        except TaskError:
            failures.append(f"command:{command}")
            print(f"FAIL  command {command}")
        else:
            print(f"ok    command {command}: {resolved}")

    for command, expected_major in (("node", NODE_MAJOR), ("pnpm", PNPM_MAJOR)):
        try:
            cwd = FRONTEND_ROOT if command == "pnpm" else REPO_ROOT
            version = require_major_version(command, expected_major, cwd=cwd)
        except TaskError as error:
            failures.append(f"version:{command}")
            print(f"FAIL  {error}")
        else:
            print(f"ok    {command} version: {version}")

    tracked_env = git("ls-files", "--error-unmatch", ".env", capture=True, check=False)
    if tracked_env.returncode == 0:
        failures.append("tracked .env")
        print("FAIL  .env is tracked; rotate any contained credentials")
    else:
        print("ok    .env is not tracked")
    history = git("log", "--all", "--oneline", "--", ".env", capture=True, check=False)
    if history.stdout.strip():
        failures.append(".env in history")
        print("FAIL  .env appears in Git history; treat contained credentials as exposed")
    else:
        print("ok    .env does not appear in Git history")

    hooks = git("config", "--get", "core.hooksPath", capture=True, check=False).stdout.strip()
    if hooks == ".githooks":
        print("ok    repository hooks are enabled")
    else:
        print("WARN  hooks are not enabled; run `make hooks`")
    if failures:
        raise TaskError("Engineering baseline has blocking gaps: " + ", ".join(failures))
    print("Baseline files and local prerequisites are present.")
