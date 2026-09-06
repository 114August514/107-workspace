"""Load repository .env files for local workflow commands."""

from __future__ import annotations

import os
from pathlib import Path

from .common import BACKEND_ROOT, REPO_ROOT

# Flask / cas-revproxy names <- WORKSPACE107_* names in .env.example.
AUTH_ENV_ALIASES: tuple[tuple[str, str], ...] = (
    ("SECRET_KEY", "WORKSPACE107_AUTH_SECRET_KEY"),
    ("PUBLIC_ORIGIN", "WORKSPACE107_PUBLIC_ORIGIN"),
    ("SESSION_COOKIE_SECURE", "WORKSPACE107_SESSION_COOKIE_SECURE"),
    ("HTTPS_PROXY", "WORKSPACE107_HTTPS_PROXY"),
    ("CAS_LOGIN_URL", "WORKSPACE107_CAS_LOGIN_URL"),
    ("CAS_VALIDATE_URL", "WORKSPACE107_CAS_VALIDATE_URL"),
    ("LOCAL_ADMIN_USERNAME", "WORKSPACE107_LOCAL_ADMIN_USERNAME"),
    ("LOCAL_ADMIN_DISPLAY_NAME", "WORKSPACE107_LOCAL_ADMIN_DISPLAY_NAME"),
    ("LOCAL_ADMIN_PASSWORD", "WORKSPACE107_LOCAL_ADMIN_PASSWORD"),
    ("LOCAL_ADMIN_PASSWORD_HASH", "WORKSPACE107_LOCAL_ADMIN_PASSWORD_HASH"),
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_local_env_files() -> dict[str, str]:
    """Apply root `.env` then `backend/.env`. Existing process env wins."""

    loaded: dict[str, str] = {}
    for path in (REPO_ROOT / ".env", BACKEND_ROOT / ".env"):
        if path.is_file():
            loaded.update(parse_env_file(path))
    for key, value in loaded.items():
        os.environ.setdefault(key, value)
    return loaded


def apply_auth_env_aliases(environment: dict[str, str]) -> dict[str, str]:
    """Fill Flask/cas-revproxy names from WORKSPACE107_* when the short name is empty."""

    merged = dict(environment)
    for short_name, prefixed in AUTH_ENV_ALIASES:
        if not merged.get(short_name) and merged.get(prefixed):
            merged[short_name] = merged[prefixed]
    if not merged.get("HTTPS_PROXY") and merged.get("https_proxy"):
        merged["HTTPS_PROXY"] = merged["https_proxy"]
    return merged
