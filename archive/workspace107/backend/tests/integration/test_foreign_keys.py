"""外键约束在测试环境里必须真的生效。

SQLite 默认 ``PRAGMA foreign_keys=OFF``。关着的时候，插入顺序写反、留下悬空引用
都不会报错，本地一百个测试全绿，换到 PostgreSQL 上直接 ForeignKeyViolation。

这几个测试保证「本地和生产一样严格」这件事不会在某次重构中被悄悄关掉。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from workspace107.infrastructure.db import tables as t


async def test_sqlite_开启了外键校验(session) -> None:
    enabled = (await session.execute(text("PRAGMA foreign_keys"))).scalar_one()
    assert enabled == 1, "SQLite 外键校验被关掉了，本地测试将无法发现引用错误"


async def test_悬空引用会被拒绝(session) -> None:
    session.add(
        t.ProjectVersionFileRow(
            version_id="pv_does_not_exist",
            path="train.py",
            size=1,
            content_hash="0" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_保存版本时父行先于子行落库(client) -> None:
    """回归：ProjectVersion 与它的文件行之间只有外键、没有 ORM relationship。

    同一次 flush 里 SQLAlchemy 不知道两者的先后依赖，可能先插子行。
    这个用例在外键校验打开时会直接暴露顺序错误。
    """
    home = (await client.get("/api/v1/me")).json()
    workspace_id = home["workspaces"][0]["id"]
    project = (
        await client.post(f"/api/v1/workspaces/{workspace_id}/projects", json={"name": "外键顺序"})
    ).json()
    await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "train.py", "content": "print(1)"},
    )

    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"message": "第一版"}
    )
    assert response.status_code == 201

    detail = (await client.get(f"/api/v1/versions/{response.json()['id']}")).json()
    assert [f["path"] for f in detail["files"]] == ["train.py"]
