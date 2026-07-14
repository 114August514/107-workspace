import tempfile
from functools import partial
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import anyio.to_thread

from workspace107.domain.errors import (
    ExternalCommandFailed,
    InvalidRelativePath,
    PathOutsideAllowedRoot,
    ResourceNotFound,
    TransferFailed,
)
from workspace107.domain.models import (
    IgnoreRules,
    ProjectSnapshot,
    PullRequest,
    TransferPlan,
    TransferResult,
)
from workspace107.domain.values import relative_posix_path
from workspace107.infrastructure.cluster.slurm.command_runner import CommandRunner
from workspace107.infrastructure.cluster.slurm.transports.ssh import (
    SshCommandRunner,
    ssh_argv,
    validate_ssh_host,
)
from workspace107.infrastructure.transfer.scanner import scan_project
from workspace107.infrastructure.transfer.tar_stream import (
    PipelineResult,
    PipelineRunner,
    SubprocessPipelineRunner,
)


class SshProjectTransfer:
    def __init__(
        self,
        host: str,
        *,
        local_roots: tuple[Path, ...],
        remote_roots: tuple[PurePosixPath, ...],
        remote_runner: CommandRunner | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        if not local_roots:
            raise ValueError("at least one local transfer root is required")
        if not remote_roots:
            raise ValueError("at least one remote transfer root is required")
        self._host = validate_ssh_host(host)
        self._local_roots = tuple(root.expanduser().resolve() for root in local_roots)
        self._remote_roots = tuple(self._safe_remote_root(root) for root in remote_roots)
        self._remote_runner = remote_runner or SshCommandRunner(self._host)
        self._pipeline_runner = pipeline_runner or SubprocessPipelineRunner()

    async def scan(self, source: Path, ignore: IgnoreRules) -> ProjectSnapshot:
        resolved = self._local_path(source)
        return await anyio.to_thread.run_sync(partial(scan_project, resolved, ignore))

    async def push(self, plan: TransferPlan) -> TransferResult:
        source = self._local_path(plan.source)
        if not source.is_dir():
            raise ResourceNotFound("project source not found")
        target = self._remote_uri(plan.target_uri)
        files = tuple(sorted(self._relative_file(value) for value in plan.files))
        for relative in files:
            path = self._local_file(source, relative)
            if not path.is_file():
                raise ResourceNotFound(f"project file {relative!r} not found")

        if files:
            mkdir_result = await self._remote_runner.run(("mkdir", "-p", "--", str(target)))
            if mkdir_result.exit_code != 0:
                raise TransferFailed("SSH project push failed while preparing its target.")
            list_path = self._write_file_list(files)
            try:
                result = await self._pipeline_runner.run(
                    (
                        "tar",
                        "-czf",
                        "-",
                        "--format=pax",
                        "--verbatim-files-from",
                        "-C",
                        str(source),
                        f"--files-from={list_path}",
                    ),
                    ssh_argv(
                        self._host,
                        ("tar", "-xzf", "-", "-C", str(target)),
                    ),
                )
            except ExternalCommandFailed as error:
                raise TransferFailed("SSH project push failed.") from error
            finally:
                list_path.unlink(missing_ok=True)
            self._require_pipeline_success(result, "SSH project push failed.")

        snapshot = await self.scan(source, IgnoreRules())
        manifest = {signature.path: signature for signature in snapshot.files}
        transferred = tuple(files)
        return TransferResult(
            transferred=transferred,
            skipped=tuple(path for path in manifest if path not in transferred),
            removed=plan.removed,
            manifest=manifest,
            warnings=snapshot.warnings,
        )

    async def pull(self, request: PullRequest) -> TransferResult:
        source = self._remote_uri(request.source_uri)
        destination = self._local_path(request.destination)
        destination.mkdir(parents=True, exist_ok=True)
        selected = tuple(sorted(self._relative_file(value) for value in request.include))
        remote_selection = selected or (".",)
        try:
            result = await self._pipeline_runner.run(
                ssh_argv(
                    self._host,
                    (
                        "tar",
                        "-czf",
                        "-",
                        "--format=pax",
                        "-C",
                        str(source),
                        "--",
                        *remote_selection,
                    ),
                ),
                ("tar", "-xzf", "-", "-C", str(destination)),
            )
        except ExternalCommandFailed as error:
            raise TransferFailed("SSH project pull failed.") from error
        self._require_pipeline_success(result, "SSH project pull failed.")
        snapshot = await self.scan(destination, IgnoreRules())
        manifest = {signature.path: signature for signature in snapshot.files}
        transferred = selected or tuple(manifest)
        return TransferResult(
            transferred=transferred,
            skipped=tuple(path for path in manifest if path not in transferred),
            removed=(),
            manifest=manifest,
            warnings=snapshot.warnings,
        )

    def _local_path(self, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not any(resolved == root or resolved.is_relative_to(root) for root in self._local_roots):
            raise PathOutsideAllowedRoot("local transfer path is outside configured roots")
        return resolved

    @staticmethod
    def _safe_remote_root(value: PurePosixPath) -> PurePosixPath:
        rendered = str(value)
        if (
            not value.is_absolute()
            or ".." in value.parts
            or any(character in rendered for character in "\r\n\x00")
        ):
            raise ValueError("remote transfer root must be a safe absolute POSIX path")
        return value

    def _remote_uri(self, value: str) -> PurePosixPath:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "file"
            or parsed.netloc not in ("", "localhost")
            or parsed.query
            or parsed.fragment
        ):
            raise PathOutsideAllowedRoot("SSH transfer requires a configured file URI")
        path = self._safe_remote_root(PurePosixPath(unquote(parsed.path)))
        if not any(path == root or path.is_relative_to(root) for root in self._remote_roots):
            raise PathOutsideAllowedRoot("remote transfer path is outside configured roots")
        return path

    @staticmethod
    def _relative_file(value: str) -> str:
        try:
            normalized = str(relative_posix_path(value))
        except InvalidRelativePath as error:
            raise PathOutsideAllowedRoot("transfer file path is invalid") from error
        if any(character in normalized for character in "\r\n\x00"):
            raise PathOutsideAllowedRoot("transfer file path contains a line break")
        return normalized

    @staticmethod
    def _local_file(root: Path, relative: str) -> Path:
        try:
            path = root.joinpath(*PurePosixPath(relative).parts).resolve(strict=True)
        except FileNotFoundError as error:
            raise ResourceNotFound(f"project file {relative!r} not found") from error
        if not path.is_relative_to(root):
            raise PathOutsideAllowedRoot("project file resolves outside its source root")
        return path

    @staticmethod
    def _write_file_list(files: tuple[str, ...]) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".workspace107-files",
            delete=False,
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write("\n".join(files))
            handle.write("\n")
            return Path(handle.name)

    @staticmethod
    def _require_pipeline_success(result: PipelineResult, message: str) -> None:
        if result.writer_exit_code != 0 or result.reader_exit_code != 0:
            raise TransferFailed(message)
