from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_user_group_and_legacy_capability_contracts_are_separate(
    client: httpx.AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    models = schema["components"]["schemas"]

    assert models["UserGroupCapability"]["enum"] == [
        "user_group.view",
        "user_group.update",
        "member.view",
        "member.manage",
        "ownership.transfer",
    ]
    assert models["UserGroupOut"]["properties"]["capabilities"]["items"] == {
        "$ref": "#/components/schemas/UserGroupCapability"
    }
    assert models["LegacyWorkspaceContextOut"]["properties"]["capabilities"]["items"] == {
        "$ref": "#/components/schemas/Capability"
    }
    assert "project.create" in models["Capability"]["enum"]
    assert "run.submit" in models["Capability"]["enum"]
