import hashlib

from httpx import AsyncClient


async def bootstrap(client: AsyncClient) -> tuple[dict[str, object], dict[str, object]]:
    user_response = await client.post(
        "/api/v1/users",
        json={"username": "alice", "display_name": "Alice"},
    )
    user = user_response.json()
    workspace_response = await client.post(
        "/api/v1/workspaces",
        headers={"X-User-Id": str(user["id"])},
        json={"kind": "course", "name": "AI 101", "slug": "ai-101"},
    )
    assert user_response.status_code == 201
    assert workspace_response.status_code == 201
    return user, workspace_response.json()


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def test_dataset_version_upload_list_and_download(client: AsyncClient) -> None:
    alice, workspace = await bootstrap(client)
    created = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets",
        headers=identity(alice),
        json={"name": "Images", "slug": "images", "description": "training"},
    )
    dataset = created.json()
    visible = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/datasets",
        headers=identity(alice),
    )
    readable = await client.get(
        f"/api/v1/datasets/{dataset['id']}",
        headers=identity(alice),
    )
    uploaded = await client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        headers=identity(alice),
        data={"version": "v1"},
        files={"file": ("dataset.bin", b"payload", "application/octet-stream")},
    )
    version = uploaded.json()

    listed = await client.get(
        f"/api/v1/datasets/{dataset['id']}/versions",
        headers=identity(alice),
    )
    downloaded = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/download",
        headers=identity(alice),
    )

    assert created.status_code == 201
    assert visible.json() == [dataset]
    assert readable.json() == dataset
    assert uploaded.status_code == 201
    assert version["sha256"] == hashlib.sha256(b"payload").hexdigest()
    assert version["size_bytes"] == 7
    assert listed.json() == [version]
    assert downloaded.status_code == 200
    assert downloaded.content == b"payload"
    assert downloaded.headers["content-type"] == "application/octet-stream"


async def test_duplicate_version_and_archived_dataset_are_rejected(
    client: AsyncClient,
) -> None:
    alice, workspace = await bootstrap(client)
    dataset = (
        await client.post(
            f"/api/v1/workspaces/{workspace['id']}/datasets",
            headers=identity(alice),
            json={"name": "Images", "slug": "images"},
        )
    ).json()
    upload_path = f"/api/v1/datasets/{dataset['id']}/versions"
    first = await client.post(
        upload_path,
        headers=identity(alice),
        data={"version": "v1"},
        files={"file": ("one.bin", b"one", "application/octet-stream")},
    )
    duplicate = await client.post(
        upload_path,
        headers=identity(alice),
        data={"version": "v1"},
        files={"file": ("two.bin", b"two", "application/octet-stream")},
    )
    archived = await client.post(
        f"/api/v1/datasets/{dataset['id']}/archive",
        headers=identity(alice),
    )
    after_archive = await client.post(
        upload_path,
        headers=identity(alice),
        data={"version": "v2"},
        files={"file": ("two.bin", b"two", "application/octet-stream")},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "resource_conflict"
    assert archived.status_code == 200
    assert after_archive.status_code == 409
    assert after_archive.json()["code"] == "resource_archived"
