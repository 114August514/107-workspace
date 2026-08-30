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


@router.get(
    "/projects/{project_id}/runs",
    response_model=s.PageOut[s.RunOut],
    summary="列出 Project 的 Run",
)
async def list_runs(
    project_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.RunOut]:
    """分页返回当前用户可访问的 Project 中的 Run；无发现权限时按不存在处理。"""
    result = await services.runs.list_for_project(user.id, project_id, page)
    return p.page_out(result, p.run_out)


@router.post(
    "/projects/{project_id}/runs/preflight",
    response_model=s.PreflightOut,
    summary="检查 Run 提交条件",
)
async def preflight(
    project_id: str, payload: s.RunDraftIn, user: CurrentUser, services: ServicesDep
) -> s.PreflightOut:
    """需要提交 Run 权限；一次性检查版本、环境、资源权益、配置与输入。

    此操作只读，会返回全部阻止提交的问题，不创建 Run 或 Run Snapshot。
    """
    result = await services.runs.preflight(user.id, project_id, _to_draft(payload))
    return s.PreflightOut(
        ok=result.ok,
        problems=result.problems,
        project_version_id=result.project_version.id if result.project_version else None,
        environment_version=(
            p.environment_version_out(result.environment_version)
            if result.environment_version
            else None
        ),
        compute_plan_id=result.compute_plan.id if result.compute_plan else None,
        compute_request=p.compute_request_out(result.compute_request),
        resolved_environment_variables=result.resolved_env_literals,
        secret_references={
            name: ref.as_key() for name, ref in result.resolved_env_secret_refs.items()
        },
    )


@router.post(
    "/projects/{project_id}/runs",
    response_model=s.RunOut,
    status_code=status.HTTP_201_CREATED,
    summary="提交 Run",
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
    """需要提交 Run 权限；校验通过后固定不可变快照并向调度系统提交任务。

    提交失败仍会保留 Run，作为可排查的历史事实。

    带 ``Idempotency-Key`` 请求头时，同一个键的重复请求返回上一次的结果（200），
    不会再跑一次；新创建返回 201。网络抖动或前端自动重试不会变成两次真实计算。
    """
    submission = await services.runs.create(
        user.id, project_id, _to_draft(payload), idempotency_key=idempotency_key
    )
    if not submission.created:
        response.status_code = status.HTTP_200_OK
    return p.run_out(await services.runs.view(submission.run))


@router.get("/runs/{run_id}", response_model=s.RunDetailOut, summary="获取 Run 详情")
async def get_run(run_id: str, user: CurrentUser, services: ServicesDep) -> s.RunDetailOut:
    """仅在当前 User 具有所属 Project owner-scope authority 时，返回 Run 详情与操作 capability。"""
    detail = await services.runs.get_detail(user.id, run_id)
    project_access = await services.projects.get(user.id, detail.run.run.project_id)
    return s.RunDetailOut(
        run=p.run_out(detail.run, capabilities=project_access.capabilities),
        snapshot=p.snapshot_out(detail.snapshot),
        events=[p.run_event_out(e) for e in detail.events],
        artifacts=[p.artifact_out(a) for a in detail.artifacts],
    )


@router.get(
    "/runs/{run_id}/logs",
    response_model=list[s.LogChunkOut],
    summary="读取 Run 日志",
)
async def read_logs(run_id: str, user: CurrentUser, services: ServicesDep) -> list[s.LogChunkOut]:
    """仅对可访问所属 Run 的用户返回 stdout 和 stderr 尾部，并抹除已知 Secret 明文。"""
    chunks = await services.runs.read_logs(user.id, run_id)
    return [
        s.LogChunkOut(stream=c.stream.value, content=c.content, truncated=c.truncated)
        for c in chunks
    ]


@router.post("/runs/{run_id}/cancel", response_model=s.RunOut, summary="取消 Run")
async def cancel_run(run_id: str, user: CurrentUser, services: ServicesDep) -> s.RunOut:
    """需要取消 Run 权限，且 Run 尚未进入终态。

    已提交的任务会向调度系统发出取消请求，最终状态由后续同步确认；尚未提交的任务
    会直接标记为已取消。
    """
    run = await services.runs.cancel(user.id, run_id)
    return p.run_out(await services.runs.view(run))


@router.post(
    "/runs/{run_id}/rerun",
    response_model=s.RunOut,
    status_code=status.HTTP_201_CREATED,
    summary="重新运行 Run",
    responses={200: {"model": s.RunOut, "description": "幂等重放，返回上一次重跑的 Run"}},
)
async def rerun(
    run_id: str,
    user: CurrentUser,
    services: ServicesDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> s.RunOut:
    """需要提交 Run 权限；基于来源快照创建新的 Run 与不可变快照。

    重跑不会修改或重启原 Run，并会按当前权限和资源权益重新校验。带
    ``Idempotency-Key`` 时，同一个键的重复请求不会产生第二次计算。
    """
    submission = await services.runs.rerun(user.id, run_id, idempotency_key=idempotency_key)
    if not submission.created:
        response.status_code = status.HTTP_200_OK
    return p.run_out(await services.runs.view(submission.run))


@router.post("/runs/sync", response_model=s.SyncOut, summary="同步 Run 状态")
async def sync_runs(services: ServicesDep) -> s.SyncOut:
    """无需用户身份，主动轮询全部未结束 Run 的调度状态。

    状态变化会写入执行记录，并在进入终态时收集 Artifact；单个 Run 同步失败不会
    中断其余 Run。生产环境由后台任务周期执行，前端轮询时也可以调用。
    """
    return s.SyncOut(changed=await services.lifecycle.sync_all())


# -- Artifact ---------------------------------------------------------------


@router.get(
    "/artifacts/{artifact_id}/files",
    response_model=list[s.ArtifactEntryOut],
    summary="列出 Artifact 文件",
)
async def list_artifact_files(
    artifact_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ArtifactEntryOut]:
    """仅在当前用户可访问所属 Run 且 Artifact 内容仍可用时，返回文件路径与大小。"""
    entries = await services.runs.list_artifact_files(user.id, artifact_id)
    return [s.ArtifactEntryOut(path=e.path, size=e.size) for e in entries]


# 不声明 responses 的话，FastAPI 会按默认填成 application/json + 空 schema，
# 契约里就写着这个接口返回 JSON——而它实际返回的是二进制文件。
# 生成的前端类型会跟着错，调用方只能靠强制转换绕过去。
@router.get(
    "/artifacts/{artifact_id}/download",
    summary="下载 Artifact 文件",
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
    """仅对可访问所属 Run 的用户，将 ``path`` 指定的已收集文件作为二进制附件返回。"""
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
