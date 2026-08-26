"""PostgreSQL minimal intent、迁移与 single-active Worker lock。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.execution import CollectedArtifact
from workspace107.domain.ports.scheduler import SchedulerJobState, SchedulerState
from workspace107.domain.run_snapshot import build_snapshot
from workspace107.domain.secrets import ResolvedEnv
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.execution import SqlExecutionStore
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.worker_lock import WORKER_LOCK_KEY, WORKER_LOCK_NAMESPACE

DATABASE_URL = os.environ.get("WORKSPACE107_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires dedicated PostgreSQL test URL")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
EXPECTED_INTENT_COLUMNS = {
    "run_id",
    "correlation",
    "attempt_no",
    "next_action_at",
    "cancel_requested_at",
    "uncertainty_code",
    "uncertainty_detail",
    "observed_scheduler_state",
    "observed_exit_code",
    "observed_started_at",
    "observed_finished_at",
    "observed_reason",
    "created_at",
    "updated_at",
}


async def _seed(factory: async_sessionmaker, *, with_intent: bool) -> None:
    snapshot = build_snapshot(
        snapshot_id="snap_claim",
        project_id="prj_claim",
        project_version_id="pv_claim",
        source_run_configuration_id=None,
        working_directory=".",
        command="true",
        environment_version_id="ev_claim",
        environment_image="",
        environment_setup_command="",
        resolved_env=ResolvedEnv(literals={}, secret_refs={}),
        input_bindings=(),
        compute_plan_id="plan_claim",
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
        initiated_by_user_id="usr_claim",
        created_at=NOW,
    )
    async with factory() as session, session.begin():
        session.add(
            t.UserRow(id="usr_claim", username="claim", display_name="Claim", created_at=NOW)
        )
        await session.flush()
        session.add(
            t.ProjectRow(
                id="prj_claim",
                name="Claim",
                owner_user_id="usr_claim",
                owner_user_group_id=None,
                repository_identity="repo_claim",
                description="",
                status="active",
                visibility="owner_scope",
                environment_version_id=None,
                default_run_configuration_id=None,
                created_by="usr_claim",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.flush()
        session.add(
            t.ProjectVersionRow(
                id="pv_claim",
                project_id="prj_claim",
                repository_identity="repo_claim",
                sequence=1,
                message="claim",
                created_by="usr_claim",
                commit_oid="1" * 40,
                tree_oid="2" * 40,
                file_count=1,
                total_size=1,
                created_at=NOW,
            )
        )
        session.add(t.RunSnapshotRow(id="snap_claim", payload=snapshot.to_payload()))
        await session.flush()
        session.add(
            t.RunRow(
                id="run_claim",
                project_id="prj_claim",
                snapshot_id="snap_claim",
                compute_plan_id="plan_claim",
                project_version_id="pv_claim",
                project_version_label="v1",
                source_run_configuration_id=None,
                source_run_id=None,
                name="Claim",
                status="queued",
                scheduler_job_id=None,
                exit_code=None,
                failure_reason="",
                initiated_by_user_id="usr_claim",
                created_at=NOW,
                submitted_at=None,
                started_at=None,
                finished_at=None,
            )
        )
        if with_intent:
            await session.flush()
            session.add(
                t.RunExecutionIntentRow(
                    run_id="run_claim",
                    correlation="workspace107:run_claim",
                    attempt_no=0,
                    next_action_at=datetime(2000, 1, 1, tzinfo=UTC),
                    uncertainty_detail="",
                    observed_reason="",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )


async def _alembic(backend_root: Path, env: dict[str, str], *args: str):
    return await asyncio.to_thread(
        subprocess.run,
        ["alembic", *args],
        cwd=backend_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_migration_refuses_nonterminal_data_and_creates_only_minimal_intent() -> None:
    engine = create_async_engine(DATABASE_URL)
    migration_env = {**os.environ, "WORKSPACE107_DATABASE_URL": DATABASE_URL}
    backend_root = Path(__file__).parents[3]
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        empty_upgrade = await _alembic(backend_root, migration_env, "upgrade", "head")
        assert empty_upgrade.returncode == 0, empty_upgrade.stderr
        empty_downgrade = await _alembic(backend_root, migration_env, "downgrade", "a1f0e2d3c4b5")
        assert empty_downgrade.returncode == 0, empty_downgrade.stderr

        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=False)
        rejected = await _alembic(backend_root, migration_env, "upgrade", "head")
        assert rejected.returncode != 0
        assert "既有非终态 Run" in rejected.stderr

        async with factory() as session, session.begin():
            await session.execute(
                update(t.RunRow)
                .where(t.RunRow.id == "run_claim")
                .values(status="cancelled", finished_at=NOW)
            )
        accepted = await _alembic(backend_root, migration_env, "upgrade", "head")
        assert accepted.returncode == 0, accepted.stderr

        async with engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema='public' AND table_name='run_execution_intents'"
                        )
                    )
                ).scalars()
            )
            attempts_table = await connection.scalar(
                text("SELECT to_regclass('public.run_submission_attempts')")
            )
        assert columns == EXPECTED_INTENT_COLUMNS
        assert attempts_table is None

        async with factory() as session, session.begin():
            session.add(
                t.RunExecutionIntentRow(
                    run_id="run_claim",
                    correlation="workspace107:run_claim",
                    attempt_no=1,
                    next_action_at=NOW,
                    uncertainty_detail="manual gate",
                    observed_reason="",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        downgrade_rejected = await _alembic(
            backend_root, migration_env, "downgrade", "a1f0e2d3c4b5"
        )
        assert downgrade_rejected.returncode != 0
        assert "仍有 execution intent" in downgrade_rejected.stderr

        async with factory() as session, session.begin():
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            await session.delete(intent)
        downgrade = await _alembic(backend_root, migration_env, "downgrade", "a1f0e2d3c4b5")
        assert downgrade.returncode == 0, downgrade.stderr
        restored = await _alembic(backend_root, migration_env, "upgrade", "head")
        assert restored.returncode == 0, restored.stderr
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_minimal_intent_arm_poll_artifact_finalize_and_delete() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=True)
        store = SqlExecutionStore(factory)

        pending = await store.next_due()
        assert pending is not None and pending.intent.attempt_no == 0
        assert await store.arm("run_claim") == 1
        assert await store.attach_job("run_claim", "job-1", reconciled=False) is True
        assert await store.attach_job("run_claim", "job-1", reconciled=True) is False
        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.RUNNING, started_at=NOW),
            cancel_failure=None,
        )
        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.PENDING),
            cancel_failure=None,
        )
        await store.record_poll(
            "run_claim",
            SchedulerJobState(
                state=SchedulerState.COMPLETED,
                exit_code=0,
                started_at=NOW,
                finished_at=NOW + timedelta(seconds=10),
            ),
            cancel_failure=None,
        )
        observed = await store.next_due()
        assert observed is not None
        assert observed.intent.observed_scheduler_state == "completed"
        artifact = CollectedArtifact(
            id="art_stable",
            source_path="outputs",
            name="outputs",
            optional=False,
            size=3,
            file_count=1,
            content_hash="a" * 64,
        )
        await store.finalize("run_claim", (artifact,))

        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            run = await session.get(t.RunRow, "run_claim")
            events = (
                (
                    await session.execute(
                        select(t.RunEventRow).where(t.RunEventRow.run_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
            artifacts = (
                (
                    await session.execute(
                        select(t.ArtifactRow).where(t.ArtifactRow.run_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
            activities = (
                (
                    await session.execute(
                        select(t.ActivityRow).where(t.ActivityRow.target_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
        assert intent is None
        assert run.status == "succeeded" and run.scheduler_job_id == "job-1"
        assert [event.type for event in events] == [
            "submitted",
            "started",
            "artifact_collected",
            "finished",
        ]
        assert len(artifacts) == len(activities) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_poll_failure_uncertainty_is_stable_across_cancel_retries() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=True)
        store = SqlExecutionStore(factory)
        assert await store.arm("run_claim") == 1
        assert await store.attach_job("run_claim", "job-1", reconciled=False)
        async with factory() as session, session.begin():
            assert await SqlRepositories(session).execution_intents.request_cancel("run_claim")

        for _ in range(3):
            # Worker 仅持久化 poll failure；同轮 cancel failure 保持为进程内局部事实。
            await store.record_uncertain("run_claim", "poll_uncertain", "poll failed")

        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            error_count = (
                await session.execute(
                    select(func.count())
                    .select_from(t.RunEventRow)
                    .where(
                        t.RunEventRow.run_id == "run_claim",
                        t.RunEventRow.type == "error",
                    )
                )
            ).scalar_one()
        assert intent is not None
        assert (intent.uncertainty_code, intent.uncertainty_detail) == (
            "poll_uncertain",
            "poll failed",
        )
        assert error_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_poll_outcome_atomically_resolves_cancel_uncertainty_precedence() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=True)
        store = SqlExecutionStore(factory)
        assert await store.arm("run_claim") == 1
        assert await store.attach_job("run_claim", "job-1", reconciled=False)
        async with factory() as session, session.begin():
            assert await SqlRepositories(session).execution_intents.request_cancel("run_claim")

        for reason in (
            "temporarily invisible 1",
            "temporarily invisible 2",
            "temporarily invisible 2",
        ):
            await store.record_poll(
                "run_claim",
                SchedulerJobState(state=SchedulerState.UNKNOWN, reason=reason),
                cancel_failure="cancel rejected",
            )
        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            unknown_error_count = (
                await session.execute(
                    select(func.count())
                    .select_from(t.RunEventRow)
                    .where(
                        t.RunEventRow.run_id == "run_claim",
                        t.RunEventRow.type == "error",
                    )
                )
            ).scalar_one()
        assert (intent.uncertainty_code, intent.uncertainty_detail) == (
            "job_unknown",
            "temporarily invisible 2",
        )
        assert unknown_error_count == 2

        for state in (
            SchedulerJobState(state=SchedulerState.PENDING),
            SchedulerJobState(state=SchedulerState.PENDING),
            SchedulerJobState(state=SchedulerState.RUNNING, started_at=NOW),
            SchedulerJobState(state=SchedulerState.RUNNING, started_at=NOW),
        ):
            await store.record_poll("run_claim", state, cancel_failure="cancel rejected")
        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            run = await session.get(t.RunRow, "run_claim")
            cancel_error_count = (
                await session.execute(
                    select(func.count())
                    .select_from(t.RunEventRow)
                    .where(
                        t.RunEventRow.run_id == "run_claim",
                        t.RunEventRow.type == "error",
                    )
                )
            ).scalar_one()
        assert (intent.uncertainty_code, intent.uncertainty_detail) == (
            "cancel_uncertain",
            "cancel rejected",
        )
        assert run.status == "running"
        assert cancel_error_count == 3

        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.RUNNING, started_at=NOW),
            cancel_failure=None,
        )
        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.PENDING),
            cancel_failure=None,
        )
        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            cleared_error_count = (
                await session.execute(
                    select(func.count())
                    .select_from(t.RunEventRow)
                    .where(
                        t.RunEventRow.run_id == "run_claim",
                        t.RunEventRow.type == "error",
                    )
                )
            ).scalar_one()
        assert intent.uncertainty_code is None
        assert intent.uncertainty_detail == ""
        assert cleared_error_count == 3

        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.PENDING),
            cancel_failure="cancel rejected",
        )
        await store.record_poll(
            "run_claim",
            SchedulerJobState(
                state=SchedulerState.CANCELLED,
                started_at=NOW,
                finished_at=NOW + timedelta(seconds=10),
                reason="cancelled by scheduler",
            ),
            cancel_failure="cancel rejected",
        )
        observed = await store.next_due()
        assert observed is not None
        assert observed.intent.observed_scheduler_state == "cancelled"
        assert observed.intent.uncertainty_code is None
        await store.finalize("run_claim", ())

        async with factory() as session:
            assert await session.get(t.RunExecutionIntentRow, "run_claim") is None
            run = await session.get(t.RunRow, "run_claim")
            final_error_count = (
                await session.execute(
                    select(func.count())
                    .select_from(t.RunEventRow)
                    .where(
                        t.RunEventRow.run_id == "run_claim",
                        t.RunEventRow.type == "error",
                    )
                )
            ).scalar_one()
        assert run.status == "cancelled"
        assert final_error_count == 4
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_completed_without_exit_code_stays_uncertain_and_keeps_intent() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=True)
        store = SqlExecutionStore(factory)
        assert await store.arm("run_claim") == 1
        assert await store.attach_job("run_claim", "job-1", reconciled=False)

        await store.record_poll(
            "run_claim",
            SchedulerJobState(state=SchedulerState.COMPLETED, exit_code=None),
            cancel_failure=None,
        )
        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            run = await session.get(t.RunRow, "run_claim")
        assert intent is not None
        assert intent.uncertainty_code == "terminal_exit_code_missing"
        assert intent.observed_scheduler_state is None
        assert run.status == "queued"

        # 即使坏数据绕过 record_poll 写入，finalize 也不能把 None 当作成功退出码。
        async with factory() as session, session.begin():
            await session.execute(
                update(t.RunExecutionIntentRow)
                .where(t.RunExecutionIntentRow.run_id == "run_claim")
                .values(observed_scheduler_state="completed")
            )
        with pytest.raises(RuntimeError, match="缺少 exit_code"):
            await store.finalize("run_claim", ())
        async with factory() as session:
            assert await session.get(t.RunExecutionIntentRow, "run_claim") is not None
            assert (await session.get(t.RunRow, "run_claim")).status == "queued"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_request_writes_activity_only_when_worker_finishes() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory, with_intent=True)
        async with factory() as session, session.begin():
            database_now = (await session.execute(select(func.now()))).scalar_one()
            assert await SqlRepositories(session).execution_intents.request_cancel("run_claim")
            intent_after_request = await session.get(t.RunExecutionIntentRow, "run_claim")
            await session.refresh(intent_after_request)
            assert intent_after_request.cancel_requested_at == database_now
            assert intent_after_request.next_action_at == database_now
            assert intent_after_request.updated_at == database_now
        async with factory() as session:
            before = (
                (
                    await session.execute(
                        select(t.ActivityRow).where(t.ActivityRow.target_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
        assert before == []

        await SqlExecutionStore(factory).cancel_without_job("run_claim")
        async with factory() as session:
            run = await session.get(t.RunRow, "run_claim")
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            activities = (
                (
                    await session.execute(
                        select(t.ActivityRow).where(t.ActivityRow.target_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
        assert run.status == "cancelled"
        assert intent is None
        assert [activity.action for activity in activities] == ["run_cancelled"]
    finally:
        await engine.dispose()


async def _wait_for_start(process: asyncio.subprocess.Process) -> str:
    assert process.stdout is not None
    output = ""
    async with asyncio.timeout(15):
        while process.returncode is None:
            line = await process.stdout.readline()
            if not line:
                break
            output += line.decode(errors="replace")
            if "Single-active Independent Worker 已启动" in output:
                return output
    raise AssertionError(f"Worker 未启动：{output}")


async def _start_worker(env: dict[str, str], storage: Path) -> asyncio.subprocess.Process:
    child_env = {
        **env,
        "WORKSPACE107_DATABASE_URL": DATABASE_URL,
        "WORKSPACE107_STORAGE_ROOT": str(storage),
        "WORKSPACE107_SCHEDULER": "mock",
        "WORKSPACE107_LOG_FORMAT": "text",
        "WORKSPACE107_WORKER_IDLE_SECONDS": "0.1",
        "PYTHONUNBUFFERED": "1",
    }
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "workspace107.worker",
        cwd=Path(__file__).parents[3],
        env=child_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


@pytest.mark.asyncio
async def test_second_worker_fails_then_sigkill_releases_lock(tmp_path: Path) -> None:
    engine = create_async_engine(DATABASE_URL)
    first: asyncio.subprocess.Process | None = None
    third: asyncio.subprocess.Process | None = None
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        first = await _start_worker(dict(os.environ), tmp_path / "first")
        await _wait_for_start(first)

        second = await _start_worker(dict(os.environ), tmp_path / "second")
        second_output, _ = await asyncio.wait_for(second.communicate(), timeout=15)
        assert second.returncode != 0
        assert "另一个 Independent Worker 已持有" in second_output.decode(errors="replace")

        first.kill()
        await first.wait()
        first = None
        await asyncio.sleep(0.1)

        third = await _start_worker(dict(os.environ), tmp_path / "third")
        await _wait_for_start(third)

        async with engine.connect() as connection:
            lock_pid = await connection.scalar(
                text(
                    "SELECT pid FROM pg_locks WHERE locktype='advisory' AND granted "
                    "AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) "
                    "AND classid=:namespace AND objid=:key"
                ),
                {"namespace": WORKER_LOCK_NAMESPACE, "key": WORKER_LOCK_KEY},
            )
            assert lock_pid is not None
            assert await connection.scalar(
                text("SELECT pg_terminate_backend(:pid)"), {"pid": lock_pid}
            )
        assert await asyncio.wait_for(third.wait(), timeout=15) != 0
        third = None
    finally:
        for process in (first, third):
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
        await engine.dispose()
