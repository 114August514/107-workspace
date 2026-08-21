"""Scoped Variable/Secret CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ...domain.errors import ObjectNotFound
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(prefix="/config", tags=["configuration"])


async def _scope(services, user_id: str, kind: str, target_id: str, manage: bool):
    if kind == "users":
        return await services.configuration.user_scope(user_id, target_id)
    if kind == "user-groups":
        return await services.configuration.group_scope(user_id, target_id, manage=manage)
    if kind == "projects":
        return await services.configuration.project_scope(user_id, target_id, manage=manage)
    raise ObjectNotFound("Configuration scope", target_id)


@router.get("/{kind}/{target_id}/variables", response_model=list[s.VariableOut])
async def list_variables(kind: str, target_id: str, user: CurrentUser, services: ServicesDep):
    scope = await _scope(services, user.id, kind, target_id, False)
    return [
        s.VariableOut(name=v.name, value=v.value)
        for v in await services.configuration.list_variables(scope)
    ]


@router.put("/{kind}/{target_id}/variables", response_model=s.VariableOut)
async def set_variable(
    kind: str, target_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
):
    scope = await _scope(services, user.id, kind, target_id, True)
    value = await services.configuration.set_variable(scope, payload.name, payload.value)
    return s.VariableOut(name=value.name, value=value.value)


@router.delete("/{kind}/{target_id}/variables/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    kind: str, target_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> Response:
    scope = await _scope(services, user.id, kind, target_id, True)
    await services.configuration.delete_variable(scope, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{kind}/{target_id}/secrets", response_model=list[str])
async def list_secrets(kind: str, target_id: str, user: CurrentUser, services: ServicesDep):
    scope = await _scope(services, user.id, kind, target_id, False)
    return await services.configuration.list_secret_names(scope)


@router.put("/{kind}/{target_id}/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def set_secret(
    kind: str, target_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
) -> Response:
    scope = await _scope(services, user.id, kind, target_id, True)
    await services.configuration.set_secret(scope, payload.name, payload.value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{kind}/{target_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    kind: str, target_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> Response:
    scope = await _scope(services, user.id, kind, target_id, True)
    await services.configuration.delete_secret(scope, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
