"""独立 Worker 的一次 claim/prepare/submit/correlation lookup/poll/finalize 编排。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import posixpath
from collections.abc import Awaitable, Iterable
from typing import TypeVar

from ..domain.errors import (
    SchedulerError,
    SchedulerSubmissionRejected,
    ValidationFailed,
)
from ..domain.execution import ClaimedExecution, CollectedArtifact, ExecutionPhase, LeaseLost
from ..domain.ports.clock import Clock
from ..domain.ports.execution import ExecutionStore
from ..domain.ports.scheduler import SchedulerPort, SchedulerSubmission
from ..domain.ports.storage import StoragePort
from ..domain.secrets import redact

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RunWorker:
    """只编排正式 ports；StoragePort 是 B seam 合入前唯一可替换的 FS 接缝。"""

    def __init__(
        self,
        *,
        worker_id: str,
        store: ExecutionStore,
        storage: StoragePort,
        scheduler: SchedulerPort,
        clock: Clock,
        lease_seconds: float,
        poll_seconds: float,
    ) -> None:
        self._worker_id = worker_id
        self._store = store
        self._storage = storage
        self._scheduler = scheduler
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._poll_seconds = poll_seconds

    async def run_once(self) -> bool:
        claimed = await self._store.claim_one(self._worker_id, self._lease_seconds)
        if claimed is None:
            return False
        token = claimed.intent.lease_token
        if token is None:  # pragma: no cover - DB lease tuple constraint protects this
            raise RuntimeError("claimed execution 缺少 lease token")

        try:
            await self._process(claimed, token)
        except LeaseLost:
            logger.warning(
                "Worker lease 已失效，停止推进",
                extra=_log(claimed, outcome="lease_lost"),
            )
        except Exception as exc:
            detail = _safe_detail(exc)
            logger.exception(
                "Worker 处理 Run 失败",
                extra=_log(claimed, outcome="worker_error"),
            )
            with contextlib.suppress(LeaseLost):
                await self._store.record_uncertain(
                    claimed.run.id,
                    token,
                    self._clock.now(),
                    "worker_error",
                    detail,
                )
        finally:
            await self._store.release(claimed.run.id, token, self._poll_seconds)
        return True

    async def _process(self, claimed: ClaimedExecution, token: str) -> None:
        run = claimed.run
        snapshot = claimed.snapshot
        intent = claimed.intent
        logger.info("Worker 已领取 Run", extra=_log(claimed, outcome="claimed"))

        if intent.phase is ExecutionPhase.FINALIZING:
            artifacts = await self._collect_artifacts(claimed, token)
            await self._store.finalize(run.id, token, self._clock.now(), artifacts)
            return

        if run.scheduler_job_id is not None:
            if intent.cancel_requested_at is not None:
                try:
                    await self._external(
                        claimed, token, self._scheduler.cancel(run.scheduler_job_id)
                    )
                except SchedulerError as exc:
                    await self._store.record_uncertain(
                        run.id,
                        token,
                        self._clock.now(),
                        "cancel_uncertain",
                        _safe_detail(exc),
                    )
                    return
            state = await self._external(claimed, token, self._scheduler.poll(run.scheduler_job_id))
            await self._store.record_poll(run.id, token, self._clock.now(), state)
            return

        if intent.attempt_no > 0:
            correlation = await self._external(
                claimed,
                token,
                self._scheduler.find_by_correlation(intent.correlation),
            )
            if not correlation.complete:
                await self._store.record_uncertain(
                    run.id,
                    token,
                    self._clock.now(),
                    "correlation_incomplete",
                    correlation.reason or "Scheduler correlation 查询不完整",
                )
                return
            if len(correlation.job_ids) > 1:
                await self._store.record_uncertain(
                    run.id,
                    token,
                    self._clock.now(),
                    "correlation_multiple",
                    f"correlation 匹配到 {len(correlation.job_ids)} 个任务",
                    multiple=True,
                )
                return
            if len(correlation.job_ids) == 1:
                await self._store.attach_job(
                    run.id,
                    token,
                    correlation.job_ids[0],
                    self._clock.now(),
                    reconciled=True,
                )
                return
            await self._store.record_reconcile_zero(run.id, token, self._clock.now())
            if intent.cancel_requested_at is not None:
                await self._store.cancel_without_job(run.id, token, self._clock.now())
                return
        elif intent.cancel_requested_at is not None:
            await self._store.cancel_without_job(run.id, token, self._clock.now())
            return

        try:
            # B 合入后只替换这个注入端口；C 不实现 Git、FS 布局或并发目录恢复。
            paths = await self._external(
                claimed,
                token,
                self._storage.prepare_run_directory(
                    run.id,
                    files=[
                        (item.path, item.content_hash) for item in claimed.project_version.files
                    ],
                    inputs=[(item.access_path, item.source_id) for item in snapshot.input_bindings],
                ),
            )
        except (OSError, ValidationFailed) as exc:
            await self._store.record_submit_failed(
                run.id, token, self._clock.now(), _safe_detail(exc)
            )
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

        await self._store.arm(run.id, token, self._clock.now())
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
        try:
            job_id = await self._external(claimed, token, self._scheduler.submit(submission))
        except SchedulerSubmissionRejected as exc:
            await self._store.record_submit_failed(
                run.id,
                token,
                self._clock.now(),
                _safe_detail(exc, secret_values=secret_values.values()),
            )
            return
        except Exception as exc:
            # 未经 adapter 明确确认 rejected 的异常一律可能已创建任务。
            await self._store.record_uncertain(
                run.id,
                token,
                self._clock.now(),
                "submit_uncertain",
                _safe_detail(exc, secret_values=secret_values.values()),
            )
            return
        finally:
            # 局部 Secret 只活到 submit 边界，不进入持久状态或结构化日志。
            environment.clear()
            secret_values.clear()

        await self._store.attach_job(run.id, token, job_id, self._clock.now(), reconciled=False)

    async def _collect_artifacts(
        self, claimed: ClaimedExecution, token: str
    ) -> tuple[CollectedArtifact, ...]:
        snapshot = claimed.snapshot
        collected: list[CollectedArtifact] = []
        for rule in snapshot.artifact_rules:
            source_path = rule.path
            if snapshot.working_directory not in {"", "."}:
                source_path = posixpath.join(snapshot.working_directory, rule.path)
            artifact_id = stable_artifact_id(claimed.run.id, rule.path)
            content = await self._external(
                claimed,
                token,
                self._storage.collect_artifact(claimed.run.id, artifact_id, source_path),
            )
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

    async def _external(self, claimed: ClaimedExecution, token: str, operation: Awaitable[T]) -> T:
        stopped = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(claimed.run.id, token, stopped))
        try:
            result = await operation
        finally:
            stopped.set()
            await heartbeat
        if not await self._store.renew(claimed.run.id, token, self._lease_seconds):
            raise LeaseLost("外部调用结束时 lease 已失效")
        return result

    async def _heartbeat(self, run_id: str, token: str, stopped: asyncio.Event) -> None:
        interval = max(self._lease_seconds / 3, 0.1)
        while True:
            try:
                await asyncio.wait_for(stopped.wait(), timeout=interval)
                return
            except TimeoutError:
                if not await self._store.renew(run_id, token, self._lease_seconds):
                    return


def stable_artifact_id(run_id: str, source_path: str) -> str:
    digest = hashlib.sha256(f"{run_id}\0{source_path}".encode()).hexdigest()[:20]
    return f"art_{digest}"


def _safe_detail(exc: BaseException, *, secret_values: Iterable[str] = ()) -> str:
    detail = " ".join(str(exc).split())[:500]
    return redact(detail, list(secret_values))


def _log(claimed: ClaimedExecution, *, outcome: str) -> dict[str, object]:
    intent = claimed.intent
    return {
        "run_id": claimed.run.id,
        "correlation": intent.correlation,
        "lease_generation": intent.lease_generation,
        "phase": intent.phase.value,
        "attempt_no": intent.attempt_no,
        "scheduler_job_id": claimed.run.scheduler_job_id,
        "outcome": outcome,
    }
