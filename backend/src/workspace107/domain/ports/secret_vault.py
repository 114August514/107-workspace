"""Secret 存取端口。

Secret values never enter domain snapshots, API responses, or logs. `resolve` is
the execution injection entry; `retain_for_redaction` is a private vault-owned
historical redaction boundary and must be replaced by KMS/Vault storage in production.
"""

from typing import Protocol

from ..config_scope import ConfigScope, SecretReference


class SecretVault(Protocol):
    async def set_secret(self, scope: ConfigScope, name: str, value: str) -> None: ...

    async def delete_secret(self, scope: ConfigScope, name: str) -> None: ...

    async def list_names(self, scope: ConfigScope) -> set[str]:
        """列出一个明确 scope 的 Secret 名称，不返回值。"""
        ...

    async def resolve(self, references: list[SecretReference]) -> dict[SecretReference, str]:
        """Resolve exact references only at execution boundary."""
        ...

    async def retain_for_redaction(self, run_id: str, values: list[str]) -> None: ...

    async def redaction_values(self, run_id: str) -> list[str]: ...
