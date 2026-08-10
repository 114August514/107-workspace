"""单 active 独立 Worker：按持久事实串行推进一个 Run。"""

from __future__ import annotations

import hashlib
import logging
import posixpath
from collections.abc import Iterable

from ..domain.errors import SchedulerError, SchedulerSubmissionRejected, ValidationFailed
from ..domain.execution import CollectedArtifact, PendingExecution
from ..domain.ports.execution import ExecutionStore
from ..domain.ports.scheduler import SchedulerPort, SchedulerSubmission
from ..domain.ports.storage import StoragePort
from ..domain.secrets import redact

logger = logging.getLogger(__name__)


class RunWorker:
    """只编排正式 ports；B 合入时只替换 StoragePort 调用点。"""

    def __init__(
        self,
        *,
        store: ExecutionStore,
        storage: StoragePort,
        scheduler: SchedulerPort,
        action_delay_seconds: float,
    ) -> None:
        self._store = store
        self._storage = storage
        self._scheduler = scheduler
        self._action_delay_seconds = action_delay_seconds

    async def run_once(self) -> bool:
        pending = await self._store.next_due()
        if pending is None:
            return False
        logger.info("Worker 推进 Run", extra=_log(pending, outcome="selected"))
        await self._process(pending)
        # intent 已被终态事务删除时这是安全 no-op；否则用 PostgreSQL 时间安排下一步。
        await self._store.defer(pending.run.id, self._action_delay_seconds)
        return True

    async def _process(self, pending: PendingExecution) -> None:
        run = pending.run
        snapshot = pending.snapshot
        intent = pending.intent

        if intent.observed_scheduler_state is not None:
            artifacts = await self._collect_artifacts(pending)
            await self._store.finalize(run.id, artifacts)
            return

        if run.scheduler_job_id is not None:
            if intent.cancel_requested_at is not None:
                try:
                    await self._scheduler.cancel(run.scheduler_job_id)
                except SchedulerError as exc:
                    await self._store.record_uncertain(
                        run.id, "cancel_uncertain", _safe_detail(exc)
                    )
                    return
            try:
                state = await self._scheduler.poll(run.scheduler_job_id)
            except SchedulerError as exc:
                await self._store.record_uncertain(run.id, "poll_uncertain", _safe_detail(exc))
                return
            await self._store.record_poll(run.id, state)
            return

        if intent.attempt_no > 0:
            try:
                correlation = await self._scheduler.find_by_correlation(intent.correlation)
            except SchedulerError as exc:
                await self._store.record_uncertain(
                    run.id, "correlation_incomplete", _safe_detail(exc)
                )
                return
            if not correlation.complete:
                await self._store.record_uncertain(
                    run.id,
                    "correlation_incomplete",
                    correlation.reason or "Scheduler correlation 查询不完整",
                )
                return
            if len(correlation.job_ids) > 1:
                await self._store.record_uncertain(
                    run.id,
                    "correlation_multiple",
                    f"correlation 匹配到 {len(correlation.job_ids)} 个任务",
                )
                return
            if len(correlation.job_ids) == 1:
                await self._store.attach_job(run.id, correlation.job_ids[0], reconciled=True)
                return
            await self._store.clear_reconciled_zero(run.id)
            if intent.cancel_requested_at is not None:
                await self._store.cancel_without_job(run.id)
                return
        elif intent.cancel_requested_at is not None:
            await self._store.cancel_without_job(run.id)
            return

        try:
            # B 的 RunWorkspacePort 尚未合入；这是 C 唯一、明确的替换点。
            paths = await self._storage.prepare_run_directory(
                run.id,
                files=[(item.path, item.content_hash) for item in pending.project_version.files],
                inputs=[(item.access_path, item.source_id) for item in snapshot.input_bindings],
            )
        except (OSError, ValidationFailed) as exc:
            await self._store.record_submit_failed(run.id, _safe_detail(exc))
            return

        environment = dict(snapshot.env_literals)
        environment.setdefault("WORKSPACE107_INPUTS_DIR", str(paths.inputs))
        secret_values: dict[str, str] = {}
        if snapshot.env_secret_refs:
            secret_values = await self._store.resolve_secrets(
                run.workspace_id, sorted(set(snapshot.env_secret_refs.values()))
            )
            for name, secret_name in snapshot.env_secret_refs.items():
                if secret_name in secret_values:
                    environment[name] = secret_values[secret_name]

        work_dir = paths.work
        if snapshot.working_directory not in {"", "."}:
            work_dir = paths.work / snapshot.working_directory
        submission = SchedulerSubmission(
            run_id=run.id,
            correlation=intent.correlation,
            job_name=run.name,
            work_dir=work_dir,
            command=snapshot.command,
            setup_command=snapshot.environment_setup_command,
            environment_image=snapshot.environment_image,
            stdout_path=paths.stdout,
            stderr_path=paths.stderr,
            configuration=snapshot.scheduler,
            environment=environment,
        )

        # 短事务先递增 attempt；进程在此后任何位置退出，恢复都必须先 correlation lookup。
        attempt_no = await self._store.arm(run.id)
        if attempt_no is None:
            await self._store.cancel_without_job(run.id)
            environment.clear()
            secret_values.clear()
            return
        try:
            job_id = await self._scheduler.submit(submission)
        except SchedulerSubmissionRejected as exc:
            await self._store.record_submit_failed(
                run.id, _safe_detail(exc, secret_values=secret_values.values())
            )
            return
        except Exception as exc:
            # adapter 未明确确认本地 rejected 的异常都可能已经创建 Scheduler Job。
            await self._store.record_uncertain(
                run.id,
                "submit_uncertain",
                _safe_detail(exc, secret_values=secret_values.values()),
            )
            return
        finally:
            environment.clear()
            secret_values.clear()

        await self._store.attach_job(run.id, job_id, reconciled=False)

    async def _collect_artifacts(self, pending: PendingExecution) -> tuple[CollectedArtifact, ...]:
        snapshot = pending.snapshot
        collected: list[CollectedArtifact] = []
        for rule in snapshot.artifact_rules:
            source_path = rule.path
            if snapshot.working_directory not in {"", "."}:
                source_path = posixpath.join(snapshot.working_directory, rule.path)
            artifact_id = stable_artifact_id(pending.run.id, rule.path)
            content = await self._storage.collect_artifact(pending.run.id, artifact_id, source_path)
            collected.append(
                CollectedArtifact(
                    id=artifact_id,
                    source_path=rule.path,
                    name=rule.name or rule.path,
                    optional=rule.optional,
                    size=content.size if content else None,
                    file_count=content.file_count if content else None,
                    content_hash=content.content_hash if content else None,
                )
            )
        return tuple(collected)


def stable_artifact_id(run_id: str, source_path: str) -> str:
    digest = hashlib.sha256(f"{run_id}\0{source_path}".encode()).hexdigest()[:20]
    return f"art_{digest}"


def _safe_detail(exc: BaseException, *, secret_values: Iterable[str] = ()) -> str:
    detail = " ".join(str(exc).split())[:500]
    return redact(detail, list(secret_values))


def _log(pending: PendingExecution, *, outcome: str) -> dict[str, object]:
    return {
        "run_id": pending.run.id,
        "correlation": pending.intent.correlation,
        "attempt_no": pending.intent.attempt_no,
        "scheduler_job_id": pending.run.scheduler_job_id,
        "outcome": outcome,
    }
