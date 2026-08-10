"""Independent Worker 的提交歧义、取消与安全重提规则。"""

from __future__ import annotations

import gc
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workspace107.application.run_worker import RunWorker
from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import SchedulerSubmissionRejected, SchedulerSubmissionUncertain
from workspace107.domain.execution import ClaimedExecution, ExecutionIntent, ExecutionPhase
from workspace107.domain.models import ProjectVersion, Run
from workspace107.domain.ports.scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerState,
)
from workspace107.domain.ports.storage import RunPaths
from workspace107.domain.run_snapshot import build_snapshot
from workspace107.domain.secrets import ResolvedEnv
from workspace107.infrastructure.scheduler.mock import MockScheduler

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return NOW


class _Store:
    def __init__(self, claimed: ClaimedExecution) -> None:
        self.claimed = claimed
        self.calls: list[tuple[str, object]] = []

    async def claim_one(self, *args):
        claimed, self.claimed = self.claimed, None
        return claimed

    async def renew(self, *args) -> bool:
        return True

    async def release(self, *args) -> None:
        self.calls.append(("release", args[0]))

    async def arm(self, *args) -> int:
        self.calls.append(("arm", args[0]))
        return 2

    async def attach_job(self, *args, **kwargs) -> bool:
        self.calls.append(("attach", args[2]))
        return True

    async def record_reconcile_zero(self, *args) -> None:
        self.calls.append(("zero", args[0]))

    async def record_uncertain(self, *args, **kwargs) -> None:
        self.calls.append(("uncertain", (args[3], args[4])))

    async def record_submit_failed(self, *args) -> None:
        self.calls.append(("submit_failed", args[0]))

    async def cancel_without_job(self, *args) -> None:
        self.calls.append(("cancel", args[0]))

    async def record_poll(self, *args) -> None:
        self.calls.append(("poll", args[3].state))

    async def finalize(self, *args) -> None:
        self.calls.append(("finalize", args[0]))

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

    async def prepare_run_directory(self, *args, **kwargs) -> RunPaths:
        return self.paths


class _Scheduler:
    name = "fake"

    def __init__(
        self,
        reconciliation: SchedulerCorrelationResult,
        *,
        submit_error: Exception | None = None,
    ) -> None:
        self.reconciliation = reconciliation
        self.submit_error = submit_error
        self.submissions = 0

    async def find_by_correlation(self, correlation: str) -> SchedulerCorrelationResult:
        return self.reconciliation

    async def submit(self, submission) -> str:
        self.submissions += 1
        if self.submit_error is not None:
            raise self.submit_error
        return "job-new"

    async def poll(self, job_id: str) -> SchedulerJobState:
        return SchedulerJobState(SchedulerState.PENDING)

    async def cancel(self, job_id: str) -> None:
        return None


def _claimed(*, attempt_no: int = 1, cancel: bool = False) -> ClaimedExecution:
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
        artifact_rules=(),
        created_by="usr_1",
        created_at=NOW,
    )
    intent = ExecutionIntent(
        run_id="run_1",
        phase=ExecutionPhase.UNCERTAIN if attempt_no else ExecutionPhase.READY,
        correlation="workspace107:run_1",
        attempt_no=attempt_no,
        next_attempt_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        cancel_requested_at=NOW if cancel else None,
        lease_owner="worker",
        lease_token="token",
        lease_generation=1,
        lease_expires_at=NOW,
    )
    return ClaimedExecution(
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
        intent=intent,
    )


async def _run(
    tmp_path: Path,
    claimed: ClaimedExecution,
    result: SchedulerCorrelationResult,
    *,
    scheduler: _Scheduler | None = None,
    store: _Store | None = None,
):
    store = store or _Store(claimed)
    scheduler = scheduler or _Scheduler(result)
    worker = RunWorker(
        worker_id="worker",
        store=store,
        storage=_Storage(tmp_path),
        scheduler=scheduler,
        clock=_Clock(),
        lease_seconds=30,
        poll_seconds=1,
    )
    assert await worker.run_once() is True
    return store, scheduler


class _WorkerCrash(BaseException):
    pass


class _RestartStore(_Store):
    def __init__(self, claimed: ClaimedExecution) -> None:
        super().__init__(claimed)
        self.state = claimed
        self.crash_on_attach = True

    async def claim_one(self, *args):
        self.state = replace(
            self.state,
            intent=replace(
                self.state.intent,
                lease_owner=str(args[0]),
                lease_token="restart-token",
                lease_generation=self.state.intent.lease_generation + 1,
            ),
        )
        return self.state

    async def arm(self, *args) -> int:
        self.state = replace(
            self.state,
            intent=replace(
                self.state.intent,
                phase=ExecutionPhase.SUBMITTING,
                attempt_no=self.state.intent.attempt_no + 1,
            ),
        )
        return self.state.intent.attempt_no

    async def attach_job(self, *args, **kwargs) -> bool:
        if self.crash_on_attach:
            raise _WorkerCrash()
        return await super().attach_job(*args, **kwargs)

    async def record_uncertain(self, *args, **kwargs) -> None:
        await super().record_uncertain(*args, **kwargs)
        self.state = replace(
            self.state,
            intent=replace(self.state.intent, phase=ExecutionPhase.UNCERTAIN),
        )


