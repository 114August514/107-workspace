"""Scoped Variable and Secret configuration use cases."""

from __future__ import annotations

from datetime import UTC, datetime

from ..domain.capabilities import Capability
from ..domain.config_scope import ConfigScope
from ..domain.errors import ObjectNotFound
from ..domain.models import Secret, Variable
from ..domain.ports.repositories import Repositories
from ..domain.ports.secret_vault import SecretVault
from .access import AccessGuard


class ConfigurationService:
    def __init__(self, repos: Repositories, guard: AccessGuard, secrets: SecretVault) -> None:
        self._repos = repos
        self._guard = guard
        self._secrets = secrets

    async def user_scope(self, actor_id: str, user_id: str) -> ConfigScope:
        if actor_id != user_id:
            raise ObjectNotFound("User", user_id)
        return ConfigScope.user(user_id)

    async def group_scope(self, actor_id: str, group_id: str, *, manage: bool) -> ConfigScope:
        await self._guard.scoped_config_group(actor_id, group_id, manage=manage)
        return ConfigScope.user_group(group_id)

    async def project_scope(self, actor_id: str, project_id: str, *, manage: bool) -> ConfigScope:
        await self._guard.project(
            actor_id,
            project_id,
            needs=Capability.CONFIG_MANAGE if manage else Capability.CONFIG_VIEW,
        )
        return ConfigScope.project(project_id)

    async def list_variables(self, scope: ConfigScope) -> list[Variable]:
        return await self._repos.variables.list_for_scope(scope)

    async def set_variable(self, scope: ConfigScope, name: str, value: str) -> Variable:
        variable = Variable(scope=scope, name=name, value=value, updated_at=datetime.now(UTC))
        await self._repos.variables.upsert(variable)
        return variable

    async def delete_variable(self, scope: ConfigScope, name: str) -> None:
        await self._repos.variables.delete(scope, name)

    async def list_secret_summaries(self, scope: ConfigScope) -> list[Secret]:
        """按名称排序的 Secret 元数据；明文永远不出 vault。"""
        return sorted(await self._secrets.list_secrets(scope), key=lambda s: s.name)

    async def set_secret(self, scope: ConfigScope, name: str, value: str) -> None:
        await self._secrets.set_secret(scope, name, value)

    async def delete_secret(self, scope: ConfigScope, name: str) -> None:
        await self._secrets.delete_secret(scope, name)
