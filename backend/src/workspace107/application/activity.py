"""Owner-scoped activity recording and authorized aggregation."""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from ..domain.capabilities import Capability, UserGroupCapability
from ..domain.enums import ActivityAction, TargetType
from ..domain.ids import ACTIVITY, new_id
from ..domain.models import Activity
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard

logger = logging.getLogger(__name__)


class SupportsNestedTransaction(Protocol):
    """Minimal application-facing savepoint dependency."""

    def begin_nested(self) -> AbstractAsyncContextManager[object]: ...


class ActivityRecorder:
    """Record successful business facts without failing their primary transaction."""

    def __init__(
        self,
        repos: Repositories,
        clock: Clock,
        session: SupportsNestedTransaction,
    ) -> None:
        self._repos = repos
        self._clock = clock
        self._session = session

    async def record(
        self,
        *,
        actor_id: str,
        owner: OwnerReference,
        action: ActivityAction,
        target_type: TargetType,
        target_id: str,
        target_name: str,
        project_id: str | None = None,
        detail: str = "",
    ) -> None:
        try:
            async with self._session.begin_nested():
                actor = await self._repos.users.get(actor_id)
                await self._repos.activities.add(
                    Activity(
                        id=new_id(ACTIVITY),
                        owner=owner,
                        project_id=project_id,
                        actor_id=actor_id,
                        actor_name=actor.username if actor else actor_id,
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        target_name=target_name,
                        detail=detail,
                        created_at=self._clock.now(),
                    )
                )
        except Exception:
            logger.warning(
                "写入活动失败，已跳过",
                extra={
                    "action": action.value,
                    "owner_kind": owner.kind.value,
                    "owner_id": owner.id,
                },
                exc_info=True,
            )


class ActivityService:
    """Read activity only after repository-backed current-authority checks."""

    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def list_for_user(self, user_id: str, page: PageRequest) -> Page[Activity]:
        return await self._repos.activities.list_for_user(user_id, page)

    async def list_for_user_group(
        self, user_id: str, user_group_id: str, page: PageRequest
    ) -> Page[Activity]:
        await self._guard.user_group(
            user_id, user_group_id, needs=UserGroupCapability.USER_GROUP_VIEW
        )
        return await self._repos.activities.list_for_owner(
            OwnerReference(OwnerKind.USER_GROUP, user_group_id), page
        )

    async def list_for_project(
        self, user_id: str, project_id: str, page: PageRequest
    ) -> Page[Activity]:
        await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_VIEW, owner_scope=True
        )
        return await self._repos.activities.list_for_project(project_id, page)
