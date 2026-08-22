"""跨 Owner 使用许可。

Grant 把资产的 *Ownership*（谁创建并管理资产）与 *使用资格*（谁能引用资产）
分离：Owner 可向其他 Owner 主体（User 或 User Group）发放 USE Grant，
使其能在自己的 Project 中引用该顶层 Environment 或 Shared Resource。
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
    """Grant 指向的资产种类。仅限顶层资产，不包含 version。"""

    ENVIRONMENT = "environment"
    SHARED_RESOURCE = "shared_resource"


@dataclass(frozen=True, slots=True)
class Grant:
    """跨 Owner 使用许可。Target 为顶层 Environment 或 Shared Resource。

    ``grantor_owner`` 记录创建此 Grant 时的资产 Owner。GR-408：资产
    Ownership 转移后，旧 Owner 建立的 Grant 失效——``exists_use_grant``
    校验 ``grantor_owner == asset.current_owner``。
    """

    id: str
    grantee: OwnerReference
    target_kind: GrantTargetKind
    target_id: str
    action: GrantAction
    granted_by: str
    grantor_owner: OwnerReference
    created_at: datetime
