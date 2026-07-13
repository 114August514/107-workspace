import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import cast
from uuid import UUID

from workspace107.application.access import require_workspace_access
from workspace107.application.preflight import PreflightDataset, PreflightInput, check_preflight
from workspace107.domain.enums import RunStatus, WorkspaceRole
from workspace107.domain.errors import (
    DomainError,
    PreflightFailed,
    ResourceArchived,
    ResourceConflict,
    ResourceNotFound,
)
from workspace107.domain.models import (
    DatasetMount,
    NewRun,
    NewRunEvent,
    PreflightCheck,
    Project,
    ResourceSpec,
    Run,
    RunDataset,
    RunSubmission,
    RunTemplate,
    utc_now,
)
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.repositories import UnitOfWork, UnitOfWorkFactory
from workspace107.domain.state_machine import transition

_TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
_CAS_ATTEMPTS = 4


@dataclass(frozen=True, slots=True)
class RunDatasetSelection:
    dataset_version_id: UUID
    mount_path: str


@dataclass(frozen=True, slots=True)
class _ResolvedDataset:
    dataset_version_id: UUID
    source_uri: str
    mount_path: str
    archived: bool


@dataclass(frozen=True, slots=True)
class _PreparedRun:
    workspace_id: UUID
    project_id: UUID
    template_id: UUID
    checks: tuple[PreflightCheck, ...]
    submission: RunSubmission | None
    snapshot: Mapping[str, object] | None
    datasets: tuple[_ResolvedDataset, ...]


def _json_object(value: Mapping[str, object]) -> dict[str, object]:
    decoded: object = json.loads(json.dumps(dict(value), sort_keys=True, separators=(",", ":")))
    if not isinstance(decoded, dict):
        raise ValueError("expected a JSON object")
    return cast(dict[str, object], decoded)


def _resource_snapshot(resources: ResourceSpec) -> dict[str, object]:
    return {
        "cpus": resources.cpus,
        "memory_mb": resources.memory_mb,
        "gpus": resources.gpus,
        "walltime_seconds": resources.walltime_seconds,
        "account": resources.account,
        "partition": resources.partition,
        "qos": resources.qos,
    }


def _failure_code(error: Exception) -> str:
    if isinstance(error, DomainError):
        return error.code
    return "cluster_unavailable"


