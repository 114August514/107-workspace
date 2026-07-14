import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest

from workspace107.application.runs import RunDatasetSelection, RunService
from workspace107.domain.enums import RunStatus, WorkspaceKind, WorkspaceRole
from workspace107.domain.errors import ResourceArchived
from workspace107.domain.models import (
    CollectedArtifact,
    Dataset,
    DatasetVersion,
    FileSignature,
    JobObservation,
    LogChunk,
    NewRun,
    NewRunEvent,
    PreflightCheck,
    Project,
    ProjectSync,
    ResourceSpec,
    Run,
    RunDataset,
    RunEvent,
    RunSubmission,
    RunTemplate,
    SubmittedJob,
    Workspace,
    WorkspaceMember,
)
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.repositories import UnitOfWorkFactory

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(slots=True)
class FakeState:
    workspaces: dict[UUID, Workspace] = field(default_factory=dict[UUID, Workspace])
    members: dict[tuple[UUID, UUID], WorkspaceMember] = field(
        default_factory=dict[tuple[UUID, UUID], WorkspaceMember]
    )
    projects: dict[UUID, Project] = field(default_factory=dict[UUID, Project])
    datasets: dict[UUID, Dataset] = field(default_factory=dict[UUID, Dataset])
    versions: dict[UUID, DatasetVersion] = field(default_factory=dict[UUID, DatasetVersion])
    templates: dict[UUID, RunTemplate] = field(default_factory=dict[UUID, RunTemplate])
    syncs: dict[UUID, ProjectSync] = field(default_factory=dict[UUID, ProjectSync])
    runs: dict[UUID, Run] = field(default_factory=dict[UUID, Run])
    run_datasets: dict[UUID, tuple[RunDataset, ...]] = field(
        default_factory=dict[UUID, tuple[RunDataset, ...]]
    )
    events: list[RunEvent] = field(default_factory=list[RunEvent])
    active_uows: int = 0
    commits: int = 0


class FakeWorkspaceRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get(self, workspace_id: UUID) -> Workspace | None:
        return self._state.workspaces.get(workspace_id)


class FakeMemberRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        return self._state.members.get((workspace_id, user_id))


class FakeProjectRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get(self, project_id: UUID) -> Project | None:
        return self._state.projects.get(project_id)


class FakeDatasetRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get(self, dataset_id: UUID) -> Dataset | None:
        return self._state.datasets.get(dataset_id)

    async def get_version(self, version_id: UUID) -> DatasetVersion | None:
        return self._state.versions.get(version_id)


class FakeTemplateRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get(self, template_id: UUID) -> RunTemplate | None:
        return self._state.templates.get(template_id)


class FakeProjectSyncRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def get_latest(self, project_id: UUID, transport: str) -> ProjectSync | None:
        sync = self._state.syncs.get(project_id)
        return sync if sync is not None and sync.transport == transport else None


class FakeRunRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def add(self, new: NewRun, datasets: tuple[RunDataset, ...] = ()) -> Run:
        run = Run(
            id=new.id,
            workspace_id=new.workspace_id,
            project_id=new.project_id,
            template_id=new.template_id,
            submitted_by=new.submitted_by,
            status=new.status,
            external_job_id=None,
            submission_snapshot=new.submission_snapshot,
            exit_code=None,
            failure_code=None,
            failure_message=None,
            submitted_at=None,
            started_at=None,
            finished_at=None,
            created_at=new.created_at,
            updated_at=new.updated_at,
        )
        self._state.runs[run.id] = run
        self._state.run_datasets[run.id] = datasets
        return run

    async def get(self, run_id: UUID) -> Run | None:
        return self._state.runs.get(run_id)

    async def compare_and_set_status(self, expected: RunStatus, replacement: Run) -> bool:
        current = self._state.runs.get(replacement.id)
        if current is None or current.status is not expected:
            return False
        self._state.runs[replacement.id] = replacement
        return True


