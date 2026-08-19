"""Stable ownership subjects shared by identity and later domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OwnerKind(StrEnum):
    USER = "user"
    USER_GROUP = "user_group"


@dataclass(frozen=True, slots=True)
class OwnerReference:
    """A typed, opaque reference to the only two legal owner subjects."""

    kind: OwnerKind
    id: str
