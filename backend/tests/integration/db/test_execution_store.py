"""PostgreSQL claim/lease/fencing 与 submit arm/attach CAS。"""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.execution import CollectedArtifact, ExecutionPhase, LeaseLost
from workspace107.domain.ports.scheduler import SchedulerJobState, SchedulerState
from workspace107.domain.run_snapshot import build_snapshot
from workspace107.domain.secrets import ResolvedEnv
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.execution import SqlExecutionStore
from workspace107.infrastructure.db.migration_guards import (
    guard_worker_downgrade,
    guard_worker_upgrade,
)

DATABASE_URL = os.environ.get("WORKSPACE107_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires dedicated PostgreSQL test URL")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


async def _seed(factory: async_sessionmaker) -> None:
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
        created_by="usr_claim",
        created_at=NOW,
    )
    async with factory() as session, session.begin():
        session.add(
            t.UserRow(id="usr_claim", username="claim", display_name="Claim", created_at=NOW)
        )
        await session.flush()
        session.add(
            t.WorkspaceRow(
                id="ws_claim",
                kind="personal",
                name="Claim",
                description="",
                owner_id="usr_claim",
                created_at=NOW,
            )
        )
        await session.flush()
        session.add(
            t.ProjectRow(
                id="prj_claim",
                workspace_id="ws_claim",
                name="Claim",
                description="",
                status="active",
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
                sequence=1,
                message="claim",
                created_by="usr_claim",
                created_at=NOW,
            )
        )
        session.add(t.RunSnapshotRow(id="snap_claim", payload=snapshot.to_payload()))
        await session.flush()
        session.add(
            t.RunRow(
                id="run_claim",
                project_id="prj_claim",
                workspace_id="ws_claim",
                snapshot_id="snap_claim",
                compute_plan_id="plan_claim",
                source_run_configuration_id=None,
                source_run_id=None,
                name="Claim",
                status="queued",
                scheduler_job_id=None,
                exit_code=None,
                failure_reason="",
                created_by="usr_claim",
                created_at=NOW,
                submitted_at=None,
                started_at=None,
                finished_at=None,
            )
        )
        await session.flush()
        session.add(
            t.RunExecutionIntentRow(
                run_id="run_claim",
                phase="ready",
                correlation="workspace107:run_claim",
                attempt_no=0,
                next_attempt_at=datetime(2000, 1, 1, tzinfo=UTC),
                lease_owner=None,
                lease_token=None,
                lease_generation=0,
                lease_expires_at=None,
                uncertainty_detail="",
                observed_reason="",
                created_at=NOW,
                updated_at=NOW,
                completed_at=None,
            )
        )


