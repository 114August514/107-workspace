"""本地存储配置的目录准备。

新克隆的仓库里没有 var/（在 .gitignore 中）。README 让新成员执行的第一条命令
就是 `alembic upgrade head`，如果目录不存在它会直接失败。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from workspace107.config import Settings
from workspace107.main import create_app


def test_initial_setup_creates_storage_and_database_directories(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'var' / 'test.db'}",
        storage_root=tmp_path / "var" / "storage",
    )
    assert not (tmp_path / "var").exists()

    settings.ensure_local_directories()

    assert (tmp_path / "var" / "storage").is_dir()
    assert (tmp_path / "var").is_dir()


def test_directory_setup_is_idempotent(tmp_path: Path) -> None:
    storage_root = tmp_path / "var" / "storage"
    database_root = tmp_path / "var"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'var' / 'test.db'}",
        storage_root=storage_root,
    )
    settings.ensure_local_directories()
    settings.ensure_local_directories()

    assert storage_root.is_dir()
    assert database_root.is_dir()


def test_non_sqlite_url_does_not_resolve_file_path(tmp_path: Path) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pw@localhost:5432/workspace107",
        storage_root=tmp_path / "storage",
    )
    assert settings.sqlite_file is None

    settings.ensure_local_directories()
    assert (tmp_path / "storage").is_dir()


def test_in_memory_database_has_no_file_path(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        storage_root=tmp_path / "storage",
    )
    assert settings.sqlite_file is None
    settings.ensure_local_directories()
    assert (tmp_path / "storage").is_dir()


def test_local_mock_uses_current_gid_when_not_explicit() -> None:
    assert Settings().resolved_shared_gid == os.getegid()


def test_api_accepts_worker_only_slurm_configuration_as_unresolved() -> None:
    settings = Settings(env="production", scheduler="slurm")
    assert create_app(settings).title == "107 Workspace API"


def test_worker_configuration_fails_fast_for_mock_production_and_incomplete_slurm() -> None:
    with pytest.raises(ValueError, match="Mock scheduler is only allowed"):
        Settings(env="production", scheduler="mock").ensure_worker_configuration()
    with pytest.raises(ValueError, match="WORKSPACE107_SHARED_GID"):
        Settings(scheduler="slurm").ensure_worker_configuration()
