"""Project Working State 与不可变 Git Version 内容端口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..enums import ChangeKind
from ..models import ProjectFile, ProjectVersionFile


@dataclass(frozen=True, slots=True)
class CommitManifest:
    """由完整 Git commit OID 确定的内容事实。"""

    commit_oid: str
    tree_oid: str
    files: tuple[ProjectVersionFile, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size(self) -> int:
        return sum(entry.size for entry in self.files)


class ProjectContentPort(Protocol):
    """每个 Project 的真实 Git repository；Version 始终使用完整 commit OID。"""

    async def initialize_project(self, project_id: str, repository_identity: str) -> None: ...

    async def list_working_files(
        self, project_id: str, repository_identity: str
    ) -> list[ProjectFile]: ...

    async def read_working_file(
        self, project_id: str, repository_identity: str, path: str
    ) -> bytes: ...

    async def write_working_file(
        self,
        project_id: str,
        repository_identity: str,
        path: str,
        content: bytes,
        updated_at: datetime,
    ) -> ProjectFile: ...

    async def delete_working_path(
        self, project_id: str, repository_identity: str, path: str
    ) -> int: ...

    async def move_working_path(
        self,
        project_id: str,
        repository_identity: str,
        source: str,
        destination: str,
        updated_at: datetime,
    ) -> list[ProjectFile]: ...

    async def working_changes(
        self,
        project_id: str,
        repository_identity: str,
        baseline_version_id: str | None,
        baseline_commit_oid: str | None,
    ) -> list[tuple[str, ChangeKind]]: ...

    async def commit_working(
        self,
        project_id: str,
        repository_identity: str,
        *,
        parent_version_id: str | None,
        version_id: str,
        parent_commit_oid: str | None,
        message: str,
        created_by: str,
        created_at: datetime,
    ) -> CommitManifest: ...

    async def manifest(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
    ) -> CommitManifest: ...

    async def read_commit_file(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        path: str,
    ) -> bytes: ...

    async def diff_commits(
        self,
        project_id: str,
        repository_identity: str,
        base_version_id: str,
        base_commit_oid: str,
        target_version_id: str,
        target_commit_oid: str,
    ) -> list[tuple[str, ChangeKind]]: ...

    async def restore_working(
        self,
        project_id: str,
        repository_identity: str,
        version_id: str,
        commit_oid: str,
        updated_at: datetime,
    ) -> list[ProjectFile]: ...

    async def fork_commit(
        self,
        source_project_id: str,
        source_repository_identity: str,
        source_version_id: str,
        source_commit_oid: str,
        target_project_id: str,
        target_repository_identity: str,
        *,
        version_id: str,
        message: str,
        created_by: str,
        created_at: datetime,
        expected_source_tree_oid: str,
        expected_source_file_count: int,
        expected_source_total_size: int,
    ) -> CommitManifest: ...
