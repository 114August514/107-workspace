from typing import cast

from httpx import AsyncClient

from .conftest import ApiHarness
from .run_support import create_workflow, finish_workflow, identity


async def create_user(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


async def test_complete_mock_run_workflow_and_permissions(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    assert workflow.preflight["passed"] is True
    assert all(
        check["passed"] for check in cast(list[dict[str, object]], workflow.preflight["checks"])
    )
    assert workflow.run["status"] == "queued"

    listed = await run_api.client.get(
        "/api/v1/runs",
        headers=identity(workflow.user),
        params={"workspace_id": str(workflow.workspace["id"])},
    )
    fetched = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}",
        headers=identity(workflow.user),
    )
    assert listed.status_code == 200
    assert cast(list[dict[str, object]], listed.json())[0]["id"] == workflow.run["id"]
    assert fetched.status_code == 200

    final = await finish_workflow(run_api, workflow)
    events = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}/events",
        headers=identity(workflow.user),
    )
    assert final["status"] == "succeeded"
    assert final["started_at"] is not None
    assert final["finished_at"] is not None
    assert events.status_code == 200
    assert [event["to_status"] for event in cast(list[dict[str, object]], events.json())] == [
        "submitting",
        "queued",
        "running",
        "succeeded",
    ]

    outsider = await create_user(run_api.client, "outsider")
    forbidden = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}",
        headers=identity(outsider),
    )
    assert forbidden.status_code == 403


async def test_viewer_can_read_run_resources(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    await finish_workflow(run_api, workflow)
    viewer = await create_user(run_api.client, "run-viewer")
    added = await run_api.client.post(
        f"/api/v1/workspaces/{workflow.workspace['id']}/members",
        headers=identity(workflow.user),
        json={"user_id": viewer["id"], "role": "viewer"},
    )
    owner_artifacts = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}/artifacts",
        headers=identity(workflow.user),
    )
    artifact_id = cast(list[dict[str, object]], owner_artifacts.json())[0]["id"]

    responses = (
        await run_api.client.get(f"/api/v1/runs/{workflow.run['id']}", headers=identity(viewer)),
        await run_api.client.get(
            f"/api/v1/runs/{workflow.run['id']}/events", headers=identity(viewer)
        ),
        await run_api.client.get(
            f"/api/v1/runs/{workflow.run['id']}/logs", headers=identity(viewer)
        ),
        await run_api.client.get(
            f"/api/v1/runs/{workflow.run['id']}/artifacts", headers=identity(viewer)
        ),
        await run_api.client.get(
            f"/api/v1/artifacts/{artifact_id}/download", headers=identity(viewer)
        ),
    )

    assert added.status_code == 201
    assert [response.status_code for response in responses] == [200, 200, 200, 200, 200]


async def test_cancel_is_idempotent_over_http(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    path = f"/api/v1/runs/{workflow.run['id']}/cancel"

    first = await run_api.client.post(path, headers=identity(workflow.user))
    second = await run_api.client.post(path, headers=identity(workflow.user))
    await run_api.reconciler.reconcile_once()
    terminal = await run_api.client.post(path, headers=identity(workflow.user))

    assert first.status_code == 202
    assert first.json()["status"] == "cancelling"
    assert second.status_code == 202
    assert terminal.status_code == 202
    assert terminal.json()["status"] == "cancelled"


async def test_mock_failure_is_visible_as_terminal_run(failure_api: ApiHarness) -> None:
    workflow = await create_workflow(failure_api)
    final = await finish_workflow(failure_api, workflow)

    assert final["status"] == "failed"
    assert final["exit_code"] == 1
    assert final["failure_code"] == "external_job_failed"


async def test_failed_preflight_does_not_create_run(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api, submit=False, include_entrypoint=False)
    checks = cast(list[dict[str, object]], workflow.preflight["checks"])
    assert workflow.preflight["passed"] is False
    assert not next(check for check in checks if check["code"] == "entrypoint_exists")["passed"]

    rejected = await run_api.client.post(
        "/api/v1/runs",
        headers=identity(workflow.user),
        json=workflow.request,
    )
    listed = await run_api.client.get(
        "/api/v1/runs",
        headers=identity(workflow.user),
        params={"workspace_id": str(workflow.workspace["id"])},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "preflight_failed"
    assert rejected.json()["errors"]
    assert listed.json() == []
