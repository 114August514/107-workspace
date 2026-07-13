from uuid import UUID

from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import ResourceArchived, ResourceNotFound, WorkspaceAccessDenied
from workspace107.domain.models import Workspace, WorkspaceMember
from workspace107.domain.permissions import require_role
from workspace107.domain.ports.repositories import UnitOfWork


async def require_workspace_access(
    uow: UnitOfWork,
    *,
    actor_id: UUID,
    workspace_id: UUID,
    minimum: WorkspaceRole = WorkspaceRole.VIEWER,
    active: bool = False,
) -> tuple[Workspace, WorkspaceMember]:
    workspace = await uow.workspaces.get(workspace_id)
    if workspace is None:
        raise ResourceNotFound(f"workspace {workspace_id} not found")
    membership = await uow.members.get(workspace_id, actor_id)
    if membership is None:
        raise WorkspaceAccessDenied("workspace membership required")
    require_role(membership.role, minimum)
    if active and workspace.archived_at is not None:
        raise ResourceArchived(f"workspace {workspace_id} is archived")
    return workspace, membership
