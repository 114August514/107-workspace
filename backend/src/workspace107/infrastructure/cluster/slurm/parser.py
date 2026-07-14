import re
from datetime import datetime

from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import ClusterUnavailable
from workspace107.domain.models import JobObservation

_SBATCH_OUTPUT = re.compile(r"(?P<job_id>[0-9]+)(?:;[A-Za-z0-9_.-]+)?")
_ACTIVE_STATES = {
    "PENDING": RunStatus.QUEUED,
    "CONFIGURING": RunStatus.QUEUED,
    "RUNNING": RunStatus.RUNNING,
    "COMPLETING": RunStatus.RUNNING,
}
_TERMINAL_STATES = {
    "COMPLETED": RunStatus.SUCCEEDED,
    "CANCELLED": RunStatus.CANCELLED,
    "FAILED": RunStatus.FAILED,
    "TIMEOUT": RunStatus.FAILED,
    "NODE_FAIL": RunStatus.FAILED,
    "OUT_OF_MEMORY": RunStatus.FAILED,
}


def _text(output: str | bytes) -> str:
    if isinstance(output, str):
        return output
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ClusterUnavailable("Slurm returned non-UTF-8 output") from error


def _state(value: str) -> str:
    return value.strip().split(maxsplit=1)[0].rstrip("+").upper()


def parse_squeue(output: str | bytes, observed_at: datetime) -> JobObservation | None:
    lines = [line.strip() for line in _text(output).splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) != 1:
        raise ClusterUnavailable("Slurm returned multiple active job records")
    fields = lines[0].split("|")
    if len(fields) != 4 or not fields[0].strip():
        raise ClusterUnavailable("Slurm returned a malformed active job record")
    raw_state = fields[1].strip()
    status = _ACTIVE_STATES.get(_state(raw_state))
    if status is None:
        raise ClusterUnavailable("Slurm returned an unsupported active job state")
    return JobObservation(
        status=status,
        observed_at=observed_at,
        details={
            "raw_state": raw_state,
            "node": fields[2].strip(),
            "start": fields[3].strip(),
        },
    )


def parse_sacct(output: str | bytes, external_job_id: str, observed_at: datetime) -> JobObservation:
    selected: list[str] | None = None
    for line in _text(output).splitlines():
        if not line.strip():
            continue
        fields = line.strip().split("|")
        if len(fields) != 5:
            raise ClusterUnavailable("Slurm returned a malformed accounting record")
        if fields[0].strip() == external_job_id:
            selected = fields
            break
    if selected is None:
        raise ClusterUnavailable("Slurm accounting did not contain the requested job record")

    raw_state = selected[1].strip()
    status = _TERMINAL_STATES.get(_state(raw_state))
    if status is None:
        raise ClusterUnavailable("Slurm returned an unsupported terminal job state")
    exit_value = selected[2].strip()
    if not re.fullmatch(r"[0-9]+:[0-9]+", exit_value):
        raise ClusterUnavailable("Slurm returned a malformed exit code")
    exit_code = int(exit_value.split(":", maxsplit=1)[0])
    return JobObservation(
        status=status,
        observed_at=observed_at,
        exit_code=exit_code,
        details={
            "raw_state": raw_state,
            "start": selected[3].strip(),
            "end": selected[4].strip(),
        },
    )


def parse_sbatch_job_id(output: str | bytes) -> str:
    value = _text(output).strip()
    match = _SBATCH_OUTPUT.fullmatch(value)
    if match is None:
        raise ClusterUnavailable("Slurm returned a malformed submission identifier")
    return match.group("job_id")
