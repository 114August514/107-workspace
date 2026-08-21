"""Scoped Variable/Secret identities and exact references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .ownership import OwnerReference


class ConfigScopeKind(StrEnum):
    USER = "user"
    USER_GROUP = "user_group"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class ConfigScope:
    kind: ConfigScopeKind
    id: str

    @classmethod
    def user(cls, user_id: str) -> ConfigScope:
        return cls(ConfigScopeKind.USER, user_id)

    @classmethod
    def user_group(cls, group_id: str) -> ConfigScope:
        return cls(ConfigScopeKind.USER_GROUP, group_id)

    @classmethod
    def project(cls, project_id: str) -> ConfigScope:
        return cls(ConfigScopeKind.PROJECT, project_id)

    @classmethod
    def owner(cls, owner: OwnerReference) -> ConfigScope:
        kind = ConfigScopeKind(owner.kind.value)
        return cls(kind, owner.id)


@dataclass(frozen=True, slots=True)
class SecretReference:
    """A scope-qualified reference; never contains secret plaintext."""

    scope: ConfigScope
    name: str

    def as_key(self) -> str:
        return f"{self.scope.kind.value}:{self.scope.id}:{self.name}"
