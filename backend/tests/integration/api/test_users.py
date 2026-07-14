from uuid import uuid4

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


async def test_create_and_get_user(client: AsyncClient) -> None:
    user = await create_user(client)

    response = await client.get(f"/api/v1/users/{user['id']}")

    assert response.status_code == 200
    assert response.json() == user
    assert user["username"] == "alice"
    assert user["email"] is None


async def test_duplicate_username_returns_problem_details(client: AsyncClient) -> None:
    await create_user(client)

    response = await client.post(
        "/api/v1/users",
        json={"username": "alice", "display_name": "Another Alice"},
    )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "resource_conflict"


async def test_unknown_user_returns_not_found_problem(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"


async def test_user_payload_forbids_unknown_fields(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/users",
        json={"username": "alice", "display_name": "Alice", "admin": True},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "request_validation_failed"
