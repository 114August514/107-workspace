"""基于数据库的 Secret 存储。

生产部署应换成外部密钥服务（KMS / Vault）。无论后端是什么，
对上层暴露的接口都保持不变：只能写入、列名和在执行边界解析（设计稿 §3.1.4）。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.config_scope import ConfigScope, SecretReference
from ...domain.models import Secret
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

    async def list_secrets(self, scope: ConfigScope) -> list[Secret]:
        stmt = select(t.SecretRow).where(
            t.SecretRow.scope_kind == scope.kind.value,
            t.SecretRow.scope_id == scope.id,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [Secret(scope=scope, name=r.name, updated_at=r.updated_at) for r in rows]

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

    async def retain_for_redaction(self, run_id: str, values: list[str]) -> None:
        """Retain injected values only for historical log redaction.

        Production should replace this private boundary with KMS/Vault storage.
        """
        for value in set(values):
            if not value:
                continue
            digest = hashlib.sha256(value.encode()).hexdigest()
            if await self._session.get(t.RunSecretRedactionRow, (run_id, digest)) is None:
                self._session.add(
                    t.RunSecretRedactionRow(run_id=run_id, value_digest=digest, value=value)
                )
        await self._session.flush()

    async def redaction_values(self, run_id: str) -> list[str]:
        rows = await self._session.execute(
            select(t.RunSecretRedactionRow.value).where(t.RunSecretRedactionRow.run_id == run_id)
        )
        return list(rows.scalars().all())
