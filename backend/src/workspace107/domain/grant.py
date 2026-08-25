"""跨 Owner 使用许可。

Grant 把资产的 *Ownership*（谁创建并管理资产）与 *使用资格*（谁能引用资产）
分离：Grantor 向 Grantee 发放 USE Grant，使其能在自己的 Project 中引用该
顶层 Environment 或 Shared Resource。

Target = ALL 表示 Grantee 可以使用 Grantor 当前以及以后拥有的全部可授权资产。
资产 Ownership 转移后，Grantor 不再拥有该资产，其 Grant 自然不再匹配——
无需额外的 Owner snapshot 机制。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from workspace107.domain.ownership import OwnerReference


class GrantAction(StrEnum):
    """Grant 授权的动作。V1 只有 USE。"""

    USE = "use"


class GrantTargetKind(StrEnum):
    """Grant 指向的资产范围。

    ``ALL`` 表示授权 Grantor 当前及未来拥有的全部可授权 Environment /
    Shared Resource；此时 ``target_id`` 为空字符串。
    ``ENVIRONMENT`` / ``SHARED_RESOURCE`` 表示仅授权具体顶层资产。
    """

    ALL = "all"
    ENVIRONMENT = "environment"
    SHARED_RESOURCE = "shared_resource"


class UseAvailabilitySource(StrEnum):
    """当前 User 对资产的使用资格来源。

    与 Run preflight 的授权语义（见 ``application/asset_use.py``）对齐：
    ``OWNER`` 对应同 Owner 路径，``USER_GRANT`` / ``USER_GROUP_GRANT`` 对应
    Grant 路径（组 Grant 要求当前 User 是该 Grantee 组的有效成员），
    ``UNAVAILABLE`` 表示当前无使用资格。
    """

    OWNER = "owner"
    USER_GRANT = "user_grant"
    USER_GROUP_GRANT = "user_group_grant"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Grant:
    """跨 Owner USE 许可。

    ``grantor`` 是发出授权的业务主体（User 或 User Group），即当前拥有
    这些资产的 Owner。使用授权时以资产 *当前* Owner 为准：只有当
    ``grantor == asset.current_owner`` 时该 Grant 才作用于该资产。

    ``granted_by`` 仅记录实际执行授权操作的具体 User，用于审计，不参与
    Grant 有效性判断。
    """

    id: str
    grantor: OwnerReference
    grantee: OwnerReference
    target_kind: GrantTargetKind
    target_id: str
    action: GrantAction
    granted_by: str
    created_at: datetime
