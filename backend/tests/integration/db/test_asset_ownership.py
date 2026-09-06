"""资产（Environment / SharedResource）ownership 的数据库层不变量。

针对当前 schema 直接验证，不经 alembic 迁移；保护即使应用层被绕过、
直接写入也必须成立的所有权约束（GR-401 归属权威）。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

NOW = "2026-08-18 18:00:00+00:00"


async def _insert_owner_fixtures(session) -> None:
    await session.execute(
        text(
            "INSERT INTO users (id, username, display_name, email, created_at) "
            "VALUES ('usr_asset_owner', 'asset-owner', 'Asset Owner', NULL, :now)"
        ),
        {"now": NOW},
    )
    await session.execute(
        text(
            "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
            "VALUES ('grp_asset_owner', 'Asset Group', '', NULL, :now)"
        ),
        {"now": NOW},
    )


@pytest.mark.asyncio
async def test_assets_require_exactly_one_owner(session) -> None:
    """environments 与 shared_resources 必须恰好持有一个 owner，直接写入也受限。"""
    await _insert_owner_fixtures(session)

    for table, id_prefix, extra_columns, extra_values in (
        ("environments", "env", "", {}),
        ("shared_resources", "shr", ", created_at", {"now": NOW}),
    ):
        columns = "id, name, description, owner_user_id, owner_user_group_id" + extra_columns
        values = (
            f"('{id_prefix}_{{kind}}', 'Invalid', '', {{owner}}, {{group}}"
            + (", :now" if extra_values else "")
            + ")"
        )

        # 两个 owner → 拒绝。
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        f"INSERT INTO {table} ({columns}) VALUES "
                        + values.format(
                            kind="both", owner="'usr_asset_owner'", group="'grp_asset_owner'"
                        )
                    ),
                    extra_values,
                )
        # 零个 owner → 拒绝。
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        f"INSERT INTO {table} ({columns}) VALUES "
                        + values.format(kind="neither", owner="NULL", group="NULL")
                    ),
                    extra_values,
                )

    # 合法写入：User-owned environment、Group-owned shared resource。
    await session.execute(
        text(
            "INSERT INTO environments (id, name, description, owner_user_id, "
            "owner_user_group_id) VALUES ('env_new', 'New Environment', '', "
            "'usr_asset_owner', NULL)"
        )
    )
    await session.execute(
        text(
            "INSERT INTO shared_resources (id, name, description, owner_user_id, "
            "owner_user_group_id, created_at) VALUES ('shr_new', 'New Resource', '', "
            "NULL, 'grp_asset_owner', :now)"
        ),
        {"now": NOW},
    )


@pytest.mark.asyncio
async def test_asset_owner_cannot_be_deleted_while_referenced(session) -> None:
    """被 Environment / SharedResource 引用的 User / UserGroup 不可删除。"""
    await _insert_owner_fixtures(session)
    await session.execute(
        text(
            "INSERT INTO environments (id, name, description, owner_user_id, "
            "owner_user_group_id) VALUES ('env_owned', 'Owned Env', '', "
            "'usr_asset_owner', NULL)"
        )
    )
    await session.execute(
        text(
            "INSERT INTO shared_resources (id, name, description, owner_user_id, "
            "owner_user_group_id, created_at) VALUES ('shr_owned', 'Owned Res', '', "
            "NULL, 'grp_asset_owner', :now)"
        ),
        {"now": NOW},
    )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM users WHERE id = 'usr_asset_owner'"))
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM user_groups WHERE id = 'grp_asset_owner'"))