@pytest.mark.asyncio
async def test_alembic_upgrade_refuses_then_accepts_nonempty_terminal_data() -> None:
    engine = create_async_engine(DATABASE_URL)
    migration_env = {**os.environ, "WORKSPACE107_DATABASE_URL": DATABASE_URL}
    backend_root = Path(__file__).parents[3]
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        previous = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "upgrade", "b48640074b91"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert previous.returncode == 0, previous.stderr

        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed_run_without_intent(factory)
        rejected = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "upgrade", "head"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert rejected.returncode != 0
        assert "既有非终态 Run" in rejected.stderr

        async with factory() as session, session.begin():
            await session.execute(
                update(t.RunRow)
                .where(t.RunRow.id == "run_claim")
                .values(status="cancelled", finished_at=NOW)
            )
        accepted = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "upgrade", "head"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert accepted.returncode == 0, accepted.stderr

        async with factory() as session, session.begin():
            session.add(
                t.RunExecutionIntentRow(
                    run_id="run_claim",
                    phase="uncertain",
                    correlation="workspace107:run_claim",
                    attempt_no=1,
                    next_attempt_at=NOW,
                    lease_owner=None,
                    lease_token=None,
                    lease_generation=0,
                    lease_expires_at=None,
                    uncertainty_code="correlation_incomplete",
                    uncertainty_detail="manual gate",
                    observed_reason="",
                    created_at=NOW,
                    updated_at=NOW,
                    completed_at=None,
                )
            )
            session.add(
                t.RunSubmissionAttemptRow(
                    run_id="run_claim",
                    attempt_no=1,
                    correlation="workspace107:run_claim",
                    outcome="armed",
                    started_at=NOW,
                    detail="",
                )
            )
        downgrade_rejected = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "downgrade", "b48640074b91"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert downgrade_rejected.returncode != 0
        assert "unresolved submission attempt" in downgrade_rejected.stderr

        async with factory() as session, session.begin():
            await session.execute(
                update(t.RunExecutionIntentRow)
                .where(t.RunExecutionIntentRow.run_id == "run_claim")
                .values(phase="complete", completed_at=NOW)
            )
            await session.execute(
                update(t.RunSubmissionAttemptRow)
                .where(t.RunSubmissionAttemptRow.run_id == "run_claim")
                .values(outcome="rejected", resolved_at=NOW)
            )
        downgrade_accepted = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "downgrade", "b48640074b91"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert downgrade_accepted.returncode == 0, downgrade_accepted.stderr
        restored = await asyncio.to_thread(
            subprocess.run,
            ["alembic", "upgrade", "head"],
            cwd=backend_root,
            env=migration_env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert restored.returncode == 0, restored.stderr
    finally:
        await engine.dispose()


async def _seed_run_without_intent(factory: async_sessionmaker) -> None:
    async with factory() as session, session.begin():
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
            created_by="usr_claim",
            created_at=NOW,
        )
        session.add(
            t.UserRow(id="usr_claim", username="claim", display_name="Claim", created_at=NOW)
        )
        await session.flush()
        session.add(
            t.WorkspaceRow(
                id="ws_claim",
                kind="personal",
                name="Claim",
                description="",
                owner_id="usr_claim",
                created_at=NOW,
            )
        )
        await session.flush()
        session.add(
            t.ProjectRow(
                id="prj_claim",
                workspace_id="ws_claim",
                name="Claim",
                description="",
                status="active",
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
                sequence=1,
                message="claim",
                created_by="usr_claim",
                created_at=NOW,
            )
        )
        session.add(t.RunSnapshotRow(id="snap_claim", payload=snapshot.to_payload()))
        await session.flush()
        session.add(
            t.RunRow(
                id="run_claim",
                project_id="prj_claim",
                workspace_id="ws_claim",
                snapshot_id="snap_claim",
                compute_plan_id="plan_claim",
                source_run_configuration_id=None,
                source_run_id=None,
                name="Claim",
                status="queued",
                scheduler_job_id=None,
                exit_code=None,
                failure_reason="",
                created_by="usr_claim",
                created_at=NOW,
                submitted_at=None,
                started_at=None,
                finished_at=None,
            )
        )


