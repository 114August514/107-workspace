from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from workspace107.cli import (
    _build_rsync_command,
    _run_rsync,
    _scan_source,
    _write_filter_file,
)


def test_scan_uses_gitignore_semantics_and_default_exclusions(tmp_path: Path) -> None:
    (tmp_path / ".107ignore").write_text("*.log\n!important.log\ncache/\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "debug.log").write_text("ignored", encoding="utf-8")
    (tmp_path / "important.log").write_text("kept", encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "data.bin").write_bytes(b"ignored")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.js").write_text("ignored", encoding="utf-8")

    scan = _scan_source(tmp_path)

    assert scan.file_count == 3  # .107ignore、app.py、important.log
    assert scan.total_bytes == sum(
        (tmp_path / name).stat().st_size for name in (".107ignore", "app.py", "important.log")
    )
    assert scan.excluded_paths == ("cache/data.bin", "debug.log")


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync is required")
def test_real_rsync_mirrors_staging_and_second_run_transfers_only_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
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
        assert "100%" in capsys.readouterr().out
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
