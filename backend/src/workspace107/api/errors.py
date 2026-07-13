from collections.abc import Sequence

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from workspace107.domain.errors import (
    DomainError,
    FinalOwnerRequired,
    InvalidRunTransition,
    InvalidWorkspaceParent,
    PreflightFailed,
    ResourceArchived,
    ResourceConflict,
    ResourceNotFound,
    WorkspaceAccessDenied,
)


class ApiProblem(Exception):
    def __init__(self, *, status: int, title: str, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.code = code
        self.detail = detail


def problem_response(
    *,
    status: int,
    title: str,
    code: str,
    detail: str,
    errors: Sequence[dict[str, object]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://workspace107.local/problems/{code.replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        body["errors"] = list(errors)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


async def api_problem_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiProblem):
        raise exc
    return problem_response(
        status=exc.status,
        title=exc.title,
        code=exc.code,
        detail=exc.detail,
    )


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    if isinstance(exc, WorkspaceAccessDenied):
        status, title = 403, "Workspace access denied"
    elif isinstance(exc, ResourceNotFound):
        status, title = 404, "Resource not found"
    elif isinstance(exc, (ResourceConflict, ResourceArchived, FinalOwnerRequired)):
        status, title = 409, "Resource conflict"
    elif isinstance(exc, InvalidRunTransition):
        status, title = 409, "Invalid run transition"
    elif isinstance(exc, (InvalidWorkspaceParent, PreflightFailed)):
        status, title = 422, "Validation failed"
    else:
        status, title = 400, "Domain operation failed"
    return problem_response(
        status=status,
        title=title,
        code=exc.code,
        detail=str(exc),
    )


async def request_validation_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors: list[dict[str, object]] = []
    for error in exc.errors():
        errors.append(
            {
                "location": [str(part) for part in error["loc"]],
                "message": str(error["msg"]),
                "type": str(error["type"]),
            }
        )
    return problem_response(
        status=422,
        title="Request validation failed",
        code="request_validation_failed",
        detail="The request payload or parameters are invalid.",
        errors=errors,
    )
