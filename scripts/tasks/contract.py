"""Generate and verify the backend-to-frontend API contract."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .common import (
    FRONTEND_ROOT,
    REPO_ROOT,
    TaskError,
    backend_uv,
    ensure_backend_dependencies,
    ensure_frontend_dependencies,
    frontend_pnpm,
    heading,
)

OPENAPI_PATH = REPO_ROOT / "docs" / "api" / "openapi.json"
SCHEMA_PATH = FRONTEND_ROOT / "src" / "api" / "schema.d.ts"


def _normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _generate(openapi_path: Path, schema_path: Path) -> None:
    openapi_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.parent.mkdir(parents=True, exist_ok=True)

    backend_uv(
        "run",
        "python",
        "-m",
        "workspace107.tools.export_openapi",
        str(openapi_path),
    )
    frontend_pnpm(
        "exec",
        "openapi-typescript",
        str(openapi_path),
        "-o",
        str(schema_path),
    )


def sync_contract() -> None:
    heading("Synchronize API contract")
    ensure_backend_dependencies(quiet=True)
    ensure_frontend_dependencies(quiet=True)
    _generate(OPENAPI_PATH, SCHEMA_PATH)
    print("Synchronized:")
    print(f"  {OPENAPI_PATH.relative_to(REPO_ROOT)}")
    print(f"  {SCHEMA_PATH.relative_to(REPO_ROOT)}")


def check_contract() -> None:
    heading("API contract")
    missing = [path for path in (OPENAPI_PATH, SCHEMA_PATH) if not path.is_file()]
    if missing:
        formatted = ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing)
        raise TaskError(
            f"Missing generated contract file(s): {formatted}. Run `make contract` and commit them."
        )

    ensure_backend_dependencies(quiet=True)
    ensure_frontend_dependencies(quiet=True)
    with tempfile.TemporaryDirectory(prefix="workspace107-contract-") as directory:
        temporary_root = Path(directory)
        generated_openapi = temporary_root / "openapi.json"
        generated_schema = temporary_root / "schema.d.ts"
        _generate(generated_openapi, generated_schema)

        changed = []
        if _normalized_text(generated_openapi) != _normalized_text(OPENAPI_PATH):
            changed.append(OPENAPI_PATH.relative_to(REPO_ROOT))
        if _normalized_text(generated_schema) != _normalized_text(SCHEMA_PATH):
            changed.append(SCHEMA_PATH.relative_to(REPO_ROOT))

    if changed:
        formatted = "\n".join(f"  - {path}" for path in changed)
        raise TaskError(
            "Generated API contract differs from the committed files:\n"
            f"{formatted}\nRun `make contract` and commit both generated files."
        )
    print("ok  OpenAPI and frontend types match the backend")
