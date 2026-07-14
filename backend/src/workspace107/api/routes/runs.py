import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from workspace107.api.dependencies import IdentityDependency, RunServiceDependency
from workspace107.api.errors import ApiProblem
from workspace107.api.schemas.runs import (
    LogChunkResponse,
    PreflightCheckResponse,
    PreflightResponse,
    RunEventResponse,
    RunRequest,
    RunResponse,
)
from workspace107.application.runs import RunDatasetSelection, RunService
from workspace107.domain.enums import RunStatus

router = APIRouter(tags=["runs"])
_TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})


def _selections(request: RunRequest) -> tuple[RunDatasetSelection, ...]:
    return tuple(
        RunDatasetSelection(
            dataset_version_id=dataset.dataset_version_id,
            mount_path=dataset.mount_path,
        )
        for dataset in request.datasets
    )


@router.post("/runs/preflight", response_model=PreflightResponse)
async def preflight_run(
    request: RunRequest,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
) -> PreflightResponse:
    checks = await service.preflight(
        actor_id=actor_id,
        project_id=request.project_id,
        template_id=request.template_id,
        datasets=_selections(request),
    )
    return PreflightResponse(
        passed=all(check.passed for check in checks),
        checks=tuple(PreflightCheckResponse.model_validate(check) for check in checks),
    )


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_run(
    request: RunRequest,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
) -> RunResponse:
    run = await service.submit(
        actor_id=actor_id,
        project_id=request.project_id,
        template_id=request.template_id,
        datasets=_selections(request),
    )
    return RunResponse.model_validate(run)


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(
    workspace_id: UUID,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RunResponse]:
    runs = await service.list(
        actor_id=actor_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [RunResponse.model_validate(run) for run in runs]


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
) -> RunResponse:
    return RunResponse.model_validate(await service.get(actor_id=actor_id, run_id=run_id))


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_run(
    run_id: UUID,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
) -> RunResponse:
    return RunResponse.model_validate(await service.cancel(actor_id=actor_id, run_id=run_id))


@router.get("/runs/{run_id}/events", response_model=list[RunEventResponse])
async def list_run_events(
    run_id: UUID,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
) -> list[RunEventResponse]:
    events = await service.list_events(actor_id=actor_id, run_id=run_id)
    return [RunEventResponse.model_validate(event) for event in events]


@router.get("/runs/{run_id}/logs", response_model=LogChunkResponse)
async def read_run_log(
    run_id: UUID,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
    offset: int = Query(default=0, ge=0),
) -> LogChunkResponse:
    chunk = await service.read_log(actor_id=actor_id, run_id=run_id, offset=offset)
    return LogChunkResponse.model_validate(chunk)


def _log_offset(offset: int | None, last_event_id: str | None) -> int:
    if offset is not None:
        return offset
    if last_event_id is None:
        return 0
    try:
        parsed = int(last_event_id)
    except ValueError as exc:
        raise ApiProblem(
            status=422,
            title="Invalid log offset",
            code="invalid_log_offset",
            detail="Last-Event-ID must be a non-negative byte offset.",
        ) from exc
    if parsed < 0:
        raise ApiProblem(
            status=422,
            title="Invalid log offset",
            code="invalid_log_offset",
            detail="Last-Event-ID must be a non-negative byte offset.",
        )
    return parsed


async def _stream_log_events(
    *,
    actor_id: UUID,
    run_id: UUID,
    service: RunService,
    offset: int,
    poll_seconds: float,
) -> AsyncIterator[str]:
    current = offset
    while True:
        chunk = await service.read_log(actor_id=actor_id, run_id=run_id, offset=current)
        current = chunk.next_offset
        if chunk.data:
            payload = json.dumps(
                {"offset": current, "data": chunk.data},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"id: {current}\nevent: line\ndata: {payload}\n\n"
        run = await service.get(actor_id=actor_id, run_id=run_id)
        if chunk.end_of_stream or run.status in _TERMINAL:
            payload = json.dumps(
                {"offset": current, "status": run.status.value},
                separators=(",", ":"),
            )
            yield f"id: {current}\nevent: end\ndata: {payload}\n\n"
            return
        await asyncio.sleep(poll_seconds)


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_log(
    run_id: UUID,
    request: Request,
    actor_id: IdentityDependency,
    service: RunServiceDependency,
    offset: int | None = Query(default=None, ge=0),
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    start = _log_offset(offset, last_event_id)
    await service.get(actor_id=actor_id, run_id=run_id)
    poll_seconds = getattr(request.app.state, "log_poll_interval_seconds", 0.2)
    if not isinstance(poll_seconds, (int, float)) or poll_seconds <= 0:
        raise RuntimeError("log poll interval is not configured")
    return StreamingResponse(
        _stream_log_events(
            actor_id=actor_id,
            run_id=run_id,
            service=service,
            offset=start,
            poll_seconds=float(poll_seconds),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
