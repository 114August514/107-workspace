from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_user_group_owner_and_execution_contracts_are_current(
    client: httpx.AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    models = schema["components"]["schemas"]

    assert models["UserGroupCapability"]["enum"] == [
        "user_group.view",
        "user_group.update",
        "user_group.delete",
        "member.view",
        "member.invite",
        "member.remove",
        "member.role.manage",
        "ownership.transfer",
    ]
    assert models["UserGroupOut"]["properties"]["capabilities"]["items"] == {
        "$ref": "#/components/schemas/UserGroupCapability"
    }
    assert models["MemberOut"]["properties"]["capabilities"]["items"] == {
        "$ref": "#/components/schemas/UserGroupCapability"
    }
    assert set(models["MemberInviteIn"]["properties"]) == {"username"}
    assert models["MemberInviteIn"]["additionalProperties"] is False
    assert "project.create" in models["Capability"]["enum"]
    assert "member.manage" not in models["Capability"]["enum"]
    assert "run.submit" in models["Capability"]["enum"]
    assert all("Workspace" not in model for model in models)
    assert not any(path.startswith("/api/v1/workspaces") for path in schema["paths"])
    assert "workspace_id" not in models["ProjectOut"]["properties"]
    assert "workspace_id" not in models["RunOut"]["properties"]
    assert "workspace_id" not in models["NotificationOut"]["properties"]
    assert set(models["HomeOut"]["required"]) == {
        "user",
        "user_groups",
        "personal_execution_context",
        "recent_projects",
        "recent_runs",
    }
