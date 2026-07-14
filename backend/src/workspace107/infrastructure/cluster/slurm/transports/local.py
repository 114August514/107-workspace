import asyncio

from workspace107.domain.errors import ExternalCommandFailed
from workspace107.domain.models import utc_now
from workspace107.infrastructure.cluster.slurm.command_runner import CommandResult


class LocalCommandRunner:
    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        if not arguments:
            raise ValueError("external command cannot be empty")
        started_at = utc_now()
        try:
            process = await asyncio.create_subprocess_exec(
                *arguments,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as error:
            raise ExternalCommandFailed("External command could not be started.") from error

        try:
            stdout, stderr = await process.communicate(input_data)
        except BaseException:
            if process.returncode is None:
                process.terminate()
                await process.wait()
            raise
        if process.returncode is None:
            raise ExternalCommandFailed("External command did not report an exit code.")
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=process.returncode,
            started_at=started_at,
            finished_at=utc_now(),
        )
