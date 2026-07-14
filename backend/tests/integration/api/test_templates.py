from typing import cast

from httpx import AsyncClient


async def create_user(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/users",
        json={"username": username, "display_name": username.title()},
    )
    assert response.status_code == 201
    return response.json()


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def create_workspace(client: AsyncClient, owner: dict[str, object]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/workspaces",
        headers=identity(owner),
        json={"kind": "course", "name": "AI 101", "slug": "ai-101"},
    )
    assert response.status_code == 201
    return response.json()


def template_payload() -> dict[str, object]:
    return {
        "name": "Train",
        "description": "Train a model",
        "entrypoint": "src/./train.py",
        "environment_spec": {"kind": "uv"},
        "resource_spec": {
            "cpus": 4,
            "memory_mb": 4096,
            "gpus": 1,
            "walltime_seconds": 3600,
        },
        "output_spec": ["results/./metrics.json"],
    }


async def test_template_crud_permissions_and_archive(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    bob = await create_user(client, "bob")
    workspace = await create_workspace(client, alice)
    path = f"/api/v1/workspaces/{workspace['id']}/run-templates"
    created = await client.post(path, headers=identity(alice), json=template_payload())
    template = created.json()
    added = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=identity(alice),
        json={"user_id": bob["id"], "role": "viewer"},
    )
    visible = await client.get(path, headers=identity(bob))
    readable = await client.get(
        f"/api/v1/run-templates/{template['id']}",
        headers=identity(bob),
    )
    create_forbidden = await client.post(
        path,
        headers=identity(bob),
        json={**template_payload(), "name": "Forbidden"},
    )
    promoted = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{bob['id']}",
        headers=identity(alice),
        json={"role": "member"},
    )
    updated = await client.patch(
        f"/api/v1/run-templates/{template['id']}",
        headers=identity(bob),
        json={"description": "Updated"},
    )
    archive_forbidden = await client.post(
        f"/api/v1/run-templates/{template['id']}/archive",
        headers=identity(bob),
    )
    archived = await client.post(
        f"/api/v1/run-templates/{template['id']}/archive",
        headers=identity(alice),
    )
    rejected = await client.patch(
        f"/api/v1/run-templates/{template['id']}",
        headers=identity(alice),
        json={"name": "After archive"},
    )

    assert created.status_code == 201
    assert template["entrypoint"] == "src/train.py"
    assert template["output_spec"] == ["results/metrics.json"]
    assert added.status_code == 201
    assert visible.json() == [template]
    assert readable.json() == template
    assert create_forbidden.status_code == 403
    assert promoted.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated"
    assert archive_forbidden.status_code == 403
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "resource_archived"


async def test_template_rejects_unsafe_paths_and_resources(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    workspace = await create_workspace(client, alice)
    path = f"/api/v1/workspaces/{workspace['id']}/run-templates"
    unsafe_entry = await client.post(
        path,
        headers=identity(alice),
        json={**template_payload(), "entrypoint": "../train.py"},
    )
    unsafe_output = await client.post(
        path,
        headers=identity(alice),
        json={**template_payload(), "output_spec": ["../private"]},
    )
    resources = dict(cast(dict[str, object], template_payload()["resource_spec"]))
    resources["cpus"] = 0
    invalid_resources = await client.post(
        path,
        headers=identity(alice),
        json={**template_payload(), "resource_spec": resources},
    )

    assert unsafe_entry.status_code == 422
    assert unsafe_entry.json()["code"] == "request_validation_failed"
    assert unsafe_output.status_code == 422
    assert invalid_resources.status_code == 422
