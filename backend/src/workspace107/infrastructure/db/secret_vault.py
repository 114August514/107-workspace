"""基于数据库的 Secret 存储。

生产部署应换成外部密钥服务（KMS / Vault）。无论后端是什么，
对上层暴露的接口都保持不变：只能写入、列名和在执行边界解析（设计稿 §3.1.4）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.config_scope import ConfigScope, SecretReference
from . import tables as t


class DatabaseSecretVault:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_secret(self, scope: ConfigScope, name: str, value: str) -> None:
        row = await self._session.get(t.SecretRow, (scope.kind.value, scope.id, name))
        if row is None:
            self._session.add(
                t.SecretRow(
                    scope_kind=scope.kind.value,
                    scope_id=scope.id,
                    name=name,
                    value=value,
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            row.value = value
            row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def delete_secret(self, scope: ConfigScope, name: str) -> None:
        await self._session.execute(
            delete(t.SecretRow).where(
                t.SecretRow.scope_kind == scope.kind.value,
                t.SecretRow.scope_id == scope.id,
                t.SecretRow.name == name,
            )
        )
        await self._session.flush()

    async def list_names(self, scope: ConfigScope) -> set[str]:
        stmt = select(t.SecretRow.name).where(
            t.SecretRow.scope_kind == scope.kind.value,
            t.SecretRow.scope_id == scope.id,
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def resolve(self, references: list[SecretReference]) -> dict[SecretReference, str]:
        result: dict[SecretReference, str] = {}
        for reference in references:
            row = await self._session.get(
                t.SecretRow,
                (reference.scope.kind.value, reference.scope.id, reference.name),
            )
            if row is not None:
                result[reference] = row.value
        return result
