from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import WorkspaceAccessDenied

_RANK = {
    WorkspaceRole.VIEWER: 0,
    WorkspaceRole.MEMBER: 1,
    WorkspaceRole.MANAGER: 2,
    WorkspaceRole.OWNER: 3,
}


def require_role(actual: WorkspaceRole, minimum: WorkspaceRole) -> None:
    if _RANK[actual] < _RANK[minimum]:
        raise WorkspaceAccessDenied(f"{minimum} role required")
