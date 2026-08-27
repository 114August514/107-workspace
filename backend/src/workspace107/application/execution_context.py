"""Shared API/Worker seam for exact delayed execution authorization."""

from __future__ import annotations

from ..domain.capabilities import Capability
from ..domain.enums import InputSourceType
from ..domain.errors import ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.execution import ValidatedExecutionContext
from ..domain.models import Run, SharedResourceVersion
from ..domain.ownership import OwnerReference
from ..domain.ports.repositories import Repositories
from ..domain.run_snapshot import RunSnapshot
from .access import AccessGuard
from .asset_use import environment_version_for_owner_use, shared_resource_version_for_owner_use
from .scoped_config_resolver import ScopedConfigResolver


class ExecutionContextService:
    """Validate authority from persisted Run identity and one exact Snapshot."""

    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        config_resolver: ScopedConfigResolver,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._config_resolver = config_resolver

    async def validate(self, run: Run, snapshot: RunSnapshot) -> ValidatedExecutionContext:
        if (
            run.snapshot_id != snapshot.id
            or run.project_id != snapshot.project_id
            or run.project_version_id != snapshot.project_version_id
        ):
            raise ValidationFailed("Run 与 exact Snapshot identity 不一致")
        if run.initiated_by_user_id != snapshot.initiated_by_user_id:
            raise ValidationFailed("Run 与 Snapshot 的发起 User identity 不一致")

        try:
            access = await self._guard.project(
                run.initiated_by_user_id,
                run.project_id,
                needs=Capability.RUN_SUBMIT,
                owner_scope=True,
            )
        except (ObjectNotFound, PermissionDenied) as exc:
            raise ValidationFailed("Run 发起 User 当前已无权在来源 Project 执行") from exc

        problems: list[str] = []
        environment_version = await environment_version_for_owner_use(
            self._repos,
            run.initiated_by_user_id,
            snapshot.environment_version_id,
            access.project.owner,
        )
        if environment_version is None:
            problems.append("来源运行环境版本已不存在或无权供当前 Project 使用")
        elif not environment_version.available:
            problems.append(f"运行环境版本 {environment_version.version} 当前不可用")

        for binding in snapshot.input_bindings:
            if binding.source_type is InputSourceType.ARTIFACT:
                problem = await self._artifact_input_problem(
                    binding.source_id,
                    binding.access_path,
                    access.project.owner,
                )
            else:
                problem = await self._shared_resource_input_problem(
                    run.initiated_by_user_id,
                    binding.source_id,
                    binding.access_path,
                    binding.source_subpath,
                    access.project.owner,
                )
            if problem is not None:
                problems.append(problem)

        secret_values, secret_problems = await self._config_resolver.validate_and_resolve(
            access,
            run.initiated_by_user_id,
            snapshot.env_secret_refs,
        )
        problems.extend(secret_problems)
        if problems:
            secret_values.clear()
            raise ValidationFailed("; ".join(problems))
        return ValidatedExecutionContext(secret_values=secret_values)

    async def _artifact_input_problem(
        self,
        artifact_id: str,
        access_path: str,
        project_owner: OwnerReference,
    ) -> str | None:
        artifact = await self._repos.artifacts.get(artifact_id)
        if artifact is None:
            return f"输入 {access_path} 引用的 Artifact 不存在或无权访问"
        source_project = await self._repos.projects.get(artifact.project_id)
        if source_project is None or source_project.owner != project_owner:
            return f"输入 {access_path} 引用的 Artifact 不存在或无权访问"
        if not artifact.is_available:
            return f"输入 {access_path} 引用的 Artifact 内容已被清理"
        return None

    async def _shared_resource_input_problem(
        self,
        user_id: str,
        version_id: str,
        access_path: str,
        subpath: str,
        project_owner: OwnerReference,
    ) -> str | None:
        version = await shared_resource_version_for_owner_use(
            self._repos, user_id, version_id, project_owner
        )
        if version is None:
            return f"输入 {access_path} 引用的 Shared Resource Version 不存在或无权访问"
        if subpath and not _subpath_exists_in_version(subpath, version):
            return f"输入 {access_path} 引用的子路径 {subpath!r} 不存在"
        return None


def _subpath_exists_in_version(subpath: str, version: SharedResourceVersion) -> bool:
    if not subpath:
        return True
    return any(
        item.path == subpath or item.path.startswith(subpath + "/") for item in version.files
    )
