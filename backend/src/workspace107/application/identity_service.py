"""User identity use cases."""

from __future__ import annotations

from ..domain import ids
from ..domain.models import User
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .activity import SupportsNestedTransaction


class IdentityService:
    def __init__(
        self, repos: Repositories, clock: Clock, session: SupportsNestedTransaction
    ) -> None:
        self._repos = repos
        self._clock = clock
        self._session = session

    async def ensure_user(self, username: str, display_name: str = "") -> User:
        """Create a dev identity if absent; never creates a Personal Workspace."""
        existing = await self._repos.users.get_by_username(username)
        if existing is not None:
            return existing

        user = User(
            id=ids.new_id(ids.USER),
            username=username,
            display_name=display_name or username,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin_nested():
                await self._repos.users.add(user)
        except Exception:
            winner = await self._repos.users.get_by_username(username)
            if winner is None:  # pragma: no cover - non-unique failure
                raise
            return winner
        return user
