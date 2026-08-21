import pytest


async def _crud(client, base: str, *, secret_value: str) -> None:
    variable = await client.put(f"{base}/variables", json={"name": "SAME", "value": "value"})
    assert variable.status_code == 200
    assert (await client.get(f"{base}/variables")).json() == [{"name": "SAME", "value": "value"}]
    assert (await client.delete(f"{base}/variables/SAME")).status_code == 204
    secret = await client.put(f"{base}/secrets", json={"name": "TOKEN", "value": secret_value})
    assert secret.status_code == 204
    listed = await client.get(f"{base}/secrets")
    assert listed.status_code == 200
    assert listed.json() == ["TOKEN"]
    assert "value" not in listed.text
    assert secret_value not in listed.text
    assert (await client.delete(f"{base}/secrets/TOKEN")).status_code == 204
    assert (await client.get(f"{base}/secrets")).json() == []


@pytest.mark.asyncio
async def test_user_group_and_project_config_full_http_crud(client) -> None:
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    user_id = me.json()["user"]["id"]
    await _crud(client, f"/api/v1/users/{user_id}", secret_value="user-plaintext")
    group_response = await client.post("/api/v1/user-groups", json={"name": "config-http"})
    assert group_response.status_code == 201
    group_id = group_response.json()["id"]
    await _crud(client, f"/api/v1/user-groups/{group_id}", secret_value="group-plaintext")

    project_response = await client.post(
        f"/api/v1/workspaces/{group_id}/projects",
        json={"name": "config-project", "description": ""},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    await _crud(client, f"/api/v1/projects/{project_id}", secret_value="project-plaintext")


@pytest.mark.asyncio
async def test_user_foreign_and_project_unauthorized_existing_are_404(client) -> None:
    own_group = await client.post("/api/v1/user-groups", json={"name": "owned"})
    group_id = own_group.json()["id"]
    project = await client.post(
        f"/api/v1/workspaces/{group_id}/projects", json={"name": "private", "description": ""}
    )
    project_id = project.json()["id"]
    assert (await client.get("/api/v1/users/other/variables")).status_code == 404
    foreign = await client.get(
        f"/api/v1/projects/{project_id}/variables", headers={"X-User": "foreign"}
    )
    assert foreign.status_code == 404
