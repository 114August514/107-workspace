from __future__ import annotations

from pathlib import Path

from workspace107.cli import _scan_source


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

    # 可观察的扫描结果：保留的文件被计入，忽略规则与默认排除生效。
    assert scan.file_count == 3  # .107ignore、app.py、important.log
    assert "important.log" not in scan.excluded_paths
    assert "cache/data.bin" in scan.excluded_paths
    assert "debug.log" in scan.excluded_paths
    # node_modules 默认整个排除，其内容不进入扫描结果（计入即错误）。
