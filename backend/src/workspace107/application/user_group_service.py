"""User Group and Membership governance use cases."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability, capabilities_of
from ..domain.enums import (
    ActivityAction,
    LegacyWorkspaceKind,
    MembershipRole,
    MembershipStatus,
    TargetType,
)
from ..domain.errors import ConflictError, ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.models import LegacyWorkspace, Membership, User, UserGroup
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard, UserGroupAccess
from .activity import ActivityRecorder
from .notifier import Notifier


def _reject_owner_role(role: MembershipRole) -> None:
    if role is MembershipRole.OWNER:
        raise ConflictError("不能直接把成员设为 Owner，请使用转让所有权")


@dataclass(frozen=True, slots=True)
class UserGroupView:
    user_group: UserGroup
    role: MembershipRole
    capabilities: frozenset[Capability]


@dataclass(frozen=True, slots=True)
class MemberView:
    membership: Membership
    user: User


@dataclass(frozen=True, slots=True)
class InvitationView:
    user_group: UserGroup
    membership: Membership


class UserGroupService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        activity: ActivityRecorder,
        notifier: Notifier,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._activity = activity
        self._notifier = notifier

    async def _lock_and_authorize_mutation(
        self,
        user_id: str,
        user_group_id: str,
        *,
        needs: Capability | None = None,
    ) -> UserGroupAccess:
        """Use one lock order: UserGroup row, authenticated discovery, Membership state."""
        if await self._repos.user_groups.get_for_update(user_group_id) is None:
            raise ObjectNotFound("User Group", user_group_id)
        return await self._guard.user_group(user_id, user_group_id, needs=needs)

    async def list_for_user(self, user_id: str) -> list[UserGroupView]:
        result: list[UserGroupView] = []
        for group in await self._repos.user_groups.list_for_user(user_id):
            access = await self._guard.user_group(user_id, group.id)
            result.append(
                UserGroupView(
                    user_group=group,
                    role=access.role,
                    capabilities=access.capabilities,
                )
            )
        return result

    async def get(self, user_id: str, user_group_id: str) -> UserGroupView:
        access = await self._guard.user_group(user_id, user_group_id)
        return UserGroupView(
            user_group=access.user_group,
            role=access.role,
            capabilities=access.capabilities,
        )

    async def create(self, user_id: str, name: str, description: str = "") -> UserGroupView:
        name = name.strip()
        if not name:
            raise ValidationFailed("User Group 名称不能为空")
        now = self._clock.now()
        group = UserGroup(
            id=ids.new_id(ids.USER_GROUP),
            name=name,
            description=description,
            created_by_id=user_id,
            created_at=now,
        )
        await self._repos.user_groups.add(group)
        # Private same-ID anchor: required only while #36-#42 tables still FK to workspaces.id.
        await self._repos.legacy_workspaces.add(
            LegacyWorkspace(
                id=group.id,
                kind=LegacyWorkspaceKind.COLLABORATIVE,
                name=group.name,
                description=group.description,
                owner_id=user_id,
                created_at=now,
            )
        )
        await self._repos.memberships.add(
            Membership(
                id=ids.new_id(ids.MEMBERSHIP),
                user_group_id=group.id,
                user_id=user_id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=now,
            )
        )
        await self._activity.record(
            actor_id=user_id,
            workspace_id=group.id,
            action=ActivityAction.USER_GROUP_CREATED,
            target_type=TargetType.USER_GROUP,
            target_id=group.id,
            target_name=group.name,
        )
        return UserGroupView(
            user_group=group,
            role=MembershipRole.OWNER,
            capabilities=capabilities_of(MembershipRole.OWNER),
        )

    async def update(
        self,
        user_id: str,
        user_group_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> UserGroup:
        access = await self._guard.user_group(
            user_id, user_group_id, needs=Capability.USER_GROUP_UPDATE
        )
        group = access.user_group
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationFailed("User Group 名称不能为空")
            group.name = name
        if description is not None:
            group.description = description
        await self._repos.user_groups.update(group)
        anchor = await self._repos.legacy_workspaces.get(group.id)
        if anchor is None:
            raise ObjectNotFound("Legacy Workspace anchor", group.id)
        anchor.name = group.name
        anchor.description = group.description
        await self._repos.legacy_workspaces.update(anchor)
        await self._activity.record(
            actor_id=user_id,
            workspace_id=group.id,
            action=ActivityAction.USER_GROUP_UPDATED,
            target_type=TargetType.USER_GROUP,
            target_id=group.id,
            target_name=group.name,
        )
        return group

    async def list_invitations(self, user_id: str) -> list[InvitationView]:
        result: list[InvitationView] = []
        for membership in await self._repos.memberships.list_pending_for_user(user_id):
            group = await self._repos.user_groups.get(membership.user_group_id)
            if group is not None:
                result.append(InvitationView(user_group=group, membership=membership))
        return result

    async def list_members(self, user_id: str, user_group_id: str) -> list[MemberView]:
        await self._guard.user_group(user_id, user_group_id, needs=Capability.MEMBER_VIEW)
        result: list[MemberView] = []
        for membership in await self._repos.memberships.list_for_user_group(user_group_id):
            user = await self._repos.users.get(membership.user_id)
            if user is not None:
                result.append(MemberView(membership=membership, user=user))
        return result

    async def invite_member(
        self,
        user_id: str,
        user_group_id: str,
        username: str,
        role: MembershipRole,
    ) -> Membership:
        access = await self._lock_and_authorize_mutation(
            user_id, user_group_id, needs=Capability.MEMBER_MANAGE
        )
        _reject_owner_role(role)
        invitee = await self._repos.users.get_by_username(username)
        if invitee is None:
            raise ObjectNotFound("User", username)
        membership = await self._repos.memberships.get(user_group_id, invitee.id)
        if membership is not None and membership.status in {
            MembershipStatus.INVITED,
            MembershipStatus.ACTIVE,
        }:
            raise ConflictError(f"{username} 已经是该 User Group 的成员或已被邀请")
        if membership is None:
            membership = Membership(
                id=ids.new_id(ids.MEMBERSHIP),
                user_group_id=user_group_id,
                user_id=invitee.id,
                role=role,
                status=MembershipStatus.INVITED,
                created_at=self._clock.now(),
            )
            await self._repos.memberships.add(membership)
        else:
            membership.role = role
            membership.status = MembershipStatus.INVITED
            await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            user_group_id=user_group_id,
            action=ActivityAction.MEMBER_INVITED,
            member=invitee,
            detail=f"角色 {role.value}",
        )
        await self._notifier.user_group_invited(
            actor_id=user_id,
            invitee_id=invitee.id,
            user_group_id=user_group_id,
            user_group_name=access.user_group.name,
            role=role.value,
        )
        return membership

    async def respond_to_invitation(
        self, user_id: str, user_group_id: str, *, accept: bool
    ) -> Membership:
        if await self._repos.user_groups.get_for_update(user_group_id) is None:
            raise ObjectNotFound("User Group 邀请", user_group_id)
        membership = await self._repos.memberships.get(user_group_id, user_id)
        if membership is None or membership.status is not MembershipStatus.INVITED:
            raise ObjectNotFound("User Group 邀请", user_group_id)
        membership.status = MembershipStatus.ACTIVE if accept else MembershipStatus.LEFT
        await self._repos.memberships.update(membership)
        if accept:
            await self._record_member_activity(
                actor_id=user_id,
                user_group_id=user_group_id,
                action=ActivityAction.MEMBER_JOINED,
                member=await self._repos.users.get(user_id),
            )
        return membership

    async def remove_member(self, user_id: str, user_group_id: str, target_user_id: str) -> None:
        access = await self._lock_and_authorize_mutation(
            user_id, user_group_id, needs=Capability.MEMBER_MANAGE
        )
        owner = await self._repos.memberships.get_active_owner(user_group_id)
        if owner is not None and owner.user_id == target_user_id:
            raise ConflictError("不能移除 User Group Owner，请先转让所有权")
        membership = await self._repos.memberships.get(user_group_id, target_user_id)
        if membership is None:
            raise ObjectNotFound("Membership", target_user_id)
        if membership.status is MembershipStatus.REMOVED:
            return
        membership.status = MembershipStatus.REMOVED
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            user_group_id=user_group_id,
            action=ActivityAction.MEMBER_REMOVED,
            member=await self._repos.users.get(target_user_id),
        )
        await self._notifier.member_removed(
            actor_id=user_id,
            member_id=target_user_id,
            user_group_id=user_group_id,
            user_group_name=access.user_group.name,
        )

    async def change_member_role(
        self,
        user_id: str,
        user_group_id: str,
        target_user_id: str,
        role: MembershipRole,
    ) -> Membership:
        access = await self._lock_and_authorize_mutation(
            user_id, user_group_id, needs=Capability.MEMBER_MANAGE
        )
        _reject_owner_role(role)
        owner = await self._repos.memberships.get_active_owner(user_group_id)
        if owner is not None and owner.user_id == target_user_id:
            raise ConflictError("不能修改 User Group Owner 的角色，请先转让所有权")
        membership = await self._repos.memberships.get(user_group_id, target_user_id)
        if membership is None or not membership.is_active:
            raise ObjectNotFound("Membership", target_user_id)
        previous = membership.role
        membership.role = role
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            user_group_id=user_group_id,
            action=ActivityAction.MEMBER_ROLE_CHANGED,
            member=await self._repos.users.get(target_user_id),
            detail=f"{previous.value} → {role.value}",
        )
        await self._notifier.role_changed(
            actor_id=user_id,
            member_id=target_user_id,
            user_group_id=user_group_id,
            user_group_name=access.user_group.name,
            role=role.value,
        )
        return membership

    async def leave(self, user_id: str, user_group_id: str) -> None:
        await self._lock_and_authorize_mutation(user_id, user_group_id)
        owner = await self._repos.memberships.get_active_owner(user_group_id)
        if owner is not None and owner.user_id == user_id:
            raise PermissionDenied("Owner 不能直接退出，请先转让 User Group 所有权")
        membership = await self._repos.memberships.get(user_group_id, user_id)
        if membership is None:  # pragma: no cover - guard already established it
            raise ObjectNotFound("Membership", user_id)
        membership.status = MembershipStatus.LEFT
        await self._repos.memberships.update(membership)
        await self._record_member_activity(
            actor_id=user_id,
            user_group_id=user_group_id,
            action=ActivityAction.MEMBER_LEFT,
            member=await self._repos.users.get(user_id),
        )

    async def transfer_ownership(
        self, user_id: str, user_group_id: str, target_user_id: str
    ) -> None:
        access = await self._lock_and_authorize_mutation(
            user_id, user_group_id, needs=Capability.OWNERSHIP_TRANSFER
        )
        group = access.user_group
        current = await self._repos.memberships.get(user_group_id, user_id)
        if current is None or not current.is_active or current.role is not MembershipRole.OWNER:
            raise PermissionDenied("只有当前 User Group Owner 可以转让所有权")
        target = await self._repos.memberships.get(user_group_id, target_user_id)
        if target is None or not target.is_active:
            raise ObjectNotFound("Membership", target_user_id)
        if target_user_id == user_id:
            raise ConflictError("这个成员已经是 User Group Owner")

        current.role = MembershipRole.ADMIN
        await self._repos.memberships.update(current)
        target.role = MembershipRole.OWNER
        await self._repos.memberships.update(target)
        anchor = await self._repos.legacy_workspaces.get(user_group_id)
        if anchor is None:
            raise ObjectNotFound("Legacy Workspace anchor", user_group_id)
        anchor.owner_id = target_user_id
        await self._repos.legacy_workspaces.update(anchor)
        owner = await self._repos.memberships.get_active_owner(user_group_id)
        if owner is None or owner.user_id != target_user_id:  # pragma: no cover - DB corruption
            raise ConflictError("User Group 所有权转让未形成唯一有效 Owner")
        await self._record_member_activity(
            actor_id=user_id,
            user_group_id=user_group_id,
            action=ActivityAction.OWNERSHIP_TRANSFERRED,
            member=await self._repos.users.get(target_user_id),
        )
        await self._notifier.ownership_received(
            actor_id=user_id,
            new_owner_id=target_user_id,
            user_group_id=user_group_id,
            user_group_name=group.name,
        )

    async def _record_member_activity(
        self,
        *,
        actor_id: str,
        user_group_id: str,
        action: ActivityAction,
        member: User | None,
        detail: str = "",
    ) -> None:
        if member is None:
            return
        await self._activity.record(
            actor_id=actor_id,
            workspace_id=user_group_id,
            action=action,
            target_type=TargetType.MEMBER,
            target_id=member.id,
            target_name=member.display_name,
            detail=detail,
        )
