import asyncio
import hashlib
import os
from pathlib import Path
from typing import cast

import pytest
from httpx import AsyncClient, Response

BASE_URL = os.getenv("WORKSPACE107_TEST_BASE_URL")
SOURCE_ROOT = os.getenv("WORKSPACE107_TEST_SOURCE_ROOT")

pytestmark = pytest.mark.skipif(
    BASE_URL is None or SOURCE_ROOT is None,
    reason="live backend URL and source root are not configured",
)

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


def _json_object(response: Response, expected_status: int) -> dict[str, object]:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


async def test_live_mock_http_workflow() -> None:
    assert BASE_URL is not None
    assert SOURCE_ROOT is not None

    async with AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        health = _json_object(await client.get("/health"), 200)
        assert health == {"status": "ok", "service": "workspace107"}

        owner = _json_object(
            await client.post(
                "/api/v1/users",
                json={"username": "smoke-owner", "display_name": "Smoke Owner"},
            ),
            201,
        )
        member = _json_object(
            await client.post(
                "/api/v1/users",
                json={"username": "smoke-member", "display_name": "Smoke Member"},
            ),
            201,
        )
        headers = {"X-User-Id": str(owner["id"])}

        workspace = _json_object(
            await client.post(
                "/api/v1/workspaces",
                headers=headers,
                json={"kind": "course", "name": "Smoke Course", "slug": "smoke-course"},
            ),
            201,
        )
        membership = _json_object(
            await client.post(
                f"/api/v1/workspaces/{workspace['id']}/members",
                headers=headers,
                json={"user_id": member["id"], "role": "member"},
            ),
            201,
        )
        assert membership["role"] == "member"

        project = _json_object(
            await client.post(
                f"/api/v1/workspaces/{workspace['id']}/projects",
                headers=headers,
                json={"name": "Smoke Project", "slug": "smoke-project"},
            ),
            201,
        )
        project_source = Path(SOURCE_ROOT) / str(project["id"])
        project_source.mkdir(parents=True, exist_ok=True)
        (project_source / "train.py").write_text("print('smoke run')\n", encoding="utf-8")
        pushed = _json_object(
            await client.post(
                f"/api/v1/projects/{project['id']}/push",
                headers=headers,
                json={"source_root": "source", "target_root": "cluster"},
            ),
            200,
        )
        assert "train.py" in cast(list[str], pushed["transferred"])

        dataset = _json_object(
            await client.post(
                f"/api/v1/workspaces/{workspace['id']}/datasets",
                headers=headers,
                json={"name": "Smoke Dataset", "slug": "smoke-dataset"},
            ),
            201,
        )
        version = _json_object(
            await client.post(
                f"/api/v1/datasets/{dataset['id']}/versions",
                headers=headers,
                data={"version": "v1"},
                files={
                    "file": (
                        "dataset.bin",
                        b"workspace107 smoke dataset\n",
                        "application/octet-stream",
                    )
                },
            ),
            201,
        )
        template = _json_object(
            await client.post(
                f"/api/v1/workspaces/{workspace['id']}/run-templates",
                headers=headers,
                json={
                    "name": "Smoke Train",
                    "entrypoint": "train.py",
                    "environment_spec": {"kind": "system"},
                    "resource_spec": {
                        "cpus": 1,
                        "memory_mb": 512,
                        "gpus": 0,
                        "walltime_seconds": 60,
                    },
                    "output_spec": ["result.json"],
                },
            ),
            201,
        )
        run_request = {
            "project_id": project["id"],
            "template_id": template["id"],
            "datasets": [
                {
                    "dataset_version_id": version["id"],
                    "mount_path": "input/dataset",
                }
            ],
        }
        preflight = _json_object(
            await client.post(
                "/api/v1/runs/preflight",
                headers=headers,
                json=run_request,
            ),
            200,
        )
        assert preflight["passed"] is True

        run = _json_object(
            await client.post("/api/v1/runs", headers=headers, json=run_request),
            202,
        )
        observed_statuses = [str(run["status"])]
        deadline = asyncio.get_running_loop().time() + 10.0
        while observed_statuses[-1] not in _TERMINAL_STATUSES:
            assert asyncio.get_running_loop().time() < deadline, observed_statuses
            await asyncio.sleep(0.02)
            run = _json_object(
                await client.get(f"/api/v1/runs/{run['id']}", headers=headers),
                200,
            )
            status = str(run["status"])
            if status != observed_statuses[-1]:
                observed_statuses.append(status)

        assert observed_statuses == ["queued", "running", "succeeded"]

        logs = _json_object(
            await client.get(f"/api/v1/runs/{run['id']}/logs", headers=headers),
            200,
        )
        assert "queued" in str(logs["data"])
        assert "running" in str(logs["data"])
        assert "succeeded" in str(logs["data"])

        artifacts_response = await client.get(
            f"/api/v1/runs/{run['id']}/artifacts",
            headers=headers,
        )
        assert artifacts_response.status_code == 200, artifacts_response.text
        artifacts = cast(list[dict[str, object]], artifacts_response.json())
        assert isinstance(artifacts, list)
        result = next(artifact for artifact in artifacts if artifact.get("kind") == "result")
        download = await client.get(
            f"/api/v1/artifacts/{result['id']}/download",
            headers=headers,
        )
        assert download.status_code == 200, download.text
        assert hashlib.sha256(download.content).hexdigest() == result["sha256"]
        assert len(download.content) == result["size_bytes"]
