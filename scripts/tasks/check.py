"""Cross-platform setup, quality, test, and build tasks."""

from __future__ import annotations

import sys
from collections.abc import Callable

from .common import (
    REPO_ROOT,
    TaskError,
    backend_uv,
    ensure_backend_dependencies,
    ensure_frontend_dependencies,
    frontend_pnpm,
    heading,
    run,
)
from .contract import check_contract

Target = str


def _uses_backend(target: Target) -> bool:
    return target in {"all", "backend"}


def _uses_frontend(target: Target) -> bool:
    return target in {"all", "frontend"}


def _prepare(target: Target, *, force: bool = False) -> None:
    if _uses_backend(target) or target == "contract":
        ensure_backend_dependencies(quiet=not force)
    if _uses_frontend(target) or target == "contract":
        ensure_frontend_dependencies(force=force, quiet=not force)


def _run_frontend_tests() -> None:
    # pnpm 11 passes an extra `--` through, so Vitest treats `--run` as a filter.
    frontend_pnpm("run", "test", "--run")


def _run_cas_revproxy_tests() -> None:
    backend_uv(
        "run",
        "--with",
        "flask",
        "pytest",
        "-q",
        str(REPO_ROOT / "deploy/cas-revproxy/tests"),
    )


def setup(target: Target = "all") -> None:
    heading(f"Setup ({target})")
    _prepare(target, force=True)


def format_code(target: Target = "all", *, check_only: bool = False) -> None:
    heading("Format check" if check_only else "Format")
    _prepare(target)
    if _uses_backend(target):
        arguments = ["run", "ruff", "format"]
        if check_only:
            arguments.append("--check")
        backend_uv(*arguments, ".")
    if _uses_frontend(target):
        script = "format:check" if check_only else "format"
        frontend_pnpm("run", script)


def lint(target: Target = "all") -> None:
    heading("Lint")
    _prepare(target)
    if _uses_backend(target):
        backend_uv("run", "ruff", "check", ".")
    if _uses_frontend(target):
        frontend_pnpm("run", "lint")


def typecheck(target: Target = "all") -> None:
    heading("Type check")
    _prepare(target)
    if target == "backend":
        print("skip  backend has no configured type checker")
        return
    if _uses_frontend(target):
        frontend_pnpm("run", "typecheck")


def test(target: Target = "all") -> None:
    heading("Tests")
    _prepare(target)
    if _uses_backend(target):
        backend_uv("run", "pytest", "-q")
        _run_cas_revproxy_tests()
    if _uses_frontend(target):
        _run_frontend_tests()


def build(target: Target = "all") -> None:
    heading("Build")
    _prepare(target)
    if _uses_backend(target):
        backend_uv("build")
    if _uses_frontend(target):
        frontend_pnpm("run", "build")


def run_check(target: Target = "all") -> None:
    heading(f"Repository check ({target})")
    _prepare(target)

    steps: list[tuple[str, Callable[[], None]]] = []
    if target == "all":
        steps.extend(
            [
                (
                    "workflow lint",
                    lambda: backend_uv("run", "ruff", "check", "../scripts"),
                ),
                (
                    "workflow format",
                    lambda: backend_uv("run", "ruff", "format", "--check", "../scripts"),
                ),
                (
                    "workflow tests",
                    lambda: run(
                        [
                            sys.executable,
                            "-m",
                            "unittest",
                            "discover",
                            "-s",
                            "scripts/tests",
                            "-v",
                        ],
                        cwd=REPO_ROOT,
                    ),
                ),
            ]
        )
    if _uses_backend(target):
        steps.extend(
            [
                ("backend lint", lambda: backend_uv("run", "ruff", "check", ".")),
                (
                    "backend format",
                    lambda: backend_uv("run", "ruff", "format", "--check", "."),
                ),
                ("backend tests", lambda: backend_uv("run", "pytest", "-q")),
                ("cas revproxy tests", _run_cas_revproxy_tests),
            ]
        )
    if _uses_frontend(target):
        steps.extend(
            [
                (
                    "frontend format",
                    lambda: frontend_pnpm("run", "format:check"),
                ),
                ("frontend lint", lambda: frontend_pnpm("run", "lint")),
                (
                    "frontend typecheck",
                    lambda: frontend_pnpm("run", "typecheck"),
                ),
                (
                    "frontend tests",
                    _run_frontend_tests,
                ),
                ("frontend build", lambda: frontend_pnpm("run", "build")),
            ]
        )
    if target in {"all", "contract"}:
        steps.append(("API contract", check_contract))

    failures: list[str] = []
    for label, action in steps:
        print(f"\n--- {label}", flush=True)
        try:
            action()
        except TaskError as error:
            failures.append(label)
            print(f"FAIL  {label}: {error}")
        else:
            print(f"ok    {label}")

    if failures:
        formatted = "\n".join(f"  - {label}" for label in failures)
        raise TaskError(f"Repository check failed:\n{formatted}")
    print("\nAll requested checks passed.")
