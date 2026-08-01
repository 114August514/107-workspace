"""Application 层的项目文件路径规范化。"""

from __future__ import annotations

import pytest

from workspace107.application.project_service import normalize_path
from workspace107.domain.errors import ValidationFailed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("train.py", "train.py"),
        ("/train.py", "train.py"),
        ("./src/train.py", "src/train.py"),
        ("src//train.py", "src/train.py"),
        ("src\\train.py", "src/train.py"),
        ("  train.py  ", "train.py"),
        ("src/./nested/train.py", "src/nested/train.py"),
        ("src/nested/../train.py", "src/train.py"),
    ],
)
def test_normalizes_valid_path(raw: str, expected: str) -> None:
    assert normalize_path(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "..", "../outside.py", "/../outside.py"])
def test_rejects_path_that_escapes_project_root(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        normalize_path(raw)
