"""本地存储 Adapter 的只读权限行为。"""

from __future__ import annotations

from pathlib import Path

import pytest

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
