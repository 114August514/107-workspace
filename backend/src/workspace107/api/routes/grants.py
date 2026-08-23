"""Grant routes.

Cross-owner USE Grant management:

- ``POST   /grants``           —— create a USE Grant (GRANT_MANAGE capability)
- ``GET    /grants``            —— list Grants (by target asset or by grantor)
- ``DELETE /grants/{id}``       —— revoke a Grant (GRANT_MANAGE capability)
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
    """Create a USE Grant allowing ``grantee`` to reference the Grantor's asset(s).

    For asset grants (environment/shared_resource), the Grantor is derived from
    the target asset's current owner.  For ALL grants, ``grantor`` must be
    supplied explicitly and the caller must have GRANT_MANAGE on that Grantor.
    """
    grantee = OwnerReference(OwnerKind(payload.grantee.kind), payload.grantee.id)
    grantor: OwnerReference | None = None
    if payload.grantor is not None:
        grantor = OwnerReference(OwnerKind(payload.grantor.kind), payload.grantor.id)
    view = await services.grants.create(
        user.id,
        target_kind=GrantTargetKind(payload.target_kind),
        target_id=payload.target_id,
        grantee=grantee,
        grantor=grantor,
    )
    return p.grant_out(view)


@router.get(
    "/grants",
    response_model=list[s.GrantOut],
    summary="列出 Grant",
)
async def list_grants(
    user: CurrentUser,
    services: ServicesDep,
    target_kind: GrantTargetKind | None = Query(
        None, description="按资产种类过滤：environment 或 shared_resource"
    ),
    target_id: str | None = Query(None, description="顶层资产 ID"),
    grantor_kind: OwnerKind | None = Query(None, description="按 Grantor 种类过滤"),
    grantor_id: str | None = Query(None, description="Grantor ID"),
) -> list[s.GrantOut]:
    """List Grants.

    Filter by target asset (``target_kind`` + ``target_id``) or by Grantor
    (``grantor_kind`` + ``grantor_id``).  Exactly one filter pair must be given.
    """
    if target_kind is not None and target_id is not None:
        views = await services.grants.list_for_target(
            user.id,
            target_kind=GrantTargetKind(target_kind),
            target_id=target_id,
        )
    elif grantor_kind is not None and grantor_id is not None:
        grantor = OwnerReference(grantor_kind, grantor_id)
        views = await services.grants.list_for_grantor(user.id, grantor)
    else:
        views = []
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
    """Revoke a Grant.  Requires GRANT_MANAGE on the Grant's Grantor."""
    await services.grants.revoke(user.id, grant_id)
