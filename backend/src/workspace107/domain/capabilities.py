"""Membership roles map to server-authoritative capabilities."""

from __future__ import annotations

from enum import StrEnum

from .enums import MembershipRole


class UserGroupCapability(StrEnum):
    """Stable public capabilities for User Group and Membership governance."""

    USER_GROUP_VIEW = "user_group.view"
    USER_GROUP_UPDATE = "user_group.update"
    MEMBER_VIEW = "member.view"
    MEMBER_INVITE = "member.invite"
    MEMBER_REMOVE = "member.remove"
    MEMBER_ROLE_MANAGE = "member.role.manage"
    OWNERSHIP_TRANSFER = "ownership.transfer"


_USER_GROUP_VIEW: frozenset[UserGroupCapability] = frozenset(
    {
        UserGroupCapability.USER_GROUP_VIEW,
        UserGroupCapability.MEMBER_VIEW,
    }
)

_USER_GROUP_ADMINISTER: frozenset[UserGroupCapability] = _USER_GROUP_VIEW | {
    UserGroupCapability.USER_GROUP_UPDATE,
    UserGroupCapability.MEMBER_INVITE,
    UserGroupCapability.MEMBER_REMOVE,
}

USER_GROUP_ROLE_CAPABILITIES: dict[MembershipRole, frozenset[UserGroupCapability]] = {
    MembershipRole.OWNER: _USER_GROUP_ADMINISTER
    | {
        UserGroupCapability.MEMBER_ROLE_MANAGE,
        UserGroupCapability.OWNERSHIP_TRANSFER,
    },
    MembershipRole.ADMIN: _USER_GROUP_ADMINISTER,
    MembershipRole.MEMBER: _USER_GROUP_VIEW,
}


def user_group_capabilities_of(
    role: MembershipRole,
) -> frozenset[UserGroupCapability]:
    return USER_GROUP_ROLE_CAPABILITIES[role]


class Capability(StrEnum):
    """一个具体的操作许可。

    命名统一为 ``对象.动作``，方便在日志和错误信息里直接读。
    """

    # -- User Group governance ------------------------------------------
    USER_GROUP_VIEW = "user_group.view"
    USER_GROUP_UPDATE = "user_group.update"

    # -- 成员 ------------------------------------------------------------
    MEMBER_VIEW = "member.view"
    MEMBER_INVITE = "member.invite"
    MEMBER_REMOVE = "member.remove"
    MEMBER_ROLE_MANAGE = "member.role.manage"
    OWNERSHIP_TRANSFER = "ownership.transfer"

    # -- 配置 ------------------------------------------------------------
    CONFIG_VIEW = "config.view"
    """查看 Variable 的值和 Secret 的名称；任何角色都读不到 Secret 值（§3.1.4）。"""
    CONFIG_MANAGE = "config.manage"

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
    """看 User Group 持有的 Shared Resource 及其版本；User-owned 资源由 owner 本人管理。"""
    SHARED_RESOURCE_MANAGE = "shared_resource.manage"
    """创建或修改当前 User / User Group Owner 范围内的 Shared Resource。"""
    SHARED_RESOURCE_VERSION_CREATE = "shared_resource.version.create"
    """为 Shared Resource 上传文件形成新的不可变版本。"""

    # -- Grant -------------------------------------------------------------
    GRANT_MANAGE = "grant.manage"
    """管理跨 Owner USE Grant（创建、查看、撤销）。"""


_VIEW_ONLY: frozenset[Capability] = frozenset(
    {
        Capability.USER_GROUP_VIEW,
        Capability.MEMBER_VIEW,
        Capability.CONFIG_VIEW,
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

# 管空间需要的能力：改设置、邀请和移除普通成员、管配置。
_ADMINISTER: frozenset[Capability] = _CONTRIBUTE | {
    Capability.USER_GROUP_UPDATE,
    Capability.MEMBER_INVITE,
    Capability.MEMBER_REMOVE,
    Capability.CONFIG_MANAGE,
    Capability.GRANT_MANAGE,
}

ROLE_CAPABILITIES: dict[MembershipRole, frozenset[Capability]] = {
    MembershipRole.OWNER: _ADMINISTER
    | {
        Capability.MEMBER_ROLE_MANAGE,
        Capability.OWNERSHIP_TRANSFER,
    },
    MembershipRole.ADMIN: _ADMINISTER,
    MembershipRole.MEMBER: _CONTRIBUTE,
}

# 面向用户的说明，用在权限不足的错误信息里。
CAPABILITY_LABELS: dict[Capability, str] = {
    Capability.USER_GROUP_VIEW: "查看 User Group",
    Capability.USER_GROUP_UPDATE: "修改 User Group 设置",
    Capability.MEMBER_VIEW: "查看成员",
    Capability.MEMBER_INVITE: "邀请成员",
    Capability.MEMBER_REMOVE: "移除成员",
    Capability.MEMBER_ROLE_MANAGE: "修改成员角色",
    Capability.OWNERSHIP_TRANSFER: "转让 User Group 所有权",
    Capability.CONFIG_VIEW: "查看配置",
    Capability.CONFIG_MANAGE: "管理配置变量与 Secret",
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
    Capability.GRANT_MANAGE: "管理 USE Grant",
}

USER_GROUP_CAPABILITY_LABELS: dict[UserGroupCapability, str] = {
    UserGroupCapability.USER_GROUP_VIEW: "查看 User Group",
    UserGroupCapability.USER_GROUP_UPDATE: "修改 User Group 设置",
    UserGroupCapability.MEMBER_VIEW: "查看成员",
    UserGroupCapability.MEMBER_INVITE: "邀请成员",
    UserGroupCapability.MEMBER_REMOVE: "移除成员",
    UserGroupCapability.MEMBER_ROLE_MANAGE: "修改成员角色",
    UserGroupCapability.OWNERSHIP_TRANSFER: "转让 User Group 所有权",
}


def capabilities_of(role: MembershipRole) -> frozenset[Capability]:
    return ROLE_CAPABILITIES[role]


def describe(capability: Capability | UserGroupCapability) -> str:
    if isinstance(capability, UserGroupCapability):
        return USER_GROUP_CAPABILITY_LABELS.get(capability, capability.value)
    return CAPABILITY_LABELS.get(capability, capability.value)
