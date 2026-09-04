"""Environment discovery and platform Compute Plan routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get(
    "/environments",
    response_model=list[s.EnvironmentOut],
    summary="列出运行环境",
)
async def list_environments(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.EnvironmentOut]:
    """返回当前 User 可在个人或有效 User Group Owner 上下文中使用的环境。"""
    views = await services.catalog.list_environments(user.id)
    return [p.environment_out(view) for view in views]


@router.get(
    "/environments/{environment_id}",
    response_model=s.EnvironmentOut,
    summary="获取运行环境",
)
async def get_environment(
    environment_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentOut:
    return p.environment_out(await services.catalog.get_environment(user.id, environment_id))


@router.get(
    "/environment-versions/{version_id}",
    response_model=s.EnvironmentVersionOut,
    summary="获取运行环境版本",
)
async def get_environment_version(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentVersionOut:
    return p.environment_version_out(
        await services.catalog.get_environment_version(user.id, version_id)
    )


@router.post(
    "/environment-versions/{version_id}/availability/refresh",
    response_model=s.EnvironmentVersionOut,
    summary="重新校验 Environment Version 当前可用性",
)
async def refresh_environment_version_availability(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentVersionOut:
    return p.environment_version_out(
        await services.environment_publications.refresh_availability(user.id, version_id)
    )


@router.post(
    "/environments/{environment_id}/publication-attempts/modules",
    response_model=s.EnvironmentPublicationAttemptOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="发布 Modules 运行环境候选",
)
async def publish_modules_environment(
    environment_id: str,
    body: s.ModulesEnvironmentPublicationIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentPublicationAttemptOut:
    attempt = await services.environment_publications.create_modules(
        user.id,
        environment_id,
        version=body.version,
        description=body.description,
        modules=body.modules,
    )
    return p.environment_publication_attempt_out(attempt)


@router.post(
    "/environments/{environment_id}/publication-attempts/apptainer-sif",
    response_model=s.EnvironmentPublicationAttemptOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传并发布受控 Apptainer SIF 候选",
)
async def publish_apptainer_environment(
    environment_id: str,
    user: CurrentUser,
    services: ServicesDep,
    version: Annotated[str, Form()],
    sif: Annotated[UploadFile, File()],
    description: Annotated[str, Form()] = "",
    source_uri: Annotated[str, Form()] = "",
    source_digest: Annotated[str, Form()] = "",
    architecture: Annotated[str, Form()] = "x86_64",
) -> s.EnvironmentPublicationAttemptOut:
    content = await sif.read()
    attempt = await services.environment_publications.create_sif(
        user.id,
        environment_id,
        version=version,
        description=description,
        content=content,
        source_uri=source_uri,
        source_digest=source_digest,
        architecture=architecture,
    )
    return p.environment_publication_attempt_out(attempt)


@router.get(
    "/environments/{environment_id}/publication-attempts",
    response_model=list[s.EnvironmentPublicationAttemptOut],
    summary="列出 Environment publication attempts",
)
async def list_environment_publication_attempts(
    environment_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.EnvironmentPublicationAttemptOut]:
    attempts = await services.environment_publications.list_attempts(user.id, environment_id)
    return [p.environment_publication_attempt_out(attempt) for attempt in attempts]


@router.get(
    "/environment-publication-attempts/{attempt_id}",
    response_model=s.EnvironmentPublicationAttemptOut,
    summary="获取 Environment publication attempt",
)
async def get_environment_publication_attempt(
    attempt_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentPublicationAttemptOut:
    return p.environment_publication_attempt_out(
        await services.environment_publications.get(user.id, attempt_id)
    )


@router.get(
    "/compute-plans",
    response_model=list[s.ComputePlanOut],
    summary="列出算力方案",
)
async def list_compute_plans(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.ComputePlanOut]:
    """登录后只读返回平台全部算力方案；列表不表示当前 User 已获得对应权益。"""
    plans = await services.catalog.list_compute_plans()
    return [p.compute_plan_out(plan) for plan in plans]
