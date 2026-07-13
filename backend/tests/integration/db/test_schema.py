from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workspace107.domain.models import utc_now
from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.models import (
    DatasetRow,
    DatasetVersionRow,
    ProjectRow,
    UserRow,
    WorkspaceMemberRow,
    WorkspaceRow,
)
from workspace107.infrastructure.db.session import create_engine, create_session_factory


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as current:
        yield current
    await engine.dispose()


def user_row(username: str) -> UserRow:
    return UserRow(
        id=uuid4(),
        username=username,
        display_name=username.title(),
        email=None,
        created_at=utc_now(),
        archived_at=None,
    )


async def create_workspace(session: AsyncSession, owner: UserRow) -> WorkspaceRow:
    workspace = WorkspaceRow(
        id=uuid4(),
        kind="course",
        name="AI 101",
        slug=f"ai-{uuid4()}",
        description="",
        parent_id=None,
        created_by=owner.id,
        created_at=utc_now(),
        archived_at=None,
    )
    session.add_all([owner, workspace])
    await session.commit()
    return workspace


async def table_names(session: AsyncSession) -> set[str]:
    connection = await session.connection()
    return set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))


async def test_metadata_contains_the_documented_tables(session: AsyncSession) -> None:
    assert await table_names(session) == {
        "artifacts",
        "dataset_versions",
        "datasets",
        "project_syncs",
        "projects",
        "run_datasets",
        "run_events",
        "run_templates",
        "runs",
        "users",
        "workspace_members",
        "workspaces",
    }


async def test_username_is_unique(session: AsyncSession) -> None:
    session.add(user_row("alice"))
    await session.commit()

    session.add(user_row("alice"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_workspace_membership_is_unique(session: AsyncSession) -> None:
    owner = user_row("owner")
    workspace = await create_workspace(session, owner)
    session.add(
        WorkspaceMemberRow(
            workspace_id=workspace.id,
            user_id=owner.id,
            role="owner",
            joined_at=utc_now(),
        )
    )
    await session.commit()

    session.add(
        WorkspaceMemberRow(
            workspace_id=workspace.id,
            user_id=owner.id,
            role="member",
            joined_at=utc_now(),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_dataset_version_name_is_unique_per_dataset(session: AsyncSession) -> None:
    owner = user_row("dataset-owner")
    workspace = await create_workspace(session, owner)
    dataset = DatasetRow(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Images",
        slug="images",
        description="",
        created_by=owner.id,
        created_at=utc_now(),
        archived_at=None,
    )
    session.add(dataset)
    await session.commit()

    first = DatasetVersionRow(
        id=uuid4(),
        dataset_id=dataset.id,
        version="v1",
        storage_key="sha256/aa/" + "a" * 64,
        size_bytes=1,
        sha256="a" * 64,
        created_by=owner.id,
        created_at=utc_now(),
    )
    session.add(first)
    await session.commit()

    duplicate = DatasetVersionRow(
        id=uuid4(),
        dataset_id=dataset.id,
        version="v1",
        storage_key="sha256/bb/" + "b" * 64,
        size_bytes=1,
        sha256="b" * 64,
        created_by=owner.id,
        created_at=utc_now(),
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_sqlite_foreign_keys_are_enabled(session: AsyncSession) -> None:
    session.add(
        ProjectRow(
            id=uuid4(),
            workspace_id=uuid4(),
            name="orphan",
            slug="orphan",
            description="",
            storage_key="projects/orphan",
            created_by=uuid4(),
            created_at=utc_now(),
            archived_at=None,
        )
    )

    with pytest.raises(IntegrityError):
        await session.commit()


def test_session_factory_type() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    assert isinstance(create_session_factory(engine), async_sessionmaker)
