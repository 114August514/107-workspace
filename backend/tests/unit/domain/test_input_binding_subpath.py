"""InputBinding.source_subpath 的规范化与校验（设计稿 §3.1.3）。

子路径在 ``__post_init__`` 里规范化成与 ``SharedResourceFile.path`` 一致的形式
（``posixpath.normpath``：无尾斜杠、无 ``.``/``..``/``//``）。否则物化时按规范
路径匹配会静默落空——这是这个单测要守的回归。

接受/拒绝边界、normpath 稳定性都在这里钉死，集成测试覆盖运行时物化行为。
"""

from __future__ import annotations

import pytest

from workspace107.domain.enums import InputSourceType
from workspace107.domain.errors import ValidationFailed
from workspace107.domain.models import InputBinding


def _binding(subpath: str = "") -> InputBinding:
    return InputBinding(
        source_type=InputSourceType.SHARED_RESOURCE_VERSION,
        source_id="shrv_1",
        access_path="/inputs/x",
        source_subpath=subpath,
    )


# -- 规范化（B1 守卫）-----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("train/", "train"),  # 去尾斜杠
        ("train//", "train"),  # 折叠重复斜杠
        ("a/./b", "a/b"),  # 折叠 .
        ("a//b", "a/b"),  # 折叠重复斜杠
        ("./train/", "train"),  # 去前导 ./
        ("  train  ", "train"),  # strip
        ("train\\sub", "train/sub"),  # 反斜杠转正斜杠
        ("/train", "train"),  # 去前导绝对斜杠
        ("a/b/../c", "a/c"),  # normpath 解析内部 ..（在界内 → 接受）
    ],
)
def test_子路径被规范化成与文件路径一致的形式(raw: str, normalized: str) -> None:
    assert _binding(raw).source_subpath == normalized


def test_空子路径保持空串表示物化全部() -> None:
    assert _binding("").source_subpath == ""
    assert _binding("   ").source_subpath == ""


# -- 拒绝越界（B1 边界）---------------------------------------------------


@pytest.mark.parametrize("raw", ["../x", "..", ".", "a/../../c/../../escape"])
def test_拒绝越出来源根目录的子路径(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        _binding(raw)
