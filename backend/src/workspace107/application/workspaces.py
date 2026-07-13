from dataclasses import replace
from uuid import UUID

from workspace107.domain.enums import WorkspaceKind, WorkspaceRole
from workspace107.domain.errors import (
    FinalOwnerRequired,
    InvalidWorkspaceParent,
    ResourceArchived,
    ResourceConflict,
    ResourceNotFound,
    WorkspaceAccessDenied,
)
from workspace107.domain.models import (
    NewWorkspace,
    NewWorkspaceMember,
    Workspace,
    WorkspaceMember,
    utc_now,
)
from workspace107.domain.permissions import require_role
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory


class WorkspaceService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        *,
        actor_id: UUID,
        kind: WorkspaceKind,
        name: str,
        slug: str,
        description: str = "",
        parent_id: UUID | None = None,
    ) -> Workspace:
        async with self._uow_factory() as uow:
            await self._validate_parent(uow, actor_id, kind, parent_id)
            if await uow.workspaces.get_by_slug(slug) is not None:
                raise ResourceConflict(f"workspace slug {slug!r} already exists")

            workspace = await uow.workspaces.add(
                NewWorkspace(
                    kind=kind,
                    name=name,
                    slug=slug,
                    description=description,
                    parent_id=parent_id,
                    created_by=actor_id,
                )
            )
            await uow.members.add(
                NewWorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=actor_id,
                    role=WorkspaceRole.OWNER,
                )
            )
            await uow.commit()
            return workspace

    async def list_visible(
        self, actor_id: UUID, *, limit: int, offset: int
    ) -> tuple[Workspace, ...]:
        async with self._uow_factory() as uow:
            return await uow.workspaces.list_for_user(actor_id, limit=limit, offset=offset)

    async def get(self, actor_id: UUID, workspace_id: UUID) -> Workspace:
        async with self._uow_factory() as uow:
            workspace, _ = await self._load_access(uow, actor_id, workspace_id)
            return workspace

    async def update(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
    ) -> Workspace:
        async with self._uow_factory() as uow:
            workspace, membership = await self._load_access(uow, actor_id, workspace_id)
            require_role(membership.role, WorkspaceRole.MANAGER)
            self._ensure_active(workspace)

            if slug is not None and slug != workspace.slug:
                existing = await uow.workspaces.get_by_slug(slug)
                if existing is not None:
                    raise ResourceConflict(f"workspace slug {slug!r} already exists")
            updated = replace(
                workspace,
                name=name if name is not None else workspace.name,
                slug=slug if slug is not None else workspace.slug,
                description=(description if description is not None else workspace.description),
            )
            updated = await uow.workspaces.save(updated)
            await uow.commit()
            return updated

    async def archive(self, actor_id: UUID, workspace_id: UUID) -> Workspace:
        async with self._uow_factory() as uow:
            workspace, membership = await self._load_access(uow, actor_id, workspace_id)
            require_role(membership.role, WorkspaceRole.OWNER)
            if workspace.archived_at is None:
                workspace = await uow.workspaces.save(replace(workspace, archived_at=utc_now()))
                await uow.commit()
            return workspace

    async def list_members(self, actor_id: UUID, workspace_id: UUID) -> tuple[WorkspaceMember, ...]:
        async with self._uow_factory() as uow:
            await self._load_access(uow, actor_id, workspace_id)
            return await uow.members.list_for_workspace(workspace_id)

    async def add_member(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        async with self._uow_factory() as uow:
            workspace, actor = await self._load_access(uow, actor_id, workspace_id)
            self._ensure_active(workspace)
            self._require_member_management(actor, role)
            if await uow.users.get(user_id) is None:
                raise ResourceNotFound(f"user {user_id} not found")
            if await uow.members.get(workspace_id, user_id) is not None:
                raise ResourceConflict("user is already a workspace member")

            member = await uow.members.add(
                NewWorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
            )
            await uow.commit()
            return member

    async def change_role(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        async with self._uow_factory() as uow:
            workspace, actor = await self._load_access(uow, actor_id, workspace_id)
            self._ensure_active(workspace)
            target = await uow.members.get(workspace_id, user_id)
            if target is None:
                raise ResourceNotFound("workspace member not found")
            self._require_member_management(actor, role, target.role)
            if target.role is WorkspaceRole.OWNER and role is not WorkspaceRole.OWNER:
                await self._ensure_another_owner(uow, workspace_id)

            changed = await uow.members.set_role(workspace_id, user_id, role)
            if changed is None:
                raise ResourceNotFound("workspace member not found")
            await uow.commit()
            return changed

    async def remove_member(
        self,
        *,
        actor_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> None:
        async with self._uow_factory() as uow:
            workspace, actor = await self._load_access(uow, actor_id, workspace_id)
            self._ensure_active(workspace)
            target = await uow.members.get(workspace_id, user_id)
            if target is None:
                raise ResourceNotFound("workspace member not found")
            self._require_member_management(actor, target.role, target.role)
            if target.role is WorkspaceRole.OWNER:
                await self._ensure_another_owner(uow, workspace_id)
            if not await uow.members.remove(workspace_id, user_id):
                raise ResourceNotFound("workspace member not found")
            await uow.commit()

    async def _validate_parent(
        self,
        uow: UnitOfWork,
        actor_id: UUID,
        kind: WorkspaceKind,
        parent_id: UUID | None,
    ) -> None:
        if kind is not WorkspaceKind.EXPERIMENT:
            if parent_id is not None:
                raise InvalidWorkspaceParent("only experiment workspaces may have a parent")
            return
        if parent_id is None:
            raise InvalidWorkspaceParent("experiment workspace requires a course parent")

        parent = await uow.workspaces.get(parent_id)
        if (
            parent is None
            or parent.kind is not WorkspaceKind.COURSE
            or parent.archived_at is not None
        ):
            raise InvalidWorkspaceParent("experiment parent must be an active course")
        if await uow.members.get(parent_id, actor_id) is None:
            raise WorkspaceAccessDenied("course membership required")

    async def _load_access(
        self, uow: UnitOfWork, actor_id: UUID, workspace_id: UUID
    ) -> tuple[Workspace, WorkspaceMember]:
        workspace = await uow.workspaces.get(workspace_id)
        if workspace is None:
            raise ResourceNotFound(f"workspace {workspace_id} not found")
        membership = await uow.members.get(workspace_id, actor_id)
        if membership is None:
            raise WorkspaceAccessDenied("workspace membership required")
        return workspace, membership

    @staticmethod
    def _ensure_active(workspace: Workspace) -> None:
        if workspace.archived_at is not None:
            raise ResourceArchived(f"workspace {workspace.id} is archived")

    @staticmethod
    def _require_member_management(
        actor: WorkspaceMember,
        requested_role: WorkspaceRole,
        current_role: WorkspaceRole | None = None,
    ) -> None:
        owner_change = requested_role is WorkspaceRole.OWNER or current_role is WorkspaceRole.OWNER
        require_role(
            actor.role,
            WorkspaceRole.OWNER if owner_change else WorkspaceRole.MANAGER,
        )

    @staticmethod
    async def _ensure_another_owner(uow: UnitOfWork, workspace_id: UUID) -> None:
        if await uow.members.count_owners(workspace_id) <= 1:
            raise FinalOwnerRequired("workspace must retain at least one owner")
