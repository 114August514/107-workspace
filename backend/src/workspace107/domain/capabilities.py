"""Membership roles map to server-authoritative capabilities."""

from __future__ import annotations

from enum import StrEnum

from .enums import MembershipRole


class Capability(StrEnum):
    """一个具体的操作许可。

    命名统一为 ``对象.动作``，方便在日志和错误信息里直接读。
    """

    # -- User Group governance ------------------------------------------
    USER_GROUP_VIEW = "user_group.view"
    USER_GROUP_UPDATE = "user_group.update"

    # -- 成员 ------------------------------------------------------------
    MEMBER_VIEW = "member.view"
    MEMBER_MANAGE = "member.manage"
    """邀请、移除、修改角色。"""
    OWNERSHIP_TRANSFER = "ownership.transfer"

    # -- 配置与权益 ------------------------------------------------------
    CONFIG_VIEW = "config.view"
    """查看 Variable 的值和 Secret 的名称；任何角色都读不到 Secret 值（§3.1.4）。"""
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

    # -- Shared Resource --------------------------------------------------
    SHARED_RESOURCE_VIEW = "shared_resource.view"
    """看 Workspace 内持有的 Shared Resource 及其版本。Platform 资源全平台可见，不靠这条。"""
    SHARED_RESOURCE_MANAGE = "shared_resource.manage"
    """在 Workspace 中创建 Shared Resource、修改名称与说明。"""
    SHARED_RESOURCE_VERSION_CREATE = "shared_resource.version.create"
    """为 Shared Resource 上传文件形成新的不可变版本。"""


_VIEW_ONLY: frozenset[Capability] = frozenset(
    {
        Capability.USER_GROUP_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
        Capability.ENTITLEMENT_VIEW,
        Capability.PROJECT_VIEW,
        Capability.RUN_VIEW,
        Capability.SHARED_RESOURCE_VIEW,
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
    Capability.SHARED_RESOURCE_MANAGE,
    Capability.SHARED_RESOURCE_VERSION_CREATE,
}

# 管空间需要的能力：改设置、管人、管配置。
_ADMINISTER: frozenset[Capability] = _CONTRIBUTE | {
    Capability.USER_GROUP_UPDATE,
    Capability.MEMBER_MANAGE,
    Capability.CONFIG_MANAGE,
}

ROLE_CAPABILITIES: dict[MembershipRole, frozenset[Capability]] = {
    # Owner 比 Admin 只多一样：转让所有权。这件事不可逆，只能由所有者本人做。
    MembershipRole.OWNER: _ADMINISTER | {Capability.OWNERSHIP_TRANSFER},
    MembershipRole.ADMIN: _ADMINISTER,
    MembershipRole.MEMBER: _CONTRIBUTE,
    MembershipRole.VIEWER: _VIEW_ONLY,
}

# 面向用户的说明，用在权限不足的错误信息里。
CAPABILITY_LABELS: dict[Capability, str] = {
    Capability.USER_GROUP_VIEW: "查看 User Group",
    Capability.USER_GROUP_UPDATE: "修改 User Group 设置",
    Capability.MEMBER_VIEW: "查看成员",
    Capability.MEMBER_MANAGE: "管理成员",
    Capability.OWNERSHIP_TRANSFER: "转让 User Group 所有权",
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
    Capability.SHARED_RESOURCE_VIEW: "查看 Shared Resource",
    Capability.SHARED_RESOURCE_MANAGE: "管理 Shared Resource",
    Capability.SHARED_RESOURCE_VERSION_CREATE: "上传 Shared Resource 版本",
}


def capabilities_of(role: MembershipRole) -> frozenset[Capability]:
    return ROLE_CAPABILITIES[role]


def describe(capability: Capability) -> str:
    return CAPABILITY_LABELS.get(capability, capability.value)
