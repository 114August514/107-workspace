"""Shared process and path helpers for repository workflow tasks."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_ROOT = REPO_ROOT / "frontend"
NODE_MAJOR = 24
PNPM_MAJOR = 11


class TaskError(RuntimeError):
    """A user-facing workflow failure with a stable process exit code."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def heading(label: str) -> None:
    print(f"\n==> {label}", flush=True)


def command_text(command: Sequence[str | os.PathLike[str]]) -> str:
    values = [os.fspath(value) for value in command]
    if os.name == "nt":
        return subprocess.list2cmdline(values)
    return shlex.join(values)


def resolve_executable(name: str, *, path: str | None = None) -> str:
    resolved = shutil.which(name, path=path)
    if resolved is None:
        raise TaskError(f"Missing required command: {name}")
    return resolved


def require_commands(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise TaskError("Missing required command(s): " + ", ".join(missing))


def _process_environment(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    if overrides is not None:
        environment.update(overrides)

    path = environment.get("PATH")
    if not path or not environment.get("UV_RUN_RECURSION_DEPTH"):
        return environment

    entries = path.split(os.pathsep)
    interpreter_dir = os.path.normcase(os.path.abspath(Path(sys.executable).parent))
    normalized_entries = [os.path.normcase(os.path.abspath(entry)) for entry in entries]
    if (
        normalized_entries
        and normalized_entries[0] == interpreter_dir
        and interpreter_dir in normalized_entries[1:]
    ):
        # uv prepends the Python directory even when it already exists later in PATH.
        # Removing only that duplicate restores the caller's tool priority.
        environment["PATH"] = os.pathsep.join(entries[1:])
    return environment


def run(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path = REPO_ROOT,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
    quiet: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    values = [os.fspath(value) for value in command]
    if not values:
        raise ValueError("command cannot be empty")

    process_env = _process_environment(env)
    values[0] = resolve_executable(values[0], path=process_env.get("PATH"))
    if not quiet:
        print(f"$ {command_text(values)}", flush=True)

    try:
        return subprocess.run(
            values,
            cwd=cwd,
            env=process_env,
            check=check,
            text=True,
            capture_output=capture,
        )
    except subprocess.CalledProcessError as error:
        if capture:
            if error.stdout:
                print(error.stdout, end="", file=sys.stdout)
            if error.stderr:
                print(error.stderr, end="", file=sys.stderr)
        raise TaskError(
            f"Command failed with exit code {error.returncode}: {command_text(values)}",
            exit_code=error.returncode or 1,
        ) from error


def git(
    *arguments: str, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(["git", *arguments], capture=capture, check=check, quiet=capture)


def backend_uv(*arguments: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return run(["uv", *arguments], cwd=BACKEND_ROOT, **kwargs)


def frontend_pnpm(*arguments: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return run(["pnpm", *arguments], cwd=FRONTEND_ROOT, **kwargs)


def _major_version(version: str) -> int:
    match = re.match(r"^v?(\d+)(?:\.|$)", version.strip())
    if match is None:
        raise TaskError(f"Could not parse tool version: {version!r}")
    return int(match.group(1))


def require_major_version(name: str, expected: int, *, cwd: Path = REPO_ROOT) -> str:
    result = run([name, "--version"], cwd=cwd, capture=True, quiet=True)
    version = result.stdout.strip()
    actual = _major_version(version)
    if actual != expected:
        raise TaskError(f"{name} {expected}.x is required; found {version}")
    return version


def ensure_backend_dependencies(*, quiet: bool = False) -> None:
    arguments = ["sync", "--frozen", "--all-extras"]
    if quiet:
        arguments.append("--quiet")
    backend_uv(*arguments)


def ensure_frontend_dependencies(*, force: bool = False, quiet: bool = False) -> None:
    require_major_version("node", NODE_MAJOR)
    require_major_version("pnpm", PNPM_MAJOR, cwd=FRONTEND_ROOT)
    if force or not (FRONTEND_ROOT / "node_modules" / ".pnpm").is_dir():
        arguments = ["install", "--frozen-lockfile"]
        if quiet:
            arguments.append("--reporter=silent")
        frontend_pnpm(*arguments)


def merged_environment(values: Mapping[str, str]) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(values)
    return environment
