"""Current-user profile updates."""

from __future__ import annotations

import httpx
import pytest

from workspace107.api.deps import AppContext

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


@pytest.mark.asyncio
async def test_user_can_update_display_name_and_username(client: httpx.AsyncClient) -> None:
    created = (await client.get("/api/v1/me", headers=ALICE)).json()["user"]
    response = await client.patch(
        "/api/v1/me",
        headers=ALICE,
        json={"display_name": "Alice Zhang", "username": "alice-z"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["username"] == "alice-z"
    assert body["display_name"] == "Alice Zhang"
    home = (await client.get("/api/v1/me", headers={"X-User": "alice-z"})).json()["user"]
    assert home == body


@pytest.mark.asyncio
async def test_username_conflict_returns_409(client: httpx.AsyncClient) -> None:
    await client.get("/api/v1/me", headers=BOB)
    await client.get("/api/v1/me", headers=ALICE)

    response = await client.patch("/api/v1/me", headers=ALICE, json={"username": "bob"})
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_cas_user_keeps_identity_after_username_change(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    context.settings.auth_mode = "ustc"
    headers = {"X-User-ID": "20260001", "X-User-Name": "Alice Student"}
    created = (await client.get("/api/v1/me", headers=headers)).json()["user"]
    response = await client.patch(
        "/api/v1/me",
        headers=headers,
        json={"username": "alice-handle"},
    )
    assert response.status_code == 200
    again = (await client.get("/api/v1/me", headers=headers)).json()["user"]
    assert again["id"] == created["id"]
    assert again["username"] == "alice-handle"


@pytest.mark.asyncio
async def test_invalid_username_returns_422(client: httpx.AsyncClient) -> None:
    await client.get("/api/v1/me", headers=ALICE)
    response = await client.patch("/api/v1/me", headers=ALICE, json={"username": "bad name"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
