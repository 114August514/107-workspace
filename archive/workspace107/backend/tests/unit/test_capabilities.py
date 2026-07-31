"""角色能力矩阵。

这张表是安全边界，不是配置。改动它意味着某些人突然能做以前不能做的事，
所以每一格都要显式写出来——**测试失败时应该先想「这是不是我要的」，
而不是顺手改断言**。

设计稿只规定了有哪四个角色，没规定各自能做什么。矩阵的理由见
docs/decisions/0008-capability-based-authorization.md。
"""

from __future__ import annotations

import pytest

from workspace107.domain.capabilities import (
    CAPABILITY_LABELS,
    ROLE_CAPABILITIES,
    Capability,
    capabilities_of,
)
from workspace107.domain.enums import WorkspaceRole

# 每个角色**预期**拥有的能力。写全，不用集合运算推导——
# 推导出来的表看不出「谁比谁多了什么」，而那正是评审时要看的。
EXPECTED: dict[WorkspaceRole, set[Capability]] = {
    WorkspaceRole.VIEWER: {
        Capability.WORKSPACE_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
        Capability.ENTITLEMENT_VIEW,
        Capability.PROJECT_VIEW,
        Capability.RUN_VIEW,
    },
    WorkspaceRole.MEMBER: {
        Capability.WORKSPACE_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
        Capability.ENTITLEMENT_VIEW,
        Capability.PROJECT_VIEW,
        Capability.RUN_VIEW,
        Capability.PROJECT_CREATE,
        Capability.PROJECT_UPDATE,
        Capability.PROJECT_CONTENT_WRITE,
        Capability.RUN_CONFIGURATION_MANAGE,
        Capability.RUN_SUBMIT,
        Capability.RUN_CANCEL,
    },
    WorkspaceRole.ADMIN: {
        Capability.WORKSPACE_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
        Capability.ENTITLEMENT_VIEW,
        Capability.PROJECT_VIEW,
        Capability.RUN_VIEW,
        Capability.PROJECT_CREATE,
        Capability.PROJECT_UPDATE,
        Capability.PROJECT_CONTENT_WRITE,
        Capability.RUN_CONFIGURATION_MANAGE,
        Capability.RUN_SUBMIT,
        Capability.RUN_CANCEL,
        Capability.WORKSPACE_UPDATE,
        Capability.MEMBER_MANAGE,
        Capability.CONFIG_MANAGE,
    },
    WorkspaceRole.OWNER: set(Capability),
}


@pytest.mark.parametrize("role", list(WorkspaceRole), ids=lambda r: r.value)
def test_角色能力与矩阵一致(role: WorkspaceRole) -> None:
    assert capabilities_of(role) == EXPECTED[role], (
        f"{role.value} 的能力和预期不一致。如果这是有意的改动，请同步更新 ADR-0008 和这里的期望表。"
    )


def test_viewer_不能做任何写操作() -> None:
    """Viewer 是给旁听的人用的：能看，不能改，也不能花算力。"""
    viewer = capabilities_of(WorkspaceRole.VIEWER)
    forbidden = [
        Capability.PROJECT_CREATE,
        Capability.PROJECT_UPDATE,
        Capability.PROJECT_CONTENT_WRITE,
        Capability.RUN_CONFIGURATION_MANAGE,
        Capability.RUN_SUBMIT,
        Capability.RUN_CANCEL,
        Capability.WORKSPACE_UPDATE,
        Capability.MEMBER_MANAGE,
        Capability.CONFIG_MANAGE,
        Capability.OWNERSHIP_TRANSFER,
    ]
    assert [c for c in forbidden if c in viewer] == []


def test_member_不能碰空间配置和成员() -> None:
    """Member 是干活的人：能建项目能跑作业，但不管人也不改空间设置。"""
    member = capabilities_of(WorkspaceRole.MEMBER)
    assert Capability.RUN_SUBMIT in member
    assert Capability.PROJECT_CONTENT_WRITE in member
    assert Capability.MEMBER_MANAGE not in member
    assert Capability.CONFIG_MANAGE not in member
    assert Capability.WORKSPACE_UPDATE not in member


def test_owner_只比_admin_多一样转让所有权() -> None:
    """转让不可逆，只能由所有者本人做；其余管理能力 Admin 都有。"""
    difference = capabilities_of(WorkspaceRole.OWNER) - capabilities_of(WorkspaceRole.ADMIN)
    assert difference == {Capability.OWNERSHIP_TRANSFER}


def test_能力是逐级包含的() -> None:
    """Viewer ⊂ Member ⊂ Admin ⊂ Owner。

    不是所有权限模型都该这样，但这个项目里角色就是「权限逐级增加」，
    出现交叉说明有人加错了地方。
    """
    viewer = capabilities_of(WorkspaceRole.VIEWER)
    member = capabilities_of(WorkspaceRole.MEMBER)
    admin = capabilities_of(WorkspaceRole.ADMIN)
    owner = capabilities_of(WorkspaceRole.OWNER)

    assert viewer < member < admin < owner


def test_每个能力都有中文说明() -> None:
    """说明会出现在权限不足的错误信息里，漏一个用户就会看到英文标识符。"""
    missing = [c.value for c in Capability if c not in CAPABILITY_LABELS]
    assert missing == []


def test_矩阵覆盖全部角色() -> None:
    assert set(ROLE_CAPABILITIES) == set(WorkspaceRole)
