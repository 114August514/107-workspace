"""Scoped Variable/Secret identities and exact references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .errors import ValidationFailed
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
        if (
            not self.scope.id
            or ":" in self.scope.id
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.name)
        ):
            raise ValidationFailed("Secret reference contains an invalid delimiter or name")
        return f"{self.scope.kind.value}:{self.scope.id}:{self.name}"

    @classmethod
    def from_key(cls, value: str) -> SecretReference:
        parts = value.split(":")
        if (
            len(parts) != 3
            or not all(parts)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", parts[2])
        ):
            raise ValidationFailed("Secret reference must be kind:id:name with a valid name")
        try:
            kind = ConfigScopeKind(parts[0])
        except ValueError as exc:
            raise ValidationFailed(f"Unknown Secret reference scope: {parts[0]!r}") from exc
        return cls(ConfigScope(kind, parts[1]), parts[2])