class FakeRunEventRepository:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    async def add(self, new: NewRunEvent) -> RunEvent:
        event = RunEvent(
            id=new.id,
            run_id=new.run_id,
            event_type=new.event_type,
            from_status=new.from_status,
            to_status=new.to_status,
            message=new.message,
            details=new.details,
            created_at=new.created_at,
        )
        self._state.events.append(event)
        return event


class FakeUnitOfWork:
    workspaces: FakeWorkspaceRepository
    members: FakeMemberRepository
    projects: FakeProjectRepository
    datasets: FakeDatasetRepository
    templates: FakeTemplateRepository
    syncs: FakeProjectSyncRepository
    runs: FakeRunRepository
    events: FakeRunEventRepository

    def __init__(self, state: FakeState) -> None:
        self._state = state
        self.workspaces = FakeWorkspaceRepository(state)
        self.members = FakeMemberRepository(state)
        self.projects = FakeProjectRepository(state)
        self.datasets = FakeDatasetRepository(state)
        self.templates = FakeTemplateRepository(state)
        self.syncs = FakeProjectSyncRepository(state)
        self.runs = FakeRunRepository(state)
        self.events = FakeRunEventRepository(state)

    async def __aenter__(self) -> "FakeUnitOfWork":
        self._state.active_uows += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self._state.active_uows -= 1

    async def commit(self) -> None:
        self._state.commits += 1


class FakeUnitOfWorkFactory:
    def __init__(self, state: FakeState) -> None:
        self._state = state

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self._state)


class FakeCluster:
    def __init__(self, state: FakeState) -> None:
        self._state = state
        self.preflight_checks = (
            PreflightCheck(code="adapter_ready", passed=True, message="Adapter is ready."),
        )
        self.preflight_calls: list[RunSubmission] = []
        self.submit_calls: list[RunSubmission] = []
        self.cancel_calls: list[str] = []
        self.submit_error: Exception | None = None
        self.on_preflight: Callable[[RunSubmission], Awaitable[None]] | None = None
        self.on_submit: Callable[[RunSubmission], Awaitable[None]] | None = None

    def _assert_outside_uow(self) -> None:
        assert self._state.active_uows == 0

    async def preflight(self, spec: RunSubmission) -> tuple[PreflightCheck, ...]:
        self._assert_outside_uow()
        self.preflight_calls.append(spec)
        if self.on_preflight is not None:
            await self.on_preflight(spec)
        return self.preflight_checks

    async def submit(self, spec: RunSubmission) -> SubmittedJob:
        self._assert_outside_uow()
        assert any(run.status is RunStatus.SUBMITTING for run in self._state.runs.values())
        self.submit_calls.append(spec)
        if self.on_submit is not None:
            await self.on_submit(spec)
        if self.submit_error is not None:
            raise self.submit_error
        return SubmittedJob(external_job_id="external-1", submitted_at=NOW)

    async def status(self, external_job_id: str) -> JobObservation:
        raise AssertionError(f"unexpected status call for {external_job_id}")

    async def cancel(self, external_job_id: str) -> None:
        self._assert_outside_uow()
        self.cancel_calls.append(external_job_id)

    async def read_log(self, external_job_id: str, offset: int) -> LogChunk:
        raise AssertionError(f"unexpected log call for {external_job_id} at {offset}")

    async def collect_artifacts(self, external_job_id: str) -> tuple[CollectedArtifact, ...]:
        raise AssertionError(f"unexpected artifact collection for {external_job_id}")

    def open_artifact(self, external_job_id: str, artifact_key: str) -> AsyncIterator[bytes]:
        async def empty() -> AsyncIterator[bytes]:
            if False:
                yield f"{external_job_id}:{artifact_key}".encode()

        return empty()


@dataclass(frozen=True, slots=True)
class Seeded:
    state: FakeState
    actor_id: UUID
    workspace_id: UUID
    project_id: UUID
    template_id: UUID
    version_ids: tuple[UUID, UUID]


