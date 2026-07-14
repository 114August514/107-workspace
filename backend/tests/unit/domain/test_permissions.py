import pytest

from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import WorkspaceAccessDenied
from workspace107.domain.permissions import require_role


@pytest.mark.parametrize(
    ("actual", "minimum"),
    [
        (WorkspaceRole.VIEWER, WorkspaceRole.VIEWER),
        (WorkspaceRole.MEMBER, WorkspaceRole.MEMBER),
        (WorkspaceRole.MANAGER, WorkspaceRole.MEMBER),
        (WorkspaceRole.OWNER, WorkspaceRole.MANAGER),
    ],
)
def test_role_meets_minimum(actual: WorkspaceRole, minimum: WorkspaceRole) -> None:
    require_role(actual, minimum)


def test_viewer_cannot_write_content() -> None:
    with pytest.raises(WorkspaceAccessDenied, match="member role required"):
        require_role(WorkspaceRole.VIEWER, WorkspaceRole.MEMBER)


def test_member_cannot_manage_workspace() -> None:
    with pytest.raises(WorkspaceAccessDenied, match="manager role required"):
        require_role(WorkspaceRole.MEMBER, WorkspaceRole.MANAGER)
