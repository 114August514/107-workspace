from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.main import create_app


@pytest.fixture
async def transfer_client(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, dict[str, Path]]]:
    roots = {
        "source": tmp_path / "source",
        "cluster": tmp_path / "cluster",
        "downloads": tmp_path / "downloads",
    }
    for root in roots.values():
        root.mkdir()
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    app = create_app(
        uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        storage=LocalStorage(tmp_path / "storage"),
        transfer=LocalProjectTransfer(tuple(roots.values())),
        transfer_roots=roots,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, roots

    await engine.dispose()


def identity(user: dict[str, object]) -> dict[str, str]:
    return {"X-User-Id": str(user["id"])}


async def bootstrap(client: AsyncClient) -> tuple[dict[str, object], dict[str, object]]:
    user = (
        await client.post(
            "/api/v1/users",
            json={"username": "alice", "display_name": "Alice"},
        )
    ).json()
    workspace = (
        await client.post(
            "/api/v1/workspaces",
            headers=identity(user),
            json={"kind": "course", "name": "AI 101", "slug": "ai-101"},
        )
    ).json()
    project_response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        headers=identity(user),
        json={"name": "Demo", "slug": "demo"},
    )
    assert project_response.status_code == 201
    return user, project_response.json()


async def test_project_scan_incremental_push_and_pull(
    transfer_client: tuple[AsyncClient, dict[str, Path]],
) -> None:
    client, roots = transfer_client
    alice, project = await bootstrap(client)
    project_id = str(project["id"])
    source = roots["source"] / project_id
    source.mkdir()
    (source / ".hpcignore").write_text("data/\n", encoding="utf-8")
    (source / "train.py").write_text("print('one')\n", encoding="utf-8")
    (source / "old.py").write_text("old\n", encoding="utf-8")
    (source / "data").mkdir()
    (source / "data" / "private.bin").write_bytes(b"private")

    scan = await client.post(
        f"/api/v1/projects/{project_id}/scan",
        headers=identity(alice),
        json={"source_root": "source"},
    )
    first_push = await client.post(
        f"/api/v1/projects/{project_id}/push",
        headers=identity(alice),
        json={"source_root": "source", "target_root": "cluster"},
    )
    cluster = roots["cluster"] / project_id

    assert scan.status_code == 200
    assert [item["path"] for item in scan.json()["files"]] == [
        ".hpcignore",
        "old.py",
        "train.py",
    ]
    assert first_push.status_code == 200
    assert first_push.json()["transferred"] == [".hpcignore", "old.py", "train.py"]
    assert not (cluster / "data" / "private.bin").exists()

    (source / "train.py").write_text("print('two and changed')\n", encoding="utf-8")
    (source / "old.py").unlink()
    second_push = await client.post(
        f"/api/v1/projects/{project_id}/push",
        headers=identity(alice),
        json={"source_root": "source", "target_root": "cluster"},
    )

    assert second_push.status_code == 200
    assert second_push.json()["transferred"] == ["train.py"]
    assert second_push.json()["removed"] == ["old.py"]
    assert (cluster / "old.py").exists()

    (cluster / "results").mkdir()
    (cluster / "results" / "metrics.json").write_text("{}\n", encoding="utf-8")
    pull = await client.post(
        f"/api/v1/projects/{project_id}/pull",
        headers=identity(alice),
        json={
            "source_root": "cluster",
            "target_root": "downloads",
            "include": ["results/metrics.json"],
        },
    )

    assert pull.status_code == 200
    assert pull.json()["transferred"] == ["results/metrics.json"]
    assert (roots["downloads"] / project_id / "results" / "metrics.json").exists()


async def test_project_transfer_rejects_unconfigured_or_absolute_root(
    transfer_client: tuple[AsyncClient, dict[str, Path]],
) -> None:
    client, roots = transfer_client
    alice, project = await bootstrap(client)
    path = f"/api/v1/projects/{project['id']}/scan"

    unknown = await client.post(
        path,
        headers=identity(alice),
        json={"source_root": "unknown"},
    )
    absolute = await client.post(
        path,
        headers=identity(alice),
        json={"source_root": "/tmp"},
    )
    missing_source = await client.post(
        path,
        headers=identity(alice),
        json={"source_root": "source"},
    )
    unsafe_include = await client.post(
        f"/api/v1/projects/{project['id']}/pull",
        headers=identity(alice),
        json={
            "source_root": "cluster",
            "target_root": "downloads",
            "include": ["../secret"],
        },
    )

    assert unknown.status_code == 404
    assert absolute.status_code == 422
    assert missing_source.status_code == 404
    assert str(roots["source"].parent) not in missing_source.text
    assert unsafe_include.status_code == 422


async def test_project_scan_redacts_server_paths_from_boundary_error(
    transfer_client: tuple[AsyncClient, dict[str, Path]],
) -> None:
    client, roots = transfer_client
    alice, project = await bootstrap(client)
    source = roots["source"] / str(project["id"])
    source.mkdir()
    secret = roots["source"].parent / "secret.txt"
    secret.write_text("secret\n", encoding="utf-8")
    (source / "escape.txt").symlink_to(secret)

    response = await client.post(
        f"/api/v1/projects/{project['id']}/scan",
        headers=identity(alice),
        json={"source_root": "source"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "path_outside_allowed_root"
    assert str(roots["source"].parent) not in response.text
