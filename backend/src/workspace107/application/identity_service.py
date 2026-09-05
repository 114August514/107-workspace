"""User identity use cases."""

from __future__ import annotations

from ..domain import ids
from ..domain.models import ExternalIdentity, ExternalIdentityProfile, User
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
        """Create a dev identity if absent without ownership side effects."""
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

    async def resolve_external_identity(self, profile: ExternalIdentityProfile) -> User:
        """Resolve or atomically bootstrap one external identity mapping."""
        existing = await self._repos.external_identities.get(
            profile.provider, profile.provider_user_id
        )
        if existing is not None:
            return await self._linked_user(existing)

        user_id = ids.new_id(ids.USER)
        username = await self._available_username(profile.username, user_id)
        user = User(
            id=user_id,
            username=username,
            display_name=profile.display_name or profile.username,
            email=profile.email,
            created_at=self._clock.now(),
        )
        identity = ExternalIdentity(
            id=ids.new_id(ids.EXTERNAL_IDENTITY),
            provider=profile.provider,
            provider_user_id=profile.provider_user_id,
            user_id=user.id,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin_nested():
                await self._repos.users.add(user)
                await self._repos.external_identities.add(identity)
        except Exception:
            winner = await self._repos.external_identities.get(
                profile.provider, profile.provider_user_id
            )
            if winner is None:  # pragma: no cover - non-identity failure
                raise
            return await self._linked_user(winner)
        return user

    async def _linked_user(self, identity: ExternalIdentity) -> User:
        user = await self._repos.users.get(identity.user_id)
        if user is None:  # pragma: no cover - protected by the database foreign key
            raise RuntimeError(f"External identity {identity.id} has no linked User")
        return user

    async def _available_username(self, preferred: str, user_id: str) -> str:
        """Keep the provider name when safe without ever merging by username."""
        candidate = preferred.strip()[:64]
        if candidate and await self._repos.users.get_by_username(candidate) is None:
            return candidate

        # A dev identity or another provider may already use the same visible name.
        # The generated User id makes the fallback stable and collision-resistant while
        # preserving enough of the asserted name to remain recognizable.
        stem = candidate[:43] or "user"
        return f"{stem}~{user_id.removeprefix('usr_')}"
