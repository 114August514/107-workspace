from uuid import UUID

from workspace107.domain.errors import ResourceConflict, ResourceNotFound
from workspace107.domain.models import NewUser, User
from workspace107.domain.ports.repositories import UnitOfWorkFactory


class UserService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        *,
        username: str,
        display_name: str,
        email: str | None = None,
    ) -> User:
        async with self._uow_factory() as uow:
            if await uow.users.get_by_username(username) is not None:
                raise ResourceConflict(f"username {username!r} already exists")
            user = await uow.users.add(
                NewUser(username=username, display_name=display_name, email=email)
            )
            await uow.commit()
            return user

    async def get(self, user_id: UUID) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get(user_id)
            if user is None:
                raise ResourceNotFound(f"user {user_id} not found")
            return user
