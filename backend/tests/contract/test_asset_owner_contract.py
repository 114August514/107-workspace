from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers import ensure_user_group

from workspace107.infrastructure.db.tables import EnvironmentRow


ALICE = {"X-User": "alice"}
FORBIDDEN_OWNER_FIELDS = {"owner_workspace_id", "is_platform_owned"}


@pytest.mark.asyncio
async def test_issue_39_openapi_uses_only_canonical_owner_summary(
    client: httpx.AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    models = schema["components"]["schemas"]

    owner = models["OwnerSummaryOut"]
    assert set(owner["required"]) == {"kind", "id", "display_name"}
    assert set(owner["properties"]) == {"kind", "id", "display_name"}
    assert owner["properties"]["kind"] == {"$ref": "#/components/schemas/OwnerKind"}
    assert set(models["OwnerKind"]["enum"]) == {"user", "user_group"}

    for model_name in ("EnvironmentOut", "SharedResourceOut", "SharedResourceDetailOut"):
        properties = models[model_name]["properties"]
        assert properties["owner"] == {"$ref": "#/components/schemas/OwnerSummaryOut"}
        assert FORBIDDEN_OWNER_FIELDS.isdisjoint(properties)


@pytest.mark.asyncio
async def test_issue_39_canonical_shared_resource_create_and_get_enforces_owner_authority(
    client: httpx.AsyncClient,
) -> None:
    me = (await client.get("/api/v1/me", headers=ALICE)).json()
    user = me["user"]
    group_id = await ensure_user_group(client, headers=ALICE)

    for name, owner, display_name in (
        ("Personal resource", {"kind": "user", "id": user["id"]}, user["display_name"]),
        ("Group resource", {"kind": "user_group", "id": group_id}, "alice test group"),
    ):
        created = await client.post(
            "/api/v1/shared-resources",
            json={"name": name, "owner": owner},
            headers=ALICE,
        )
        assert created.status_code == 201
        resource_id = created.json()["id"]
        detail = await client.get(f"/api/v1/shared-resources/{resource_id}", headers=ALICE)
        assert detail.status_code == 200
        assert detail.json()["owner"] == {**owner, "display_name": display_name}

    bob = (await client.get("/api/v1/me", headers={"X-User": "bob"})).json()["user"]
    denied = await client.post(
        "/api/v1/shared-resources",
        json={"name": "Cross-owner resource", "owner": {"kind": "user", "id": bob["id"]}},
        headers=ALICE,
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_issue_39_environment_catalog_emits_both_canonical_owner_kinds(
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    me = (await client.get("/api/v1/me", headers=ALICE)).json()
    user = me["user"]
    group_id = await ensure_user_group(client, headers=ALICE)
    session.add_all(
        [
            EnvironmentRow(
                id="env_api_user_owner",
                name="User environment",
                description="",
                owner_user_id=user["id"],
            ),
            EnvironmentRow(
                id="env_api_group_owner",
                name="Group environment",
                description="",
                owner_user_group_id=group_id,
            ),
        ]
    )
    await session.commit()

    response = await client.get("/api/v1/catalog/environments", headers=ALICE)
    assert response.status_code == 200
    owners = {item["id"]: item["owner"] for item in response.json()}
    assert owners == {
        "env_api_user_owner": {
            "kind": "user",
            "id": user["id"],
            "display_name": user["display_name"],
        },
        "env_api_group_owner": {
            "kind": "user_group",
            "id": group_id,
            "display_name": "alice test group",
        },
    }
