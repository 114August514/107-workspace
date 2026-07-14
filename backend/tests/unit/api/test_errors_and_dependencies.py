import json
from collections.abc import Callable
from typing import cast

import pytest
from fastapi import FastAPI, Request
from starlette.types import Scope

from workspace107.api.dependencies import (
    get_clock,
    get_cluster,
    get_project_transport,
    get_storage,
    get_transfer,
    get_transfer_roots,
    get_uow_factory,
)
from workspace107.api.errors import (
    ApiProblem,
    api_problem_handler,
    domain_error_handler,
    request_validation_handler,
)
from workspace107.domain.errors import (
    ClusterUnavailable,
    DomainError,
    ExternalCommandFailed,
    FinalOwnerRequired,
    InvalidRunTransition,
    InvalidWorkspaceParent,
    PathOutsideAllowedRoot,
    PreflightFailed,
    ResourceArchived,
    ResourceConflict,
    ResourceNotFound,
    TransferFailed,
    WorkspaceAccessDenied,
)


def request_for(app: FastAPI | None = None) -> Request:
    return Request(
        cast(
            Scope,
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "app": app or FastAPI(),
            },
        )
    )


@pytest.mark.parametrize(
    ("error", "status", "title", "detail"),
    [
        (WorkspaceAccessDenied("denied"), 403, "Workspace access denied", "denied"),
        (ResourceNotFound("missing"), 404, "Resource not found", "missing"),
        (ResourceConflict("conflict"), 409, "Resource conflict", "conflict"),
        (ResourceArchived("archived"), 409, "Resource conflict", "archived"),
        (FinalOwnerRequired("owner"), 409, "Resource conflict", "owner"),
        (InvalidRunTransition("transition"), 409, "Invalid run transition", "transition"),
        (PreflightFailed("preflight"), 422, "Run preflight failed", "preflight"),
        (InvalidWorkspaceParent("parent"), 422, "Validation failed", "parent"),
        (
            PathOutsideAllowedRoot("/private/path"),
            422,
            "Validation failed",
            "A transfer path is outside its configured root.",
        ),
        (
            ClusterUnavailable("private cluster"),
            503,
            "Cluster unavailable",
            "The configured cluster adapter is unavailable.",
        ),
        (
            ExternalCommandFailed("private command"),
            503,
            "External command failed",
            "An external cluster command failed.",
        ),
        (
            TransferFailed("private transfer"),
            502,
            "Project transfer failed",
            "The project transfer failed.",
        ),
        (DomainError("domain"), 400, "Domain operation failed", "domain"),
    ],
)
async def test_domain_errors_map_to_stable_problem_details(
    error: DomainError,
    status: int,
    title: str,
    detail: str,
) -> None:
    response = await domain_error_handler(request_for(), error)
    body = cast(dict[str, object], json.loads(bytes(response.body)))

    assert response.status_code == status
    assert body["title"] == title
    assert body["code"] == error.code
    assert body["detail"] == detail


async def test_preflight_problem_includes_structured_errors() -> None:
    error = PreflightFailed(errors=({"code": "entrypoint_exists", "message": "missing"},))

    response = await domain_error_handler(request_for(), error)
    body = cast(dict[str, object], json.loads(bytes(response.body)))

    assert body["errors"] == [{"code": "entrypoint_exists", "message": "missing"}]


async def test_exception_handlers_reject_wrong_exception_types() -> None:
    error = RuntimeError("wrong handler")

    with pytest.raises(RuntimeError, match="wrong handler"):
        await api_problem_handler(request_for(), error)
    with pytest.raises(RuntimeError, match="wrong handler"):
        await domain_error_handler(request_for(), error)
    with pytest.raises(RuntimeError, match="wrong handler"):
        await request_validation_handler(request_for(), error)


async def test_api_problem_handler_preserves_explicit_contract() -> None:
    problem = ApiProblem(status=418, title="Teapot", code="teapot", detail="Short and stout")

    response = await api_problem_handler(request_for(), problem)
    body = cast(dict[str, object], json.loads(bytes(response.body)))

    assert response.status_code == 418
    assert body["type"] == "https://workspace107.local/problems/teapot"
    assert body["detail"] == "Short and stout"


@pytest.mark.parametrize(
    "getter",
    [
        get_uow_factory,
        get_storage,
        get_cluster,
        get_project_transport,
        get_clock,
        get_transfer,
        get_transfer_roots,
    ],
)
def test_runtime_dependencies_require_composition_root_state(
    getter: Callable[[Request], object],
) -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        getter(request_for())


def test_runtime_dependencies_reject_invalid_scalar_state() -> None:
    app = FastAPI()
    app.state.project_transport = 42
    app.state.clock = "not-callable"
    request = request_for(app)

    with pytest.raises(RuntimeError, match="project transport"):
        get_project_transport(request)
    with pytest.raises(RuntimeError, match="clock"):
        get_clock(request)
