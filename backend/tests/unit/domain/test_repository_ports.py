from uuid import UUID

from workspace107.domain.models import NewUser, User
from workspace107.domain.ports.repositories import UserRepository


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def add(self, new: NewUser) -> User:
        user = User(
            id=new.id,
            username=new.username,
            display_name=new.display_name,
            email=new.email,
            created_at=new.created_at,
        )
        self.users[user.id] = user
        return user

    async def get(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.users.values() if user.username == username), None)


def accepts_user_repository(repository: UserRepository) -> UserRepository:
    return repository


async def test_user_repository_is_a_structural_contract() -> None:
    repository = accepts_user_repository(FakeUserRepository())
    created = await repository.add(NewUser(username="alice", display_name="Alice"))

    assert await repository.get(created.id) == created
    assert await repository.get_by_username("alice") == created
