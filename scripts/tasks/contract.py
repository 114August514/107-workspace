"""Generate and verify the backend-to-frontend API contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
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

OPENAPI_PATH = REPO_ROOT / "backend" / "contracts" / "openapi.json"
CONSUMED_PATH = REPO_ROOT / "frontend" / "contracts" / "openapi.json"
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
    CONSUMED_PATH.write_bytes(OPENAPI_PATH.read_bytes())
    backend_root = OPENAPI_PATH.parents[1]
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=backend_root, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=backend_root, text=True
        ).strip()
    )
    provenance = {
        "repository": "107-backend",
        "commit": revision,
        "working_tree_dirty": dirty,
        "sha256": hashlib.sha256(OPENAPI_PATH.read_bytes()).hexdigest(),
    }
    CONSUMED_PATH.with_name("source.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print("Synchronized:")
    print(f"  {OPENAPI_PATH.relative_to(REPO_ROOT)}")
    print(f"  {SCHEMA_PATH.relative_to(REPO_ROOT)}")


def check_contract() -> None:
    heading("API contract")
    missing = [path for path in (OPENAPI_PATH, CONSUMED_PATH, SCHEMA_PATH) if not path.is_file()]
    if missing:
        formatted = ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing)
        raise TaskError(
            f"Missing generated contract file(s): {formatted}. Run `make contract` and commit them."
        )

    ensure_backend_dependencies(quiet=True)
    ensure_frontend_dependencies(quiet=True)
    source = json.loads(CONSUMED_PATH.with_name("source.json").read_text(encoding="utf-8"))
    if source["working_tree_dirty"]:
        raise TaskError("Commit backend changes, then run make contract again")
    recorded = subprocess.check_output(
        ["git", "show", f"{source['commit']}:contracts/openapi.json"],
        cwd=OPENAPI_PATH.parents[1],
    )
    if recorded != CONSUMED_PATH.read_bytes():
        raise TaskError("Frontend contract differs from its recorded backend commit")
    if source["sha256"] != hashlib.sha256(recorded).hexdigest():
        raise TaskError("Frontend contract checksum differs from its source record")
    with tempfile.TemporaryDirectory(prefix="workspace107-contract-") as directory:
        temporary_root = Path(directory)
        generated_openapi = temporary_root / "openapi.json"
        generated_schema = temporary_root / "schema.d.ts"
        _generate(generated_openapi, generated_schema)

        changed = []
        if _normalized_text(CONSUMED_PATH) != _normalized_text(OPENAPI_PATH):
            changed.append(CONSUMED_PATH.relative_to(REPO_ROOT))
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
