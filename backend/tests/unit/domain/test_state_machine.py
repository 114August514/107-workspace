import pytest

from workspace107.domain.enums import RunStatus
from workspace107.domain.errors import InvalidRunTransition
from workspace107.domain.state_machine import transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunStatus.SUBMITTING, RunStatus.QUEUED),
        (RunStatus.SUBMITTING, RunStatus.FAILED),
        (RunStatus.SUBMITTING, RunStatus.CANCELLING),
        (RunStatus.QUEUED, RunStatus.RUNNING),
        (RunStatus.QUEUED, RunStatus.FAILED),
        (RunStatus.QUEUED, RunStatus.CANCELLING),
        (RunStatus.RUNNING, RunStatus.SUCCEEDED),
        (RunStatus.RUNNING, RunStatus.FAILED),
        (RunStatus.RUNNING, RunStatus.CANCELLING),
        (RunStatus.CANCELLING, RunStatus.CANCELLED),
        (RunStatus.CANCELLING, RunStatus.FAILED),
    ],
)
def test_legal_transition(current: RunStatus, target: RunStatus) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(
    "terminal",
    [RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED],
)
def test_terminal_transition_is_rejected(terminal: RunStatus) -> None:
    with pytest.raises(InvalidRunTransition, match="cannot transition"):
        transition(terminal, RunStatus.RUNNING)


def test_backward_transition_is_rejected() -> None:
    with pytest.raises(InvalidRunTransition):
        transition(RunStatus.RUNNING, RunStatus.QUEUED)