class RunService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        cluster: ClusterPort,
        *,
        project_transport: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._cluster = cluster
        self._project_transport = project_transport

    async def preflight(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        template_id: UUID,
        datasets: tuple[RunDatasetSelection, ...],
    ) -> tuple[PreflightCheck, ...]:
        prepared = await self._prepare(
            actor_id=actor_id,
            project_id=project_id,
            template_id=template_id,
            datasets=datasets,
        )
        if prepared.submission is None or not all(check.passed for check in prepared.checks):
            return prepared.checks
        try:
            adapter_checks = await self._cluster.preflight(prepared.submission)
        except Exception:
            adapter_checks = (
                PreflightCheck(
                    code="cluster_unavailable",
                    passed=False,
                    message="The cluster adapter is unavailable.",
                ),
            )
        return (*prepared.checks, *adapter_checks)

    async def submit(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        template_id: UUID,
        datasets: tuple[RunDatasetSelection, ...],
    ) -> Run:
        prepared = await self._prepare(
            actor_id=actor_id,
            project_id=project_id,
            template_id=template_id,
            datasets=datasets,
        )
        if prepared.submission is None or prepared.snapshot is None:
            raise PreflightFailed("run preflight failed")
        try:
            adapter_checks = await self._cluster.preflight(prepared.submission)
        except Exception as error:
            raise PreflightFailed("cluster preflight failed") from error
        checks = (*prepared.checks, *adapter_checks)
        if not all(check.passed for check in checks):
            raise PreflightFailed("run preflight failed")

        now = utc_now()
        new_run = NewRun(
            workspace_id=prepared.workspace_id,
            project_id=prepared.project_id,
            template_id=prepared.template_id,
            submitted_by=actor_id,
            submission_snapshot=prepared.snapshot,
            created_at=now,
            updated_at=now,
        )
        links = tuple(
            RunDataset(
                run_id=new_run.id,
                dataset_version_id=dataset.dataset_version_id,
                mount_path=dataset.mount_path,
            )
            for dataset in prepared.datasets
        )
        async with self._uow_factory() as uow:
            await self._ensure_submittable(
                uow,
                actor_id=actor_id,
                prepared=prepared,
            )
            run = await uow.runs.add(new_run, links)
            await uow.events.add(
                NewRunEvent(
                    run_id=run.id,
                    event_type="run_created",
                    to_status=RunStatus.SUBMITTING,
                    message="Run submission started.",
                    created_at=now,
                )
            )
            await uow.commit()

        try:
            submitted = await self._cluster.submit(prepared.submission)
        except Exception as error:
            return await self._mark_submission_failed(run.id, error)
        return await self._attach_submission(
            run.id, submitted.external_job_id, submitted.submitted_at
        )

    async def cancel(self, *, actor_id: UUID, run_id: UUID) -> Run:
        result: Run | None = None
        external_job_id: str | None = None
        for _ in range(_CAS_ATTEMPTS):
            async with self._uow_factory() as uow:
                run = await self._authorized_run(uow, actor_id, run_id)
                if run.status in _TERMINAL:
                    return run
                if run.status is RunStatus.CANCELLING:
                    result = run
                    external_job_id = run.external_job_id
                    break
                now = utc_now()
                replacement = replace(
                    run,
                    status=transition(run.status, RunStatus.CANCELLING),
                    updated_at=now,
                )
                if not await uow.runs.compare_and_set_status(run.status, replacement):
                    continue
                await uow.events.add(
                    NewRunEvent(
                        run_id=run.id,
                        event_type="cancellation_requested",
                        from_status=run.status,
                        to_status=RunStatus.CANCELLING,
                        message="Run cancellation requested.",
                        created_at=now,
                    )
                )
                await uow.commit()
                result = replacement
                external_job_id = replacement.external_job_id
                break
        if result is None:
            raise ResourceConflict("run changed while cancellation was requested")
        if external_job_id is not None:
            try:
                await self._cluster.cancel(external_job_id)
            except Exception as error:
                await self._record_adapter_error(run_id, "cancel", error)
        return result

    async def _prepare(
        self,
        *,
        actor_id: UUID,
        project_id: UUID,
        template_id: UUID,
        datasets: tuple[RunDatasetSelection, ...],
    ) -> _PreparedRun:
        async with self._uow_factory() as uow:
            project, template = await self._authorize_references(
                uow,
                actor_id=actor_id,
                project_id=project_id,
                template_id=template_id,
            )
            sync = await uow.syncs.get_latest(project.id, self._project_transport)
            resolved: list[_ResolvedDataset] = []
            for selection in datasets:
                version = await uow.datasets.get_version(selection.dataset_version_id)
                if version is None:
                    raise ResourceNotFound(
                        f"dataset version {selection.dataset_version_id} not found"
                    )
                dataset = await uow.datasets.get(version.dataset_id)
                if dataset is None or dataset.workspace_id != project.workspace_id:
                    raise ResourceNotFound(
                        f"dataset version {selection.dataset_version_id} not found"
                    )
                resolved.append(
                    _ResolvedDataset(
                        dataset_version_id=version.id,
                        source_uri=f"storage:///{version.storage_key}",
                        mount_path=selection.mount_path,
                        archived=dataset.archived_at is not None,
                    )
                )

        ordered = tuple(
            sorted(resolved, key=lambda item: (item.mount_path, str(item.dataset_version_id)))
        )
        project_uri = (
            sync.target_uri
            if sync is not None
            else f"workspace107-project:///{project.storage_key}"
        )
        project_files: frozenset[str] = (
            frozenset(sync.manifest) if sync is not None else frozenset()
        )
        checks = check_preflight(
            PreflightInput(
                project_archived=project.archived_at is not None,
                template_archived=template.archived_at is not None,
                entrypoint=template.entrypoint,
                project_files=project_files,
                datasets=tuple(
                    PreflightDataset(
                        dataset_id=dataset.dataset_version_id,
                        archived=dataset.archived,
                        mount_path=dataset.mount_path,
                    )
                    for dataset in ordered
                ),
                outputs=template.output_spec,
                resources=template.resource_spec,
            )
        )
        synced = PreflightCheck(
            code="project_synced",
            passed=sync is not None,
            message=(
                "Project files are synchronized."
                if sync is not None
                else "Project files have not been synchronized."
            ),
        )
        checks = (*checks, synced)
        if not all(check.passed for check in checks):
            return _PreparedRun(
                workspace_id=project.workspace_id,
                project_id=project.id,
                template_id=template.id,
                checks=checks,
                submission=None,
                snapshot=None,
                datasets=ordered,
            )

        environment = _json_object(template.environment_spec)
        mounts = tuple(
            DatasetMount(
                dataset_version_id=str(dataset.dataset_version_id),
                source_uri=dataset.source_uri,
                mount_path=dataset.mount_path,
            )
            for dataset in ordered
        )
        submission = RunSubmission(
            project_uri=project_uri,
            entrypoint=template.entrypoint,
            resources=template.resource_spec,
            mounts=mounts,
            outputs=tuple(sorted(template.output_spec)),
            environment=environment,
        )
        snapshot = _json_object(
            {
                "schema_version": 1,
                "workspace_id": str(project.workspace_id),
                "project": {"id": str(project.id), "uri": submission.project_uri},
                "template": {"id": str(template.id), "name": template.name},
                "entrypoint": submission.entrypoint,
                "resources": _resource_snapshot(submission.resources),
                "environment": dict(submission.environment),
                "mounts": [
                    {
                        "dataset_version_id": mount.dataset_version_id,
                        "source_uri": mount.source_uri,
                        "mount_path": mount.mount_path,
                    }
                    for mount in submission.mounts
                ],
                "outputs": list(submission.outputs),
            }
        )
        return _PreparedRun(
            workspace_id=project.workspace_id,
            project_id=project.id,
            template_id=template.id,
            checks=checks,
            submission=submission,
            snapshot=snapshot,
            datasets=ordered,
        )

    async def _attach_submission(
        self,
        run_id: UUID,
        external_job_id: str,
        submitted_at: datetime,
    ) -> Run:
        result: Run | None = None
        cancel_late_job = False
        for _ in range(_CAS_ATTEMPTS):
            async with self._uow_factory() as uow:
                run = await uow.runs.get(run_id)
                if run is None:
                    raise ResourceNotFound(f"run {run_id} not found")
                if run.status is RunStatus.SUBMITTING:
                    replacement = replace(
                        run,
                        status=transition(run.status, RunStatus.QUEUED),
                        external_job_id=external_job_id,
                        submitted_at=submitted_at,
                        updated_at=submitted_at,
                    )
                    event = NewRunEvent(
                        run_id=run.id,
                        event_type="status_changed",
                        from_status=run.status,
                        to_status=RunStatus.QUEUED,
                        message="Run was accepted by the cluster.",
                        details={"external_job_id": external_job_id},
                        created_at=submitted_at,
                    )
                elif run.status is RunStatus.CANCELLING:
                    replacement = replace(
                        run,
                        external_job_id=external_job_id,
                        submitted_at=submitted_at,
                        updated_at=submitted_at,
                    )
                    event = NewRunEvent(
                        run_id=run.id,
                        event_type="external_job_attached",
                        from_status=RunStatus.CANCELLING,
                        to_status=RunStatus.CANCELLING,
                        message="Late cluster submission was attached for cancellation.",
                        details={"external_job_id": external_job_id},
                        created_at=submitted_at,
                    )
                    cancel_late_job = True
                else:
                    result = run
                    cancel_late_job = True
                    break
                if not await uow.runs.compare_and_set_status(run.status, replacement):
                    continue
                await uow.events.add(event)
                await uow.commit()
                result = replacement
                break
        if result is None:
            raise ResourceConflict("run changed while cluster submission completed")
        if cancel_late_job:
            try:
                await self._cluster.cancel(external_job_id)
            except Exception as error:
                await self._record_adapter_error(run_id, "cancel_late_submission", error)
        return result

    async def _mark_submission_failed(self, run_id: UUID, error: Exception) -> Run:
        for _ in range(_CAS_ATTEMPTS):
            async with self._uow_factory() as uow:
                run = await uow.runs.get(run_id)
                if run is None:
                    raise ResourceNotFound(f"run {run_id} not found")
                if run.status in _TERMINAL:
                    return run
                now = utc_now()
                replacement = replace(
                    run,
                    status=transition(run.status, RunStatus.FAILED),
                    failure_code=_failure_code(error),
                    failure_message="Cluster submission failed.",
                    finished_at=now,
                    updated_at=now,
                )
                if not await uow.runs.compare_and_set_status(run.status, replacement):
                    continue
                await uow.events.add(
                    NewRunEvent(
                        run_id=run.id,
                        event_type="submission_failed",
                        from_status=run.status,
                        to_status=RunStatus.FAILED,
                        message="Cluster submission failed.",
                        details={"code": replacement.failure_code or "cluster_unavailable"},
                        created_at=now,
                    )
                )
                await uow.commit()
                return replacement
        raise ResourceConflict("run changed while submission failure was recorded")

    async def _record_adapter_error(self, run_id: UUID, operation: str, error: Exception) -> None:
        async with self._uow_factory() as uow:
            if await uow.runs.get(run_id) is None:
                return
            await uow.events.add(
                NewRunEvent(
                    run_id=run_id,
                    event_type="adapter_error",
                    message="Cluster adapter operation failed.",
                    details={"code": _failure_code(error), "operation": operation},
                )
            )
            await uow.commit()

    async def _ensure_submittable(
        self,
        uow: UnitOfWork,
        *,
        actor_id: UUID,
        prepared: _PreparedRun,
    ) -> None:
        project, template = await self._authorize_references(
            uow,
            actor_id=actor_id,
            project_id=prepared.project_id,
            template_id=prepared.template_id,
        )
        if project.archived_at is not None:
            raise ResourceArchived(f"project {project.id} is archived")
        if template.archived_at is not None:
            raise ResourceArchived(f"run template {template.id} is archived")
        for selected in prepared.datasets:
            version = await uow.datasets.get_version(selected.dataset_version_id)
            if version is None:
                raise ResourceNotFound(f"dataset version {selected.dataset_version_id} not found")
            dataset = await uow.datasets.get(version.dataset_id)
            if dataset is None or dataset.workspace_id != prepared.workspace_id:
                raise ResourceNotFound(f"dataset version {selected.dataset_version_id} not found")
            if dataset.archived_at is not None:
                raise ResourceArchived(f"dataset {dataset.id} is archived")

    @staticmethod
    async def _authorize_references(
        uow: UnitOfWork,
        *,
        actor_id: UUID,
        project_id: UUID,
        template_id: UUID,
    ) -> tuple[Project, RunTemplate]:
        project = await uow.projects.get(project_id)
        if project is None:
            raise ResourceNotFound(f"project {project_id} not found")
        await require_workspace_access(
            uow,
            actor_id=actor_id,
            workspace_id=project.workspace_id,
            minimum=WorkspaceRole.MEMBER,
            active=True,
        )
        template = await uow.templates.get(template_id)
        if template is None or template.workspace_id != project.workspace_id:
            raise ResourceNotFound(f"run template {template_id} not found")
        return project, template

    @staticmethod
    async def _authorized_run(uow: UnitOfWork, actor_id: UUID, run_id: UUID) -> Run:
        run = await uow.runs.get(run_id)
        if run is None:
            raise ResourceNotFound(f"run {run_id} not found")
        await require_workspace_access(
            uow,
            actor_id=actor_id,
            workspace_id=run.workspace_id,
            minimum=WorkspaceRole.MEMBER,
        )
        return run
