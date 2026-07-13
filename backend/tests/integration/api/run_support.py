from dataclasses import dataclass
from typing import cast

from .conftest import ApiHarness


@dataclass(frozen=True, slots=True)
class RunWorkflow:
    user: dict[str, object]
    workspace: dict[str, object]
    project: dict[str, object]
    dataset: dict[str, object]
    version: dict[str, object]
    template: dict[str, object]
    request: dict[str, object]
    preflight: dict[str, object]
    run: dict[str, object] | None


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def create_workflow(
    api: ApiHarness,
    *,
    submit: bool = True,
    include_entrypoint: bool = True,
) -> RunWorkflow:
    client = api.client
    created_user = await client.post(
        "/api/v1/users",
        json={"username": f"runner-{id(api)}", "display_name": "Runner"},
    )
    assert created_user.status_code == 201
    user = cast(dict[str, object], created_user.json())
    headers = identity(user)

    created_workspace = await client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={
            "kind": "course",
            "name": "AI 101",
            "slug": f"ai-101-{id(api)}",
        },
    )
    assert created_workspace.status_code == 201
    workspace = cast(dict[str, object], created_workspace.json())

    created_project = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        headers=headers,
        json={"name": "Demo", "slug": "demo"},
    )
    assert created_project.status_code == 201
    project = cast(dict[str, object], created_project.json())
    project_source = api.roots["source"] / str(project["id"])
    project_source.mkdir(parents=True, exist_ok=True)
    if include_entrypoint:
        (project_source / "train.py").write_text("print('train')\n", encoding="utf-8")
    pushed = await client.post(
        f"/api/v1/projects/{project['id']}/push",
        headers=headers,
        json={"source_root": "source", "target_root": "cluster"},
    )
    assert pushed.status_code == 200

    created_dataset = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets",
        headers=headers,
        json={"name": "Images", "slug": "images"},
    )
    assert created_dataset.status_code == 201
    dataset = cast(dict[str, object], created_dataset.json())
    created_version = await client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        headers=headers,
        data={"version": "v1"},
        files={"file": ("images.bin", b"dataset", "application/octet-stream")},
    )
    assert created_version.status_code == 201
    version = cast(dict[str, object], created_version.json())

    created_template = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/run-templates",
        headers=headers,
        json={
            "name": "Train",
            "entrypoint": "train.py",
            "environment_spec": {"kind": "system"},
            "resource_spec": {
                "cpus": 2,
                "memory_mb": 2048,
                "gpus": 0,
                "walltime_seconds": 60,
            },
            "output_spec": ["result.json"],
        },
    )
    assert created_template.status_code == 201
    template = cast(dict[str, object], created_template.json())
    request: dict[str, object] = {
        "project_id": project["id"],
        "template_id": template["id"],
        "datasets": [
            {
                "dataset_version_id": version["id"],
                "mount_path": "input/images",
            }
        ],
    }
    preflight_response = await client.post(
        "/api/v1/runs/preflight",
        headers=headers,
        json=request,
    )
    assert preflight_response.status_code == 200
    preflight = cast(dict[str, object], preflight_response.json())
    run: dict[str, object] | None = None
    if submit:
        submitted = await client.post("/api/v1/runs", headers=headers, json=request)
        assert submitted.status_code == 202
        run = cast(dict[str, object], submitted.json())
    return RunWorkflow(
        user=user,
        workspace=workspace,
        project=project,
        dataset=dataset,
        version=version,
        template=template,
        request=request,
        preflight=preflight,
        run=run,
    )


async def finish_workflow(api: ApiHarness, workflow: RunWorkflow) -> dict[str, object]:
    assert workflow.run is not None
    api.clock.advance(api.queue_seconds)
    await api.reconciler.reconcile_once()
    api.clock.advance(api.run_seconds)
    await api.reconciler.reconcile_once()
    response = await api.client.get(
        f"/api/v1/runs/{workflow.run['id']}",
        headers=identity(workflow.user),
    )
    assert response.status_code == 200
    return cast(dict[str, object], response.json())
