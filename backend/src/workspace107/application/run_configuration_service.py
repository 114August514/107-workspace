"""运行方案用例。

Run Configuration 描述「以后准备怎样运行」，可以编辑、复制和删除。
修改它不影响已经创建的 Run——那些 Run 按各自的 Run Snapshot 执行。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.compute import ComputePlan, ComputeRequest, check_request_against_plan
from ..domain.enums import InputSourceType
from ..domain.errors import ConflictError, ObjectNotFound, ValidationFailed
from ..domain.models import ArtifactCollectionRule, InputBinding, RunConfiguration
from ..domain.ports.repositories import Repositories
from ..domain.secrets import EnvValue, parse_env_map
from .access import AccessGuard
from .project_service import normalize_path


@dataclass(frozen=True, slots=True)
class RunConfigurationInput:
    """创建或更新运行方案时的输入。"""

    name: str
    command: str
    compute_plan_id: str
    working_directory: str = "."
    description: str = ""
    environment_version_id: str | None = None
    environment_variables: dict[str, str] | None = None
    input_bindings: list[dict[str, str]] | None = None
    compute_request: dict[str, int] | None = None
    artifact_rules: list[dict[str, object]] | None = None


class RunConfigurationService:
    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def list_for_project(self, user_id: str, project_id: str) -> list[RunConfiguration]:
        await self._guard.project(user_id, project_id, owner_scope=True)
        return await self._repos.run_configurations.list_for_project(project_id)

    async def get(self, user_id: str, configuration_id: str) -> RunConfiguration:
        configuration = await self._repos.run_configurations.get(configuration_id)
        if configuration is None:
            raise ObjectNotFound("Run Configuration", configuration_id)
        try:
            await self._guard.project(user_id, configuration.project_id, owner_scope=True)
        except ObjectNotFound as exc:
            raise ObjectNotFound("Run Configuration", configuration_id) from exc
        return configuration

    async def create(
        self, user_id: str, project_id: str, data: RunConfigurationInput
    ) -> RunConfiguration:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.RUN_CONFIGURATION_MANAGE
        )
        plan = await self._require_plan(data.compute_plan_id)
        parsed = await self._build_fields(data, plan)

        configuration = RunConfiguration(
            id=ids.new_id(ids.RUN_CONFIGURATION),
            project_id=project_id,
            name=parsed.name,
            description=data.description,
            working_directory=parsed.working_directory,
            command=parsed.command,
            environment_version_id=parsed.environment_version_id,
            environment_variables=parsed.environment_variables,
            input_bindings=parsed.input_bindings,
            compute_plan_id=plan.id,
            compute_request=parsed.compute_request,
            artifact_rules=parsed.artifact_rules,
        )
        await self._repos.run_configurations.add(configuration)

        # 第一个运行方案自动成为 Project 默认方案。
        if access.project.default_run_configuration_id is None:
            access.project.default_run_configuration_id = configuration.id
            await self._repos.projects.update(access.project)

        return configuration

    async def update(
        self, user_id: str, configuration_id: str, data: RunConfigurationInput
    ) -> RunConfiguration:
        configuration = await self.get(user_id, configuration_id)
        await self._guard.project(
            user_id, configuration.project_id, needs=Capability.RUN_CONFIGURATION_MANAGE
        )
        plan = await self._require_plan(data.compute_plan_id)
        parsed = await self._build_fields(data, plan)

        configuration.name = parsed.name
        configuration.description = data.description
        configuration.working_directory = parsed.working_directory
        configuration.command = parsed.command
        configuration.environment_version_id = parsed.environment_version_id
        configuration.environment_variables = parsed.environment_variables
        configuration.input_bindings = parsed.input_bindings
        configuration.compute_plan_id = plan.id
        configuration.compute_request = parsed.compute_request
        configuration.artifact_rules = parsed.artifact_rules

        await self._repos.run_configurations.update(configuration)
        return configuration

    async def delete(self, user_id: str, configuration_id: str) -> None:
        configuration = await self.get(user_id, configuration_id)
        await self._guard.project(
            user_id, configuration.project_id, needs=Capability.RUN_CONFIGURATION_MANAGE
        )
        project = await self._repos.projects.get(configuration.project_id)
        if project is not None and project.default_run_configuration_id == configuration.id:
            remaining = [
                c
                for c in await self._repos.run_configurations.list_for_project(project.id)
                if c.id != configuration.id
            ]
            project.default_run_configuration_id = remaining[0].id if remaining else None
            await self._repos.projects.update(project)
        await self._repos.run_configurations.delete(configuration_id)

    # -- 内部 -----------------------------------------------------------

    async def _require_plan(self, compute_plan_id: str) -> ComputePlan:
        plan = await self._repos.compute_plans.get(compute_plan_id)
        if plan is None:
            raise ObjectNotFound("Compute Plan", compute_plan_id)
        return plan

    async def _build_fields(
        self, data: RunConfigurationInput, plan: ComputePlan
    ) -> _ParsedConfiguration:
        name = data.name.strip()
        if not name:
            raise ValidationFailed("运行方案名称不能为空")
        if not data.command.strip():
            raise ValidationFailed("执行命令不能为空")

        working_directory = data.working_directory.strip() or "."
        if working_directory != ".":
            working_directory = normalize_path(working_directory)

        environment_version_id: str | None = None
        if data.environment_version_id:
            version = await self._repos.environments.get_version(data.environment_version_id)
            if version is None:
                raise ObjectNotFound("Environment Version", data.environment_version_id)
            environment_version_id = version.id

        env: dict[str, EnvValue] = parse_env_map(data.environment_variables or {})

        bindings: list[InputBinding] = []
        seen_paths: set[str] = set()
        for raw in data.input_bindings or []:
            source_type = InputSourceType(raw.get("source_type", InputSourceType.ARTIFACT.value))
            if source_type not in (
                InputSourceType.ARTIFACT,
                InputSourceType.SHARED_RESOURCE_VERSION,
            ):
                raise ValidationFailed(f"未知的输入来源类型 {source_type!r}")
            binding = InputBinding(
                source_type=source_type,
                source_id=raw["source_id"],
                access_path=raw["access_path"],
                source_subpath=raw.get("source_subpath", ""),
            )
            if binding.access_path in seen_paths:
                raise ConflictError(f"输入访问路径 {binding.access_path} 重复")
            seen_paths.add(binding.access_path)
            bindings.append(binding)

        request: ComputeRequest | None = None
        if data.compute_request is not None:
            request = ComputeRequest(**data.compute_request)
            problems = check_request_against_plan(plan, request)
            if problems:
                raise ValidationFailed("；".join(problems))

        rules: list[ArtifactCollectionRule] = []
        seen_rule_paths: set[str] = set()
        for raw_rule in data.artifact_rules or []:
            rule = ArtifactCollectionRule(
                path=str(raw_rule["path"]),
                name=str(raw_rule.get("name", "")),
                optional=bool(raw_rule.get("optional", True)),
            )
            if rule.path in seen_rule_paths:
                raise ConflictError(f"Artifact 收集路径 {rule.path} 重复")
            seen_rule_paths.add(rule.path)
            rules.append(rule)

        return _ParsedConfiguration(
            name=name,
            command=data.command.strip(),
            working_directory=working_directory,
            environment_version_id=environment_version_id,
            environment_variables=env,
            input_bindings=tuple(bindings),
            compute_request=request,
            artifact_rules=tuple(rules),
        )


@dataclass(frozen=True, slots=True)
class _ParsedConfiguration:
    name: str
    command: str
    working_directory: str
    environment_version_id: str | None
    environment_variables: dict[str, EnvValue]
    input_bindings: tuple[InputBinding, ...]
    compute_request: ComputeRequest | None
    artifact_rules: tuple[ArtifactCollectionRule, ...]
