import shlex
import sys

import pytest

from workspace107.domain.errors import ExternalCommandFailed
from workspace107.infrastructure.cluster.slurm.command_runner import (
    CommandResult,
    CommandRunner,
)
from workspace107.infrastructure.cluster.slurm.transports.local import LocalCommandRunner
from workspace107.infrastructure.cluster.slurm.transports.ssh import (
    SSH_OPTIONS,
    SshCommandRunner,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], bytes | None]] = []

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        self.calls.append((arguments, input_data))
        return CommandResult.completed(stdout=b"remote", stderr=b"", exit_code=0)


async def test_local_runner_uses_argument_array_and_binary_input() -> None:
    runner = LocalCommandRunner()
    script = (
        "import sys; data=sys.stdin.buffer.read(); "
        "sys.stdout.buffer.write(data.upper()); sys.stderr.write('note')"
    )

    result = await runner.run((sys.executable, "-c", script), input_data=b"payload")

    assert result.exit_code == 0
    assert result.stdout == b"PAYLOAD"
    assert result.stderr == b"note"
    assert result.started_at.tzinfo is not None
    assert result.finished_at >= result.started_at


async def test_local_runner_returns_nonzero_result_without_shell() -> None:
    runner = LocalCommandRunner()
    result = await runner.run(
        (
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('failed'); raise SystemExit(7)",
        )
    )

    assert result.exit_code == 7
    assert result.stderr == b"failed"


async def test_local_runner_normalizes_spawn_failure() -> None:
    runner = LocalCommandRunner()

    with pytest.raises(ExternalCommandFailed, match="could not be started"):
        await runner.run(("workspace107-command-does-not-exist",))


async def test_ssh_runner_builds_one_quoted_remote_command() -> None:
    local = RecordingRunner()
    runner = SshCommandRunner("ustc-cluster", local=local)
    remote_arguments = ("printf", "%s", "x; touch /tmp/pwned", "$(id)")

    result = await runner.run(remote_arguments, input_data=b"input")

    assert result.stdout == b"remote"
    assert local.calls == [
        (
            (
                "ssh",
                *SSH_OPTIONS,
                "ustc-cluster",
                shlex.join(remote_arguments),
            ),
            b"input",
        )
    ]


@pytest.mark.parametrize(
    "host",
    ["", "-oProxyCommand=touch /tmp/pwned", "host\nother", "host alias"],
)
def test_ssh_runner_rejects_unsafe_host_alias(host: str) -> None:
    with pytest.raises(ValueError, match="SSH host alias"):
        SshCommandRunner(host, local=RecordingRunner())


async def test_ssh_runner_rejects_empty_remote_command() -> None:
    runner = SshCommandRunner("ustc-cluster", local=RecordingRunner())

    with pytest.raises(ValueError, match="remote command"):
        await runner.run(())


def test_recording_runner_satisfies_command_contract() -> None:
    assert isinstance(RecordingRunner(), CommandRunner)
