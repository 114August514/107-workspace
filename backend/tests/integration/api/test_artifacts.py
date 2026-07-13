import hashlib
from typing import cast

from .conftest import ApiHarness
from .run_support import create_workflow, finish_workflow, identity
from .test_runs import create_user


async def test_artifacts_list_and_download_match_digest(run_api: ApiHarness) -> None:
    workflow = await create_workflow(run_api)
    assert workflow.run is not None
    await finish_workflow(run_api, workflow)
    listed = await run_api.client.get(
        f"/api/v1/runs/{workflow.run['id']}/artifacts",
        headers=identity(workflow.user),
    )
    assert listed.status_code == 200
    artifacts = cast(list[dict[str, object]], listed.json())
    assert {artifact["kind"] for artifact in artifacts} == {"log", "result"}

    for artifact in artifacts:
        downloaded = await run_api.client.get(
            f"/api/v1/artifacts/{artifact['id']}/download",
            headers=identity(workflow.user),
        )
        assert downloaded.status_code == 200
        assert hashlib.sha256(downloaded.content).hexdigest() == artifact["sha256"]
        assert int(downloaded.headers["content-length"]) == artifact["size_bytes"]

    outsider = await create_user(run_api.client, "artifact-outsider")
    forbidden = await run_api.client.get(
        f"/api/v1/artifacts/{artifacts[0]['id']}/download",
        headers=identity(outsider),
    )
    assert forbidden.status_code == 403
