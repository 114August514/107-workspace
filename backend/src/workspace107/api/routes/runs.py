"""Run、日志与 Artifact 路由。"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Header, Query, Response, status

from ...application.run_service import RunDraft
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(tags=["run"])


@router.get("/projects/{project_id}/runs", response_model=s.PageOut[s.RunOut])
async def list_runs(
    project_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.RunOut]:
    result = await services.runs.list_for_project(user.id, project_id, page)
    return p.page_out(result, p.run_out)


@router.post("/projects/{project_id}/runs/preflight", response_model=s.PreflightOut)
async def preflight(
    project_id: str, payload: s.RunDraftIn, user: CurrentUser, services: ServicesDep
) -> s.PreflightOut:
    """提交前检查。只读，不创建任何对象。"""
    result = await services.runs.preflight(user.id, project_id, _to_draft(payload))
    return s.PreflightOut(
        ok=result.ok,
        problems=result.problems,
        project_version_id=result.project_version.id if result.project_version else None,
        environment_version_id=(
            result.environment_version.id if result.environment_version else None
        ),
        compute_plan_id=result.compute_plan.id if result.compute_plan else None,
        compute_request=p.compute_request_out(result.compute_request),
        resolved_environment_variables=result.resolved_env_literals,
        secret_references=result.resolved_env_secret_refs,
    )


@router.post(
    "/projects/{project_id}/runs",
    response_model=s.RunOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": s.RunOut, "description": "幂等重放，返回上一次提交的 Run"}},
)
async def create_run(
    project_id: str,
    payload: s.RunDraftIn,
    user: CurrentUser,
    services: ServicesDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> s.RunOut:
    """提交 Run。

    带 ``Idempotency-Key`` 请求头时，同一个键的重复请求返回上一次的结果（200），
    不会再跑一次；新创建返回 201。网络抖动或前端自动重试不会变成两次真实计算。
    """
    submission = await services.runs.create(
        user.id, project_id, _to_draft(payload), idempotency_key=idempotency_key
    )
    if not submission.created:
        response.status_code = status.HTTP_200_OK
    return p.run_out(submission.run)


@router.get("/runs/{run_id}", response_model=s.RunDetailOut)
async def get_run(run_id: str, user: CurrentUser, services: ServicesDep) -> s.RunDetailOut:
    detail = await services.runs.get_detail(user.id, run_id)
    return s.RunDetailOut(
        run=p.run_out(detail.run),
        snapshot=p.snapshot_out(detail.snapshot),
        events=[p.run_event_out(e) for e in detail.events],
        artifacts=[p.artifact_out(a) for a in detail.artifacts],
    )


@router.get("/runs/{run_id}/logs", response_model=list[s.LogChunkOut])
async def read_logs(run_id: str, user: CurrentUser, services: ServicesDep) -> list[s.LogChunkOut]:
    chunks = await services.runs.read_logs(user.id, run_id)
    return [
        s.LogChunkOut(stream=c.stream.value, content=c.content, truncated=c.truncated)
        for c in chunks
    ]


@router.post("/runs/{run_id}/cancel", response_model=s.RunOut)
async def cancel_run(run_id: str, user: CurrentUser, services: ServicesDep) -> s.RunOut:
    run = await services.runs.cancel(user.id, run_id)
    return p.run_out(run)


@router.post(
    "/runs/{run_id}/rerun",
    response_model=s.RunOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": s.RunOut, "description": "幂等重放，返回上一次重跑的 Run"}},
)
async def rerun(
    run_id: str,
    user: CurrentUser,
    services: ServicesDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> s.RunOut:
    submission = await services.runs.rerun(user.id, run_id, idempotency_key=idempotency_key)
    if not submission.created:
        response.status_code = status.HTTP_200_OK
    return p.run_out(submission.run)


@router.post("/runs/sync", response_model=s.SyncOut)
async def sync_runs(services: ServicesDep) -> s.SyncOut:
    """主动触发一次状态同步。

    生产环境由后台任务周期执行；前端在轮询时也可以调用它，
    让状态立刻反映调度系统的实际情况。
    """
    return s.SyncOut(changed=await services.lifecycle.sync_all())


# -- Artifact ---------------------------------------------------------------


@router.get("/artifacts/{artifact_id}/files", response_model=list[s.ArtifactEntryOut])
async def list_artifact_files(
    artifact_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ArtifactEntryOut]:
    entries = await services.runs.list_artifact_files(user.id, artifact_id)
    return [s.ArtifactEntryOut(path=e.path, size=e.size) for e in entries]


# 不声明 responses 的话，FastAPI 会按默认填成 application/json + 空 schema，
# 契约里就写着这个接口返回 JSON——而它实际返回的是二进制文件。
# 生成的前端类型会跟着错，调用方只能靠强制转换绕过去。
@router.get(
    "/artifacts/{artifact_id}/download",
    # response_class 决定契约里默认写哪种 media type。不写的话默认是
    # JSONResponse，即使这里又声明了 octet-stream，契约也会同时留着
    # application/json——等于告诉调用方「可能返回 JSON」，而它从来不会。
    response_class=Response,
    responses={
        200: {
            "description": "产物文件内容",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def download_artifact_file(
    artifact_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> Response:
    data, filename = await services.runs.read_artifact_file(user.id, artifact_id, path)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


def _content_disposition(filename: str) -> str:
    """按 RFC 6266 拼下载头。

    HTTP 头只能是 latin-1，中文文件名直接塞进去会在 Starlette 编码响应头时
    抛 UnicodeEncodeError，而那不是 DomainError，没有 handler 接，
    最后是一个裸 500——**产物名字带中文就下载不了**。

    所以给两份：``filename`` 用 ASCII 兜底保证老客户端能用，
    ``filename*`` 用 RFC 5987 的百分号编码带上真实名字，现代浏览器优先取它。
    """
    fallback = filename.encode("ascii", errors="replace").decode("ascii").replace('"', "_")
    quoted = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quoted}"


def _to_draft(payload: s.RunDraftIn) -> RunDraft:
    return RunDraft(
        run_configuration_id=payload.run_configuration_id,
        project_version_id=payload.project_version_id,
        name=payload.name or "",
        command_override=payload.command_override or "",
        working_directory_override=payload.working_directory_override or "",
        compute_request_override=(
            payload.compute_request_override.model_dump()
            if payload.compute_request_override
            else None
        ),
    )
