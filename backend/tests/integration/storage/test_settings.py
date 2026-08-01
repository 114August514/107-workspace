"""本地存储配置的目录准备。

新克隆的仓库里没有 var/（在 .gitignore 中）。README 让新成员执行的第一条命令
就是 `alembic upgrade head`，如果目录不存在它会直接失败。
"""

from __future__ import annotations

from pathlib import Path

from workspace107.config import Settings


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
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'var' / 'test.db'}",
        storage_root=tmp_path / "var" / "storage",
    )
    settings.ensure_local_directories()
    settings.ensure_local_directories()


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
