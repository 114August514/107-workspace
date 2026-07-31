"""基于数据库的 Secret 存储。

生产部署应换成外部密钥服务（KMS / Vault）。无论后端是什么，
对上层暴露的接口都保持不变：只能写入、列名和在执行边界解析（设计稿 §3.1.4）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import tables as t


class DatabaseSecretVault:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_secret(self, workspace_id: str, name: str, value: str) -> None:
        row = await self._session.get(t.WorkspaceSecretRow, (workspace_id, name))
        if row is None:
            self._session.add(
                t.WorkspaceSecretRow(
                    workspace_id=workspace_id,
                    name=name,
                    value=value,
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            row.value = value
            row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def delete_secret(self, workspace_id: str, name: str) -> None:
        await self._session.execute(
            delete(t.WorkspaceSecretRow).where(
                t.WorkspaceSecretRow.workspace_id == workspace_id,
                t.WorkspaceSecretRow.name == name,
            )
        )
        await self._session.flush()

    async def list_names(self, workspace_id: str) -> set[str]:
        stmt = select(t.WorkspaceSecretRow.name).where(
            t.WorkspaceSecretRow.workspace_id == workspace_id
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def resolve(self, workspace_id: str, names: list[str]) -> dict[str, str]:
        if not names:
            return {}
        stmt = select(t.WorkspaceSecretRow).where(
            t.WorkspaceSecretRow.workspace_id == workspace_id,
            t.WorkspaceSecretRow.name.in_(names),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.name: row.value for row in rows}