def seed() -> Seeded:
    state = FakeState()
    actor_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    template_id = uuid4()
    dataset_ids = (uuid4(), uuid4())
    version_ids = (uuid4(), uuid4())
    state.workspaces[workspace_id] = Workspace(
        id=workspace_id,
        kind=WorkspaceKind.COURSE,
        name="AI 101",
        slug="ai-101",
        description="",
        parent_id=None,
        created_by=actor_id,
        created_at=NOW,
    )
    state.members[(workspace_id, actor_id)] = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.MEMBER,
        joined_at=NOW,
    )
    state.projects[project_id] = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Demo",
        slug="demo",
        description="",
        storage_key=f"projects/{project_id}",
        created_by=actor_id,
        created_at=NOW,
    )
    state.templates[template_id] = RunTemplate(
        id=template_id,
        workspace_id=workspace_id,
        name="Train",
        description="",
        entrypoint="train.py",
        environment_spec={"kind": "uv", "options": {"lock": "original"}},
        resource_spec=ResourceSpec(
            cpus=4,
            memory_mb=4096,
            gpus=1,
            walltime_seconds=3600,
        ),
        output_spec=("z-last.json", "a-first.json"),
        created_by=actor_id,
        created_at=NOW,
        updated_at=NOW,
    )
    for index, (dataset_id, version_id) in enumerate(zip(dataset_ids, version_ids, strict=True)):
        state.datasets[dataset_id] = Dataset(
            id=dataset_id,
            workspace_id=workspace_id,
            name=f"Dataset {index}",
            slug=f"dataset-{index}",
            description="",
            created_by=actor_id,
            created_at=NOW,
        )
        state.versions[version_id] = DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            version="v1",
            storage_key=f"sha256/{index:02x}/" + f"{index:064x}",
            size_bytes=7,
            sha256=f"{index:064x}",
            created_by=actor_id,
            created_at=NOW,
        )
    state.syncs[project_id] = ProjectSync(
        id=uuid4(),
        project_id=project_id,
        transport="local",
        target_uri="file:///cluster/projects/demo",
        manifest={"train.py": FileSignature(path="train.py", size_bytes=10, mtime_ns=1)},
        last_synced_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    return Seeded(
        state=state,
        actor_id=actor_id,
        workspace_id=workspace_id,
        project_id=project_id,
        template_id=template_id,
        version_ids=version_ids,
    )


def selections(seeded: Seeded) -> tuple[RunDatasetSelection, ...]:
    return (
        RunDatasetSelection(
            dataset_version_id=seeded.version_ids[1],
            mount_path="z-data",
        ),
        RunDatasetSelection(
            dataset_version_id=seeded.version_ids[0],
            mount_path="a-data",
        ),
    )


def service_for(seeded: Seeded, cluster: FakeCluster) -> RunService:
    factory = cast(UnitOfWorkFactory, FakeUnitOfWorkFactory(seeded.state))
    return RunService(
        factory,
        cast(ClusterPort, cluster),
        project_transport="local",
        clock=lambda: NOW,
    )


async def test_preflight_aggregates_checks_without_persisting() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    service = service_for(seeded, cluster)

    checks = await service.preflight(
        actor_id=seeded.actor_id,
        project_id=seeded.project_id,
        template_id=seeded.template_id,
        datasets=selections(seeded),
    )

    assert "project_active" in {check.code for check in checks}
    assert "project_synced" in {check.code for check in checks}
    assert checks[-1] == cluster.preflight_checks[0]
    assert all(check.passed for check in checks)
    assert seeded.state.runs == {}
    assert seeded.state.events == []
    assert seeded.state.commits == 0
    assert len(cluster.preflight_calls) == 1


async def test_submit_freezes_snapshot_before_adapter_and_transitions_to_queued() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    service = service_for(seeded, cluster)

    async def mutate_source_after_persistence(_: RunSubmission) -> None:
        environment = seeded.state.templates[seeded.template_id].environment_spec
        options = cast(dict[str, object], environment["options"])
        options["lock"] = "mutated"

    cluster.on_submit = mutate_source_after_persistence
    run = await service.submit(
        actor_id=seeded.actor_id,
        project_id=seeded.project_id,
        template_id=seeded.template_id,
        datasets=selections(seeded),
    )

    snapshot = dict(run.submission_snapshot)
    assert run.status is RunStatus.QUEUED
    assert run.external_job_id == "external-1"
    assert run.submitted_at == NOW
    assert json.loads(json.dumps(snapshot)) == snapshot
    assert snapshot["outputs"] == ["a-first.json", "z-last.json"]
    assert [mount["mount_path"] for mount in cast(list[dict[str, object]], snapshot["mounts"])] == [
        "a-data",
        "z-data",
    ]
    environment = cast(dict[str, object], snapshot["environment"])
    assert cast(dict[str, object], environment["options"])["lock"] == "original"
    assert [event.to_status for event in seeded.state.events] == [
        RunStatus.SUBMITTING,
        RunStatus.QUEUED,
    ]
    assert len(cluster.preflight_calls) == 1
    assert len(cluster.submit_calls) == 1


async def test_submit_failure_persists_sanitized_stable_failure() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    cluster.submit_error = RuntimeError("secret token at /home/alice/.ssh/id_ed25519")
    service = service_for(seeded, cluster)

    run = await service.submit(
        actor_id=seeded.actor_id,
        project_id=seeded.project_id,
        template_id=seeded.template_id,
        datasets=selections(seeded),
    )

    assert run.status is RunStatus.FAILED
    assert run.failure_code == "cluster_unavailable"
    assert run.failure_message == "Cluster submission failed."
    serialized_events = json.dumps(
        [dict(event.details) | {"message": event.message} for event in seeded.state.events]
    )
    assert "secret" not in serialized_events
    assert "/home/alice" not in serialized_events


async def test_submit_rechecks_archived_references_after_adapter_preflight() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    service = service_for(seeded, cluster)

    async def archive_project(_: RunSubmission) -> None:
        project = seeded.state.projects[seeded.project_id]
        seeded.state.projects[seeded.project_id] = replace(project, archived_at=NOW)

    cluster.on_preflight = archive_project

    with pytest.raises(ResourceArchived):
        await service.submit(
            actor_id=seeded.actor_id,
            project_id=seeded.project_id,
            template_id=seeded.template_id,
            datasets=selections(seeded),
        )

    assert seeded.state.runs == {}
    assert cluster.submit_calls == []


async def test_cancel_is_idempotent_and_terminal_run_does_not_call_adapter() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    service = service_for(seeded, cluster)
    run = await service.submit(
        actor_id=seeded.actor_id,
        project_id=seeded.project_id,
        template_id=seeded.template_id,
        datasets=(),
    )

    first = await service.cancel(actor_id=seeded.actor_id, run_id=run.id)
    second = await service.cancel(actor_id=seeded.actor_id, run_id=run.id)
    seeded.state.runs[run.id] = replace(second, status=RunStatus.CANCELLED, finished_at=NOW)
    terminal = await service.cancel(actor_id=seeded.actor_id, run_id=run.id)

    assert first.status is RunStatus.CANCELLING
    assert second.status is RunStatus.CANCELLING
    assert terminal.status is RunStatus.CANCELLED
    assert cluster.cancel_calls == ["external-1", "external-1"]
    assert sum(event.to_status is RunStatus.CANCELLING for event in seeded.state.events) == 1


async def test_cancel_during_submission_cancels_late_external_job() -> None:
    seeded = seed()
    cluster = FakeCluster(seeded.state)
    service = service_for(seeded, cluster)

    async def cancel_while_submitting(_: RunSubmission) -> None:
        run_id = next(iter(seeded.state.runs))
        await service.cancel(actor_id=seeded.actor_id, run_id=run_id)

    cluster.on_submit = cancel_while_submitting
    run = await service.submit(
        actor_id=seeded.actor_id,
        project_id=seeded.project_id,
        template_id=seeded.template_id,
        datasets=(),
    )

    assert run.status is RunStatus.CANCELLING
    assert run.external_job_id == "external-1"
    assert cluster.cancel_calls == ["external-1"]
    assert all(event.to_status is not RunStatus.QUEUED for event in seeded.state.events)
    assert any(event.event_type == "external_job_attached" for event in seeded.state.events)
