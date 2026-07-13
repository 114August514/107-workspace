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


async def create_course(client: AsyncClient, owner: dict[str, object]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/workspaces",
        headers=identity(owner),
        json={"kind": "course", "name": "AI 101", "slug": "ai-101"},
    )
    assert response.status_code == 201
    return response.json()


async def test_project_crud_permissions_and_archive(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    bob = await create_user(client, "bob")
    workspace = await create_course(client, alice)
    created = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        headers=identity(alice),
        json={"name": "Demo", "slug": "demo", "description": "first"},
    )
    project = created.json()
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=identity(alice),
        json={"user_id": bob["id"], "role": "viewer"},
    )

    visible = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        headers=identity(bob),
    )
    readable = await client.get(f"/api/v1/projects/{project['id']}", headers=identity(bob))
    forbidden = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        headers=identity(bob),
        json={"name": "No", "slug": "no"},
    )
    promoted = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{bob['id']}",
        headers=identity(alice),
        json={"role": "member"},
    )
    updated = await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=identity(bob),
        json={"description": "updated"},
    )
    archive_forbidden = await client.post(
        f"/api/v1/projects/{project['id']}/archive",
        headers=identity(bob),
    )
    archived = await client.post(
        f"/api/v1/projects/{project['id']}/archive",
        headers=identity(alice),
    )
    rejected = await client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=identity(alice),
        json={"name": "After archive"},
    )

    assert created.status_code == 201
    assert visible.json() == [project]
    assert readable.status_code == 200
    assert forbidden.status_code == 403
    assert promoted.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["description"] == "updated"
    assert archive_forbidden.status_code == 403
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "resource_archived"


async def test_duplicate_project_slug_returns_conflict(client: AsyncClient) -> None:
    alice = await create_user(client, "alice")
    workspace = await create_course(client, alice)
    path = f"/api/v1/workspaces/{workspace['id']}/projects"
    assert (
        await client.post(
            path,
            headers=identity(alice),
            json={"name": "Demo", "slug": "demo"},
        )
    ).status_code == 201

    duplicate = await client.post(
        path,
        headers=identity(alice),
        json={"name": "Other", "slug": "demo"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "resource_conflict"
