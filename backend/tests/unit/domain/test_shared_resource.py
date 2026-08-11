"""Shared Resource 领域对象的稳定规则（设计稿 §2.6、GR-201）。

直接断言可变性边界和派生属性，不经过 DB/HTTP——这些规则离领域最近，
应该在这个层级被直接保护（参考 ``test_run_snapshot.py`` 的约定）。
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from workspace107.domain.errors import ValidationFailed
from workspace107.domain.models import (
    SharedResource,
    SharedResourceFile,
    SharedResourceVersion,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _files(*paths: str) -> tuple[SharedResourceFile, ...]:
    return tuple(SharedResourceFile(path=p, size=len(p), content_hash=f"hash-{p}") for p in paths)


# -- SharedResource：可变（非 frozen） ---------------------------------------


def test_shared_resource_可变_名称和说明可就地修改() -> None:
    """与 Project/Workspace 同属「可变对象」——展示元数据可在范围内修改。"""
    resource = SharedResource(id="shr_1", name="原名", description="旧说明")
    resource.name = "新名"
    resource.description = "新说明"
    assert resource.name == "新名"
    assert resource.description == "新说明"


def test_shared_resource_is_platform_owned_按_owner_workspace_id_判断() -> None:
    assert SharedResource(id="shr_p", name="平台资源", owner_workspace_id=None).is_platform_owned
    assert not SharedResource(
        id="shr_w", name="空间资源", owner_workspace_id="ws_1"
    ).is_platform_owned


# -- SharedResourceVersion / File：不可变（frozen） --------------------------


def test_shared_resource_version_不可变_赋值抛_FrozenInstanceError() -> None:
    version = SharedResourceVersion(
        id="shrv_1",
        shared_resource_id="shr_1",
        sequence=1,
        description="v1",
        files=_files("a.txt"),
        created_by="alice",
        created_at=NOW,
    )
    with pytest.raises(FrozenInstanceError):
        version.description = "改不了"  # type: ignore[misc]


def test_shared_resource_file_不可变_赋值抛_FrozenInstanceError() -> None:
    file = SharedResourceFile(path="a.txt", size=3, content_hash="h")
    with pytest.raises(FrozenInstanceError):
        file.path = "b.txt"  # type: ignore[misc]


def test_shared_resource_version_files_是_tuple_不可变容器() -> None:
    """files 用 tuple 而非 list，固化后不能增删文件（GR-201）。"""
    files = _files("a.txt", "b.txt")
    version = SharedResourceVersion(
        id="shrv_1",
        shared_resource_id="shr_1",
        sequence=1,
        description="",
        files=files,
        created_by="alice",
        created_at=NOW,
    )
    assert isinstance(version.files, tuple)
    with pytest.raises(AttributeError):
        version.files.append("c.txt")  # type: ignore[attr-defined]


# -- 派生属性 --------------------------------------------------------------


def test_label_按_sequence_展示为_vN() -> None:
    v1 = SharedResourceVersion(
        id="shrv_1",
        shared_resource_id="shr_1",
        sequence=1,
        description="",
        files=(),
        created_by="alice",
        created_at=NOW,
    )
    v12 = SharedResourceVersion(
        id="shrv_12",
        shared_resource_id="shr_1",
        sequence=12,
        description="",
        files=(),
        created_by="alice",
        created_at=NOW,
    )
    assert v1.label == "v1"
    assert v12.label == "v12"


def test_file_count_和_total_size_按文件列表汇总() -> None:
    version = SharedResourceVersion(
        id="shrv_1",
        shared_resource_id="shr_1",
        sequence=1,
        description="",
        files=(
            SharedResourceFile(path="a.txt", size=10, content_hash="ha"),
            SharedResourceFile(path="dir/b.txt", size=20, content_hash="hb"),
        ),
        created_by="alice",
        created_at=NOW,
    )
    assert version.file_count == 2
    assert version.total_size == 30


def test_空版本文件列表的_file_count_和_total_size_为零() -> None:
    version = SharedResourceVersion(
        id="shrv_1",
        shared_resource_id="shr_1",
        sequence=1,
        description="",
        files=(),
        created_by="alice",
        created_at=NOW,
    )
    assert version.file_count == 0
    assert version.total_size == 0


# -- SharedResourceFile 无路径校验（校验在 application 层，见 test_shared_resource_paths） --


def test_shared_resource_file_本身不做路径校验() -> None:
    """路径校验在 application 层的 ``_normalize_path``，不在领域对象上（与 ProjectFile 一致）。"""
    # 构造时不抛——校验是 service 层职责
    file = SharedResourceFile(path="any/raw/path", size=1, content_hash="h")
    assert file.path == "any/raw/path"
    # 即便如此，ValidationFailed 仍是这一族对象在校验层抛出的错误类型
    assert ValidationFailed is not None
