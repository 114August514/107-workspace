"""本地存储配置的目录准备。

新克隆的仓库里没有 var/（在 .gitignore 中）。README 让新成员执行的第一条命令
就是 `alembic upgrade head`，如果目录不存在它会直接失败。
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from workspace107.config import Settings
from workspace107.domain.errors import ValidationFailed
from workspace107.infrastructure.storage.local import LocalStorage


def test_initial_setup_creates_storage_and_database_directories(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'var' / 'test.db'}",
        storage_root=tmp_path / "var" / "storage",
    )
    assert not (tmp_path / "var").exists()

    settings.ensure_local_directories()

    assert (tmp_path / "var" / "storage").is_dir()
    assert (tmp_path / "var").is_dir()
    assert stat.S_IMODE((tmp_path / "var" / "storage").stat().st_mode) == 0o750


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


@pytest.mark.parametrize("mode", [0o700, 0o770, 0o775])
def test_existing_storage_root_mode_drift_is_rejected(tmp_path: Path, mode: int) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(mode=mode)
    storage_root.chmod(mode)
    settings = Settings(storage_root=storage_root)

    with pytest.raises(ValueError, match="mode must be exactly 0o750"):
        settings.ensure_local_directories()


def test_existing_service_owned_0755_storage_root_is_tightened(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(mode=0o755)
    storage_root.chmod(0o755)

    Settings(storage_root=storage_root).ensure_local_directories()

    assert stat.S_IMODE(storage_root.stat().st_mode) == 0o750


def test_storage_root_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o750)
    storage_root = tmp_path / "storage"
    storage_root.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="cannot be a symbolic link"):
        Settings(storage_root=storage_root).ensure_local_directories()


def test_storage_root_ancestor_symlink_is_rejected_without_touching_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o750)
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="ancestors must be real directories"):
        Settings(storage_root=linked_parent / "storage").ensure_local_directories()

    assert sentinel.read_text() == "keep"
    assert not (outside / "storage").exists()


def test_group_writable_storage_parent_is_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "shared-parent"
    parent.mkdir(mode=0o770)
    parent.chmod(0o770)

    with pytest.raises(ValueError, match="ancestor is writable"):
        Settings(storage_root=parent / "storage").ensure_local_directories()

    assert not (parent / "storage").exists()


def test_storage_and_run_tree_gid_must_match() -> None:
    with pytest.raises(ValueError, match="must match"):
        Settings(storage_gid=13001, shared_gid=13002)


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


def test_slurm_worker_fails_closed_without_per_run_isolation(tmp_path: Path) -> None:
    settings = Settings(
        env="production",
        database_url="postgresql+asyncpg://user:pw@localhost:5432/workspace107",
        storage_root=tmp_path / "storage",
        scheduler="slurm",
        shared_gid=13001,
    )

    with pytest.raises(ValueError, match="per-Run filesystem isolation"):
        settings.ensure_worker_configuration()


@pytest.mark.asyncio
async def test_shared_resource_blobs_are_service_private(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir(mode=0o750)
    storage = LocalStorage(root)

    content_hash = await storage.write_blob(b"private content")
    shard = root / "blobs" / content_hash[:2]
    blob = shard / content_hash

    assert stat.S_IMODE((root / "blobs").stat().st_mode) == 0o700
    assert stat.S_IMODE(shard.stat().st_mode) == 0o700
    assert stat.S_IMODE(blob.stat().st_mode) == 0o600
    assert await storage.read_blob(content_hash) == b"private content"


def test_blob_store_rejects_symbolic_link(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir(mode=0o750)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "blobs").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValidationFailed, match="symbolic link"):
        LocalStorage(root)
