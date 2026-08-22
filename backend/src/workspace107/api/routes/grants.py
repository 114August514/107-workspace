"""Grant routes.

Cross-owner USE Grant management:

- ``POST   /grants``           —— create a USE Grant (asset Owner only)
- ``GET    /grants``            —— list Grants for a target asset (asset Owner only)
- ``DELETE /grants/{id}``       —— revoke a Grant (asset Owner only)
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from ...domain.grant import GrantTargetKind
from ...domain.ownership import OwnerKind, OwnerReference
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(tags=["grant"])


@router.post(
    "/grants",
    response_model=s.GrantOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建跨 Owner USE Grant",
)
async def create_grant(
    payload: s.GrantCreateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.GrantOut:
    """Create a USE Grant allowing ``grantee`` to reference the target asset.

    Only the target asset's Owner may create a Grant.  The target must be a
    top-level Environment or Shared Resource (not a version).
    """
    grantee = OwnerReference(OwnerKind(payload.grantee.kind), payload.grantee.id)
    view = await services.grants.create(
        user.id,
        target_kind=GrantTargetKind(payload.target_kind),
        target_id=payload.target_id,
        grantee=grantee,
    )
    return p.grant_out(view)


@router.get(
    "/grants",
    response_model=list[s.GrantOut],
    summary="列出指向某资产的 Grant",
)
async def list_grants(
    user: CurrentUser,
    services: ServicesDep,
    target_kind: GrantTargetKind = Query(
        ..., description="资产种类：environment 或 shared_resource"
    ),
    target_id: str = Query(..., description="顶层资产 ID"),
) -> list[s.GrantOut]:
    """List all Grants for a target asset.  Only the asset Owner may list."""
    views = await services.grants.list_for_target(
        user.id,
        target_kind=GrantTargetKind(target_kind),
        target_id=target_id,
    )
    return [p.grant_out(view) for view in views]


@router.delete(
    "/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="撤销 USE Grant",
)
async def revoke_grant(
    grant_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> None:
    """Revoke a Grant.  Only the target asset's Owner may revoke."""
    await services.grants.revoke(user.id, grant_id)
