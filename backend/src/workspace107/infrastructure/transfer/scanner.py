import fnmatch
import os
from pathlib import Path

from workspace107.domain.errors import PathOutsideAllowedRoot, ResourceNotFound
from workspace107.domain.models import (
    FileSignature,
    IgnoreRules,
    ProjectSnapshot,
    TransferWarning,
)

_MANDATORY_EXCLUSIONS = frozenset(
    {
        ".git",
        ".ipynb_checkpoints",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
)
_DEFAULT_LARGE_FILE_THRESHOLD = 512 * 1024 * 1024
_DEFAULT_FILE_COUNT_THRESHOLD = 1_000


def _load_hpcignore(source: Path) -> tuple[str, ...]:
    path = source / ".hpcignore"
    if not path.is_file():
        return ()
    patterns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().rstrip("/")
        if line and not line.startswith("#"):
            patterns.append(line)
    return tuple(patterns)


def _is_ignored(relative: str, patterns: tuple[str, ...]) -> bool:
    parts = relative.split("/")
    if any(part in _MANDATORY_EXCLUSIONS for part in parts):
        return True
    for pattern in patterns:
        normalized = pattern.replace("\\", "/").rstrip("/")
        if fnmatch.fnmatchcase(relative, normalized):
            return True
        if any(fnmatch.fnmatchcase(part, normalized) for part in parts):
            return True
    return False


def _require_within(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise PathOutsideAllowedRoot(f"{path} resolves outside the project source")
    return resolved


def scan_project(
    source: Path,
    ignore: IgnoreRules,
    *,
    large_file_threshold: int = _DEFAULT_LARGE_FILE_THRESHOLD,
    file_count_threshold: int = _DEFAULT_FILE_COUNT_THRESHOLD,
) -> ProjectSnapshot:
    root = source.expanduser().resolve()
    if not root.is_dir():
        raise ResourceNotFound("project source not found")
    patterns = (*_load_hpcignore(root), *ignore.patterns)
    signatures: list[FileSignature] = []

    for current_value, directory_names, file_names in os.walk(root, topdown=True):
        current = Path(current_value)
        directory_names.sort()
        kept_directories: list[str] = []
        for name in directory_names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if _is_ignored(relative, patterns):
                continue
            if path.is_symlink():
                _require_within(path, root)
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if _is_ignored(relative, patterns):
                continue
            resolved = _require_within(path, root)
            if not resolved.is_file():
                continue
            stat = resolved.stat()
            signatures.append(
                FileSignature(
                    path=relative,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                )
            )

    signatures.sort(key=lambda signature: signature.path)
    warnings = [
        TransferWarning(
            code="large_file",
            message=f"File exceeds {large_file_threshold} bytes.",
            path=signature.path,
            size_bytes=signature.size_bytes,
        )
        for signature in signatures
        if signature.size_bytes > large_file_threshold
    ]
    if len(signatures) > file_count_threshold:
        warnings.append(
            TransferWarning(
                code="large_file_count",
                message=f"Project contains more than {file_count_threshold} files.",
                count=len(signatures),
            )
        )
    return ProjectSnapshot(source=root, files=tuple(signatures), warnings=tuple(warnings))
