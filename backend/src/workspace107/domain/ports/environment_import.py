"""Import an external image into immutable platform-controlled storage."""

from collections.abc import Awaitable, Callable
from typing import Protocol

ImportProgress = Callable[[str, str], Awaitable[None]]


class EnvironmentImportPort(Protocol):
    async def import_image(
        self, source_uri: str, expected_sha256: str, progress: ImportProgress
    ) -> dict[str, object]: ...
