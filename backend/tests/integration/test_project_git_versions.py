"""Project API Git version identity and immutable content behavior."""

from __future__ import annotations

import hashlib
import re

import pytest
from sqlalchemy import select

from tests.helpers import ensure_user_group
from workspace107.domain.errors import ProjectContentIdentityMismatch
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.project_version_exporter import GitProjectVersionExporter

FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


async def test_project_api_persists_exact_git_version_and_reads_immutable_content(
    client, context, tmp_path
) -> None:
    user_group_id = await ensure_user_group(client)
    created = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user_group", "id": user_group_id}, "name": "Git Project"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "main.py", "content": "print('v1')\n"},
    )
    saved = await client.post(f"/api/v1/projects/{project_id}/versions", json={"message": "first"})
    assert saved.status_code == 201, saved.text
    version = saved.json()

    async with context.session_factory() as session:
        row = (
            await session.execute(
                select(t.ProjectVersionRow).where(t.ProjectVersionRow.id == version["id"])
            )
        ).scalar_one()
        assert FULL_OID.fullmatch(row.commit_oid)
        assert FULL_OID.fullmatch(row.tree_oid)
        assert row.repository_identity
        assert row.file_count == 1
        assert row.total_size == len(b"print('v1')\n")
        commit_oid = row.commit_oid
        tree_oid = row.tree_oid

    export = tmp_path / "export"
    export.mkdir()
    evidence = await GitProjectVersionExporter(
        context.session_factory, context.project_content
    ).export(
        project_version_id=version["id"],
        expected_commit_oid=commit_oid,
        target=export,
    )
    assert evidence.commit_oid == commit_oid
    assert evidence.tree_oid == tree_oid
    assert (export / "main.py").read_bytes() == b"print('v1')\n"

    await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "main.py", "content": "print('v2')\n"},
    )
    detail = (await client.get(f"/api/v1/versions/{version['id']}")).json()
    assert detail["files"] == [
        {
            "path": "main.py",
            "size": len(b"print('v1')\n"),
            "content_hash": hashlib.sha256(b"print('v1')\n").hexdigest(),
        }
    ]
    assert "commit_oid" not in detail
    content = await client.get(
        f"/api/v1/versions/{version['id']}/files/content", params={"path": "main.py"}
    )
    assert content.status_code == 200
    assert content.json()["content"] == "print('v1')\n"

    async with context.session_factory() as session:
        persisted = await session.get(t.ProjectVersionRow, version["id"])
        assert persisted is not None
        persisted.tree_oid = "f" * 40
        await session.commit()
    rejected = tmp_path / "rejected"
    rejected.mkdir()
    with pytest.raises(ProjectContentIdentityMismatch, match="持久化 evidence"):
        await GitProjectVersionExporter(context.session_factory, context.project_content).export(
            project_version_id=version["id"],
            expected_commit_oid=commit_oid,
            target=rejected,
        )
    assert list(rejected.iterdir()) == []
