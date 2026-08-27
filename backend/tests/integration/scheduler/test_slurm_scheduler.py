"""Deterministic fixtures for the locally covered slurmrestd adapter profile."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.errors import (
    SchedulerError,
    SchedulerJobNotFound,
    SchedulerProtocolError,
    SchedulerSubmissionRejected,
    SchedulerSubmissionUncertain,
)
from workspace107.domain.ports.scheduler import SchedulerState, SchedulerSubmission
from workspace107.infrastructure.scheduler.slurm import SlurmRestApiContract, SlurmRestScheduler

JWT = "fixture-jwt-must-never-escape"
ENV_SECRET = "fixture-environment-secret"
CORRELATION = "run_01JEXACT:snapshot_01:version_01:0123456789abcdef"


def _contract(*, complete: bool = True) -> SlurmRestApiContract:
    return SlurmRestApiContract(
        target_cluster_id="fixture-cluster",
        api_version="v0.0.40",
        schema_profile="slurm-v0.0.40",
        submit_path="/fixture/v0.0.40/job/submit",
        job_path_template="/fixture/v0.0.40/job/{job_id}",
        jobs_path="/fixture/v0.0.40/jobs",
        cancel_path_template="/fixture/v0.0.40/job/{job_id}",
        correlation_field="comment",
        correlation_query_parameter="comment",
        correlation_query_complete=complete,
        correlation_max_bytes=128,
    )


def _submission(
    root: Path, *, image: str = "", nodes: int = 1, cluster: str = "fixture-cluster"
) -> SchedulerSubmission:
    work = root / "work"
    logs = root / "logs"
    work.mkdir(parents=True)
    logs.mkdir(parents=True)
    return SchedulerSubmission(
        run_id="run_fixture",
        correlation=CORRELATION,
        job_name="visible-name-" + "x" * 100,
        work_dir=work,
        command="python main.py",
        setup_command="module load python/3.12",
        environment_image=image,
        stdout_path=logs / "stdout.log",
        stderr_path=logs / "stderr.log",
        configuration=ResolvedSchedulerConfiguration(
            cluster=cluster,
            account="fixture-account",
            partition="fixture-partition",
            qos="fixture-qos",
            nodes=nodes,
            cpus=2,
            memory_mb=1024,
            gpus=1,
            time_limit_minutes=5,
        ),
        environment={"API_KEY": ENV_SECRET},
    )


def _scheduler(
    transport: httpx.AsyncBaseTransport,
    *,
    complete: bool = True,
    runtime_mode: str = "native",
) -> SlurmRestScheduler:
    return SlurmRestScheduler(
        base_url="https://slurm.invalid",
        user="fixture-user",
        jwt=JWT,
        contract=_contract(complete=complete),
        runtime_mode=runtime_mode,
        timeout=0.1,
        transport=transport,
    )


@pytest.mark.parametrize("version", ["v0.0.41", "v0.0.42", "v0.0.43", "v0.0.44"])
def test_contract_rejects_unverified_profile_version_and_paths(version: str) -> None:
    with pytest.raises(ValueError, match="unsupported Slurm schema profile"):
        replace(_contract(), schema_profile=f"slurm-{version}")
    with pytest.raises(ValueError, match="not covered"):
        replace(_contract(), api_version=version)
    with pytest.raises(ValueError, match="relative to the configured host"):
        replace(_contract(), jobs_path="//other.invalid/fixture/v0.0.40/jobs")


@pytest.mark.asyncio
async def test_submit_uses_full_correlation_and_keeps_secrets_out_of_script(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"job_id": 731})

    job_id = await _scheduler(httpx.MockTransport(handler)).submit(_submission(tmp_path))

    assert job_id == "731"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["job"]["comment"] == CORRELATION
    assert payload["job"]["tasks"] == 1
    assert f"#SBATCH --comment={CORRELATION}" in payload["script"]
    assert "#SBATCH --ntasks-per-node=1" in payload["script"]
    assert ENV_SECRET not in payload["script"]
    assert JWT not in payload["script"]
    assert CORRELATION not in payload["job"]["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [300, 400, 401, 404, 409, 500, 503])
async def test_submit_non_2xx_is_ambiguous_and_secret_safe(tmp_path: Path, status: int) -> None:
    scheduler = _scheduler(
        httpx.MockTransport(
            lambda _request: httpx.Response(status, text=f"echoed {JWT} {ENV_SECRET}")
        )
    )

    with pytest.raises(SchedulerSubmissionUncertain) as captured:
        await scheduler.submit(_submission(tmp_path))

    assert str(status) in str(captured.value)
    assert JWT not in str(captured.value)
    assert ENV_SECRET not in str(captured.value)


@pytest.mark.asyncio
async def test_submit_transport_failure_and_missing_job_id_are_ambiguous(tmp_path: Path) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout with {JWT}", request=request)

    with pytest.raises(SchedulerSubmissionUncertain) as timeout_error:
        await _scheduler(httpx.MockTransport(timeout)).submit(_submission(tmp_path))
    assert timeout_error.value.__cause__ is None
    assert JWT not in str(timeout_error.value)

    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200, json={})))
    with pytest.raises(SchedulerSubmissionUncertain, match="job_id"):
        await scheduler.submit(_submission(tmp_path / "second"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"correlation": "run_ok\n#SBATCH --export=ALL"}, "correlation"),
        ({"environment_image": "image-not-applied"}, "environment_image"),
    ],
)
async def test_submit_explicit_local_rejection_precedes_http(
    tmp_path: Path, change: dict[str, str], message: str
) -> None:
    def unexpected(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("local rejection must not reach HTTP")

    submission = replace(_submission(tmp_path), **change)
    with pytest.raises(SchedulerSubmissionRejected, match=message):
        await _scheduler(httpx.MockTransport(unexpected)).submit(submission)


@pytest.mark.asyncio
async def test_submit_rejects_cluster_mismatch_and_multi_node(tmp_path: Path) -> None:
    def unexpected(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not reach HTTP")

    transport = httpx.MockTransport(unexpected)
    scheduler = _scheduler(transport)
    with pytest.raises(SchedulerSubmissionRejected, match="target cluster"):
        await scheduler.submit(_submission(tmp_path / "cluster", cluster="other"))
    with pytest.raises(SchedulerSubmissionRejected, match="nodes=1"):
        await scheduler.submit(_submission(tmp_path / "nodes", nodes=2))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jobs", "expected_ids"),
    [
        ([], ()),
        ([{"job_id": 731, "comment": CORRELATION}], ("731",)),
        (
            [
                {"job_id": 731, "comment": CORRELATION},
                {"job_id": 732, "comment": CORRELATION},
            ],
            ("731", "732"),
        ),
    ],
)
async def test_find_by_correlation_exact_zero_one_and_multiple(
    jobs: list[dict[str, object]], expected_ids: tuple[str, ...]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["comment"] == CORRELATION
        return httpx.Response(200, json={"jobs": jobs, "errors": [], "warnings": []})

    result = await _scheduler(httpx.MockTransport(handler)).find_by_correlation(CORRELATION)

    assert result.complete is True
    assert result.job_ids == expected_ids
    assert result.reason == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"jobs": [], "pagination": {"complete": True}},
        {"jobs": [], "meta": {"has_more": False}},
        {"jobs": [], "next_cursor": ""},
        {"jobs": "not-a-list"},
        {"jobs": [{"job_id": 731}]},
        {"jobs": [{"job_id": 731, "comment": "another-run"}]},
        {"jobs": [], "warnings": ["partial result"]},
        {
            "jobs": [
                {"job_id": 731, "comment": CORRELATION},
                {"job_id": 731, "comment": CORRELATION},
            ]
        },
    ],
)
async def test_find_by_correlation_never_claims_incomplete_or_paginated_results_complete(
    payload: dict[str, object],
) -> None:
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)))
    result = await scheduler.find_by_correlation(CORRELATION)
    assert result.complete is False
    assert result.job_ids == ()
    assert result.reason


@pytest.mark.asyncio
async def test_find_by_correlation_requires_verified_complete_query() -> None:
    scheduler = _scheduler(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={"jobs": []})),
        complete=False,
    )
    result = await scheduler.find_by_correlation(CORRELATION)
    assert result.complete is False
    assert result.job_ids == ()
    assert result.reason


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 500])
async def test_find_by_correlation_http_failure_is_incomplete_and_secret_safe(status: int) -> None:
    scheduler = _scheduler(
        httpx.MockTransport(lambda _request: httpx.Response(status, text=f"{JWT} {ENV_SECRET}"))
    )
    result = await scheduler.find_by_correlation(CORRELATION)
    assert result.complete is False
    assert result.job_ids == ()
    assert JWT not in result.reason
    assert ENV_SECRET not in result.reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_state", "expected"),
    [
        ("PENDING", SchedulerState.PENDING),
        (["RUNNING"], SchedulerState.RUNNING),
        ("COMPLETED", SchedulerState.COMPLETED),
        ("OUT_OF_MEMORY", SchedulerState.FAILED),
        ("CANCELLED+", SchedulerState.CANCELLED),
        ("SITE_PRIVATE_STATE", SchedulerState.UNKNOWN),
    ],
)
async def test_poll_maps_states_and_exit_data(raw_state: object, expected: SchedulerState) -> None:
    payload = {
        "jobs": [
            {
                "job_id": 731,
                "job_state": raw_state,
                "exit_code": {"return_code": {"number": 7}},
                "start_time": {"number": 1_700_000_000},
                "end_time": {"number": 1_700_000_100},
                "state_reason": f"token={JWT}",
            }
        ]
    }
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)))
    state = await scheduler.poll("731")
    assert state.state is expected
    assert state.exit_code == 7
    assert state.started_at is not None
    assert state.finished_at is not None
    assert JWT not in state.reason


@pytest.mark.asyncio
async def test_poll_zero_jobs_and_404_are_unknown_but_bad_shape_is_protocol_error() -> None:
    responses = iter(
        [
            httpx.Response(404),
            httpx.Response(200, json={"jobs": []}),
            httpx.Response(200, json={"jobs": "bad"}),
        ]
    )
    scheduler = _scheduler(httpx.MockTransport(lambda _request: next(responses)))
    assert (await scheduler.poll("404")).state is SchedulerState.UNKNOWN
    assert (await scheduler.poll("405")).state is SchedulerState.UNKNOWN
    with pytest.raises(SchedulerProtocolError):
        await scheduler.poll("406")


@pytest.mark.asyncio
async def test_cancel_uses_encoded_configured_path_and_404_is_explicit() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path.decode())
        return httpx.Response(204) if len(seen) == 1 else httpx.Response(404)

    scheduler = _scheduler(httpx.MockTransport(handler))
    await scheduler.cancel("731/unsafe")
    with pytest.raises(SchedulerJobNotFound):
        await scheduler.cancel("missing")
    assert seen[0] == "/fixture/v0.0.40/job/731%2Funsafe"


@pytest.mark.asyncio
async def test_poll_and_cancel_errors_never_echo_response_secrets() -> None:
    scheduler = _scheduler(
        httpx.MockTransport(lambda _request: httpx.Response(503, text=f"{JWT} {ENV_SECRET}"))
    )
    with pytest.raises(SchedulerError) as poll_error:
        await scheduler.poll("731")
    with pytest.raises(SchedulerError) as cancel_error:
        await scheduler.cancel("731")
    for error in (poll_error.value, cancel_error.value):
        assert JWT not in str(error)
        assert ENV_SECRET not in str(error)


def test_runtime_and_repr_keep_unverified_capabilities_gated() -> None:
    with pytest.raises(ValueError, match="Apptainer"):
        _scheduler(
            httpx.MockTransport(lambda _request: httpx.Response(200)),
            runtime_mode="apptainer",
        )
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200)))
    assert JWT not in repr(scheduler)
    assert JWT not in str(scheduler)
