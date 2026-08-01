"""AccessGuard 权限解析。

对应 GR-001：Workspace 是基础归属边界。
对应 GR-013：无发现权限时对象视为不存在——抛 ObjectNotFound 而不是 PermissionDenied。
"""

from __future__ import annotations

import pytest

from workspace107.domain.capabilities import Capability
from workspace107.domain.enums import WorkspaceRole
from workspace107.domain.errors import ObjectNotFound, PermissionDenied


async def test_personal_workspace_只有所属用户可见(services, guard) -> None:
    owner = await services.workspaces.ensure_user("alice")
    other = await services.workspaces.ensure_user("bob")
    workspace = await services.workspaces.personal_workspace(owner.id)

    access = await guard.workspace(owner.id, workspace.id)
    assert access.role is WorkspaceRole.OWNER

    # 对 bob 来说这个 Workspace 就是不存在，而不是「存在但没权限」。
    with pytest.raises(ObjectNotFound):
        await guard.workspace(other.id, workspace.id)


async def test_协作空间成员按角色解析(services, guard) -> None:
    owner = await services.workspaces.ensure_user("alice")
    member = await services.workspaces.ensure_user("bob")
    workspace = (await services.workspaces.create_collaborative(owner.id, "算法组", "")).workspace

    with pytest.raises(ObjectNotFound):
        await guard.workspace(member.id, workspace.id)

    await services.workspaces.invite_member(owner.id, workspace.id, "bob", WorkspaceRole.MEMBER)
    # 还没接受邀请，仍然不可见。
    with pytest.raises(ObjectNotFound):
        await guard.workspace(member.id, workspace.id)

    await services.workspaces.respond_to_invitation(member.id, workspace.id, accept=True)
    access = await guard.workspace(member.id, workspace.id)
    assert access.role is WorkspaceRole.MEMBER
    assert access.can(Capability.RUN_SUBMIT)
    assert not access.can(Capability.MEMBER_MANAGE)


async def test_普通成员执行_owner_操作时得到_403_而不是_404(services, guard) -> None:
    """对象已经可见了，这时候角色不足就是明确的权限问题。"""
    owner = await services.workspaces.ensure_user("alice")
    member = await services.workspaces.ensure_user("bob")
    workspace = (await services.workspaces.create_collaborative(owner.id, "算法组", "")).workspace
    await services.workspaces.invite_member(owner.id, workspace.id, "bob", WorkspaceRole.MEMBER)
    await services.workspaces.respond_to_invitation(member.id, workspace.id, accept=True)

    with pytest.raises(PermissionDenied):
        await guard.workspace(member.id, workspace.id, needs=Capability.MEMBER_MANAGE)


async def test_退出后重新变为不可见(services, guard) -> None:
    owner = await services.workspaces.ensure_user("alice")
    member = await services.workspaces.ensure_user("bob")
    workspace = (await services.workspaces.create_collaborative(owner.id, "算法组", "")).workspace
    await services.workspaces.invite_member(owner.id, workspace.id, "bob", WorkspaceRole.MEMBER)
    await services.workspaces.respond_to_invitation(member.id, workspace.id, accept=True)

    await services.workspaces.leave(member.id, workspace.id)
    with pytest.raises(ObjectNotFound):
        await guard.workspace(member.id, workspace.id)


async def test_归属空间不可见时_project_也视为不存在(services, guard) -> None:
    owner = await services.workspaces.ensure_user("alice")
    other = await services.workspaces.ensure_user("bob")
    workspace = await services.workspaces.personal_workspace(owner.id)
    project = await services.projects.create(owner.id, workspace.id, "私有项目")

    with pytest.raises(ObjectNotFound) as excinfo:
        await guard.project(other.id, project.id)
    # 错误信息里说的是 Project 不存在，不透露它属于谁。
    assert excinfo.value.kind == "Project"
