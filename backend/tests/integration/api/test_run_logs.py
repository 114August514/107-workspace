from typing import cast

from .conftest import ApiHarness
from .run_support import create_workflow, identity
from .test_runs import create_user


async def test_log_reads_and_sse_resume_by_last_event_id(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    path = f"/api/v1/runs/{workflow.run['id']}/logs"
    queued_response = await run_api.client.get(path, headers=identity(workflow.user))
    assert queued_response.status_code == 200
    queued = cast(dict[str, object], queued_response.json())
    assert "queued" in str(queued["data"])

    run_api.clock.advance(run_api.queue_seconds)
    await run_api.reconciler.reconcile_once()
    running_response = await run_api.client.get(
        path,
        headers=identity(workflow.user),
        params={"offset": int(cast(int, queued["next_offset"]))},
    )
    running = cast(dict[str, object], running_response.json())
    assert "running" in str(running["data"])

    run_api.clock.advance(run_api.run_seconds)
    await run_api.reconciler.reconcile_once()
    stream = await run_api.client.get(
        f"{path}/stream",
        headers={
            **identity(workflow.user),
            "Last-Event-ID": str(running["next_offset"]),
        },
    )
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: line" in stream.text
    assert "succeeded" in stream.text
    assert "event: end" in stream.text
    assert " queued" not in stream.text


async def test_sse_rejects_invalid_last_event_id(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    response = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}/logs/stream",
        headers={**identity(workflow.user), "Last-Event-ID": "not-an-offset"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_log_offset"


async def test_sse_rejects_unauthorized_user_before_streaming(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    outsider = await create_user(run_api.client, "log-outsider")

    response = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}/logs/stream",
        headers=identity(outsider),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "workspace_access_denied"