@pytest.mark.asyncio
async def test_migration_guards_refuse_ambiguous_existing_data() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory)

        async with engine.begin() as connection:
            with pytest.raises(RuntimeError, match="既有非终态 Run"):
                await connection.run_sync(guard_worker_upgrade)
            await connection.execute(
                update(t.RunRow)
                .where(t.RunRow.id == "run_claim")
                .values(status="cancelled", finished_at=NOW)
            )
            await connection.execute(
                text("ALTER TABLE artifacts DROP CONSTRAINT uq_artifact_run_source_path")
            )
            for artifact_id in ("art_duplicate_a", "art_duplicate_b"):
                await connection.execute(
                    t.ArtifactRow.__table__.insert().values(
                        id=artifact_id,
                        run_id="run_claim",
                        project_id="prj_claim",
                        workspace_id="ws_claim",
                        name="duplicate",
                        source_path="outputs",
                        size=1,
                        file_count=1,
                        content_hash="a" * 64,
                        status="available",
                        description="",
                        created_at=NOW,
                    )
                )
            with pytest.raises(RuntimeError, match=r"重复 .* Artifact"):
                await connection.run_sync(guard_worker_upgrade)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_downgrade_refuses_unresolved_attempt() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory)
        async with engine.begin() as connection:
            await connection.execute(
                update(t.RunRow)
                .where(t.RunRow.id == "run_claim")
                .values(status="cancelled", finished_at=NOW)
            )
            await connection.execute(
                update(t.RunExecutionIntentRow)
                .where(t.RunExecutionIntentRow.run_id == "run_claim")
                .values(phase="complete", completed_at=NOW)
            )
            await connection.execute(
                t.RunSubmissionAttemptRow.__table__.insert().values(
                    run_id="run_claim",
                    attempt_no=1,
                    correlation="workspace107:run_claim",
                    outcome="armed",
                    started_at=NOW,
                    detail="",
                )
            )
            with pytest.raises(RuntimeError, match="unresolved submission attempt"):
                await connection.run_sync(guard_worker_downgrade)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_claim_lease_uses_database_time_and_fences_old_token() -> None:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(t.Base.metadata.drop_all)
            await connection.run_sync(t.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await _seed(factory)
        first_store = SqlExecutionStore(factory)
        second_store = SqlExecutionStore(factory)

        first, second = await asyncio.gather(
            first_store.claim_one("worker-a-clock-plus-24h", 0.2),
            second_store.claim_one("worker-b-clock-minus-24h", 0.2),
        )
        claimed = first or second
        assert claimed is not None
        assert (first is None) != (second is None)
        old_token = claimed.intent.lease_token
        assert old_token is not None

        await asyncio.sleep(0.25)
        recovered = await second_store.claim_one("worker-b-clock-minus-24h", 30)
        assert recovered is not None
        assert recovered.intent.lease_generation == 2
        assert recovered.intent.lease_token != old_token
        assert await first_store.renew("run_claim", old_token, 30) is False

        new_token = recovered.intent.lease_token
        assert new_token is not None
        attempt_no = await second_store.arm("run_claim", new_token, NOW + timedelta(seconds=32))
        assert attempt_no == 1
        assert (
            await second_store.attach_job(
                "run_claim",
                new_token,
                "job-1",
                NOW + timedelta(seconds=33),
                reconciled=False,
            )
            is True
        )
        assert (
            await second_store.attach_job(
                "run_claim",
                new_token,
                "job-1",
                NOW + timedelta(seconds=34),
                reconciled=True,
            )
            is False
        )
        await second_store.record_poll(
            "run_claim",
            new_token,
            NOW + timedelta(seconds=35),
            SchedulerJobState(state=SchedulerState.RUNNING, started_at=NOW),
        )
        await second_store.record_poll(
            "run_claim",
            new_token,
            NOW + timedelta(seconds=36),
            SchedulerJobState(state=SchedulerState.PENDING),
        )
        async with factory() as session:
            running = await session.get(t.RunRow, "run_claim")
            assert running.status == "running"

        await second_store.record_poll(
            "run_claim",
            new_token,
            NOW + timedelta(seconds=37),
            SchedulerJobState(
                state=SchedulerState.COMPLETED,
                exit_code=0,
                started_at=NOW,
                finished_at=NOW + timedelta(seconds=37),
            ),
        )
        artifact = CollectedArtifact(
            id="art_stable",
            source_path="outputs",
            name="outputs",
            optional=False,
            size=3,
            file_count=1,
            content_hash="a" * 64,
        )
        await second_store.finalize(
            "run_claim", new_token, NOW + timedelta(seconds=38), (artifact,)
        )
        with pytest.raises(LeaseLost):
            await second_store.finalize(
                "run_claim", new_token, NOW + timedelta(seconds=39), (artifact,)
            )

        async with factory() as session:
            intent = await session.get(t.RunExecutionIntentRow, "run_claim")
            attempt = await session.get(t.RunSubmissionAttemptRow, ("run_claim", 1))
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
            notifications = (
                (
                    await session.execute(
                        select(t.NotificationRow).where(t.NotificationRow.target_id == "run_claim")
                    )
                )
                .scalars()
                .all()
            )
        assert intent.phase == ExecutionPhase.COMPLETE.value
        assert attempt.outcome == "accepted"
        assert run.status == "succeeded"
        assert run.scheduler_job_id == "job-1"
        assert [event.type for event in events] == [
            "submitted",
            "started",
            "artifact_collected",
            "finished",
        ]
        assert len(artifacts) == len(activities) == len(notifications) == 1
    finally:
        await engine.dispose()
