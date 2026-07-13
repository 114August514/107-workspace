import os
import shutil
from functools import partial
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import anyio.to_thread

from workspace107.domain.errors import PathOutsideAllowedRoot, ResourceNotFound
from workspace107.domain.models import (
    IgnoreRules,
    ProjectSnapshot,
    PullRequest,
    TransferPlan,
    TransferResult,
)
from workspace107.domain.values import relative_posix_path
from workspace107.infrastructure.transfer.scanner import scan_project


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".workspace107-{uuid4().hex}.tmp"
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


class LocalProjectTransfer:
    def __init__(self, allowed_roots: tuple[Path, ...]) -> None:
        if not allowed_roots:
            raise ValueError("at least one transfer root is required")
        self._allowed_roots = tuple(root.expanduser().resolve() for root in allowed_roots)

    async def scan(self, source: Path, ignore: IgnoreRules) -> ProjectSnapshot:
        resolved = self._allowed_path(source)
        return await anyio.to_thread.run_sync(partial(scan_project, resolved, ignore))

    async def push(self, plan: TransferPlan) -> TransferResult:
        source = self._allowed_path(plan.source)
        if not source.is_dir():
            raise ResourceNotFound("project source not found")
        target = self._allowed_path(self._path_from_uri(plan.target_uri))
        target.mkdir(parents=True, exist_ok=True)

        transferred: list[str] = []
        for relative in sorted(plan.files):
            source_file = self._file_within(source, relative, must_exist=True)
            if not source_file.is_file():
                raise ResourceNotFound(f"project file {relative!r} not found")
            target_file = self._file_within(target, relative, must_exist=False)
            await anyio.to_thread.run_sync(_atomic_copy, source_file, target_file)
            transferred.append(relative)

        snapshot = await self.scan(source, IgnoreRules())
        manifest = {signature.path: signature for signature in snapshot.files}
        skipped = tuple(
            signature.path for signature in snapshot.files if signature.path not in transferred
        )
        return TransferResult(
            transferred=tuple(transferred),
            skipped=skipped,
            removed=plan.removed,
            manifest=manifest,
            warnings=snapshot.warnings,
        )

    async def pull(self, request: PullRequest) -> TransferResult:
        source = self._allowed_path(self._path_from_uri(request.source_uri))
        if not source.is_dir():
            raise ResourceNotFound("transfer source not found")
        destination = self._allowed_path(request.destination)
        destination.mkdir(parents=True, exist_ok=True)
        snapshot = await self.scan(source, IgnoreRules())
        available = {signature.path: signature for signature in snapshot.files}
        selected = tuple(sorted(request.include or tuple(available)))

        transferred: list[str] = []
        for relative in selected:
            if relative not in available:
                raise ResourceNotFound(f"transfer file {relative!r} not found")
            source_file = self._file_within(source, relative, must_exist=True)
            target_file = self._file_within(destination, relative, must_exist=False)
            await anyio.to_thread.run_sync(_atomic_copy, source_file, target_file)
            transferred.append(relative)

        return TransferResult(
            transferred=tuple(transferred),
            skipped=tuple(path for path in available if path not in transferred),
            removed=(),
            manifest=available,
            warnings=snapshot.warnings,
        )

    def _allowed_path(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if not any(resolved.is_relative_to(root) for root in self._allowed_roots):
            raise PathOutsideAllowedRoot(f"path {path} is outside configured transfer roots")
        return resolved

    @staticmethod
    def _path_from_uri(value: str) -> Path:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "file"
            or parsed.netloc not in ("", "localhost")
            or parsed.query
            or parsed.fragment
        ):
            raise PathOutsideAllowedRoot("local transfer requires a file URI")
        return Path(unquote(parsed.path))

    @staticmethod
    def _file_within(root: Path, relative: str, *, must_exist: bool) -> Path:
        normalized = relative_posix_path(relative)
        path = root.joinpath(*normalized.parts)
        resolved = path.resolve(strict=must_exist)
        if not resolved.is_relative_to(root):
            raise PathOutsideAllowedRoot(f"path {relative!r} resolves outside transfer root")
        return resolved
