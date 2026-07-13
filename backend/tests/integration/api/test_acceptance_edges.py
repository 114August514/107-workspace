from typing import cast
from uuid import uuid4

from httpx import AsyncClient, Response


def object_response(response: Response, status: int) -> dict[str, object]:
    assert response.status_code == status, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


async def create_user(client: AsyncClient, username: str) -> dict[str, object]:
    return object_response(
        await client.post(
            "/api/v1/users",
            json={"username": username, "display_name": username.title()},
        ),
        201,
    )


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def create_workspace(
    client: AsyncClient,
    owner: dict[str, object],
    *,
    slug: str,
    kind: str = "course",
    parent_id: object = None,
) -> Response:
    payload: dict[str, object] = {
        "kind": kind,
        "name": slug.replace("-", " ").title(),
        "slug": slug,
    }
    if parent_id is not None:
        payload["parent_id"] = str(parent_id)
    return await client.post("/api/v1/workspaces", headers=identity(owner), json=payload)


def template_payload(name: str = "Train") -> dict[str, object]:
    return {
        "name": name,
        "entrypoint": "train.py",
        "environment_spec": {"kind": "system"},
        "resource_spec": {
            "cpus": 1,
            "memory_mb": 512,
            "gpus": 0,
            "walltime_seconds": 60,
        },
        "output_spec": ["result.json"],
    }


async def test_workspace_update_archive_and_access_edges(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    bob = await create_user(client, "bob")
    workspace = object_response(
        await create_workspace(client, alice, slug="primary-course"),
        201,
    )
    other = object_response(
        await create_workspace(client, alice, slug="other-course"),
        201,
    )

    invalid_identity = await client.get(
        "/api/v1/workspaces",
        headers={"X-User-Id": "not-a-uuid"},
    )
    missing = await client.get(
        f"/api/v1/workspaces/{uuid4()}",
        headers=identity(alice),
    )
    outsider = await client.get(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=identity(bob),
    )
    updated = object_response(
        await client.patch(
            f"/api/v1/workspaces/{workspace['id']}",
            headers=identity(alice),
            json={
                "name": "Updated Course",
                "slug": "updated-course",
                "description": "updated",
            },
        ),
        200,
    )
    duplicate_slug = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=identity(alice),
        json={"slug": other["slug"]},
    )
    archived = object_response(
        await client.post(
            f"/api/v1/workspaces/{workspace['id']}/archive",
            headers=identity(alice),
        ),
        200,
    )
    archived_again = object_response(
        await client.post(
            f"/api/v1/workspaces/{workspace['id']}/archive",
            headers=identity(alice),
        ),
        200,
    )
    update_archived = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=identity(alice),
        json={"name": "Too Late"},
    )

    assert invalid_identity.status_code == 401
    assert missing.status_code == 404
    assert outsider.status_code == 403
    assert updated["description"] == "updated"
    assert duplicate_slug.status_code == 409
    assert archived_again["archived_at"] == archived["archived_at"]
    assert update_archived.status_code == 409
    assert update_archived.json()["code"] == "resource_archived"


