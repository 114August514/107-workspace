"""本地存储 Adapter 的平台权限行为。"""

from __future__ import annotations

from pathlib import Path

from workspace107.infrastructure.storage import local as local_module


def test_windows_only_makes_files_readonly(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "dataset"
    nested.mkdir(parents=True)
    content = nested / "sample.txt"
    content.write_text("data", encoding="utf-8")
    chmod_calls: list[tuple[Path, int]] = []

    def record_chmod(path: Path, mode: int) -> None:
        chmod_calls.append((path, mode))

    monkeypatch.setattr(local_module.os, "name", "nt")
    monkeypatch.setattr(Path, "chmod", record_chmod)
    local_module._make_readonly(root)

    assert chmod_calls == [(content, local_module.READONLY_FILE)]


def test_posix_makes_directories_and_files_readonly(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "dataset"
    nested.mkdir(parents=True)
    content = nested / "sample.txt"
    content.write_text("data", encoding="utf-8")

    chmod_calls: dict[Path, int] = {}

    def record_chmod(path: Path, mode: int) -> None:
        chmod_calls[path] = mode

    monkeypatch.setattr(local_module.os, "name", "posix")
    monkeypatch.setattr(Path, "chmod", record_chmod)
    local_module._make_readonly(root)

    assert chmod_calls == {
        root: local_module.READONLY_DIR,
        nested: local_module.READONLY_DIR,
        content: local_module.READONLY_FILE,
    }
