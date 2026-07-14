from pathlib import PurePosixPath

from workspace107.domain.errors import InvalidRelativePath


def relative_posix_path(value: str) -> PurePosixPath:
    if not value or "\x00" in value or "\\" in value:
        raise InvalidRelativePath(value)

    path = PurePosixPath(value)
    normalized = PurePosixPath(*(part for part in path.parts if part not in ("", ".")))
    if path.is_absolute() or not normalized.parts or ".." in normalized.parts:
        raise InvalidRelativePath(value)
    return normalized
