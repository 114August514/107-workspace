from collections.abc import AsyncIterator

import pytest

from workspace107.domain.enums import ArtifactKind, RunStatus
from workspace107.domain.errors import ResourceNotFound
from workspace107.domain.models import RunSubmission

from .conftest import ClusterHarness


async def read_all(source: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in source])


async def finish(harness: ClusterHarness, submission: RunSubmission) -> str:
    job = await harness.adapter.submit(submission)
    harness.clock.advance(harness.queue_seconds + harness.run_seconds)
    return job.external_job_id


async def test_cluster_lifecycle_logs_and_artifacts(
    cluster_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    checks = await cluster_harness.adapter.preflight(valid_submission)
    assert checks
    assert all(check.passed for check in checks)

    job = await cluster_harness.adapter.submit(valid_submission)
    queued = await cluster_harness.adapter.status(job.external_job_id)
    cluster_harness.clock.advance(cluster_harness.queue_seconds)
    running = await cluster_harness.adapter.status(job.external_job_id)
    cluster_harness.clock.advance(cluster_harness.run_seconds)
    succeeded = await cluster_harness.adapter.status(job.external_job_id)
    log = await cluster_harness.adapter.read_log(job.external_job_id, 0)
    artifacts = await cluster_harness.adapter.collect_artifacts(job.external_job_id)
    result = next(artifact for artifact in artifacts if artifact.kind is ArtifactKind.RESULT)
    content = await read_all(
        cluster_harness.adapter.open_artifact(job.external_job_id, result.artifact_key)
    )

    assert queued.status is RunStatus.QUEUED
    assert running.status is RunStatus.RUNNING
    assert succeeded.status is RunStatus.SUCCEEDED
    assert succeeded.exit_code == 0
    assert log.data
    assert log.end_of_stream
    assert artifacts
    assert content
    assert job.external_job_id.encode() in content


async def test_deterministic_failure(
    failure_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    external_job_id = await finish(failure_harness, valid_submission)

    observation = await failure_harness.adapter.status(external_job_id)
    artifacts = await failure_harness.adapter.collect_artifacts(external_job_id)

    assert observation.status is RunStatus.FAILED
    assert observation.exit_code == 1
    assert tuple(artifact.kind for artifact in artifacts) == (ArtifactKind.LOG,)


async def test_cancel_is_idempotent_and_terminal_jobs_stay_terminal(
    cluster_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    cancelled = await cluster_harness.adapter.submit(valid_submission)
    await cluster_harness.adapter.cancel(cancelled.external_job_id)
    await cluster_harness.adapter.cancel(cancelled.external_job_id)

    assert (
        await cluster_harness.adapter.status(cancelled.external_job_id)
    ).status is RunStatus.CANCELLED

    succeeded = await finish(cluster_harness, valid_submission)
    assert (await cluster_harness.adapter.status(succeeded)).status is RunStatus.SUCCEEDED
    await cluster_harness.adapter.cancel(succeeded)
    assert (await cluster_harness.adapter.status(succeeded)).status is RunStatus.SUCCEEDED


async def test_unknown_job_and_artifact_are_not_found(
    cluster_harness: ClusterHarness,
) -> None:
    with pytest.raises(ResourceNotFound):
        await cluster_harness.adapter.status("missing")
    with pytest.raises(ResourceNotFound):
        await cluster_harness.adapter.cancel("missing")
    with pytest.raises(ResourceNotFound):
        await cluster_harness.adapter.read_log("missing", 0)
    with pytest.raises(ResourceNotFound):
        await cluster_harness.adapter.collect_artifacts("missing")
    with pytest.raises(ResourceNotFound):
        await read_all(cluster_harness.adapter.open_artifact("missing", "result"))


async def test_log_reads_resume_from_byte_offset(
    cluster_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    job = await cluster_harness.adapter.submit(valid_submission)
    queued = await cluster_harness.adapter.read_log(job.external_job_id, 0)
    repeated = await cluster_harness.adapter.read_log(job.external_job_id, queued.next_offset)
    cluster_harness.clock.advance(cluster_harness.queue_seconds)
    running = await cluster_harness.adapter.read_log(job.external_job_id, queued.next_offset)
    cluster_harness.clock.advance(cluster_harness.run_seconds)
    terminal = await cluster_harness.adapter.read_log(
        job.external_job_id,
        running.next_offset,
    )

    assert "queued" in queued.data
    assert repeated.data == ""
    assert not repeated.end_of_stream
    assert running.offset == queued.next_offset
    assert "running" in running.data
    assert terminal.offset == running.next_offset
    assert "succeeded" in terminal.data
    assert terminal.end_of_stream


async def test_terminal_artifact_collection_is_idempotent(
    cluster_harness: ClusterHarness,
    valid_submission: RunSubmission,
) -> None:
    external_job_id = await finish(cluster_harness, valid_submission)

    first = await cluster_harness.adapter.collect_artifacts(external_job_id)
    second = await cluster_harness.adapter.collect_artifacts(external_job_id)
    first_content = await read_all(
        cluster_harness.adapter.open_artifact(external_job_id, first[0].artifact_key)
    )
    second_content = await read_all(
        cluster_harness.adapter.open_artifact(external_job_id, second[0].artifact_key)
    )

    assert first == second
    assert first_content == second_content
