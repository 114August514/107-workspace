from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workspace107.infrastructure.db.repositories import (
    SqlAlchemyArtifactRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyMemberRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyProjectSyncRepository,
    SqlAlchemyRunEventRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyTemplateRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)


class SqlAlchemyUnitOfWork:
    session: AsyncSession
    users: SqlAlchemyUserRepository
    workspaces: SqlAlchemyWorkspaceRepository
    members: SqlAlchemyMemberRepository
    projects: SqlAlchemyProjectRepository
    datasets: SqlAlchemyDatasetRepository
    templates: SqlAlchemyTemplateRepository
    runs: SqlAlchemyRunRepository
    events: SqlAlchemyRunEventRepository
    artifacts: SqlAlchemyArtifactRepository
    syncs: SqlAlchemyProjectSyncRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self.session)
        self.workspaces = SqlAlchemyWorkspaceRepository(self.session)
        self.members = SqlAlchemyMemberRepository(self.session)
        self.projects = SqlAlchemyProjectRepository(self.session)
        self.datasets = SqlAlchemyDatasetRepository(self.session)
        self.templates = SqlAlchemyTemplateRepository(self.session)
        self.runs = SqlAlchemyRunRepository(self.session)
        self.events = SqlAlchemyRunEventRepository(self.session)
        self.artifacts = SqlAlchemyArtifactRepository(self.session)
        self.syncs = SqlAlchemyProjectSyncRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session.in_transaction():
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
