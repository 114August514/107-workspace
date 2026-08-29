"""Shared Resource candidate path normalization behavior."""

from __future__ import annotations

import pytest

from workspace107.application.shared_resource_service import normalize_shared_resource_path
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
        ("dir/data.txt", "dir/data.txt"),
    ],
)
def test_规范化合法相对路径(raw: str, expected: str) -> None:
    assert normalize_shared_resource_path(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "..", "../outside.py", "/../outside.py", "a/../../b"])
def test_拒绝越出资源根目录的路径(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        normalize_shared_resource_path(raw)
