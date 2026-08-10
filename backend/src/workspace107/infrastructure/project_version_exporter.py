"""把持久化 Project Version identity 适配为 B 的确定内容导出端口。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.errors import ProjectContentIdentityMismatch, ProjectContentMissing
from ..domain.ports.version_control import (
    ProjectVersionExportEvidence,
    ProjectVersionExportFile,
)
from .db import tables as t
from .project_git import GitProjectContent


class GitProjectVersionExporter:
    """按 version id 查持久化 identity，再导出其精确 Git commit。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        content: GitProjectContent,
    ) -> None:
        self._session_factory = session_factory
        self._content = content

    async def export(
        self,
        *,
        project_version_id: str,
        expected_commit_oid: str,
        target: Path,
    ) -> ProjectVersionExportEvidence:
        async with self._session_factory() as session:
            version = await session.get(t.ProjectVersionRow, project_version_id)
            if version is None:
                raise ProjectContentMissing(f"Project Version {project_version_id} 不存在")
            project = await session.get(t.ProjectRow, version.project_id)
            if project is None:
                raise ProjectContentMissing(f"Project {version.project_id} 不存在")
            if (
                version.commit_oid != expected_commit_oid
                or project.repository_identity != version.repository_identity
            ):
                raise ProjectContentIdentityMismatch(
                    f"Project Version {project_version_id} identity mismatch"
                )
            project_id = project.id
            repository_identity = version.repository_identity

        manifest = await self._content.export_commit(
            project_id,
            repository_identity,
            project_version_id,
            expected_commit_oid,
            target,
        )
        return ProjectVersionExportEvidence(
            commit_oid=manifest.commit_oid,
            tree_oid=manifest.tree_oid,
            manifest=tuple(
                ProjectVersionExportFile(
                    path=entry.path,
                    size=entry.size,
                    content_hash=entry.content_hash,
                )
                for entry in manifest.files
            ),
        )
