"""Shared Resource 路径规范化（application 层 ``_normalize_path``）。

参考 ``test_project_paths.py`` 先例：application 层的路径归一化函数在这里
做纯函数单测，不经过 DB/HTTP。``_normalize_path`` 是 ``publish_version`` 和
``read_version_file`` 共用的入口，规则必须和 ``ProjectService.normalize_path`` 一致：
拒绝绝对路径和越出根目录的写法。
"""

from __future__ import annotations

import pytest

from workspace107.application.shared_resource_service import _normalize_path
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
    assert _normalize_path(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "..", "../outside.py", "/../outside.py", "a/../../b"])
def test_拒绝越出资源根目录的路径(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        _normalize_path(raw)
