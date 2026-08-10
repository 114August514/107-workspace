"""Single-active Worker 的恢复、提交歧义与终态恢复规则。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workspace107.application.run_worker import RunWorker
from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import SchedulerSubmissionRejected, SchedulerSubmissionUncertain
from workspace107.domain.execution import ExecutionIntent, PendingExecution
from workspace107.domain.models import ArtifactCollectionRule, ProjectVersion, Run
from workspace107.domain.ports.scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerState,
)
from workspace107.domain.ports.storage import ArtifactContent, RunPaths
from workspace107.domain.run_snapshot import build_snapshot
from workspace107.domain.secrets import ResolvedEnv

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class _Store:
    def __init__(self, pending: PendingExecution) -> None:
        self.pending: PendingExecution | None = pending
        self.calls: list[tuple[str, object]] = []
        self.finalize_error: BaseException | None = None

    async def next_due(self):
        return self.pending

    async def defer(self, run_id: str, delay: float) -> None:
        self.calls.append(("defer", run_id))

    async def arm(self, run_id: str) -> int:
        assert self.pending is not None
        attempt = self.pending.intent.attempt_no + 1
        self.pending = replace(
            self.pending,
            intent=replace(self.pending.intent, attempt_no=attempt),
        )
        self.calls.append(("arm", attempt))
        return attempt

    async def attach_job(self, run_id: str, job_id: str, *, reconciled: bool) -> bool:
        assert self.pending is not None
        self.pending = replace(
            self.pending,
            run=replace(self.pending.run, scheduler_job_id=job_id, submitted_at=NOW),
        )
        self.calls.append(("attach", job_id))
        return True

    async def clear_reconciled_zero(self, run_id: str) -> None:
        self.calls.append(("zero", run_id))

    async def record_uncertain(self, run_id: str, code: str, detail: str) -> None:
        assert self.pending is not None
        self.pending = replace(
            self.pending,
            intent=replace(
                self.pending.intent,
                uncertainty_code=code,
                uncertainty_detail=detail,
            ),
        )
        self.calls.append(("uncertain", (code, detail)))

    async def record_submit_failed(self, run_id: str, reason: str) -> None:
        self.calls.append(("submit_failed", reason))
        self.pending = None

    async def cancel_without_job(self, run_id: str) -> None:
        self.calls.append(("cancel", run_id))
        self.pending = None

    async def record_poll(self, run_id: str, state: SchedulerJobState) -> None:
        assert self.pending is not None
        if state.state in {
            SchedulerState.COMPLETED,
            SchedulerState.FAILED,
            SchedulerState.CANCELLED,
        }:
            self.pending = replace(
                self.pending,
                intent=replace(
                    self.pending.intent,
                    observed_scheduler_state=state.state.value,
                    observed_exit_code=state.exit_code,
                    observed_finished_at=state.finished_at or NOW,
                ),
            )
        self.calls.append(("poll", state.state))

    async def finalize(self, run_id: str, artifacts) -> None:
        self.calls.append(("finalize", tuple(artifacts)))
        if self.finalize_error is not None:
            error, self.finalize_error = self.finalize_error, None
            raise error
        self.pending = None

    async def resolve_secrets(self, *args) -> dict[str, str]:
        return {}


class _Storage:
    def __init__(self, root: Path) -> None:
        self.paths = RunPaths(
            root=root,
            work=root / "work",
            inputs=root / "inputs",
            logs=root / "logs",
        )
        for path in (self.paths.work, self.paths.inputs, self.paths.logs):
            path.mkdir(parents=True, exist_ok=True)
        self.paths.stdout.touch()
        self.paths.stderr.touch()
        self.collect_calls = 0

    async def prepare_run_directory(self, *args, **kwargs) -> RunPaths:
        return self.paths

    async def collect_artifact(self, *args) -> ArtifactContent:
        self.collect_calls += 1
        return ArtifactContent(size=3, file_count=1, content_hash="a" * 64)


class _Scheduler:
    name = "fake"

    def __init__(
        self,
        correlation: SchedulerCorrelationResult,
        *,
        submit_error: BaseException | None = None,
        poll_state: SchedulerJobState | None = None,
    ) -> None:
        self.correlation = correlation
        self.submit_error = submit_error
        self.poll_state = poll_state or SchedulerJobState(SchedulerState.PENDING)
        self.submissions = 0

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        return self.correlation

    async def submit(self, submission) -> str:
        self.submissions += 1
        if self.submit_error is not None:
            raise self.submit_error
        return "job-new"

    async def poll(self, job_id: str) -> SchedulerJobState:
        return self.poll_state

    async def cancel(self, job_id: str) -> None:
        return None


def _pending(
    *,
    attempt_no: int = 1,
    cancel: bool = False,
    job_id: str | None = None,
    observed: SchedulerState | None = None,
    artifact: bool = False,
) -> PendingExecution:
    snapshot = build_snapshot(
        snapshot_id="snap_1",
        project_id="prj_1",
        project_version_id="pv_1",
        source_run_configuration_id="rc_1",
        working_directory=".",
        command="true",
        environment_version_id="ev_1",
        environment_image="",
        environment_setup_command="",
        resolved_env=ResolvedEnv(literals={}, secret_refs={}),
        input_bindings=(),
        compute_plan_id="plan_1",
        compute_request=ComputeRequest(
            nodes=1, cpus=1, memory_mb=512, gpus=0, time_limit_minutes=5
        ),
        scheduler=ResolvedSchedulerConfiguration(
            cluster="local",
            account="test",
            partition="test",
            qos="normal",
            nodes=1,
            cpus=1,
            memory_mb=512,
            gpus=0,
            time_limit_minutes=5,
        ),
        artifact_rules=(ArtifactCollectionRule(path="outputs", optional=False),)
        if artifact
        else (),
        created_by="usr_1",
        created_at=NOW,
    )
    return PendingExecution(
        run=Run(
            id="run_1",
            project_id="prj_1",
            workspace_id="ws_1",
            snapshot_id="snap_1",
            compute_plan_id="plan_1",
            source_run_configuration_id="rc_1",
            source_run_id=None,
            name="run",
            status=RunStatus.QUEUED,
            created_by="usr_1",
            created_at=NOW,
            scheduler_job_id=job_id,
        ),
        snapshot=snapshot,
        project_version=ProjectVersion(
            id="pv_1",
            project_id="prj_1",
            sequence=1,
            message="v1",
            files=(),
            created_by="usr_1",
            created_at=NOW,
        ),
        intent=ExecutionIntent(
            run_id="run_1",
            correlation="workspace107:run_1",
            attempt_no=attempt_no,
            next_action_at=NOW,
            created_at=NOW,
            updated_at=NOW,
            cancel_requested_at=NOW if cancel else None,
            observed_scheduler_state=observed.value if observed else None,
            observed_exit_code=0 if observed else None,
            observed_finished_at=NOW if observed else None,
        ),
    )


async def _run(
    tmp_path: Path,
    pending: PendingExecution,
    result: SchedulerCorrelationResult,
    *,
    scheduler: _Scheduler | None = None,
    store: _Store | None = None,
    storage: _Storage | None = None,
):
    store = store or _Store(pending)
    scheduler = scheduler or _Scheduler(result)
    storage = storage or _Storage(tmp_path)
    worker = RunWorker(
        store=store,
        storage=storage,
        scheduler=scheduler,
        action_delay_seconds=1,
    )
    assert await worker.run_once() is True
    return store, scheduler, storage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (SchedulerCorrelationResult(complete=True, job_ids=()), "submit"),
        (SchedulerCorrelationResult(complete=True, job_ids=("job-old",)), "attach"),
        (SchedulerCorrelationResult(complete=True, job_ids=("job-a", "job-b")), "multiple"),
        (SchedulerCorrelationResult(complete=False, reason="permission denied"), "incomplete"),
    ],
)
async def test_correlation_zero_one_multiple_and_incomplete(
    tmp_path: Path, result: SchedulerCorrelationResult, expected: str
) -> None:
    store, scheduler, _ = await _run(tmp_path, _pending(), result)

    if expected == "submit":
        assert scheduler.submissions == 1
        assert [call[0] for call in store.calls[:3]] == ["zero", "arm", "attach"]
    elif expected == "attach":
        assert scheduler.submissions == 0
        assert ("attach", "job-old") in store.calls
    else:
        assert scheduler.submissions == 0
        code = "correlation_multiple" if expected == "multiple" else "correlation_incomplete"
        assert any(call[0] == "uncertain" and call[1][0] == code for call in store.calls)
        assert not any(call[0] == "arm" for call in store.calls)


class _WorkerCrash(BaseException):
    pass


@pytest.mark.asyncio
async def test_arm_then_submit_crash_recovers_without_second_submit(tmp_path: Path) -> None:
    store = _Store(_pending(attempt_no=0))
    first_scheduler = _Scheduler(
        SchedulerCorrelationResult(complete=False), submit_error=_WorkerCrash()
    )
    worker = RunWorker(
        store=store,
        storage=_Storage(tmp_path),
        scheduler=first_scheduler,
        action_delay_seconds=0,
    )
    with pytest.raises(_WorkerCrash):
        await worker.run_once()
    assert first_scheduler.submissions == 1
    assert store.pending is not None and store.pending.intent.attempt_no == 1

    restarted = _Scheduler(
        SchedulerCorrelationResult(complete=True, job_ids=("job-created-before-crash",))
    )
    await _run(tmp_path, store.pending, restarted.correlation, scheduler=restarted, store=store)
    assert restarted.submissions == 0
    assert ("attach", "job-created-before-crash") in store.calls


@pytest.mark.asyncio
async def test_terminal_artifact_restart_reuses_evidence_then_finalizes(tmp_path: Path) -> None:
    pending = _pending(observed=SchedulerState.COMPLETED, artifact=True, job_id="job-1")
    store = _Store(pending)
    store.finalize_error = _WorkerCrash()
    storage = _Storage(tmp_path)
    worker = RunWorker(
        store=store,
        storage=storage,
        scheduler=_Scheduler(SchedulerCorrelationResult(complete=False)),
        action_delay_seconds=0,
    )
    with pytest.raises(_WorkerCrash):
        await worker.run_once()
    assert store.pending is not None

    await _run(
        tmp_path,
        store.pending,
        SchedulerCorrelationResult(complete=False),
        store=store,
        storage=storage,
    )
    assert store.pending is None
    assert storage.collect_calls == 2
    assert [call[0] for call in store.calls].count("finalize") == 2


@pytest.mark.asyncio
async def test_cancel_before_first_attempt_never_submits(tmp_path: Path) -> None:
    store, scheduler, _ = await _run(
        tmp_path,
        _pending(attempt_no=0, cancel=True),
        SchedulerCorrelationResult(complete=True, job_ids=()),
    )
    assert scheduler.submissions == 0
    assert ("cancel", "run_1") in store.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SchedulerSubmissionRejected("invalid account"), "submit_failed"),
        (SchedulerSubmissionUncertain("transport lost"), "uncertain"),
    ],
)
async def test_submit_error_classification_is_explicit(
    tmp_path: Path, error: Exception, expected: str
) -> None:
    pending = _pending(attempt_no=0)
    store = _Store(pending)
    scheduler = _Scheduler(SchedulerCorrelationResult(complete=False), submit_error=error)
    await _run(tmp_path, pending, scheduler.correlation, scheduler=scheduler, store=store)
    assert any(call[0] == expected for call in store.calls)


@pytest.mark.asyncio
async def test_submit_failure_redacts_resolved_secret_before_persisting(tmp_path: Path) -> None:
    secret = "super-secret-value"
    pending = _pending(attempt_no=0)
    pending = replace(
        pending,
        snapshot=replace(pending.snapshot, env_secret_refs={"TOKEN": "TOKEN"}),
    )
    store = _Store(pending)

    async def resolve_secrets(*args) -> dict[str, str]:
        return {"TOKEN": secret}

    store.resolve_secrets = resolve_secrets
    scheduler = _Scheduler(
        SchedulerCorrelationResult(complete=False),
        submit_error=SchedulerSubmissionUncertain(f"scheduler echoed {secret}"),
    )
    await _run(tmp_path, pending, scheduler.correlation, scheduler=scheduler, store=store)

    uncertain = next(call for call in store.calls if call[0] == "uncertain")
    assert secret not in str(uncertain)
    assert "***" in str(uncertain)
