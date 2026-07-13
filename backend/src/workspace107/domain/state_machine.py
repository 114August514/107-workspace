from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import InvalidRunTransition

_ALLOWED: dict[RunStatus, set[RunStatus]] = {
    RunStatus.SUBMITTING: {RunStatus.QUEUED, RunStatus.FAILED, RunStatus.CANCELLING},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLING},
    RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLING},
    RunStatus.CANCELLING: {RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.SUCCEEDED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


def transition(current: RunStatus, target: RunStatus) -> RunStatus:
    if target not in _ALLOWED[current]:
        raise InvalidRunTransition(f"cannot transition {current} to {target}")
    return target
