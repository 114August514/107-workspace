"""Environment discovery and platform Compute Plan routes."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from ...application.environment_publication import ALLOWED_MODULES
from ...domain.errors import ValidationFailed
from .. import presenters as p
from .. import schemas as s
from ..deps import ContextDep, CurrentUser, ServicesDep

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/environment-publication-options", response_model=s.EnvironmentPublicationOptionsOut)
async def environment_publication_options(
    user: CurrentUser, context: ContextDep
) -> s.EnvironmentPublicationOptionsOut:
    return s.EnvironmentPublicationOptionsOut(
        modules=sorted(ALLOWED_MODULES),
        max_upload_bytes=min(
            context.settings.environment_import_max_bytes,
            max(0, context.settings.max_request_bytes - 65536),
        ),
        max_import_bytes=context.settings.environment_import_max_bytes,
        import_timeout_seconds=context.settings.environment_import_timeout_seconds,
        architecture="x86_64",
    )


@router.post(
    "/environments/{environment_id}/publication-attempts/import",
    response_model=s.EnvironmentPublicationAttemptOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_environment(
    environment_id: str,
    body: s.ImportEnvironmentPublicationIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentPublicationAttemptOut:
    attempt = await services.environment_publications.create_import(
        user.id, environment_id, **body.model_dump()
    )
    return p.environment_publication_attempt_out(attempt)


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
    context: ContextDep,
    user: CurrentUser,
    services: ServicesDep,
    version: Annotated[str, Form()],
    sif: Annotated[UploadFile, File()],
    description: Annotated[str, Form()] = "",
    source_uri: Annotated[str, Form()] = "",
    source_digest: Annotated[str, Form()] = "",
    architecture: Annotated[str, Form()] = "x86_64",
) -> s.EnvironmentPublicationAttemptOut:
    await services.environment_publications.authorize(user.id, environment_id)
    limit = min(
        context.settings.environment_import_max_bytes, context.settings.max_request_bytes - 65536
    )
    with tempfile.TemporaryDirectory(prefix="workspace107-upload-") as directory:
        path = Path(directory) / "image.sif"
        size = 0
        with path.open("wb") as output:
            while chunk := await sif.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValidationFailed("SIF 文件超过平台上传大小上限")
                await asyncio.to_thread(output.write, chunk)
        attempt = await services.environment_publications.create_sif_file(
            user.id,
            environment_id,
            version=version,
            description=description,
            path=path,
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
