from dataclasses import dataclass, replace
from uuid import UUID

from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import DomainError
from workspace107.domain.models import (
    CollectedArtifact,
    JobObservation,
    NewArtifact,
    NewRunEvent,
    ObjectMetadata,
    Run,
    StoredObject,
)
from workspace107.domain.ports.cluster import ClusterPort
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.domain.ports.storage import StoragePort
from workspace107.domain.state_machine import transition

_TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})


@dataclass(frozen=True, slots=True)
class _PendingArtifact:
    collected: CollectedArtifact
    stored: StoredObject


def _error_code(error: Exception) -> str:
    if isinstance(error, DomainError):
        return error.code
    return "cluster_unavailable"


class RunReconciler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        cluster: ClusterPort,
        storage: StoragePort,
    ) -> None:
        self._uow_factory = uow_factory
        self._cluster = cluster
        self._storage = storage

    async def reconcile_once(self) -> None:
        async with self._uow_factory() as uow:
            run_ids = tuple(run.id for run in await uow.runs.list_non_terminal())
        for run_id in run_ids:
            await self._reconcile_run(run_id)

    async def _reconcile_run(self, run_id: UUID) -> None:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
        if run is None or run.status in _TERMINAL or run.external_job_id is None:
            return

        try:
            if run.status is RunStatus.CANCELLING:
                await self._cluster.cancel(run.external_job_id)
            observation = await self._cluster.status(run.external_job_id)
        except Exception as error:
            await self._record_adapter_error(run_id, error)
            return
        target = self._target_status(run.status, observation.status)
        if target is None:
            return

        pending: tuple[_PendingArtifact, ...] = ()
        if target in _TERMINAL:
            try:
                pending = await self._collect(run.external_job_id)
            except Exception as error:
                await self._record_adapter_error(run_id, error)
                return
        await self._persist_observation(run, observation, target, pending)

    async def _collect(self, external_job_id: str) -> tuple[_PendingArtifact, ...]:
        collected = await self._cluster.collect_artifacts(external_job_id)
        pending: list[_PendingArtifact] = []
        for artifact in collected:
            stored = await self._storage.put(
                self._cluster.open_artifact(external_job_id, artifact.artifact_key),
                ObjectMetadata(name=artifact.name, media_type=artifact.media_type),
            )
            pending.append(_PendingArtifact(collected=artifact, stored=stored))
        return tuple(pending)

    async def _persist_observation(
        self,
        observed_run: Run,
        observation: JobObservation,
        target: RunStatus,
        pending: tuple[_PendingArtifact, ...],
    ) -> None:
        async with self._uow_factory() as uow:
            current = await uow.runs.get(observed_run.id)
            if (
                current is None
                or current.status is not observed_run.status
                or current.external_job_id != observed_run.external_job_id
            ):
                return
            replacement = self._replacement(current, observation, target)
            if not await uow.runs.compare_and_set_status(current.status, replacement):
                return
            for artifact in pending:
                if await uow.artifacts.exists_for_run_and_storage_key(
                    current.id, artifact.stored.storage_key
                ):
                    continue
                await uow.artifacts.add(
                    NewArtifact(
                        run_id=current.id,
                        kind=artifact.collected.kind,
                        name=artifact.collected.name,
                        storage_key=artifact.stored.storage_key,
                        media_type=artifact.collected.media_type,
                        size_bytes=artifact.stored.size_bytes,
                        sha256=artifact.stored.sha256,
                        created_at=observation.observed_at,
                    )
                )
            await uow.events.add(
                NewRunEvent(
                    run_id=current.id,
                    event_type="status_changed",
                    from_status=current.status,
                    to_status=target,
                    message=f"Run status changed to {target.value}.",
                    details={
                        "exit_code": observation.exit_code,
                        "observation": dict(observation.details),
                    },
                    created_at=observation.observed_at,
                )
            )
            await uow.commit()

    async def _record_adapter_error(self, run_id: UUID, error: Exception) -> None:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
            if run is None or run.status in _TERMINAL:
                return
            await uow.events.add(
                NewRunEvent(
                    run_id=run_id,
                    event_type="adapter_error",
                    message="Cluster adapter operation failed.",
                    details={"code": _error_code(error)},
                )
            )
            await uow.commit()

    @staticmethod
    def _target_status(current: RunStatus, observed: RunStatus) -> RunStatus | None:
        if current is RunStatus.SUBMITTING:
            return RunStatus.FAILED if observed is RunStatus.FAILED else None
        if current is RunStatus.QUEUED:
            if observed in (RunStatus.RUNNING, RunStatus.FAILED):
                return observed
            if observed in (RunStatus.SUCCEEDED, RunStatus.CANCELLED):
                return (
                    RunStatus.RUNNING if observed is RunStatus.SUCCEEDED else RunStatus.CANCELLING
                )
            return None
        if current is RunStatus.RUNNING:
            if observed in (RunStatus.SUCCEEDED, RunStatus.FAILED):
                return observed
            if observed is RunStatus.CANCELLED:
                return RunStatus.CANCELLING
            return None
        if current is RunStatus.CANCELLING:
            if observed in (RunStatus.CANCELLED, RunStatus.FAILED):
                return observed
            if observed is RunStatus.SUCCEEDED:
                return RunStatus.FAILED
        return None

    @staticmethod
    def _replacement(run: Run, observation: JobObservation, target: RunStatus) -> Run:
        transition(run.status, target)
        started_at = run.started_at
        finished_at = run.finished_at
        failure_code = run.failure_code
        failure_message = run.failure_message
        if target is RunStatus.RUNNING and started_at is None:
            started_at = observation.observed_at
        if target in _TERMINAL:
            finished_at = observation.observed_at
        if target is RunStatus.FAILED:
            failure_code = (
                "cancellation_race"
                if run.status is RunStatus.CANCELLING and observation.status is RunStatus.SUCCEEDED
                else "external_job_failed"
            )
            failure_message = "Cluster job failed."
        return replace(
            run,
            status=target,
            exit_code=observation.exit_code,
            failure_code=failure_code,
            failure_message=failure_message,
            started_at=started_at,
            finished_at=finished_at,
            updated_at=observation.observed_at,
        )
