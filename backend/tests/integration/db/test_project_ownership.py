"""Project ownership 的数据库层不变量。

针对当前 schema 直接验证，不经 alembic 迁移；保护即使应用层被绕过、
直接写入也必须成立的所有权约束（GR-306 归属权威）。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

NOW = "2026-08-23 00:00:00+00:00"


async def _insert_owner_fixtures(session) -> None:
    await session.execute(
        text(
            "INSERT INTO users (id, username, display_name, email, created_at) "
            "VALUES ('usr_alice', 'alice', 'Alice', NULL, :now)"
        ),
        {"now": NOW},
    )
    await session.execute(
        text(
            "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
            "VALUES ('grp_research', 'Research Lab', '', 'usr_alice', :now)"
        ),
        {"now": NOW},
    )


@pytest.mark.asyncio
async def test_project_requires_exactly_one_owner(session) -> None:
    """projects 必须恰好持有一个 owner（User 或 UserGroup），直接写入也受限。"""
    await _insert_owner_fixtures(session)
    columns = (
        "id, owner_user_id, owner_user_group_id, name, description, status, "
        "visibility, environment_version_id, default_run_configuration_id, "
        "created_by, created_at, updated_at"
    )

    # 两个 owner 同时设置 → 拒绝。
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(
                    f"INSERT INTO projects ({columns}) VALUES "
                    "('prj_both', 'usr_alice', 'grp_research', 'Invalid', '', 'active', "
                    "'owner_scope', NULL, NULL, 'usr_alice', :now, :now)"
                ),
                {"now": NOW},
            )

    # 零个 owner → 拒绝。
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(
                    f"INSERT INTO projects ({columns}) VALUES "
                    "('prj_neither', NULL, NULL, 'Invalid', '', 'active', "
                    "'owner_scope', NULL, NULL, 'usr_alice', :now, :now)"
                ),
                {"now": NOW},
            )

    # 合法写入：显式 User owner + public visibility。
    await session.execute(
        text(
            f"INSERT INTO projects ({columns}) VALUES "
            "('prj_public', 'usr_alice', NULL, 'Public', '', 'active', 'public', "
            "NULL, NULL, 'usr_alice', :now, :now)"
        ),
        {"now": NOW},
    )
    row = (
        await session.execute(
            text(
                "SELECT owner_user_id, owner_user_group_id, visibility FROM projects "
                "WHERE id = 'prj_public'"
            )
        )
    ).one()
    assert tuple(row) == ("usr_alice", None, "public")


@pytest.mark.asyncio
async def test_project_owner_cannot_be_deleted_while_referenced(session) -> None:
    """被 Project 引用的 User / UserGroup 不可删除（FK RESTRICT）。"""
    await _insert_owner_fixtures(session)
    columns = (
        "id, owner_user_id, owner_user_group_id, name, description, status, "
        "visibility, created_by, created_at, updated_at"
    )
    await session.execute(
        text(
            f"INSERT INTO projects ({columns}) VALUES "
            "('prj_u', 'usr_alice', NULL, 'Mine', '', 'active', 'owner_scope', "
            "'usr_alice', :now, :now)"
        ),
        {"now": NOW},
    )
    await session.execute(
        text(
            f"INSERT INTO projects ({columns}) VALUES "
            "('prj_g', NULL, 'grp_research', 'Team', '', 'active', 'owner_scope', "
            "'usr_alice', :now, :now)"
        ),
        {"now": NOW},
    )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM users WHERE id = 'usr_alice'"))
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM user_groups WHERE id = 'grp_research'"))
