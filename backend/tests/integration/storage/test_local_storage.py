"""本地存储 Adapter 的只读权限行为。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from workspace107.domain.errors import ValidationFailed
from workspace107.infrastructure.storage import local as local_module
from workspace107.infrastructure.storage.local import LocalStorage


def test_makes_directories_and_files_readonly(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "dataset"
    nested.mkdir(parents=True)
    content = nested / "sample.txt"
    content.write_text("data", encoding="utf-8")

    chmod_calls: dict[Path, int] = {}

    def record_chmod(path: Path, mode: int) -> None:
        chmod_calls[path] = mode

    monkeypatch.setattr(Path, "chmod", record_chmod)
    local_module._make_readonly(root)
    assert chmod_calls == {
        root: local_module.READONLY_DIR,
        nested: local_module.READONLY_DIR,
        content: local_module.READONLY_FILE,
    }


@pytest.mark.asyncio
async def test_temporary_files_are_materialized_and_cleaned_after_failure(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "storage")
    content_hash = await storage.write_blob(b"print('saved')\n")

    with pytest.raises(RuntimeError, match="analysis failed"):
        async with storage.materialize_temporary_files([("src/main.py", content_hash)]) as root:
            assert (root / "src/main.py").read_bytes() == b"print('saved')\n"
            raise RuntimeError("analysis failed")

    assert not any((tmp_path / "storage" / "temporary").iterdir())


def _staging_root(storage_root: Path, prepare_key: str) -> Path:
    """用 prepare_project_sync 返回的公开相对 key 定位 actor 暂存目录。"""
    return storage_root / "project-sync" / prepare_key


@pytest.mark.asyncio
async def test_collect_rejects_symlinked_staging_root_escape(tmp_path: Path) -> None:
    """scan 后把 actor 暂存目录换成指向外部的符号链接时，读取必须拒绝而不是跟随。"""
    storage = LocalStorage(tmp_path / "storage")
    key = await storage.prepare_project_sync("proj-1", "alice")
    root = _staging_root(tmp_path / "storage", key)

    # 合法内容先就位，攻击者在 scan/apply 之间把整个 actor 目录替换成 symlink。
    (root / "evil.txt").write_text("x", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("sensitive", encoding="utf-8")
    root.rename(tmp_path / "real-staging")
    root.symlink_to(outside)

    with pytest.raises(ValidationFailed):
        await storage.collect_project_sync_files("proj-1", "alice")


@pytest.mark.asyncio
async def test_collect_rejects_atomic_replace_after_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scan 后同路径被原子 replace（新 inode、内容变长），collect 必须发现快照不一致。"""
    storage = LocalStorage(tmp_path / "storage")
    key = await storage.prepare_project_sync("proj-1", "alice")
    root = _staging_root(tmp_path / "storage", key)
    (root / "data.bin").write_bytes(b"short")

    # 用真实改写制造 scan→read 之间的原子替换，直接观察 scan/read 原语的对象同一性。
    entries_before = local_module._scan_project_sync(root)
    assert len(entries_before) == 1
    replacement = root / "data.bin.tmp"
    replacement.write_bytes(b"short-but-now-much-longer")
    os.replace(replacement, root / "data.bin")

    content, info = local_module._read_sync_file_within_root(root, "data.bin")
    entry = entries_before[0]
    # 新 inode 原子 replace 后：scan 快照（inode/mtime/size）与读取对象不再同一。
    assert not (
        len(content) == entry.size
        and info.st_ino == entry.inode
        and info.st_mtime_ns == entry.mtime_ns
    )

    # 端到端：在 collect 的 scan 之后、read 之前用真实文件替换触发一致性核对。
    real_scan = local_module._scan_project_sync

    def scan_then_replace(scan_root: Path):
        entries = real_scan(scan_root)
        repl = scan_root / "data.bin.tmp"
        repl.write_bytes(b"mutated-after-scan")
        os.replace(repl, scan_root / "data.bin")
        return entries

    monkeypatch.setattr(local_module, "_scan_project_sync", scan_then_replace)
    with pytest.raises(ValidationFailed):
        await storage.collect_project_sync_files("proj-1", "alice")


@pytest.mark.asyncio
async def test_prepare_sync_scopes_sync_tree_to_service_only(tmp_path: Path) -> None:
    """prepare 后 project-sync 根、project 中间目录、actor 叶目录都是 0700。"""
    storage_root = tmp_path / "storage"
    storage = LocalStorage(storage_root)
    key = await storage.prepare_project_sync("proj-1", "alice")

    root_mode = stat.S_IMODE((storage_root / "project-sync").stat().st_mode)
    project_mode = stat.S_IMODE((storage_root / "project-sync" / "proj-1").stat().st_mode)
    actor_mode = stat.S_IMODE(_staging_root(storage_root, key).stat().st_mode)
    assert root_mode == 0o700
    assert project_mode == 0o700
    assert actor_mode == 0o700
