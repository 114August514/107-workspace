"""本地存储的平台权限行为。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from workspace107.infrastructure.storage import local as local_module


def test_windows_只给文件设置只读属性(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "dataset"
    nested.mkdir(parents=True)
    content = nested / "sample.txt"
    content.write_text("data", encoding="utf-8")
    root_mode = stat.S_IMODE(root.stat().st_mode)
    nested_mode = stat.S_IMODE(nested.stat().st_mode)

    monkeypatch.setattr(local_module.os, "name", "nt")
    local_module._make_readonly(root)

    assert stat.S_IMODE(root.stat().st_mode) == root_mode
    assert stat.S_IMODE(nested.stat().st_mode) == nested_mode
    assert not content.stat().st_mode & stat.S_IWUSR


@pytest.mark.skipif(os.name == "nt", reason="POSIX 权限位仅在 POSIX 文件系统上有效")
def test_posix_目录和文件都变为只读(tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    nested = root / "dataset"
    nested.mkdir(parents=True)
    content = nested / "sample.txt"
    content.write_text("data", encoding="utf-8")

    local_module._make_readonly(root)

    assert stat.S_IMODE(root.stat().st_mode) == local_module.READONLY_DIR
    assert stat.S_IMODE(nested.stat().st_mode) == local_module.READONLY_DIR
    assert stat.S_IMODE(content.stat().st_mode) == local_module.READONLY_FILE

    local_module._force_rmtree(root)
    assert not root.exists()
