from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workspace107.domain.models import NewUser
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork


def accepts_uow_factory(factory: UnitOfWorkFactory) -> UnitOfWorkFactory:
    return factory


def test_sqlalchemy_uow_satisfies_the_domain_contract(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = accepts_uow_factory(lambda: SqlAlchemyUnitOfWork(session_factory))

    assert isinstance(factory(), SqlAlchemyUnitOfWork)


async def test_commit_is_visible_in_a_new_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user = await uow.users.add(NewUser(username="alice", display_name="Alice"))
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.users.get(user.id) == user


async def test_rollback_hides_an_uncommitted_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user = await uow.users.add(NewUser(username="alice", display_name="Alice"))
        await uow.rollback()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.users.get(user.id) is None


async def test_exception_rolls_back_the_transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = NewUser(username="alice", display_name="Alice")

    try:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.users.add(user)
            raise RuntimeError("stop")
    except RuntimeError:
        pass

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.users.get(user.id) is None
