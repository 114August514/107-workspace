from httpx import AsyncClient


async def create_user(
    client: AsyncClient, username: str = "alice", display_name: str = "Alice"
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/users",
        json={"username": username, "display_name": display_name},
    )
    assert response.status_code == 201
    return response.json()


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def create_workspace(
    client: AsyncClient,
    user: dict[str, object],
    *,
    kind: str = "course",
    name: str = "AI 101",
    slug: str = "ai-101",
    parent_id: object = None,
):
    payload: dict[str, object] = {
        "kind": kind,
        "name": name,
        "slug": slug,
        "description": "",
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return await client.post("/api/v1/workspaces", headers=identity(user), json=payload)


async def test_create_workspace_assigns_owner_and_lists_visible(client: AsyncClient) -> None:
    alice = await create_user(client)
    response = await create_workspace(client, alice)

    assert response.status_code == 201
    workspace = response.json()
    members = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=identity(alice),
    )
    visible = await client.get("/api/v1/workspaces", headers=identity(alice))

    assert members.status_code == 200
    assert members.json()[0]["user_id"] == alice["id"]
    assert members.json()[0]["role"] == "owner"
    assert visible.json() == [workspace]


async def test_workspace_endpoints_require_existing_identity(client: AsyncClient) -> None:
    missing = await client.get("/api/v1/workspaces")
    unknown = await client.get(
        "/api/v1/workspaces",
        headers={"X-User-Id": "d8e7aeac-c6da-4b02-8684-cefc23306e88"},
    )

    assert missing.status_code == 401
    assert missing.json()["code"] == "identity_required"
    assert unknown.status_code == 401
    assert unknown.json()["code"] == "identity_required"


async def test_duplicate_workspace_slug_returns_conflict(client: AsyncClient) -> None:
    alice = await create_user(client)
    assert (await create_workspace(client, alice)).status_code == 201

    duplicate = await create_workspace(client, alice, name="Other")

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "resource_conflict"


async def test_viewer_can_read_but_cannot_mutate_workspace(client: AsyncClient) -> None:
    alice = await create_user(client)
    bob = await create_user(client, "bob", "Bob")
    workspace = (await create_workspace(client, alice)).json()
    added = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=identity(alice),
        json={"user_id": bob["id"], "role": "viewer"},
    )

    read = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=identity(bob))
    update = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=identity(bob),
        json={"name": "Changed"},
    )

    assert added.status_code == 201
    assert read.status_code == 200
    assert update.status_code == 403
    assert update.json()["code"] == "workspace_access_denied"


async def test_last_owner_cannot_be_changed_or_removed(client: AsyncClient) -> None:
    alice = await create_user(client)
    workspace = (await create_workspace(client, alice)).json()

    changed = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{alice['id']}",
        headers=identity(alice),
        json={"role": "manager"},
    )
    removed = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{alice['id']}",
        headers=identity(alice),
    )

    assert changed.status_code == 409
    assert changed.json()["code"] == "final_owner_required"
    assert removed.status_code == 409
    assert removed.json()["code"] == "final_owner_required"


async def test_experiment_requires_a_course_parent(client: AsyncClient) -> None:
    alice = await create_user(client)
    missing_parent = await create_workspace(
        client,
        alice,
        kind="experiment",
        name="Lab 1",
        slug="lab-1",
    )
    team = (
        await create_workspace(
            client,
            alice,
            kind="team",
            name="Team",
            slug="team",
        )
    ).json()
    wrong_parent = await create_workspace(
        client,
        alice,
        kind="experiment",
        name="Lab 2",
        slug="lab-2",
        parent_id=team["id"],
    )
    course = (
        await create_workspace(
            client,
            alice,
            kind="course",
            name="Systems",
            slug="systems",
        )
    ).json()
    valid = await create_workspace(
        client,
        alice,
        kind="experiment",
        name="Lab 3",
        slug="lab-3",
        parent_id=course["id"],
    )

    assert missing_parent.status_code == 422
    assert missing_parent.json()["code"] == "invalid_workspace_parent"
    assert wrong_parent.status_code == 422
    assert valid.status_code == 201


async def test_owner_can_manage_members_and_archive(client: AsyncClient) -> None:
    alice = await create_user(client)
    bob = await create_user(client, "bob", "Bob")
    workspace = (await create_workspace(client, alice)).json()
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=identity(alice),
        json={"user_id": bob["id"], "role": "viewer"},
    )

    changed = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{bob['id']}",
        headers=identity(alice),
        json={"role": "member"},
    )
    removed = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{bob['id']}",
        headers=identity(alice),
    )
    archived = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/archive",
        headers=identity(alice),
    )

    assert changed.status_code == 200
    assert changed.json()["role"] == "member"
    assert removed.status_code == 204
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
