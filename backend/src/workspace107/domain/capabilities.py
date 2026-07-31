"""角色能力模型。

权限判断写成 ``role is WorkspaceRole.OWNER`` 的话，每加一个角色就要把所有判断点
翻一遍，而且很容易漏——漏掉的那处就是一个越权。所以判断的对象是**能力**，
角色只是能力的一个命名集合。

设计稿（§2.2 C）只规定了有 Owner / Admin / Member / Viewer 四个角色，
没有规定各自能做什么。下面这张表是本项目的选择，理由见
[ADR-0008](../../../../docs/decisions/0008-capability-based-authorization.md)。

判断权限时永远问「有没有这个能力」，不要问「是不是某个角色」。
"""

from __future__ import annotations

from enum import StrEnum

from .enums import WorkspaceRole


class Capability(StrEnum):
    """一个具体的操作许可。

    命名统一为 ``对象.动作``，方便在日志和错误信息里直接读。
    """

    # -- Workspace 本身 --------------------------------------------------
    WORKSPACE_VIEW = "workspace.view"
    WORKSPACE_UPDATE = "workspace.update"

    # -- 成员 ------------------------------------------------------------
    MEMBER_VIEW = "member.view"
    MEMBER_MANAGE = "member.manage"
    """邀请、移除、修改角色。"""
    OWNERSHIP_TRANSFER = "ownership.transfer"

    # -- 配置与权益 ------------------------------------------------------
    CONFIG_VIEW = "config.view"
    """查看 Variable 的值和 Secret 的名称。Secret 的值任何角色都读不到（GR-012）。"""
    CONFIG_MANAGE = "config.manage"
    ENTITLEMENT_VIEW = "entitlement.view"

    # -- Project ---------------------------------------------------------
    PROJECT_VIEW = "project.view"
    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    """改名称、说明、默认环境、归档状态。"""
    PROJECT_CONTENT_WRITE = "project.content.write"
    """改文件、保存版本、恢复版本。"""
    RUN_CONFIGURATION_MANAGE = "run_configuration.manage"

    # -- Run --------------------------------------------------------------
    RUN_VIEW = "run.view"
    """看 Run、日志、事件和产物。"""
    RUN_SUBMIT = "run.submit"
    """提交和重跑。两者都消耗算力，所以是同一个能力。"""
    RUN_CANCEL = "run.cancel"


_VIEW_ONLY: frozenset[Capability] = frozenset(
    {
        Capability.WORKSPACE_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
        Capability.ENTITLEMENT_VIEW,
        Capability.PROJECT_VIEW,
        Capability.RUN_VIEW,
    }
)

# 干活需要的能力：建项目、改内容、跑作业。
_CONTRIBUTE: frozenset[Capability] = _VIEW_ONLY | {
    Capability.PROJECT_CREATE,
    Capability.PROJECT_UPDATE,
    Capability.PROJECT_CONTENT_WRITE,
    Capability.RUN_CONFIGURATION_MANAGE,
    Capability.RUN_SUBMIT,
    Capability.RUN_CANCEL,
}

# 管空间需要的能力：改设置、管人、管配置。
_ADMINISTER: frozenset[Capability] = _CONTRIBUTE | {
    Capability.WORKSPACE_UPDATE,
    Capability.MEMBER_MANAGE,
    Capability.CONFIG_MANAGE,
}

ROLE_CAPABILITIES: dict[WorkspaceRole, frozenset[Capability]] = {
    # Owner 比 Admin 只多一样：转让所有权。这件事不可逆，只能由所有者本人做。
    WorkspaceRole.OWNER: _ADMINISTER | {Capability.OWNERSHIP_TRANSFER},
    WorkspaceRole.ADMIN: _ADMINISTER,
    WorkspaceRole.MEMBER: _CONTRIBUTE,
    WorkspaceRole.VIEWER: _VIEW_ONLY,
}

# 面向用户的说明，用在权限不足的错误信息里。
CAPABILITY_LABELS: dict[Capability, str] = {
    Capability.WORKSPACE_VIEW: "查看空间",
    Capability.WORKSPACE_UPDATE: "修改空间设置",
    Capability.MEMBER_VIEW: "查看成员",
    Capability.MEMBER_MANAGE: "管理成员",
    Capability.OWNERSHIP_TRANSFER: "转让空间所有权",
    Capability.CONFIG_VIEW: "查看配置",
    Capability.CONFIG_MANAGE: "管理配置变量与 Secret",
    Capability.ENTITLEMENT_VIEW: "查看资源权益",
    Capability.PROJECT_VIEW: "查看 Project",
    Capability.PROJECT_CREATE: "创建 Project",
    Capability.PROJECT_UPDATE: "修改 Project 设置",
    Capability.PROJECT_CONTENT_WRITE: "修改项目内容",
    Capability.RUN_CONFIGURATION_MANAGE: "管理运行方案",
    Capability.RUN_VIEW: "查看 Run",
    Capability.RUN_SUBMIT: "提交 Run",
    Capability.RUN_CANCEL: "取消 Run",
}


def capabilities_of(role: WorkspaceRole) -> frozenset[Capability]:
    return ROLE_CAPABILITIES[role]


def describe(capability: Capability) -> str:
    return CAPABILITY_LABELS.get(capability, capability.value)
