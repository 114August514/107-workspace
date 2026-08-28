from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers import ensure_user_group

from workspace107.infrastructure.db.tables import EnvironmentRow, EnvironmentVersionRow, GrantRow

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


@pytest.mark.asyncio
async def test_issue_45_environment_catalog_includes_granted_assets_in_owner_context(
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    bob_headers = {"X-User": "bob"}
    bob = (await client.get("/api/v1/me", headers=bob_headers)).json()["user"]
    alice_group_id = await ensure_user_group(client, headers=ALICE)
    bob_group_id = await ensure_user_group(client, headers=bob_headers)
    session.add(
        EnvironmentRow(
            id="env_issue_45_granted",
            name="Granted CUDA",
            description="Granted from Bob Lab",
            owner_user_group_id=bob_group_id,
        )
    )
    session.add(
        EnvironmentVersionRow(
            id="envv_issue_45_granted",
            environment_id="env_issue_45_granted",
            version="cuda-12.4",
            description="CUDA 12.4",
            image="cuda:12.4",
            setup_command="",
            available=True,
        )
    )
    session.add(
        EnvironmentVersionRow(
            id="envv_issue_45_unavailable_grant",
            environment_id="env_issue_45_granted",
            version="cuda-12.5",
            description="Unavailable image",
            image="cuda:12.5",
            setup_command="",
            available=False,
        )
    )
    session.add(
        GrantRow(
            id="grt_issue_45_environment",
            grantor_kind="user_group",
            grantor_id=bob_group_id,
            grantee_kind="user_group",
            grantee_id=alice_group_id,
            target_kind="environment",
            target_id="env_issue_45_granted",
            action="use",
            granted_by_id=bob["id"],
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()

    catalog = await client.get("/api/v1/catalog/environments", headers=ALICE)
    assert catalog.status_code == 200
    granted = next(item for item in catalog.json() if item["id"] == "env_issue_45_granted")
    assert granted["owner"] == {
        "kind": "user_group",
        "id": bob_group_id,
        "display_name": "bob test group",
    }
    assert {version["id"] for version in granted["versions"]} == {
        "envv_issue_45_granted",
        "envv_issue_45_unavailable_grant",
    }

    project = await client.post(
        "/api/v1/projects",
        json={
            "owner": {"kind": "user_group", "id": alice_group_id},
            "name": "Environment consumer",
        },
        headers=ALICE,
    )
    assert project.status_code == 201
    project_catalog = await client.get(
        f"/api/v1/projects/{project.json()['id']}/environments",
        headers=ALICE,
    )
    assert project_catalog.status_code == 200
    assert {item["id"] for item in project_catalog.json()} == {"env_issue_45_granted"}

    rejected_configuration = await client.post(
        f"/api/v1/projects/{project.json()['id']}/run-configurations",
        json={
            "name": "Unavailable environment",
            "command": "python train.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": "envv_issue_45_unavailable_grant",
        },
        headers=ALICE,
    )
    assert rejected_configuration.status_code == 422
    assert rejected_configuration.json()["message"] == "Environment Version 当前不可用"

    detail = await client.get("/api/v1/catalog/environments/env_issue_45_granted", headers=ALICE)
    assert detail.status_code == 200
    assert detail.json()["id"] == "env_issue_45_granted"

    revoked = await client.delete("/api/v1/grants/grt_issue_45_environment", headers=bob_headers)
    assert revoked.status_code == 204

    catalog_after_revoke = await client.get("/api/v1/catalog/environments", headers=ALICE)
    assert "env_issue_45_granted" not in {item["id"] for item in catalog_after_revoke.json()}
    project_after_revoke = await client.get(
        f"/api/v1/projects/{project.json()['id']}/environments",
        headers=ALICE,
    )
    assert project_after_revoke.status_code == 200
    assert project_after_revoke.json() == []
    assert (
        await client.get(
            "/api/v1/catalog/environments/env_issue_45_granted",
            headers=ALICE,
        )
    ).status_code == 404
