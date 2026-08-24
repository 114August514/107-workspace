"""Application seam for resolving scoped Run configuration references."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.config_scope import ConfigScope, SecretReference
from ..domain.enums import EnvValueKind
from ..domain.models import Variable
from ..domain.ownership import OwnerKind
from ..domain.ports.repositories import VariableRepository
from ..domain.ports.secret_vault import SecretVault
from ..domain.secrets import EnvValue
from .access import ProjectAccess


@dataclass(frozen=True, slots=True)
class ScopedResolution:
    literals: dict[str, str]
    secret_refs: dict[str, SecretReference]
    problems: list[str]


class ScopedConfigResolver:
    """Resolve config after ProjectAccess has established actor authorization."""

    def __init__(self, variables: VariableRepository, secrets: SecretVault) -> None:
        self._variables = variables
        self._secrets = secrets

    async def resolve(
        self,
        access: ProjectAccess,
        initiated_by_user_id: str,
        env: dict[str, EnvValue],
    ) -> ScopedResolution:
        project_scope = ConfigScope.project(access.project.id)
        # Owner scope 从 Project Owner 推导（#41），Workspace 不再参与：
        # USER owner → User scope，USER_GROUP owner → User Group scope。
        owner = access.project.owner
        if owner.kind is OwnerKind.USER:
            owner_scope = ConfigScope.user(owner.id)
        else:
            owner_scope = ConfigScope.user_group(owner.id)
        user_scope = ConfigScope.user(initiated_by_user_id)
        literals: dict[str, str] = {}
        refs: dict[str, SecretReference] = {}
        problems: list[str] = []
        cache: dict[tuple[ConfigScope, str], Variable | None] = {}
        secret_cache: dict[ConfigScope, set[str]] = {}

        async def variable(scope: ConfigScope, name: str) -> Variable | None:
            key = (scope, name)
            if key not in cache:
                cache[key] = await self._variables.get(scope, name)
            return cache[key]

        async def secret_names(scope: ConfigScope) -> set[str]:
            if scope not in secret_cache:
                secret_cache[scope] = await self._secrets.list_names(scope)
            return secret_cache[scope]

        for env_name, value in env.items():
            if value.kind is EnvValueKind.LITERAL:
                literals[env_name] = value.value
                continue
            if value.kind is EnvValueKind.VARIABLE:
                scope = user_scope if value.user_scope else project_scope
                selected = await variable(scope, value.value)
                if selected is None and not value.user_scope:
                    selected = await variable(owner_scope, value.value)
                    scope = owner_scope if selected is not None else scope
                if selected is None:
                    problems.append(
                        f"环境变量 {env_name} 引用的 Variable {value.value} 不存在或不可用"
                    )
                else:
                    literals[env_name] = selected.value
                continue
            scope = user_scope if value.user_scope else project_scope
            available = await secret_names(scope)
            if value.value not in available and not value.user_scope:
                scope = owner_scope
                available = await secret_names(scope)
            if value.value not in available:
                problems.append(f"环境变量 {env_name} 引用的 Secret {value.value} 不存在或不可用")
            else:
                refs[env_name] = SecretReference(scope, value.value)
        return ScopedResolution(literals=literals, secret_refs=refs, problems=problems)

    async def validate_and_resolve(
        self,
        access: ProjectAccess,
        initiated_by_user_id: str,
        refs: dict[str, SecretReference],
    ) -> tuple[dict[str, str], list[str]]:
        """Validate every exact ref first, then resolve all-or-fail."""
        allowed = {
            ConfigScope.project(access.project.id),
            ConfigScope.user(initiated_by_user_id),
        }
        owner = access.project.owner
        if owner.kind is OwnerKind.USER_GROUP:
            allowed.add(ConfigScope.user_group(owner.id))
        problems: list[str] = []
        for env_name, ref in refs.items():
            if ref.scope not in allowed:
                problems.append(f"环境变量 {env_name} 的 exact Secret reference 无权使用")
        if problems:
            return {}, problems
        resolved = await self._secrets.resolve(list(refs.values()))
        missing = [name for name, ref in refs.items() if ref not in resolved]
        if missing:
            return {}, [f"环境变量 {name} 引用的 exact Secret 不存在或不可用" for name in missing]
        return {name: resolved[ref] for name, ref in refs.items()}, []
