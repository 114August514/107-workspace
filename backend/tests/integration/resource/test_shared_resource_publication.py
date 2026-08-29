"""Durable asynchronous Shared Resource publication behavior (Issue #46)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from tests.helpers import ensure_user_group
from workspace107.api.deps import AppContext, build_services

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _create_resource(client: httpx.AsyncClient) -> dict:
    owner_id = await ensure_user_group(client, headers=ALICE)
    response = await client.post(
        "/api/v1/shared-resources",
        json={"name": "异步数据集", "owner": {"kind": "user_group", "id": owner_id}},
        headers=ALICE,
    )
    assert response.status_code == 201
    return response.json()


async def _upload(client: httpx.AsyncClient, resource_id: str, content: bytes = b"payload") -> dict:
    response = await client.post(
        f"/api/v1/shared-resources/{resource_id}/versions",
        data={"description": "candidate"},
        files={"files": ("data.txt", content, "text/plain")},
        headers=ALICE,
    )
    assert response.status_code == 202
    return response.json()


async def _process_once(context: AppContext) -> None:
    claim_session = context.session_factory()
    try:
        services = build_services(context, claim_session)
        attempt = await services.shared_resource_publications.claim_next()
        await claim_session.commit()
    finally:
        await claim_session.close()
    assert attempt is not None

    process_session = context.session_factory()
    try:
        services = build_services(context, process_session)
        await services.shared_resource_publications.process(attempt.id)
        await process_session.commit()
    finally:
        await process_session.close()


async def test_upload_creates_pending_attempt_without_version(
    client: httpx.AsyncClient,
) -> None:
    resource = await _create_resource(client)
    attempt = await _upload(client, resource["id"])

    assert attempt["id"].startswith("shrpa_")
    assert attempt["shared_resource_id"] == resource["id"]
    assert attempt["status"] == "pending"
    assert attempt["version_id"] is None
    assert attempt["failure_reason"] is None

    detail = (await client.get(f"/api/v1/shared-resources/{resource['id']}", headers=ALICE)).json()
    assert detail["versions"] == []


async def test_attempt_read_is_owner_scoped(client: httpx.AsyncClient) -> None:
    resource = await _create_resource(client)
    attempt = await _upload(client, resource["id"])

    own = await client.get(
        f"/api/v1/shared-resource-publication-attempts/{attempt['id']}", headers=ALICE
    )
    concealed = await client.get(
        f"/api/v1/shared-resource-publication-attempts/{attempt['id']}", headers=BOB
    )
    assert own.status_code == 200
    assert concealed.status_code == 404


async def test_processing_validates_and_publishes_exactly_one_version(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client)
    attempt = await _upload(client, resource["id"])

    await _process_once(context)
    result = (
        await client.get(
            f"/api/v1/shared-resource-publication-attempts/{attempt['id']}", headers=ALICE
        )
    ).json()
    assert result["status"] == "succeeded"
    assert result["version_id"].startswith("shrv_")
    assert result["failure_reason"] is None
    assert "1" in result["validation_summary"]

    version = (
        await client.get(f"/api/v1/shared-resource-versions/{result['version_id']}", headers=ALICE)
    ).json()
    assert version["manifest_hash"]
    assert version["validation_summary"] == result["validation_summary"]
    assert version["files"][0]["content_hash"] == hashlib.sha256(b"payload").hexdigest()

    # Processing a terminal attempt again is idempotent and cannot publish another version.
    session = context.session_factory()
    try:
        services = build_services(context, session)
        repeated = await services.shared_resource_publications.process(attempt["id"])
        await session.commit()
    finally:
        await session.close()
    assert repeated.version_id == result["version_id"]
    detail = (await client.get(f"/api/v1/shared-resources/{resource['id']}", headers=ALICE)).json()
    assert [item["id"] for item in detail["versions"]] == [result["version_id"]]


async def test_processing_failure_is_durable_and_publishes_no_version(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    resource = await _create_resource(client)
    attempt = await _upload(client, resource["id"], b"will disappear")
    digest = hashlib.sha256(b"will disappear").hexdigest()
    blob = Path(context.settings.storage_root) / "blobs" / digest[:2] / digest
    blob.unlink()

    await _process_once(context)
    result = (
        await client.get(
            f"/api/v1/shared-resource-publication-attempts/{attempt['id']}", headers=ALICE
        )
    ).json()
    assert result["status"] == "failed"
    assert "data.txt" in result["failure_reason"]
    assert "不存在" in result["failure_reason"]
    assert result["version_id"] is None
    detail = (await client.get(f"/api/v1/shared-resources/{resource['id']}", headers=ALICE)).json()
    assert detail["versions"] == []


async def test_interrupted_claim_is_recoverable_without_duplicate_version(
    client: httpx.AsyncClient, context: AppContext
) -> None:
    context.settings.shared_resource_publication_recovery_seconds = 0
    resource = await _create_resource(client)
    attempt = await _upload(client, resource["id"])

    interrupted_session = context.session_factory()
    try:
        services = build_services(context, interrupted_session)
        interrupted = await services.shared_resource_publications.claim_next()
        await interrupted_session.commit()
    finally:
        await interrupted_session.close()
    assert interrupted is not None
    assert interrupted.status.value == "processing"

    await _process_once(context)
    result = (
        await client.get(
            f"/api/v1/shared-resource-publication-attempts/{attempt['id']}", headers=ALICE
        )
    ).json()
    assert result["status"] == "succeeded"
    detail = (await client.get(f"/api/v1/shared-resources/{resource['id']}", headers=ALICE)).json()
    assert len(detail["versions"]) == 1
