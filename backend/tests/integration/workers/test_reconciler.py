from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workspace107.domain.enums import ArtifactKind, RunStatus, WorkspaceKind, WorkspaceRole
from workspace107.domain.errors import ClusterUnavailable
from workspace107.domain.models import (
    CollectedArtifact,
    JobObservation,
    LogChunk,
    NewProject,
    NewRun,
    NewRunTemplate,
    NewUser,
    NewWorkspace,
    NewWorkspaceMember,
    PreflightCheck,
    ResourceSpec,
    Run,
    RunSubmission,
    SubmittedJob,
)
from workspace107.infrastructure.db.base import Base
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.workers.reconciler import RunReconciler

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


class ScriptedCluster:
    def __init__(self) -> None:
        self.observations = {
            "queued": JobObservation(
                status=RunStatus.RUNNING,
                observed_at=NOW + timedelta(seconds=1),
                details={"node": "mock-1"},
            ),
            "success": JobObservation(
                status=RunStatus.SUCCEEDED,
                observed_at=NOW + timedelta(seconds=2),
                exit_code=0,
            ),
            "cancel": JobObservation(
                status=RunStatus.CANCELLED,
                observed_at=NOW + timedelta(seconds=3),
                exit_code=130,
            ),
        }
        self.cancel_calls: list[str] = []
        self.collection_calls: list[str] = []

    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]:
        raise AssertionError(f"unexpected preflight for {spec.entrypoint}")

    async def submit(self, spec: RunSubmission) -> SubmittedJob:
        raise AssertionError(f"unexpected submit for {spec.entrypoint}")

    async def status(self, external_job_id: str) -> JobObservation:
        if external_job_id == "unavailable":
            raise ClusterUnavailable("private scheduler details")
        return self.observations[external_job_id]

    async def cancel(self, external_job_id: str) -> None:
        self.cancel_calls.append(external_job_id)

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk:
        raise AssertionError(f"unexpected log for {external_job_id} at {offset}")

    async def collect_artifacts(self, external_job_id: str) -> tuple[CollectedArtifact, ...]:
        self.collection_calls.append(external_job_id)
        return (
            CollectedArtifact(
                artifact_key=f"{external_job_id}-result",
                name="result.json",
                kind=ArtifactKind.RESULT,
                media_type="application/json",
            ),
        )

    def open_artifact(self, external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            yield f'{{"job":"{external_job_id}","key":"{artifact_key}"}}'.encode()

        return stream()


class PersistenceFailureReconciler(RunReconciler):
    async def _reconcile_run(self, run_id: UUID) -> None:
        raise RuntimeError(f"database write failed for {run_id}")


async def add_run(
    uow: SqlAlchemyUnitOfWork,
    *,
    status: RunStatus,
    external_job_id: str,
    workspace_id: UUID,
    project_id: UUID,
    template_id: UUID,
    user_id: UUID,
    created_at: datetime,
) -> Run:
    run = await uow.runs.add(
        NewRun(
            workspace_id=workspace_id,
            project_id=project_id,
            template_id=template_id,
            submitted_by=user_id,
            submission_snapshot={"entrypoint": "train.py"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    replacement = replace(
        run,
        status=status,
        external_job_id=external_job_id,
        submitted_at=created_at,
        started_at=created_at if status is RunStatus.RUNNING else None,
        updated_at=created_at,
    )
    assert await uow.runs.compare_and_set_status(RunStatus.SUBMITTING, replacement)
    return replacement


async def seed_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Run]:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user = await uow.users.add(NewUser(username="runner", display_name="Runner"))
        workspace = await uow.workspaces.add(
            NewWorkspace(
                kind=WorkspaceKind.COURSE,
                name="AI 101",
                slug="worker-ai-101",
                created_by=user.id,
            )
        )
        await uow.members.add(
            NewWorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceRole.OWNER,
            )
        )
        project = await uow.projects.add(
            NewProject(
                workspace_id=workspace.id,
                name="Demo",
                slug="worker-demo",
                storage_key=f"projects/{uuid4()}",
                created_by=user.id,
            )
        )
        template = await uow.templates.add(
            NewRunTemplate(
                workspace_id=workspace.id,
                name="Train",
                entrypoint="train.py",
                environment_spec={"kind": "system"},
                resource_spec=ResourceSpec(
                    cpus=1,
                    memory_mb=1024,
                    gpus=0,
                    walltime_seconds=60,
                ),
                output_spec=("result.json",),
                created_by=user.id,
            )
        )
        runs = {
            "unavailable": await add_run(
                uow,
                status=RunStatus.QUEUED,
                external_job_id="unavailable",
                workspace_id=workspace.id,
                project_id=project.id,
                template_id=template.id,
                user_id=user.id,
                created_at=NOW,
            ),
            "queued": await add_run(
                uow,
                status=RunStatus.QUEUED,
                external_job_id="queued",
                workspace_id=workspace.id,
                project_id=project.id,
                template_id=template.id,
                user_id=user.id,
                created_at=NOW + timedelta(milliseconds=1),
            ),
            "success": await add_run(
                uow,
                status=RunStatus.RUNNING,
                external_job_id="success",
                workspace_id=workspace.id,
                project_id=project.id,
                template_id=template.id,
                user_id=user.id,
                created_at=NOW + timedelta(milliseconds=2),
            ),
            "cancel": await add_run(
                uow,
                status=RunStatus.CANCELLING,
                external_job_id="cancel",
                workspace_id=workspace.id,
                project_id=project.id,
                template_id=template.id,
                user_id=user.id,
                created_at=NOW + timedelta(milliseconds=3),
            ),
        }
        await uow.commit()
        return runs


async def test_reconciler_isolates_errors_transitions_and_collects_once(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    seeded = await seed_runs(session_factory)
    cluster = ScriptedCluster()
    reconciler = RunReconciler(
        lambda: SqlAlchemyUnitOfWork(session_factory),
        cluster,
        LocalStorage(tmp_path / "storage"),
    )

    await reconciler.reconcile_once()
    await reconciler.reconcile_once()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        unavailable = await uow.runs.get(seeded["unavailable"].id)
        queued = await uow.runs.get(seeded["queued"].id)
        success = await uow.runs.get(seeded["success"].id)
        cancelled = await uow.runs.get(seeded["cancel"].id)
        unavailable_events = await uow.events.list_for_run(seeded["unavailable"].id)
        queued_events = await uow.events.list_for_run(seeded["queued"].id)
        success_events = await uow.events.list_for_run(seeded["success"].id)
        cancel_events = await uow.events.list_for_run(seeded["cancel"].id)
        artifacts = await uow.artifacts.list_for_run(seeded["success"].id)

    assert unavailable is not None and unavailable.status is RunStatus.QUEUED
    assert queued is not None and queued.status is RunStatus.RUNNING
    assert queued.started_at == NOW + timedelta(seconds=1)
    assert success is not None and success.status is RunStatus.SUCCEEDED
    assert success.exit_code == 0
    assert success.finished_at == NOW + timedelta(seconds=2)
    assert cancelled is not None and cancelled.status is RunStatus.CANCELLED
    assert cancelled.finished_at == NOW + timedelta(seconds=3)
    assert all(event.event_type == "adapter_error" for event in unavailable_events)
    assert all(dict(event.details)["code"] == "cluster_unavailable" for event in unavailable_events)
    assert all("private" not in (event.message or "") for event in unavailable_events)
    assert [event.to_status for event in queued_events] == [RunStatus.RUNNING]
    assert [event.to_status for event in success_events] == [RunStatus.SUCCEEDED]
    assert [event.to_status for event in cancel_events] == [RunStatus.CANCELLED]
    assert len(artifacts) == 1
    assert artifacts[0].sha256
    assert cluster.collection_calls.count("success") == 1
    assert cluster.cancel_calls == ["cancel"]


async def test_reconciler_does_not_misclassify_persistence_errors(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await seed_runs(session_factory)
    reconciler = PersistenceFailureReconciler(
        lambda: SqlAlchemyUnitOfWork(session_factory),
        ScriptedCluster(),
        LocalStorage(tmp_path / "storage"),
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        await reconciler.reconcile_once()
