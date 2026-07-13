from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self, runtime_checkable

from workspace107.domain.models import utc_now


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: bytes
    stderr: bytes
    exit_code: int
    started_at: datetime
    finished_at: datetime

    @classmethod
    def completed(
        cls,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        exit_code: int = 0,
    ) -> Self:
        now = utc_now()
        return cls(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            started_at=now,
            finished_at=now,
        )


@runtime_checkable
class CommandRunner(Protocol):
    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult: ...