async def test_workspace_parent_and_member_management_edges(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    bob = await create_user(client, "bob")
    carol = await create_user(client, "carol")
    dave = await create_user(client, "dave")
    course = object_response(
        await create_workspace(client, alice, slug="parent-course"),
        201,
    )

    non_experiment_parent = await create_workspace(
        client,
        alice,
        slug="invalid-team",
        kind="team",
        parent_id=course["id"],
    )
    unknown_parent = await create_workspace(
        client,
        alice,
        slug="unknown-parent",
        kind="experiment",
        parent_id=uuid4(),
    )
    outsider_parent = await create_workspace(
        client,
        bob,
        slug="outsider-lab",
        kind="experiment",
        parent_id=course["id"],
    )
    await client.post(
        f"/api/v1/workspaces/{course['id']}/archive",
        headers=identity(alice),
    )
    archived_parent = await create_workspace(
        client,
        alice,
        slug="archived-parent",
        kind="experiment",
        parent_id=course["id"],
    )

    workspace = object_response(
        await create_workspace(client, alice, slug="member-course"),
        201,
    )
    member_path = f"/api/v1/workspaces/{workspace['id']}/members"
    manager = object_response(
        await client.post(
            member_path,
            headers=identity(alice),
            json={"user_id": bob["id"], "role": "manager"},
        ),
        201,
    )
    added_by_manager = object_response(
        await client.post(
            member_path,
            headers=identity(bob),
            json={"user_id": carol["id"], "role": "member"},
        ),
        201,
    )
    manager_adds_owner = await client.post(
        member_path,
        headers=identity(bob),
        json={"user_id": dave["id"], "role": "owner"},
    )
    unknown_user = await client.post(
        member_path,
        headers=identity(alice),
        json={"user_id": str(uuid4()), "role": "member"},
    )
    duplicate = await client.post(
        member_path,
        headers=identity(alice),
        json={"user_id": carol["id"], "role": "viewer"},
    )
    missing_member = await client.patch(
        f"{member_path}/{uuid4()}",
        headers=identity(alice),
        json={"role": "viewer"},
    )
    bob_owner = object_response(
        await client.patch(
            f"{member_path}/{bob['id']}",
            headers=identity(alice),
            json={"role": "owner"},
        ),
        200,
    )
    alice_manager = object_response(
        await client.patch(
            f"{member_path}/{alice['id']}",
            headers=identity(bob),
            json={"role": "manager"},
        ),
        200,
    )
    await client.patch(
        f"{member_path}/{alice['id']}",
        headers=identity(bob),
        json={"role": "owner"},
    )
    removed_owner = await client.delete(
        f"{member_path}/{alice['id']}",
        headers=identity(bob),
    )
    removed_again = await client.delete(
        f"{member_path}/{alice['id']}",
        headers=identity(bob),
    )
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/archive",
        headers=identity(bob),
    )
    add_to_archived = await client.post(
        member_path,
        headers=identity(bob),
        json={"user_id": dave["id"], "role": "member"},
    )

    assert non_experiment_parent.status_code == 422
    assert unknown_parent.status_code == 422
    assert outsider_parent.status_code == 403
    assert archived_parent.status_code == 422
    assert manager["role"] == "manager"
    assert added_by_manager["role"] == "member"
    assert manager_adds_owner.status_code == 403
    assert unknown_user.status_code == 404
    assert duplicate.status_code == 409
    assert missing_member.status_code == 404
    assert bob_owner["role"] == "owner"
    assert alice_manager["role"] == "manager"
    assert removed_owner.status_code == 204
    assert removed_again.status_code == 404
    assert add_to_archived.status_code == 409


