import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol, Self, runtime_checkable

from workspace107.domain.errors import TransferFailed


@dataclass(frozen=True, slots=True)
class PipelineResult:
    writer_exit_code: int
    reader_exit_code: int
    writer_stderr: bytes
    reader_stderr: bytes

    @classmethod
    def completed(
        cls,
        *,
        writer_exit_code: int = 0,
        reader_exit_code: int = 0,
        writer_stderr: bytes = b"",
        reader_stderr: bytes = b"",
    ) -> Self:
        return cls(
            writer_exit_code=writer_exit_code,
            reader_exit_code=reader_exit_code,
            writer_stderr=writer_stderr,
            reader_stderr=reader_stderr,
        )


@runtime_checkable
class PipelineRunner(Protocol):
    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult: ...


class SubprocessPipelineRunner:
    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult:
        if not writer_arguments or not reader_arguments:
            raise ValueError("pipeline commands cannot be empty")
        read_fd, write_fd = os.pipe()
        writer: asyncio.subprocess.Process | None = None
        reader: asyncio.subprocess.Process | None = None
        try:
            try:
                writer = await asyncio.create_subprocess_exec(
                    *writer_arguments,
                    stdout=write_fd,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as error:
                raise TransferFailed("Transfer pipeline could not be started.") from error
            os.close(write_fd)
            write_fd = -1
            try:
                reader = await asyncio.create_subprocess_exec(
                    *reader_arguments,
                    stdin=read_fd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as error:
                raise TransferFailed("Transfer pipeline could not be started.") from error
            os.close(read_fd)
            read_fd = -1

            (_, writer_stderr), (_, reader_stderr) = await asyncio.gather(
                writer.communicate(),
                reader.communicate(),
            )
        except BaseException:
            await self._terminate(writer, reader)
            raise
        finally:
            if write_fd >= 0:
                os.close(write_fd)
            if read_fd >= 0:
                os.close(read_fd)

        if writer.returncode is None or reader.returncode is None:
            raise TransferFailed("Transfer pipeline did not report an exit code.")
        return PipelineResult(
            writer_exit_code=writer.returncode,
            reader_exit_code=reader.returncode,
            writer_stderr=writer_stderr,
            reader_stderr=reader_stderr,
        )

    @staticmethod
    async def _terminate(*processes: asyncio.subprocess.Process | None) -> None:
        active = tuple(process for process in processes if process is not None)
        for process in active:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.terminate()
        await asyncio.gather(*(process.wait() for process in active), return_exceptions=True)
