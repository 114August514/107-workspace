"""确定 Project Version 导出的窄端口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProjectVersionExportFile:
    """导出树中的一个普通文件事实。"""

    path: str
    size: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ProjectVersionExportEvidence:
    """A 导出后交给 workspace 绑定的不可变内容证据。"""

    commit_oid: str
    tree_oid: str
    manifest: tuple[ProjectVersionExportFile, ...]


class ProjectVersionExporter(Protocol):
    """把一个已确定版本导出到调用方提供的空目录。"""

    async def export(
        self,
        *,
        project_version_id: str,
        expected_commit_oid: str,
        target: Path,
    ) -> ProjectVersionExportEvidence:
        """导出精确 commit；identity 不符、目标非空或导出失败时大声失败。"""
        ...
