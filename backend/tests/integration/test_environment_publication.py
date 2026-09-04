"""Observable Environment publication contract."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import grant_test_entitlement
from workspace107.api.deps import AppContext
from workspace107.application.environment_publication import EnvironmentPublicationProcessor
from workspace107.domain.ports.scheduler import (
    SchedulerJobState,
    SchedulerState,
    SchedulerSubmission,
)
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.tables import (
    EnvironmentPublicationAttemptRow,
    EnvironmentRow,
    EnvironmentVersionRow,
)
from workspace107.infrastructure.scheduler.script import render_body

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}
APPTAINER_BUILD_ARCH_LABEL = "org.label-schema.build-arch"


def _install_apptainer_inspect_double(monkeypatch, *, architecture: str) -> None:
    stdout = json.dumps(
        {
            "data": {
                "attributes": {
                    "labels": {
                        APPTAINER_BUILD_ARCH_LABEL: architecture,
                        "org.label-schema.usage.apptainer.version": "1.4.2",
                    }
                }
            },
            "type": "container",
        }
    ).encode()

    class SuccessfulInspect:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return stdout, b""

    async def create_subprocess_exec(*args, **kwargs):
        assert args[:3] == ("/usr/bin/apptainer", "inspect", "--json")
        assert await asyncio.to_thread(Path(args[3]).is_file)
        assert kwargs["stdout"] is asyncio.subprocess.PIPE
        assert kwargs["stderr"] is asyncio.subprocess.PIPE
        return SuccessfulInspect()

    monkeypatch.setattr(
        "workspace107.application.environment_publication._find_apptainer",
        lambda: "/usr/bin/apptainer",
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess_exec)


class CaptureScheduler:
    name = "capture"

    def __init__(self) -> None:
        self.submission: SchedulerSubmission | None = None

    async def submit(self, submission: SchedulerSubmission) -> str:
        self.submission = submission
        return "captured-job"

    async def poll(self, job_id: str) -> SchedulerJobState:
        return SchedulerJobState(SchedulerState.PENDING)

    async def cancel(self, job_id: str) -> None:
        return None


async def _user_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/me", headers=headers)
    response.raise_for_status()
    return str(response.json()["user"]["id"])


async def _environment(
    client: httpx.AsyncClient, session: AsyncSession, *, owner_headers: dict[str, str] = ALICE
) -> str:
    owner_id = await _user_id(client, owner_headers)
    environment_id = f"env_publication_{owner_id[-8:]}"
    session.add(
        EnvironmentRow(
            id=environment_id,
            name="Validated runtime",
            description="",
            owner_user_id=owner_id,
        )
    )
    await session.commit()
    return environment_id


async def _process(context: AppContext) -> tuple[object, list[EnvironmentVersionRow]]:
    async with context.session_factory() as session:
        repos = SqlRepositories(session)
        processor = EnvironmentPublicationProcessor(repos, context.storage, context.clock)
        claimed = await processor.claim()
        assert claimed is not None
        result = await processor.process(claimed.id)
        await session.commit()
        versions = list(
            (await session.execute(EnvironmentVersionRow.__table__.select())).mappings().all()
        )
        return result, versions


async def test_modules_publication_is_durable_canonical_and_atomic(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    environment_id = await _environment(client, session)
    response = await client.post(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts/modules",
        json={
            "version": "py-cuda",
            "description": "ordered",
            "modules": ["python3.12/3.12", "cuda/12.6"],
        },
        headers=ALICE,
    )
    assert response.status_code == 202, response.text
    attempt = response.json()
    interrupted = await session.get(EnvironmentPublicationAttemptRow, attempt["id"])
    assert interrupted is not None
    interrupted.status = "processing"
    await session.commit()

    assert attempt["status"] == "pending"

    result, versions = await _process(context)
    assert result.status.value == "succeeded"
    assert len(versions) == 1
    version = versions[0]
    assert version["definition"]["modules"] == ["python3.12/3.12", "cuda/12.6"]
    assert version["execution_spec"]["commands"] == [
        ["module", "purge"],
        ["module", "load", "python3.12/3.12"],
        ["module", "load", "cuda/12.6"],
    ]
    assert len(version["definition_hash"]) == 64

    visible = await client.get(
        f"/api/v1/catalog/environment-publication-attempts/{attempt['id']}", headers=ALICE
    )
    assert visible.json()["status"] == "succeeded"
    concealed = await client.get(
        f"/api/v1/catalog/environment-publication-attempts/{attempt['id']}", headers=BOB
    )
    assert concealed.status_code == 404
    history = await client.get(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts",
        headers=ALICE,
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [attempt["id"]]
    concealed_history = await client.get(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts",
        headers=BOB,
    )
    assert concealed_history.status_code == 404


async def test_modules_reject_unallowlisted_module_without_version(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    environment_id = await _environment(client, session)
    response = await client.post(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts/modules",
        json={"version": "bad", "modules": ["vscode/4.118.0"]},
        headers=ALICE,
    )
    assert response.status_code == 202
    result, versions = await _process(context)
    assert result.status.value == "failed"
    assert "不支持模块" in (result.failure_reason or "")
    assert versions == []


async def test_sif_hashes_exact_bytes_and_cli_absence_fails_clearly(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext, monkeypatch
) -> None:
    environment_id = await _environment(client, session)
    content = b"not-a-hand-rolled-sif"
    response = await client.post(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts/apptainer-sif",
        data={
            "version": "sif-1",
            "source_uri": "https://example.invalid/image.sif",
            "source_digest": hashlib.sha256(content).hexdigest(),
            "architecture": "x86_64",
        },
        files={"sif": ("image.sif", content, "application/octet-stream")},
        headers=ALICE,
    )
    assert response.status_code == 202, response.text
    monkeypatch.setattr(
        "workspace107.application.environment_publication._find_apptainer", lambda: None
    )
    result, versions = await _process(context)
    assert result.status.value == "failed"
    assert "未安装 Apptainer CLI" in (result.failure_reason or "")
    assert versions == []


async def test_sif_inspect_rejects_non_x86_architecture_without_version(
    client: httpx.AsyncClient,
    session: AsyncSession,
    context: AppContext,
    monkeypatch,
) -> None:
    environment_id = await _environment(client, session)
    content = b"arm-sif-inspected-by-apptainer"
    response = await client.post(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts/apptainer-sif",
        data={
            "version": "arm-sif",
            "source_uri": "https://example.invalid/arm.sif",
            "source_digest": hashlib.sha256(content).hexdigest(),
            "architecture": "x86_64",
        },
        files={"sif": ("arm.sif", content, "application/octet-stream")},
        headers=ALICE,
    )
    assert response.status_code == 202, response.text
    _install_apptainer_inspect_double(monkeypatch, architecture="arm64")

    result, versions = await _process(context)

    assert result.status.value == "failed"
    assert "SIF architecture" in (result.failure_reason or "")
    assert versions == []


async def test_validated_sif_run_resolves_real_cas_path_before_scheduler_submission(
    client: httpx.AsyncClient,
    session: AsyncSession,
    context: AppContext,
    monkeypatch,
) -> None:
    environment_id = await _environment(client, session)
    content = b"cli-validated-sif-bytes"
    _install_apptainer_inspect_double(monkeypatch, architecture="amd64")
    response = await client.post(
        f"/api/v1/catalog/environments/{environment_id}/publication-attempts/apptainer-sif",
        data={
            "version": "sif-run",
            "source_uri": "https://example.invalid/run.sif",
            "source_digest": hashlib.sha256(content).hexdigest(),
            "architecture": "x86_64",
        },
        files={"sif": ("run.sif", content, "application/octet-stream")},
        headers=ALICE,
    )
    response.raise_for_status()
    result, _ = await _process(context)
    assert result.status.value == "succeeded"
    assert result.version_id is not None

    alice_id = await _user_id(client, ALICE)
    project = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user", "id": alice_id}, "name": "SIF run"},
        headers=ALICE,
    )
    project.raise_for_status()
    project_id = project.json()["id"]
    uploaded = await client.put(
        f"/api/v1/projects/{project_id}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=ALICE,
    )
    uploaded.raise_for_status()
    saved = await client.post(
        f"/api/v1/projects/{project_id}/versions",
        json={"message": "v1"},
        headers=ALICE,
    )
    saved.raise_for_status()
    await grant_test_entitlement(session, "alice")
    configuration = await client.post(
        f"/api/v1/projects/{project_id}/run-configurations",
        json={
            "name": "SIF",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": result.version_id,
        },
        headers=ALICE,
    )
    configuration.raise_for_status()
    scheduler = CaptureScheduler()
    context.scheduler = scheduler
    run = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration.json()["id"]},
        headers=ALICE,
    )
    assert run.status_code == 201, run.text
    assert scheduler.submission is not None
    locator = scheduler.submission.environment_execution_spec["locator"]
    assert isinstance(locator, str)
    assert await asyncio.to_thread(Path(locator).is_file)
    assert Path(locator).name == hashlib.sha256(content).hexdigest()
    rendered = render_body(scheduler.submission)
    assert locator in rendered
    assert f"apptainer exec {hashlib.sha256(content).hexdigest()}" not in rendered

    before = await session.get(EnvironmentVersionRow, result.version_id)
    assert before is not None
    frozen_definition = dict(before.definition)
    frozen_evidence = dict(before.validation_evidence)
    await asyncio.to_thread(Path(locator).unlink)
    refreshed = await client.post(
        f"/api/v1/catalog/environment-versions/{result.version_id}/availability/refresh",
        headers=ALICE,
    )
    assert refreshed.status_code == 200, refreshed.text
    refreshed_body = refreshed.json()
    assert refreshed_body["availability"] == "unavailable"
    assert refreshed_body["definition"] == frozen_definition
    assert refreshed_body["validation_evidence"] == frozen_evidence
    notifications = await client.get("/api/v1/notifications", headers=ALICE)
    assert notifications.status_code == 200
    environment_notice = next(
        item
        for item in notifications.json()["items"]
        if item["type"] == "environment_unavailable" and item["target_id"] == project_id
    )
    assert environment_notice["mandatory"] is True

    preflight = await client.post(
        f"/api/v1/projects/{project_id}/runs/preflight",
        json={"run_configuration_id": configuration.json()["id"]},
        headers=ALICE,
    )
    assert preflight.status_code == 200
    assert any("当前unavailable" in problem for problem in preflight.json()["problems"])
