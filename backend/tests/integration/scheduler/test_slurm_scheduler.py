"""slurmrestd adapter candidate exercised only through deterministic HTTP fixtures."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from workspace107.config import Settings
from workspace107.domain.compute import ResolvedSchedulerConfiguration
from workspace107.domain.errors import (
    SchedulerError,
    SchedulerJobNotFound,
    SchedulerProtocolError,
    SchedulerSubmissionRejected,
    SchedulerSubmissionUncertain,
)
from workspace107.domain.ports.scheduler import SchedulerState, SchedulerSubmission
from workspace107.infrastructure.scheduler.slurm import (
    SlurmRestApiContract,
    SlurmRestScheduler,
)

JWT = "fixture-jwt-must-never-escape"
ENV_SECRET = "fixture-environment-secret"
CORRELATION = "run_01JEXACTFULLCORRELATION000000000001"


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
    work.mkdir()
    logs.mkdir()
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
    handler: httpx.AsyncBaseTransport | httpx.MockTransport,
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
        transport=handler,
    )


def test_slurm_settings_fail_fast_without_human_verified_contract() -> None:
    with pytest.raises(ValidationError, match="SLURM_API_VERSION") as captured:
        Settings(
            scheduler="slurm",
            slurm_api_base_url="https://slurm.invalid",
            slurm_api_user="fixture-user",
            slurm_jwt=JWT,
            shared_gid=10001,
        )

    assert "SLURM_TARGET_CLUSTER_ID" in str(captured.value)


def test_slurm_settings_accept_only_explicit_verified_candidate_contract() -> None:
    settings = Settings(
        scheduler="slurm",
        slurm_api_base_url="https://slurm.invalid",
        slurm_api_user="fixture-user",
        slurm_jwt=JWT,
        shared_gid=10001,
        slurm_target_cluster_id="fixture-cluster",
        slurm_api_version="v0.0.40",
        slurm_api_schema_profile="slurm-v0.0.40",
        slurm_submit_path="/fixture/v0.0.40/job/submit",
        slurm_job_path_template="/fixture/v0.0.40/job/{job_id}",
        slurm_jobs_path="/fixture/v0.0.40/jobs",
        slurm_cancel_path_template="/fixture/v0.0.40/job/{job_id}",
        slurm_correlation_field="comment",
        slurm_correlation_query_parameter="comment",
        slurm_correlation_query_complete=True,
        slurm_correlation_max_bytes=128,
        slurm_runtime_mode="native",
    )

    assert settings.slurm_api_version == "v0.0.40"
    assert JWT not in repr(settings)
    assert JWT not in str(settings)


def test_api_contract_rejects_unversioned_or_remote_paths() -> None:
    with pytest.raises(ValueError, match="API version"):
        SlurmRestApiContract(
            api_version="v0.0.40",
            target_cluster_id="fixture-cluster",
            schema_profile="slurm-v0.0.40",
            submit_path="/fixture/job/submit",
            job_path_template="https://other.invalid/v0.0.40/job/{job_id}",
            jobs_path="/fixture/v0.0.40/jobs",
            cancel_path_template="/fixture/v0.0.40/job/{job_id}",
            correlation_field="comment",
            correlation_query_parameter="comment",
            correlation_query_complete=True,
            correlation_max_bytes=128,
        )

    with pytest.raises(ValueError, match="relative to the configured host"):
        replace(
            _contract(),
            submit_path="https://other.invalid/fixture/v0.0.40/job/submit",
        )

    with pytest.raises(ValueError, match="relative to the configured host"):
        replace(
            _contract(),
            jobs_path="//other.invalid/fixture/v0.0.40/jobs",
        )

    with pytest.raises(ValueError, match="target_cluster_id"):
        replace(_contract(), target_cluster_id="")


@pytest.mark.asyncio
async def test_submit_uses_full_comment_correlation_and_keeps_secrets_out_of_script(
    tmp_path: Path,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["token"] = request.headers["X-SLURM-USER-TOKEN"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"job_id": 731})

    scheduler = _scheduler(httpx.MockTransport(handler))
    job_id = await scheduler.submit(_submission(tmp_path))

    assert job_id == "731"
    assert seen["path"] == "/fixture/v0.0.40/job/submit"
    assert seen["token"] == JWT
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["job"]["comment"] == CORRELATION
    assert payload["job"]["environment"] == {"API_KEY": ENV_SECRET}
    assert payload["job"]["tasks"] == 1
    assert f"#SBATCH --comment={CORRELATION}" in payload["script"]
    assert "#SBATCH --ntasks-per-node=1" in payload["script"]
    assert payload["script"].index("umask 0007") < payload["script"].index("module load")
    assert ENV_SECRET not in payload["script"]
    assert JWT not in payload["script"]
    assert CORRELATION not in payload["job"]["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [300, 307, 400, 401, 403, 404, 408, 409, 425, 429, 500, 502, 503, 504],
)
async def test_submit_non_2xx_is_ambiguous_and_redacted(tmp_path: Path, status: int) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=f"echoed {JWT} {ENV_SECRET}")

    scheduler = _scheduler(httpx.MockTransport(handler))
    with pytest.raises(SchedulerSubmissionUncertain) as captured:
        await scheduler.submit(_submission(tmp_path))

    message = str(captured.value)
    assert str(status) in message
    assert JWT not in message
    assert ENV_SECRET not in message


@pytest.mark.asyncio
async def test_submit_timeout_is_ambiguous_and_redacted(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout with {JWT}", request=request)

    scheduler = _scheduler(httpx.MockTransport(handler))
    with pytest.raises(SchedulerSubmissionUncertain) as captured:
        await scheduler.submit(_submission(tmp_path))

    assert JWT not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.asyncio
async def test_submit_rejects_unsafe_correlation_before_http(tmp_path: Path) -> None:
    def unexpected_http(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid correlation must fail before HTTP")

    scheduler = _scheduler(httpx.MockTransport(unexpected_http))
    submission = replace(_submission(tmp_path), correlation="run_ok\n#SBATCH --export=ALL")

    with pytest.raises(SchedulerSubmissionRejected, match="correlation"):
        await scheduler.submit(submission)


@pytest.mark.asyncio
async def test_submit_rejects_multi_node_total_resources_before_http(tmp_path: Path) -> None:
    def unexpected_http(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("multi-node submissions must fail before HTTP")

    scheduler = _scheduler(httpx.MockTransport(unexpected_http))

    with pytest.raises(SchedulerSubmissionRejected, match="nodes=1"):
        await scheduler.submit(_submission(tmp_path, nodes=2))


@pytest.mark.asyncio
async def test_submit_success_without_job_id_is_ambiguous_protocol_error(tmp_path: Path) -> None:
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200, json={})))
    with pytest.raises(SchedulerSubmissionUncertain, match="job_id"):
        await scheduler.submit(_submission(tmp_path))


@pytest.mark.asyncio
async def test_submit_rejects_target_cluster_mismatch_before_http(tmp_path: Path) -> None:
    def unexpected_http(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("cluster mismatch must fail before HTTP")

    scheduler = _scheduler(httpx.MockTransport(unexpected_http))

    with pytest.raises(SchedulerSubmissionRejected, match="target cluster"):
        await scheduler.submit(_submission(tmp_path, cluster="different-cluster"))


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
async def test_poll_maps_supported_states_and_exit_data(
    raw_state: object, expected: SchedulerState
) -> None:
    payload = {
        "jobs": [
            {
                "job_id": 731,
                "job_state": raw_state,
                "exit_code": {"return_code": {"number": 7}},
                "start_time": {"number": 1_700_000_000},
                "end_time": {"number": 1_700_000_100},
                "state_reason": "fixture reason",
            }
        ]
    }
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)))

    state = await scheduler.poll("731")

    assert state.state is expected
    assert state.exit_code == 7
    assert state.started_at is not None
    assert state.finished_at is not None


@pytest.mark.asyncio
async def test_poll_404_and_empty_jobs_are_unknown() -> None:
    responses = iter([httpx.Response(404), httpx.Response(200, json={"jobs": []})])
    scheduler = _scheduler(httpx.MockTransport(lambda _request: next(responses)))

    missing = await scheduler.poll("404")
    empty = await scheduler.poll("405")

    assert missing.state is SchedulerState.UNKNOWN
    assert empty.state is SchedulerState.UNKNOWN


@pytest.mark.asyncio
async def test_poll_redacts_authentication_secret_before_returning_reason() -> None:
    scheduler = _scheduler(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "job_id": 731,
                            "job_state": "FAILED",
                            "state_reason": f"token={JWT}",
                        }
                    ]
                },
            )
        )
    )

    state = await scheduler.poll("731")

    assert state.state is SchedulerState.FAILED
    assert JWT not in state.reason
    assert "[REDACTED]" in state.reason


@pytest.mark.asyncio
async def test_poll_protocol_error_is_explicit_and_redacted() -> None:
    scheduler = _scheduler(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"jobs": [{"job_id": 731, "job_state": {"secret": JWT}}]},
            )
        )
    )

    with pytest.raises(SchedulerProtocolError) as captured:
        await scheduler.poll("731")

    assert JWT not in str(captured.value)


@pytest.mark.asyncio
async def test_poll_and_cancel_http_errors_are_explicit_and_redacted() -> None:
    scheduler = _scheduler(
        httpx.MockTransport(lambda _request: httpx.Response(503, text=f"echoed {JWT} {ENV_SECRET}"))
    )

    with pytest.raises(SchedulerError, match="poll returned HTTP 503") as poll_error:
        await scheduler.poll("731")
    with pytest.raises(SchedulerError, match="cancel returned HTTP 503") as cancel_error:
        await scheduler.cancel("731")

    assert JWT not in str(poll_error.value)
    assert ENV_SECRET not in str(poll_error.value)
    assert JWT not in str(cancel_error.value)
    assert ENV_SECRET not in str(cancel_error.value)


@pytest.mark.asyncio
async def test_cancel_uses_configured_path_and_404_is_not_success() -> None:
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
async def test_find_by_correlation_complete_zero_one_and_multiple(
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
@pytest.mark.parametrize("response", [httpx.Response(403), httpx.Response(500)])
async def test_find_by_correlation_http_failure_is_incomplete(response: httpx.Response) -> None:
    scheduler = _scheduler(httpx.MockTransport(lambda _request: response))

    result = await scheduler.find_by_correlation(CORRELATION)

    assert result.complete is False
    assert result.job_ids == ()
    assert result.reason


@pytest.mark.asyncio
async def test_find_by_correlation_network_failure_is_incomplete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout with {JWT}", request=request)

    result = await _scheduler(httpx.MockTransport(handler)).find_by_correlation(CORRELATION)

    assert result.complete is False
    assert result.job_ids == ()
    assert result.reason


@pytest.mark.asyncio
async def test_find_by_correlation_pagination_or_schema_uncertainty_is_incomplete() -> None:
    responses = iter(
        [
            httpx.Response(200, json={"jobs": [], "pagination": {"complete": True}}),
            httpx.Response(200, json={"jobs": [], "meta": {"has_more": False}}),
            httpx.Response(200, json={"jobs": [], "next_cursor": ""}),
            httpx.Response(200, json={"jobs": "not-a-list"}),
            httpx.Response(200, json={"jobs": [{"job_id": 731}]}),
            httpx.Response(
                200,
                json={"jobs": [{"job_id": 731, "comment": "another-run"}]},
            ),
            httpx.Response(200, json={"jobs": [], "warnings": ["partial result"]}),
            httpx.Response(
                200,
                json={
                    "jobs": [
                        {"job_id": 731, "comment": CORRELATION},
                        {"job_id": 731, "comment": CORRELATION},
                    ]
                },
            ),
        ]
    )
    scheduler = _scheduler(httpx.MockTransport(lambda _request: next(responses)))

    for _ in range(8):
        result = await scheduler.find_by_correlation(CORRELATION)
        assert result.complete is False
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
async def test_native_runtime_refuses_unapplied_environment_image(tmp_path: Path) -> None:
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200)))

    with pytest.raises(SchedulerSubmissionRejected, match="environment_image"):
        await scheduler.submit(_submission(tmp_path, image="image-not-actually-applied"))


def test_apptainer_runtime_fails_fast_until_human_capability_gate() -> None:
    with pytest.raises(ValueError, match="Apptainer"):
        _scheduler(
            httpx.MockTransport(lambda _request: httpx.Response(200)), runtime_mode="apptainer"
        )


def test_scheduler_repr_never_contains_authentication_secret() -> None:
    scheduler = _scheduler(httpx.MockTransport(lambda _request: httpx.Response(200)))

    assert JWT not in repr(scheduler)
    assert JWT not in str(scheduler)
