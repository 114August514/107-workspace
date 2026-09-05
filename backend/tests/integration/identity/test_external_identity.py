"""USTC CAS identity mapping at the HTTP and persistence boundary."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace107.api.deps import AppContext
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.tables import UserRow

ALICE = {
    "X-User-ID": "20260001",
    "X-User-Name": "Alice Student",
    "X-User-Email": "alice@example.edu.cn",
}


@pytest.mark.asyncio
async def test_first_cas_request_creates_mapping_and_second_request_reuses_user(
    client: httpx.AsyncClient,
    context: AppContext,
    session: AsyncSession,
) -> None:
    context.settings.auth_mode = "ustc"

    first = await client.get("/api/v1/me", headers=ALICE)
    second = await client.get(
        "/api/v1/me",
        headers={**ALICE, "X-User-Name": "A changed upstream name"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    user = first.json()["user"]
    assert user == {
        "id": second.json()["user"]["id"],
        "username": "20260001",
        "display_name": "Alice Student",
        "email": "alice@example.edu.cn",
    }
    identity = await SqlRepositories(session).external_identities.get("ustc-cas", "20260001")
    assert identity is not None
    assert identity.user_id == user["id"]
    matching_users = await session.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.email == "alice@example.edu.cn")
    )
    assert matching_users == 1


@pytest.mark.asyncio
async def test_distinct_cas_identities_never_merge_even_with_same_profile(
    client: httpx.AsyncClient,
    context: AppContext,
) -> None:
    context.settings.auth_mode = "ustc"

    first = await client.get("/api/v1/me", headers=ALICE)
    second = await client.get(
        "/api/v1/me",
        headers={**ALICE, "X-User-ID": "20260002"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user"]["id"] != second.json()["user"]["id"]


@pytest.mark.asyncio
async def test_cas_identity_does_not_claim_an_existing_dev_username(
    client: httpx.AsyncClient,
    context: AppContext,
) -> None:
    dev = await client.get("/api/v1/me", headers={"X-User": "20260001"})
    context.settings.auth_mode = "ustc"

    cas = await client.get("/api/v1/me", headers=ALICE)

    assert dev.status_code == 200
    assert cas.status_code == 200
    assert cas.json()["user"]["id"] != dev.json()["user"]["id"]
    assert cas.json()["user"]["username"].startswith("20260001~")


@pytest.mark.asyncio
async def test_ustc_mode_rejects_request_without_proxy_identity(
    client: httpx.AsyncClient,
    context: AppContext,
) -> None:
    context.settings.auth_mode = "ustc"

    response = await client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
