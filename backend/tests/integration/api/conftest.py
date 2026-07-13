from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    app = create_app(uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as current:
        yield current

    await engine.dispose()
