from pathlib import Path

import pytest

from workspace107.domain.errors import PathOutsideAllowedRoot
from workspace107.domain.models import IgnoreRules
from workspace107.infrastructure.transfer.scanner import scan_project


def test_scanner_applies_mandatory_and_hpcignore_rules(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / ".hpcignore").write_text("data/\n*.tmp\n!.git/\n", encoding="utf-8")
    (source / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (source / "结果.txt").write_text("result\n", encoding="utf-8")
    (source / "scratch.tmp").write_text("ignored\n", encoding="utf-8")
    for directory in (".git", ".venv", "__pycache__", "data"):
        path = source / directory
        path.mkdir()
        (path / "hidden.txt").write_text("hidden\n", encoding="utf-8")

    snapshot = scan_project(source, IgnoreRules())

    assert tuple(signature.path for signature in snapshot.files) == (
        ".hpcignore",
        "main.py",
        "结果.txt",
    )


def test_scanner_returns_structured_size_and_count_warnings(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "large.bin").write_bytes(b"1234")
    (source / "small.txt").write_text("x", encoding="utf-8")

    snapshot = scan_project(
        source,
        IgnoreRules(),
        large_file_threshold=3,
        file_count_threshold=1,
    )

    assert tuple(warning.code for warning in snapshot.warnings) == (
        "large_file",
        "large_file_count",
    )
    assert snapshot.warnings[0].path == "large.bin"
    assert snapshot.warnings[0].size_bytes == 4
    assert snapshot.warnings[1].count == 2


def test_scanner_rejects_symlink_outside_source_root(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret\n", encoding="utf-8")
    (source / "escape.txt").symlink_to(outside)

    with pytest.raises(PathOutsideAllowedRoot):
        scan_project(source, IgnoreRules())
