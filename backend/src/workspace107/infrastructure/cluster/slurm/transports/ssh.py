import re
import shlex

from workspace107.infrastructure.cluster.slurm.command_runner import (
    CommandResult,
    CommandRunner,
)
from workspace107.infrastructure.cluster.slurm.transports.local import LocalCommandRunner

SSH_OPTIONS = (
    "-o",
    "ControlMaster=no",
    "-o",
    "ControlPath=none",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "ServerAliveInterval=15",
    "-o",
    "ServerAliveCountMax=3",
)
_HOST_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def validate_ssh_host(host: str) -> str:
    if _HOST_ALIAS.fullmatch(host) is None:
        raise ValueError("SSH host alias contains unsupported characters")
    return host


def ssh_argv(host: str, remote_arguments: tuple[str, ...]) -> tuple[str, ...]:
    if not remote_arguments:
        raise ValueError("remote command cannot be empty")
    return ("ssh", *SSH_OPTIONS, validate_ssh_host(host), shlex.join(remote_arguments))


class SshCommandRunner:
    def __init__(self, host: str, *, local: CommandRunner | None = None) -> None:
        self._host = validate_ssh_host(host)
        self._local = local or LocalCommandRunner()

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        return await self._local.run(
            ssh_argv(self._host, arguments),
            input_data=input_data,
        )
