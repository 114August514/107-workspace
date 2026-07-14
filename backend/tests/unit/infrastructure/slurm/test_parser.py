from datetime import UTC, datetime

import pytest

from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import ClusterUnavailable
from workspace107.infrastructure.cluster.slurm.parser import (
    parse_sacct,
    parse_sbatch_job_id,
    parse_squeue,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("PENDING", RunStatus.QUEUED),
        ("CONFIGURING", RunStatus.QUEUED),
        ("RUNNING", RunStatus.RUNNING),
        ("COMPLETING", RunStatus.RUNNING),
    ],
)
def test_parse_squeue_active_states(state: str, expected: RunStatus) -> None:
    observation = parse_squeue(f"123|{state}|gpu01|2026-01-01T00:00:00\n", NOW)

    assert observation is not None
    assert observation.status is expected
    assert observation.observed_at == NOW
    assert observation.details["raw_state"] == state
    assert observation.details["node"] == "gpu01"


def test_parse_squeue_empty_means_not_active() -> None:
    assert parse_squeue("\n", NOW) is None


def test_parse_squeue_rejects_multiple_active_records() -> None:
    with pytest.raises(ClusterUnavailable, match="multiple active"):
        parse_squeue(
            "123|RUNNING|gpu01|start\n124|PENDING|(null)|N/A\n",
            NOW,
        )


@pytest.mark.parametrize(
    ("state", "expected", "exit_code"),
    [
        ("COMPLETED", RunStatus.SUCCEEDED, 0),
        ("CANCELLED by 1000", RunStatus.CANCELLED, 0),
        ("FAILED", RunStatus.FAILED, 1),
        ("TIMEOUT", RunStatus.FAILED, 1),
        ("NODE_FAIL", RunStatus.FAILED, 1),
        ("OUT_OF_MEMORY", RunStatus.FAILED, 137),
    ],
)
def test_parse_sacct_terminal_states(
    state: str,
    expected: RunStatus,
    exit_code: int,
) -> None:
    output = (
        "123.batch|COMPLETED|0:0|2026-01-01T00:00:01|2026-01-01T00:00:02\n"
        f"123|{state}|{exit_code}:0|2026-01-01T00:00:01|2026-01-01T00:00:02\n"
    )

    observation = parse_sacct(output, "123", NOW)

    assert observation.status is expected
    assert observation.exit_code == exit_code
    assert observation.details["raw_state"] == state


@pytest.mark.parametrize(
    "output",
    [
        "123|UNKNOWN|node|time\n",
        "not-delimited\n",
    ],
)
def test_parse_squeue_rejects_unknown_or_malformed_output(output: str) -> None:
    with pytest.raises(ClusterUnavailable):
        parse_squeue(output, NOW)


@pytest.mark.parametrize(
    "output",
    [
        "123|MYSTERY|0:0|start|end\n",
        "123|COMPLETED|bad|start|end\n",
    ],
)
def test_parse_sacct_rejects_unknown_or_malformed_output(output: str) -> None:
    with pytest.raises(ClusterUnavailable):
        parse_sacct(output, "123", NOW)


def test_parse_sacct_missing_main_job_is_not_found() -> None:
    with pytest.raises(ClusterUnavailable, match="job record"):
        parse_sacct("123.batch|COMPLETED|0:0|start|end\n", "123", NOW)


def test_parse_sacct_skips_blank_lines_and_rejects_malformed_record() -> None:
    observation = parse_sacct("\n123|COMPLETED|0:0|start|end\n", "123", NOW)
    assert observation.status is RunStatus.SUCCEEDED

    with pytest.raises(ClusterUnavailable, match="malformed accounting"):
        parse_sacct("123|COMPLETED|0:0|start\n", "123", NOW)


def test_parse_sbatch_parsable_output() -> None:
    assert parse_sbatch_job_id("12345;cluster\n") == "12345"


def test_parse_rejects_non_utf8_command_output() -> None:
    with pytest.raises(ClusterUnavailable, match="non-UTF-8"):
        parse_sbatch_job_id(b"\xff")


@pytest.mark.parametrize("output", ["", "Submitted batch job 123", "123;bad;extra", "x$(id)"])
def test_parse_sbatch_rejects_malformed_output(output: str) -> None:
    with pytest.raises(ClusterUnavailable):
        parse_sbatch_job_id(output)
