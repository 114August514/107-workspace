"""CLI rsync 同步对真实子进程的集成行为。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from workspace107.cli import _build_rsync_command, _run_rsync, _scan_source, _write_filter_file
from workspace107.infrastructure.storage.local import _scan_project_sync


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync is required")
def test_real_rsync_mirrors_staging_and_second_run_transfers_only_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / ".107ignore").write_text("*.tmp\n", encoding="utf-8")
    (source / "changed.txt").write_text("v1", encoding="utf-8")
    (source / "stable.txt").write_text("stable", encoding="utf-8")
    (source / "ignored.tmp").write_text("ignored", encoding="utf-8")

    scan = _scan_source(source)
    filter_file = _write_filter_file(scan.excluded_paths)
    try:
        command = _build_rsync_command(source, "example", "/controlled", filter_file)
        command[-1] = f"{target}/"
        _run_rsync(command)
        assert sorted(path.name for path in target.iterdir()) == [
            ".107ignore",
            "changed.txt",
            "stable.txt",
        ]

        (source / "changed.txt").write_text("version two", encoding="utf-8")
        (source / "new.txt").write_text("new", encoding="utf-8")
        (target / "remote-only.txt").write_text("stale staging content", encoding="utf-8")

        separator = command.index("--")
        itemized = [*command[:separator], "--itemize-changes", *command[separator:]]
        second = subprocess.run(itemized, check=True, capture_output=True, text=True)
        transferred = [
            line
            for line in second.stdout.splitlines()
            if len(line) >= 2 and line[0] in "<>" and line[1] == "f"
        ]
        assert any(line.endswith(" changed.txt") for line in transferred)
        assert any(line.endswith(" new.txt") for line in transferred)
        assert not any(line.endswith(" stable.txt") for line in transferred)
        assert not (target / "remote-only.txt").exists()
    finally:
        filter_file.unlink(missing_ok=True)


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync is required")
def test_rsync_isolates_incomplete_transfers_from_applied_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--partial-dir 把中断的半截文件隔离进 .rsync-partial，不留半截正式文件。"""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "big.bin").write_bytes(b"x" * 4096)

    scan = _scan_source(source)
    filter_file = _write_filter_file(scan.excluded_paths)
    try:
        command = _build_rsync_command(source, "example", "/controlled", filter_file)
        command[-1] = f"{target}/"
        _run_rsync(command)
        capsys.readouterr()
        assert (target / "big.bin").read_bytes() == b"x" * 4096

        # 真实中断语义：rsync --partial-dir 在远端把半截文件留在 .rsync-partial，
        # 顶层不出现同名的半截正式文件。
        dest = target / "big.bin"
        dest.write_bytes(b"y" * 16)  # 旧版本
        partial_dir = target / ".rsync-partial"
        partial_dir.mkdir()
        (partial_dir / "big.bin").write_bytes(b"x" * 1024)  # 模拟中断的半截

        # 关键行为：服务端 apply 前的扫描把 .rsync-partial 整体排除在可应用内容之外，
        # 半截半成品不会进入 Working State。
        apply_entries = _scan_project_sync(target)
        assert [entry.path for entry in apply_entries] == ["big.bin"]
    finally:
        filter_file.unlink(missing_ok=True)
