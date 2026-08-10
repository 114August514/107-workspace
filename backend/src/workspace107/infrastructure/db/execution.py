"""PostgreSQL execution intent claim/lease/CAS implementation。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, literal, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain import ids
from ...domain.enums import (
    ActivityAction,
    ArtifactStatus,
    NotificationType,
    RunEventType,
    RunStatus,
    TargetType,
)
from ...domain.execution import (
    ClaimedExecution,
    CollectedArtifact,
    ExecutionIntent,
    ExecutionPhase,
    LeaseLost,
    SubmissionOutcome,
)
from ...domain.models import Activity, Artifact, Notification, RunEvent
from ...domain.ports.execution import ExecutionStore
from ...domain.ports.scheduler import SchedulerJobState, SchedulerState
from . import tables as t
from .repositories import SqlRepositories
from .secret_vault import DatabaseSecretVault


class SqlExecutionStore(ExecutionStore):
    """每个方法自己提交一个短事务；外部调用永远不在这些方法内部。"""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def claim_one(self, worker_id: str, lease_seconds: float) -> ClaimedExecution | None:
        async with self._factory() as session, session.begin():
            stmt = (
                select(t.RunExecutionIntentRow)
                .where(
                    t.RunExecutionIntentRow.completed_at.is_(None),
                    t.RunExecutionIntentRow.next_attempt_at <= func.now(),
                    or_(
                        t.RunExecutionIntentRow.lease_expires_at.is_(None),
                        t.RunExecutionIntentRow.lease_expires_at <= func.now(),
                    ),
                )
                .order_by(
                    t.RunExecutionIntentRow.next_attempt_at,
                    t.RunExecutionIntentRow.created_at,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            row.lease_owner = worker_id
            row.lease_token = str(uuid4())
            row.lease_generation += 1
            row.lease_expires_at = _database_deadline(lease_seconds)
            row.updated_at = func.now()
            await session.flush()
            await session.refresh(row)

            repos = SqlRepositories(session)
            run = await repos.runs.get(row.run_id)
            if run is None:
                raise RuntimeError(f"execution intent {row.run_id} 缺少 Run")
            snapshot = await repos.run_snapshots.get(run.snapshot_id)
            if snapshot is None:
                raise RuntimeError(f"Run {run.id} 缺少 Snapshot {run.snapshot_id}")
            version = await repos.project_versions.get(snapshot.project_version_id)
            if version is None:
                raise RuntimeError(
                    f"Run {run.id} 缺少 Project Version {snapshot.project_version_id}"
                )
            return ClaimedExecution(
                run=run,
                snapshot=snapshot,
                project_version=version,
                intent=_to_intent(row),
            )

    async def renew(self, run_id: str, token: str, lease_seconds: float) -> bool:
        async with self._factory() as session, session.begin():
            result = await session.execute(
                update(t.RunExecutionIntentRow)
                .where(*_lease_where(run_id, token))
                .values(
                    lease_expires_at=_database_deadline(lease_seconds),
                    updated_at=func.now(),
                )
            )
            return int(result.rowcount or 0) == 1

    async def release(self, run_id: str, token: str, delay_seconds: float) -> None:
        async with self._factory() as session, session.begin():
            await session.execute(
                update(t.RunExecutionIntentRow)
                .where(
                    t.RunExecutionIntentRow.run_id == run_id,
                    t.RunExecutionIntentRow.lease_token == token,
                    t.RunExecutionIntentRow.completed_at.is_(None),
                )
                .values(
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    next_attempt_at=_database_deadline(delay_seconds),
                    updated_at=func.now(),
                )
            )

    async def arm(self, run_id: str, token: str, now: datetime) -> int:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            run = await _run_for_update(session, run_id)
            if run.status != RunStatus.QUEUED.value or run.scheduler_job_id is not None:
                raise LeaseLost("Run 已不再允许提交")
            if intent.cancel_requested_at is not None:
                raise LeaseLost("Run 已请求取消")

            intent.attempt_no += 1
            intent.phase = ExecutionPhase.SUBMITTING.value
            intent.uncertainty_code = None
            intent.uncertainty_detail = ""
            intent.updated_at = now
            session.add(
                t.RunSubmissionAttemptRow(
                    run_id=run_id,
                    attempt_no=intent.attempt_no,
                    correlation=intent.correlation,
                    outcome=SubmissionOutcome.ARMED.value,
                    scheduler_job_id=None,
                    started_at=now,
                    resolved_at=None,
                    detail="",
                )
            )
            await session.flush()
            return intent.attempt_no

    async def attach_job(
        self, run_id: str, token: str, job_id: str, now: datetime, *, reconciled: bool
    ) -> bool:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            run = await _run_for_update(session, run_id)
            if run.scheduler_job_id is not None:
                if run.scheduler_job_id == job_id:
                    intent.phase = ExecutionPhase.MONITORING.value
                    intent.updated_at = now
                    return False
                await _uncertain(
                    session,
                    intent,
                    now,
                    "job_id_conflict",
                    "Scheduler 返回的 job id 与已关联值不同",
                    multiple=True,
                )
                return False
            if run.status != RunStatus.QUEUED.value:
                raise LeaseLost("Run 已不再允许关联 Scheduler job")

            run.scheduler_job_id = job_id
            run.submitted_at = now
            intent.phase = ExecutionPhase.MONITORING.value
            intent.uncertainty_code = None
            intent.uncertainty_detail = ""
            intent.updated_at = now
            attempt = await _current_attempt(session, intent)
            if attempt is not None:
                attempt.outcome = (
                    SubmissionOutcome.RECONCILED_ONE.value
                    if reconciled
                    else SubmissionOutcome.ACCEPTED.value
                )
                attempt.scheduler_job_id = job_id
                attempt.resolved_at = now
            await _add_event(
                session,
                run_id,
                RunEventType.SUBMITTED,
                f"已唯一关联调度任务 {job_id}",
                now,
            )
            return True

    async def record_reconcile_zero(self, run_id: str, token: str, now: datetime) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            attempt = await _current_attempt(session, intent)
            if attempt is not None:
                attempt.outcome = SubmissionOutcome.RECONCILED_ZERO.value
                attempt.resolved_at = now
            intent.phase = ExecutionPhase.READY.value
            intent.uncertainty_code = None
            intent.uncertainty_detail = ""
            intent.updated_at = now

    async def record_uncertain(
        self,
        run_id: str,
        token: str,
        now: datetime,
        code: str,
        detail: str,
        *,
        multiple: bool = False,
    ) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            await _uncertain(session, intent, now, code, detail, multiple=multiple)

    async def record_submit_failed(
        self, run_id: str, token: str, now: datetime, reason: str
    ) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            run = await _run_for_update(session, run_id)
            if run.scheduler_job_id is not None:
                raise LeaseLost("已有 Scheduler job，不能标记提交失败")
            if run.status != RunStatus.QUEUED.value:
                return
            run.status = RunStatus.SUBMIT_FAILED.value
            run.failure_reason = reason
            run.finished_at = now
            attempt = await _current_attempt(session, intent)
            if attempt is not None:
                attempt.outcome = SubmissionOutcome.REJECTED.value
                attempt.resolved_at = now
                attempt.detail = reason
            _complete_intent(intent, now)
            await _add_event(session, run_id, RunEventType.SUBMIT_FAILED, reason, now)
            await _add_notification(
                session,
                run,
                NotificationType.RUN_SUBMIT_FAILED,
                f"Run 提交失败：{run.name}",
                reason,
                now,
            )

    async def cancel_without_job(self, run_id: str, token: str, now: datetime) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            run = await _run_for_update(session, run_id)
            if run.scheduler_job_id is not None:
                raise LeaseLost("已有 Scheduler job，不能本地直接取消")
            if run.status == RunStatus.QUEUED.value:
                run.status = RunStatus.CANCELLED.value
                run.finished_at = now
                run.failure_reason = "用户在 Scheduler 接受任务前取消"
                await _add_event(session, run_id, RunEventType.CANCELLED, "任务未提交，已取消", now)
                await _add_activity(session, run, ActivityAction.RUN_CANCELLED, now)
            _complete_intent(intent, now)

    async def record_poll(
        self, run_id: str, token: str, now: datetime, state: SchedulerJobState
    ) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            run = await _run_for_update(session, run_id)
            if run.status in _TERMINAL_VALUES:
                _complete_intent(intent, now)
                return
            if state.state is SchedulerState.UNKNOWN:
                await _uncertain(session, intent, now, "job_unknown", state.reason or "任务未知")
                return
            if state.state is SchedulerState.PENDING:
                intent.phase = ExecutionPhase.MONITORING.value
                intent.updated_at = now
                return
            if state.state is SchedulerState.RUNNING:
                if run.status == RunStatus.QUEUED.value:
                    run.status = RunStatus.RUNNING.value
                    run.started_at = state.started_at or now
                    await _add_event(session, run_id, RunEventType.STARTED, "任务开始执行", now)
                intent.phase = ExecutionPhase.MONITORING.value
                intent.updated_at = now
                return

            intent.phase = ExecutionPhase.FINALIZING.value
            intent.observed_scheduler_state = state.state.value
            intent.observed_exit_code = state.exit_code
            intent.observed_started_at = state.started_at
            intent.observed_finished_at = state.finished_at or now
            intent.observed_reason = state.reason
            intent.updated_at = now

    async def finalize(
        self,
        run_id: str,
        token: str,
        now: datetime,
        artifacts: tuple[CollectedArtifact, ...],
    ) -> None:
        async with self._factory() as session, session.begin():
            intent = await _leased_intent(session, run_id, token)
            if intent.phase != ExecutionPhase.FINALIZING.value:
                raise LeaseLost("execution intent 不在 finalizing")
            run_row = await _run_for_update(session, run_id)
            repos = SqlRepositories(session)
            run = await repos.runs.get(run_id)
            if run is None:
                raise RuntimeError(f"Run {run_id} 不存在")

            required_missing = ""
            for item in artifacts:
                if item.content_hash is None:
                    await _add_event(
                        session,
                        run_id,
                        RunEventType.ARTIFACT_MISSING,
                        f"收集路径 {item.source_path} 不存在",
                        now,
                    )
                    if not item.optional:
                        required_missing = f"必需的 Artifact {item.source_path} 未生成"
                    continue
                existing = (
                    await session.execute(
                        select(t.ArtifactRow).where(
                            t.ArtifactRow.run_id == run_id,
                            t.ArtifactRow.source_path == item.source_path,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    if existing.content_hash != item.content_hash:
                        raise RuntimeError(f"Artifact {run_id}/{item.source_path} 恢复时摘要不一致")
                    continue
                await repos.artifacts.add(
                    Artifact(
                        id=item.id,
                        run_id=run_id,
                        project_id=run.project_id,
                        workspace_id=run.workspace_id,
                        name=item.name,
                        source_path=item.source_path,
                        size=item.size or 0,
                        file_count=item.file_count or 0,
                        content_hash=item.content_hash,
                        status=ArtifactStatus.AVAILABLE,
                        created_at=now,
                    )
                )
                await _add_event(
                    session,
                    run_id,
                    RunEventType.ARTIFACT_COLLECTED,
                    f"已收集 {item.source_path}，{item.file_count or 0} 个文件，"
                    f"{item.size or 0} 字节",
                    now,
                )

            status = _terminal_status(intent)
            if required_missing:
                status = RunStatus.FAILED
                run_row.failure_reason = required_missing
            else:
                run_row.failure_reason = intent.observed_reason
            run_row.status = status.value
            run_row.exit_code = intent.observed_exit_code
            run_row.started_at = run_row.started_at or intent.observed_started_at
            run_row.finished_at = intent.observed_finished_at or now
            await _add_event(
                session,
                run_id,
                RunEventType.FINISHED,
                f"任务结束，状态 {status.value}，退出码 {run_row.exit_code}",
                now,
            )
            run.status = status
            run.failure_reason = run_row.failure_reason
            action = (
                ActivityAction.RUN_CANCELLED
                if status is RunStatus.CANCELLED
                else ActivityAction.RUN_FINISHED
            )
            await _add_activity(session, run, action, now, detail=status.value)
            if status is not RunStatus.CANCELLED:
                await _add_notification(
                    session,
                    run,
                    NotificationType.RUN_SUCCEEDED
                    if status is RunStatus.SUCCEEDED
                    else NotificationType.RUN_FAILED,
                    f"Run {'成功' if status is RunStatus.SUCCEEDED else '失败'}：{run.name}",
                    run.failure_reason,
                    now,
                )
            _complete_intent(intent, now)

    async def resolve_secrets(self, workspace_id: str, names: list[str]) -> dict[str, str]:
        async with self._factory() as session, session.begin():
            return await DatabaseSecretVault(session).resolve(workspace_id, names)


async def _leased_intent(session: AsyncSession, run_id: str, token: str) -> t.RunExecutionIntentRow:
    row = (
        await session.execute(
            select(t.RunExecutionIntentRow).where(*_lease_where(run_id, token)).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise LeaseLost(f"Run {run_id} 的 lease 已失效")
    return row


def _lease_where(run_id: str, token: str) -> tuple[object, ...]:
    return (
        t.RunExecutionIntentRow.run_id == run_id,
        t.RunExecutionIntentRow.lease_token == token,
        t.RunExecutionIntentRow.lease_expires_at > func.now(),
        t.RunExecutionIntentRow.completed_at.is_(None),
    )


def _database_deadline(seconds: float):
    return func.now() + literal(seconds) * text("INTERVAL '1 second'")


async def _run_for_update(session: AsyncSession, run_id: str) -> t.RunRow:
    row = (
        await session.execute(select(t.RunRow).where(t.RunRow.id == run_id).with_for_update())
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"Run {run_id} 不存在")
    return row


async def _current_attempt(
    session: AsyncSession, intent: t.RunExecutionIntentRow
) -> t.RunSubmissionAttemptRow | None:
    if intent.attempt_no <= 0:
        return None
    return await session.get(t.RunSubmissionAttemptRow, (intent.run_id, intent.attempt_no))


async def _uncertain(
    session: AsyncSession,
    intent: t.RunExecutionIntentRow,
    now: datetime,
    code: str,
    detail: str,
    *,
    multiple: bool = False,
) -> None:
    changed = intent.uncertainty_code != code or intent.uncertainty_detail != detail
    intent.phase = ExecutionPhase.UNCERTAIN.value
    intent.uncertainty_code = code
    intent.uncertainty_detail = detail
    intent.updated_at = now
    attempt = await _current_attempt(session, intent)
    if attempt is not None:
        attempt.outcome = (
            SubmissionOutcome.RECONCILED_MULTIPLE.value
            if multiple
            else SubmissionOutcome.UNCERTAIN.value
        )
        attempt.resolved_at = now
        attempt.detail = detail
    if changed:
        await _add_event(
            session,
            intent.run_id,
            RunEventType.ERROR,
            f"submission uncertain: {detail}",
            now,
        )


def _complete_intent(intent: t.RunExecutionIntentRow, now: datetime) -> None:
    intent.phase = ExecutionPhase.COMPLETE.value
    intent.completed_at = now
    intent.updated_at = now
    intent.lease_owner = None
    intent.lease_token = None
    intent.lease_expires_at = None


def _terminal_status(intent: t.RunExecutionIntentRow) -> RunStatus:
    state = intent.observed_scheduler_state
    if state == SchedulerState.CANCELLED.value:
        return RunStatus.CANCELLED
    if state == SchedulerState.COMPLETED.value and (intent.observed_exit_code or 0) == 0:
        return RunStatus.SUCCEEDED
    return RunStatus.FAILED


async def _add_event(
    session: AsyncSession,
    run_id: str,
    event_type: RunEventType,
    message: str,
    at: datetime,
) -> None:
    await SqlRepositories(session).run_events.add(
        RunEvent(
            id=ids.new_id(ids.EVENT),
            run_id=run_id,
            type=event_type,
            message=message,
            created_at=at,
        )
    )


async def _add_activity(
    session: AsyncSession,
    run: object,
    action: ActivityAction,
    at: datetime,
    *,
    detail: str = "",
) -> None:
    repos = SqlRepositories(session)
    user = await repos.users.get(run.created_by)
    await repos.activities.add(
        Activity(
            id=ids.new_id(ids.ACTIVITY),
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            actor_id=run.created_by,
            actor_name=user.username if user else run.created_by,
            action=action,
            target_type=TargetType.RUN,
            target_id=run.id,
            target_name=run.name,
            detail=detail,
            created_at=at,
        )
    )


async def _add_notification(
    session: AsyncSession,
    run: object,
    notification_type: NotificationType,
    title: str,
    body: str,
    at: datetime,
) -> None:
    await SqlRepositories(session).notifications.add(
        Notification(
            id=ids.new_id(ids.NOTIFICATION),
            recipient_id=run.created_by,
            type=notification_type,
            title=title,
            body=body,
            workspace_id=run.workspace_id,
            target_type=TargetType.RUN,
            target_id=run.id,
            created_at=at,
        )
    )


def _to_intent(row: t.RunExecutionIntentRow) -> ExecutionIntent:
    return ExecutionIntent(
        run_id=row.run_id,
        phase=ExecutionPhase(row.phase),
        correlation=row.correlation,
        attempt_no=row.attempt_no,
        next_attempt_at=_aware(row.next_attempt_at),
        cancel_requested_at=_aware(row.cancel_requested_at),
        lease_owner=row.lease_owner,
        lease_token=row.lease_token,
        lease_generation=row.lease_generation,
        lease_expires_at=_aware(row.lease_expires_at),
        uncertainty_code=row.uncertainty_code,
        uncertainty_detail=row.uncertainty_detail,
        observed_scheduler_state=row.observed_scheduler_state,
        observed_exit_code=row.observed_exit_code,
        observed_started_at=_aware(row.observed_started_at),
        observed_finished_at=_aware(row.observed_finished_at),
        observed_reason=row.observed_reason,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        completed_at=_aware(row.completed_at),
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


_TERMINAL_VALUES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
    RunStatus.SUBMIT_FAILED.value,
}