class _CountingMock(MockScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.submissions = 0

    async def submit(self, submission) -> str:
        self.submissions += 1
        return await super().submit(submission)


@pytest.mark.asyncio
async def test_worker_and_mock_restart_after_submit_never_resubmits(tmp_path: Path) -> None:
    claimed = _claimed(attempt_no=0)
    store = _RestartStore(claimed)
    storage = _Storage(tmp_path)
    first_scheduler = _CountingMock()
    first_worker = RunWorker(
        worker_id="worker-before-crash",
        store=store,
        storage=storage,
        scheduler=first_scheduler,
        clock=_Clock(),
        lease_seconds=30,
        poll_seconds=0,
    )

    with pytest.raises(_WorkerCrash):
        await first_worker.run_once()
    assert first_scheduler.submissions == 1

    del first_worker, first_scheduler
    gc.collect()
    store.crash_on_attach = False
    restarted_scheduler = _CountingMock()
    restarted_worker = RunWorker(
        worker_id="worker-after-crash",
        store=store,
        storage=storage,
        scheduler=restarted_scheduler,
        clock=_Clock(),
        lease_seconds=30,
        poll_seconds=0,
    )

    assert await restarted_worker.run_once() is True
    assert restarted_scheduler.submissions == 0
    assert any(
        call[0] == "uncertain" and call[1][0] == "correlation_incomplete" for call in store.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "code"),
    [
        (
            SchedulerCorrelationResult(complete=False, reason="permission denied"),
            "correlation_incomplete",
        ),
        (
            SchedulerCorrelationResult(complete=True, job_ids=("job-1", "job-2")),
            "correlation_multiple",
        ),
    ],
)
async def test_incomplete_or_multiple_reconcile_never_resubmits(
    tmp_path: Path, result: SchedulerCorrelationResult, code: str
) -> None:
    store, scheduler = await _run(tmp_path, _claimed(), result)

    assert scheduler.submissions == 0
    assert any(call[0] == "uncertain" and call[1][0] == code for call in store.calls)
    assert not any(call[0] == "arm" for call in store.calls)


@pytest.mark.asyncio
async def test_unique_reconcile_attaches_without_resubmitting(tmp_path: Path) -> None:
    store, scheduler = await _run(
        tmp_path, _claimed(), SchedulerCorrelationResult(complete=True, job_ids=("job-existing",))
    )

    assert scheduler.submissions == 0
    assert ("attach", "job-existing") in store.calls


@pytest.mark.asyncio
async def test_authoritative_zero_arms_before_one_resubmit(tmp_path: Path) -> None:
    store, scheduler = await _run(
        tmp_path, _claimed(), SchedulerCorrelationResult(complete=True, job_ids=())
    )

    assert scheduler.submissions == 1
    assert [call[0] for call in store.calls if call[0] != "release"] == ["zero", "arm", "attach"]


@pytest.mark.asyncio
async def test_cancel_before_first_attempt_never_submits(tmp_path: Path) -> None:
    claimed = _claimed(attempt_no=0, cancel=True)
    store, scheduler = await _run(
        tmp_path, claimed, SchedulerCorrelationResult(complete=True, job_ids=())
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
    claimed = _claimed(attempt_no=0)
    store = _Store(claimed)
    scheduler = _Scheduler(SchedulerCorrelationResult(complete=False), submit_error=error)

    await _run(
        tmp_path,
        claimed,
        SchedulerCorrelationResult(complete=False),
        scheduler=scheduler,
        store=store,
    )

    assert any(call[0] == expected for call in store.calls)


@pytest.mark.asyncio
async def test_submit_failure_redacts_resolved_secret_before_persisting(tmp_path: Path) -> None:
    secret = "super-secret-value"
    claimed = _claimed(attempt_no=0)
    claimed = replace(
        claimed,
        snapshot=replace(claimed.snapshot, env_secret_refs={"TOKEN": "TOKEN"}),
    )
    store = _Store(claimed)

    async def resolve_secrets(*args) -> dict[str, str]:
        return {"TOKEN": secret}

    store.resolve_secrets = resolve_secrets
    scheduler = _Scheduler(
        SchedulerCorrelationResult(complete=False),
        submit_error=SchedulerSubmissionUncertain(f"scheduler echoed {secret}"),
    )

    await _run(
        tmp_path,
        claimed,
        SchedulerCorrelationResult(complete=False),
        scheduler=scheduler,
        store=store,
    )

    uncertain = next(call for call in store.calls if call[0] == "uncertain")
    assert secret not in str(uncertain)
    assert "***" in str(uncertain)