async def test_project_dataset_and_template_error_edges(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    workspace = object_response(
        await create_workspace(client, alice, slug="resource-course"),
        201,
    )
    headers = identity(alice)

    projects_path = f"/api/v1/workspaces/{workspace['id']}/projects"
    first_project = object_response(
        await client.post(
            projects_path,
            headers=headers,
            json={"name": "First", "slug": "first"},
        ),
        201,
    )
    second_project = object_response(
        await client.post(
            projects_path,
            headers=headers,
            json={"name": "Second", "slug": "second"},
        ),
        201,
    )
    project_updated = object_response(
        await client.patch(
            f"/api/v1/projects/{first_project['id']}",
            headers=headers,
            json={"name": "Updated", "slug": "updated", "description": "complete"},
        ),
        200,
    )
    project_slug_conflict = await client.patch(
        f"/api/v1/projects/{first_project['id']}",
        headers=headers,
        json={"slug": second_project["slug"]},
    )
    missing_project_id = uuid4()
    missing_project_responses = (
        await client.get(f"/api/v1/projects/{missing_project_id}", headers=headers),
        await client.patch(
            f"/api/v1/projects/{missing_project_id}",
            headers=headers,
            json={"name": "Missing"},
        ),
        await client.post(
            f"/api/v1/projects/{missing_project_id}/archive",
            headers=headers,
        ),
        await client.post(
            f"/api/v1/projects/{missing_project_id}/scan",
            headers=headers,
            json={"source_root": "source"},
        ),
    )
    project_archived = object_response(
        await client.post(
            f"/api/v1/projects/{first_project['id']}/archive",
            headers=headers,
        ),
        200,
    )
    project_archived_again = object_response(
        await client.post(
            f"/api/v1/projects/{first_project['id']}/archive",
            headers=headers,
        ),
        200,
    )
    push_archived = await client.post(
        f"/api/v1/projects/{first_project['id']}/push",
        headers=headers,
        json={"source_root": "source", "target_root": "cluster"},
    )

    datasets_path = f"/api/v1/workspaces/{workspace['id']}/datasets"
    dataset = object_response(
        await client.post(
            datasets_path,
            headers=headers,
            json={"name": "Dataset", "slug": "dataset"},
        ),
        201,
    )
    duplicate_dataset = await client.post(
        datasets_path,
        headers=headers,
        json={"name": "Duplicate", "slug": "dataset"},
    )
    missing_dataset_id = uuid4()
    missing_dataset_responses = (
        await client.get(f"/api/v1/datasets/{missing_dataset_id}", headers=headers),
        await client.get(
            f"/api/v1/datasets/{missing_dataset_id}/versions",
            headers=headers,
        ),
        await client.post(
            f"/api/v1/datasets/{missing_dataset_id}/archive",
            headers=headers,
        ),
        await client.get(f"/api/v1/dataset-versions/{uuid4()}/download", headers=headers),
    )
    dataset_archived = object_response(
        await client.post(
            f"/api/v1/datasets/{dataset['id']}/archive",
            headers=headers,
        ),
        200,
    )
    dataset_archived_again = object_response(
        await client.post(
            f"/api/v1/datasets/{dataset['id']}/archive",
            headers=headers,
        ),
        200,
    )

    templates_path = f"/api/v1/workspaces/{workspace['id']}/run-templates"
    template = object_response(
        await client.post(templates_path, headers=headers, json=template_payload()),
        201,
    )
    template_updated = object_response(
        await client.patch(
            f"/api/v1/run-templates/{template['id']}",
            headers=headers,
            json={
                "name": "Conda Train",
                "description": "all fields",
                "entrypoint": "src/train.py",
                "environment_spec": {"kind": "conda", "conda_env": "ml"},
                "resource_spec": {
                    "cpus": 2,
                    "memory_mb": 2048,
                    "gpus": 1,
                    "walltime_seconds": 120,
                    "account": "course",
                    "partition": "gpu",
                    "qos": "normal",
                },
                "output_spec": [],
            },
        ),
        200,
    )
    invalid_conda = await client.post(
        templates_path,
        headers=headers,
        json={**template_payload("Invalid Conda"), "environment_spec": {"kind": "conda"}},
    )
    invalid_system = await client.post(
        templates_path,
        headers=headers,
        json={
            **template_payload("Invalid System"),
            "environment_spec": {"kind": "system", "conda_env": "ml"},
        },
    )
    missing_template_id = uuid4()
    missing_template_responses = (
        await client.get(f"/api/v1/run-templates/{missing_template_id}", headers=headers),
        await client.patch(
            f"/api/v1/run-templates/{missing_template_id}",
            headers=headers,
            json={"name": "Missing"},
        ),
        await client.post(
            f"/api/v1/run-templates/{missing_template_id}/archive",
            headers=headers,
        ),
    )
    template_archived = object_response(
        await client.post(
            f"/api/v1/run-templates/{template['id']}/archive",
            headers=headers,
        ),
        200,
    )
    template_archived_again = object_response(
        await client.post(
            f"/api/v1/run-templates/{template['id']}/archive",
            headers=headers,
        ),
        200,
    )

    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/archive",
        headers=headers,
    )
    create_after_workspace_archive = (
        await client.post(
            projects_path,
            headers=headers,
            json={"name": "Late", "slug": "late-project"},
        ),
        await client.post(
            datasets_path,
            headers=headers,
            json={"name": "Late", "slug": "late-dataset"},
        ),
        await client.post(
            templates_path,
            headers=headers,
            json=template_payload("Late Template"),
        ),
    )

    assert project_updated["description"] == "complete"
    assert project_slug_conflict.status_code == 409
    assert all(response.status_code == 404 for response in missing_project_responses)
    assert project_archived_again["archived_at"] == project_archived["archived_at"]
    assert push_archived.status_code == 409
    assert duplicate_dataset.status_code == 409
    assert all(response.status_code == 404 for response in missing_dataset_responses)
    assert dataset_archived_again["archived_at"] == dataset_archived["archived_at"]
    assert template_updated["environment_spec"] == {"kind": "conda", "conda_env": "ml"}
    assert template_updated["output_spec"] == []
    assert invalid_conda.status_code == 422
    assert invalid_system.status_code == 422
    assert all(response.status_code == 404 for response in missing_template_responses)
    assert template_archived_again["archived_at"] == template_archived["archived_at"]
    assert all(response.status_code == 409 for response in create_after_workspace_archive)
