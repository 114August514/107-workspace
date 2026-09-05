"""User identity use cases."""

from __future__ import annotations

import re

from ..domain import ids
from ..domain.errors import ConflictError, ObjectNotFound, ValidationFailed
from ..domain.models import ExternalIdentity, ExternalIdentityProfile, User
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .activity import SupportsNestedTransaction

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._~-]{1,64}$")


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

    async def update_profile(
        self,
        user_id: str,
        *,
        username: str | None = None,
        display_name: str | None = None,
    ) -> User:
        """Update the current User's visible username and display name."""
        user = await self._repos.users.get(user_id)
        if user is None:
            raise ObjectNotFound("User", user_id)
        if username is not None:
            candidate = username.strip()
            if not candidate:
                raise ValidationFailed("用户名不能为空")
            if not _USERNAME_RE.fullmatch(candidate):
                raise ValidationFailed("用户名只能包含字母、数字、点、下划线、连字符和波浪号")
            if candidate != user.username:
                taken = await self._repos.users.get_by_username(candidate)
                if taken is not None:
                    raise ConflictError("这个用户名已经被占用")
                user.username = candidate
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise ValidationFailed("显示名称不能为空")
            if len(name) > 128:
                raise ValidationFailed("显示名称不能超过 128 个字符")
            user.display_name = name
        await self._repos.users.update(user)
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
