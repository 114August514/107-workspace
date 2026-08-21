"""Scoped Variable/Secret CRUD routes with explicit owner resources."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(tags=["configuration"])


async def _user(services, actor: str, target: str, manage: bool):
    return await services.configuration.user_scope(actor, target)


async def _group(services, actor: str, target: str, manage: bool):
    return await services.configuration.group_scope(actor, target, manage=manage)


async def _project(services, actor: str, target: str, manage: bool):
    return await services.configuration.project_scope(actor, target, manage=manage)


async def _list_variables(scope, services):
    return [
        s.VariableOut(name=v.name, value=v.value)
        for v in await services.configuration.list_variables(scope)
    ]


async def _set_variable(scope, payload, services):
    value = await services.configuration.set_variable(scope, payload.name, payload.value)
    return s.VariableOut(name=value.name, value=value.value)


async def _delete_variable(scope, name, services):
    await services.configuration.delete_variable(scope, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _list_secrets(scope, services):
    return await services.configuration.list_secret_names(scope)


async def _set_secret(scope, payload, services):
    await services.configuration.set_secret(scope, payload.name, payload.value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _delete_secret(scope, name, services):
    await services.configuration.delete_secret(scope, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/variables", response_model=list[s.VariableOut])
async def list_user_variables(user_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_variables(await _user(services, user.id, user_id, False), services)


@router.put("/users/{user_id}/variables", response_model=s.VariableOut)
async def set_user_variable(
    user_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
):
    return await _set_variable(await _user(services, user.id, user_id, True), payload, services)


@router.delete("/users/{user_id}/variables/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_variable(user_id: str, name: str, user: CurrentUser, services: ServicesDep):
    return await _delete_variable(await _user(services, user.id, user_id, True), name, services)


@router.get("/users/{user_id}/secrets", response_model=list[str])
async def list_user_secrets(user_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_secrets(await _user(services, user.id, user_id, False), services)


@router.put("/users/{user_id}/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def set_user_secret(
    user_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
):
    return await _set_secret(await _user(services, user.id, user_id, True), payload, services)


@router.delete("/users/{user_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_secret(user_id: str, name: str, user: CurrentUser, services: ServicesDep):
    return await _delete_secret(await _user(services, user.id, user_id, True), name, services)


@router.get("/user-groups/{user_group_id}/variables", response_model=list[s.VariableOut])
async def list_group_variables(user_group_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_variables(await _group(services, user.id, user_group_id, False), services)


@router.put("/user-groups/{user_group_id}/variables", response_model=s.VariableOut)
async def set_group_variable(
    user_group_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
):
    return await _set_variable(
        await _group(services, user.id, user_group_id, True), payload, services
    )


@router.delete(
    "/user-groups/{user_group_id}/variables/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_group_variable(
    user_group_id: str, name: str, user: CurrentUser, services: ServicesDep
):
    return await _delete_variable(
        await _group(services, user.id, user_group_id, True), name, services
    )


@router.get("/user-groups/{user_group_id}/secrets", response_model=list[str])
async def list_group_secrets(user_group_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_secrets(await _group(services, user.id, user_group_id, False), services)


@router.put("/user-groups/{user_group_id}/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def set_group_secret(
    user_group_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
):
    return await _set_secret(
        await _group(services, user.id, user_group_id, True), payload, services
    )


@router.delete(
    "/user-groups/{user_group_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_group_secret(
    user_group_id: str, name: str, user: CurrentUser, services: ServicesDep
):
    return await _delete_secret(
        await _group(services, user.id, user_group_id, True), name, services
    )


@router.get("/projects/{project_id}/variables", response_model=list[s.VariableOut])
async def list_project_variables(project_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_variables(await _project(services, user.id, project_id, False), services)


@router.put("/projects/{project_id}/variables", response_model=s.VariableOut)
async def set_project_variable(
    project_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
):
    return await _set_variable(
        await _project(services, user.id, project_id, True), payload, services
    )


@router.delete("/projects/{project_id}/variables/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_variable(
    project_id: str, name: str, user: CurrentUser, services: ServicesDep
):
    return await _delete_variable(
        await _project(services, user.id, project_id, True), name, services
    )


@router.get("/projects/{project_id}/secrets", response_model=list[str])
async def list_project_secrets(project_id: str, user: CurrentUser, services: ServicesDep):
    return await _list_secrets(await _project(services, user.id, project_id, False), services)


@router.put("/projects/{project_id}/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def set_project_secret(
    project_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
):
    return await _set_secret(await _project(services, user.id, project_id, True), payload, services)


@router.delete("/projects/{project_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_secret(
    project_id: str, name: str, user: CurrentUser, services: ServicesDep
):
    return await _delete_secret(await _project(services, user.id, project_id, True), name, services)
