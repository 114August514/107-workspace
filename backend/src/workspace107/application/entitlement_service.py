"""User-scoped Resource Entitlement 用例。

Resource Entitlement 属于 User（设计稿 §Resource Entitlement）：
只表示 User 对 Compute Plan 的算力使用资格，User Group Ownership /
Membership 不转移这个资格。正式的发放流程（Entitlement Request 审批）
在 V1，本 Core 阶段只有读取；dev / test 需要的默认资格由明确的
seed / fixture 写入，不作为业务创建的副作用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..domain.compute import ComputePlan, ResourceEntitlement
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories


@dataclass(frozen=True, slots=True)
class EntitlementView:
    entitlement: ResourceEntitlement
    plan: ComputePlan
    status: Literal["active", "expired"]
    status_reason: str | None


class EntitlementService:
    def __init__(self, repos: Repositories, clock: Clock) -> None:
        self._repos = repos
        self._clock = clock

    async def list_for_user(self, user_id: str) -> list[EntitlementView]:
        """查看自己的资源权益——主体就是当前 User，无需空间级授权。"""
        result: list[EntitlementView] = []
        now_iso = self._clock.now().isoformat()
        for entitlement in await self._repos.entitlements.list_for_user(user_id):
            plan = await self._repos.compute_plans.get(entitlement.compute_plan_id)
            if plan is not None:
                expired = entitlement.is_expired(now_iso)
                result.append(
                    EntitlementView(
                        entitlement=entitlement,
                        plan=plan,
                        status="expired" if expired else "active",
                        status_reason=(
                            f"权益已于 {entitlement.expires_at} 过期" if expired else None
                        ),
                    )
                )
        return result
