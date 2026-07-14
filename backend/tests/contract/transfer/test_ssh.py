import asyncio
import shlex
import shutil
import sys
from pathlib import Path, PurePosixPath

import pytest

from workspace107.domain.errors import (
    ExternalCommandFailed,
    PathOutsideAllowedRoot,
    ResourceNotFound,
    TransferFailed,
)
from workspace107.domain.models import IgnoreRules, PullRequest, TransferPlan
from workspace107.infrastructure.cluster.slurm.command_runner import CommandResult
from workspace107.infrastructure.cluster.slurm.transports.ssh import SSH_OPTIONS
from workspace107.infrastructure.transfer.ssh import SshProjectTransfer
from workspace107.infrastructure.transfer.tar_stream import (
    PipelineResult,
    SubprocessPipelineRunner,
)


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        assert input_data is None
        self.calls.append(arguments)
        return CommandResult.completed()


class CopyingPipelineRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult:
        self.calls.append((writer_arguments, reader_arguments))
        if writer_arguments[0] == "tar":
            self._push(writer_arguments, reader_arguments)
        else:
            self._pull(writer_arguments, reader_arguments)
        return PipelineResult.completed()

    @staticmethod
    def _push(
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> None:
        source = Path(writer_arguments[writer_arguments.index("-C") + 1])
        list_argument = next(
            argument for argument in writer_arguments if argument.startswith("--files-from=")
        )
        file_list = Path(list_argument.removeprefix("--files-from="))
        files = tuple(line for line in file_list.read_text(encoding="utf-8").splitlines() if line)
        remote = shlex.split(reader_arguments[-1])
        destination = Path(remote[remote.index("-C") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        for relative in files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)

    @staticmethod
    def _pull(
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> None:
        remote = shlex.split(writer_arguments[-1])
        source = Path(remote[remote.index("-C") + 1])
        selected = tuple(remote[remote.index("-C") + 2 :])
        if selected and selected[0] == "--":
            selected = selected[1:]
        destination = Path(reader_arguments[reader_arguments.index("-C") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        if selected == (".",):
            selected = tuple(
                path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()
            )
        for relative in selected:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)


class FailingPipelineRunner:
    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult:
        del writer_arguments, reader_arguments
        return PipelineResult.completed(reader_exit_code=2, reader_stderr=b"tar failed")


class FailingCommandRunner:
    async def run(
        self,
        arguments: tuple[str, ...],
        *,
        input_data: bytes | None = None,
    ) -> CommandResult:
        del arguments, input_data
        return CommandResult.completed(exit_code=1, stderr=b"mkdir failed")


class RaisingPipelineRunner:
    def __init__(self) -> None:
        self.writer_arguments: tuple[str, ...] | None = None

    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult:
        del reader_arguments
        self.writer_arguments = writer_arguments
        raise ExternalCommandFailed("private process details")


async def test_subprocess_pipeline_streams_bytes_and_reports_status(tmp_path: Path) -> None:
    destination = tmp_path / "payload.bin"
    writer = (
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('writer-note'); sys.stdout.buffer.write(b'payload')",
    )
    reader = (
        sys.executable,
        "-c",
        (
            "import pathlib,sys; "
            f"pathlib.Path({str(destination)!r}).write_bytes(sys.stdin.buffer.read()); "
            "sys.stderr.write('reader-note')"
        ),
    )

    result = await SubprocessPipelineRunner().run(writer, reader)

    assert result.writer_exit_code == 0
    assert result.reader_exit_code == 0
    assert result.writer_stderr == b"writer-note"
    assert result.reader_stderr == b"reader-note"
    assert destination.read_bytes() == b"payload"


async def test_subprocess_pipeline_returns_nonzero_exit_codes() -> None:
    writer = (
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('nope'); raise SystemExit(7)",
    )
    reader = (sys.executable, "-c", "import sys; sys.stdin.buffer.read()")

    result = await SubprocessPipelineRunner().run(writer, reader)

    assert result.writer_exit_code == 7
    assert result.reader_exit_code == 0


@pytest.mark.parametrize(
    ("writer", "reader"),
    [
        ((), ("reader",)),
        (("writer",), ()),
    ],
)
async def test_subprocess_pipeline_rejects_empty_commands(
    writer: tuple[str, ...],
    reader: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        await SubprocessPipelineRunner().run(writer, reader)


async def test_subprocess_pipeline_normalizes_writer_spawn_failure() -> None:
    with pytest.raises(TransferFailed, match="could not be started"):
        await SubprocessPipelineRunner().run(
            ("workspace107-writer-does-not-exist",),
            (sys.executable, "-c", "pass"),
        )


async def test_subprocess_pipeline_terminates_writer_when_reader_spawn_fails() -> None:
    with pytest.raises(TransferFailed, match="could not be started"):
        await asyncio.wait_for(
            SubprocessPipelineRunner().run(
                (sys.executable, "-c", "import time; time.sleep(30)"),
                ("workspace107-reader-does-not-exist",),
            ),
            timeout=2,
        )


async def test_subprocess_pipeline_terminates_children_when_cancelled() -> None:
    sleeper = (sys.executable, "-c", "import time; time.sleep(30)")
    reader = (sys.executable, "-c", "import sys; sys.stdin.buffer.read()")
    task = asyncio.create_task(SubprocessPipelineRunner().run(sleeper, reader))
    await asyncio.sleep(0.05)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)


async def test_ssh_transfer_incremental_push_and_pull(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    downloads = tmp_path / "downloads"
    source.mkdir()
    remote.mkdir()
    downloads.mkdir()
    (source / "keep.py").write_text("one\n", encoding="utf-8")
    (source / "old.py").write_text("old\n", encoding="utf-8")
    (source / "结果.txt").write_text("first\n", encoding="utf-8")
    command = RecordingCommandRunner()
    pipeline = CopyingPipelineRunner()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source, downloads),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=command,
        pipeline_runner=pipeline,
    )

    first_snapshot = await transfer.scan(source, IgnoreRules())
    first = await transfer.push(
        TransferPlan(
            source=source,
            target_uri=remote.as_uri(),
            files=tuple(signature.path for signature in first_snapshot.files),
        )
    )
    assert first.transferred == ("keep.py", "old.py", "结果.txt")
    assert (remote / "结果.txt").read_text(encoding="utf-8") == "first\n"

    (source / "keep.py").write_text("two\n", encoding="utf-8")
    (source / "old.py").unlink()
    (source / "new.py").write_text("new\n", encoding="utf-8")
    second = await transfer.push(
        TransferPlan(
            source=source,
            target_uri=remote.as_uri(),
            files=("keep.py", "new.py"),
            removed=("old.py",),
        )
    )

    assert second.transferred == ("keep.py", "new.py")
    assert second.removed == ("old.py",)
    assert (remote / "old.py").read_text(encoding="utf-8") == "old\n"
    assert (remote / "keep.py").read_text(encoding="utf-8") == "two\n"

    (remote / "results").mkdir()
    (remote / "results" / "metrics.json").write_text('{"accuracy":1}\n', encoding="utf-8")
    pulled = await transfer.pull(
        PullRequest(
            source_uri=remote.as_uri(),
            destination=downloads,
            include=("results/metrics.json",),
        )
    )

    assert pulled.transferred == ("results/metrics.json",)
    assert (downloads / "results" / "metrics.json").read_text(encoding="utf-8") == (
        '{"accuracy":1}\n'
    )
    assert command.calls == [("mkdir", "-p", "--", str(remote))] * 2
    assert all("--format=pax" in call[0] or call[0][0] == "ssh" for call in pipeline.calls)
    assert all(call[1][1 : 1 + len(SSH_OPTIONS)] == SSH_OPTIONS for call in pipeline.calls[:2])
    list_files = [
        Path(argument.removeprefix("--files-from="))
        for writer, _ in pipeline.calls
        for argument in writer
        if argument.startswith("--files-from=")
    ]
    assert list_files
    assert not any(path.exists() for path in list_files)


async def test_ssh_transfer_rejects_out_of_root_before_process_start(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    outside = tmp_path / "outside"
    source.mkdir()
    remote.mkdir()
    outside.mkdir()
    command = RecordingCommandRunner()
    pipeline = CopyingPipelineRunner()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=command,
        pipeline_runner=pipeline,
    )

    with pytest.raises(PathOutsideAllowedRoot):
        await transfer.push(TransferPlan(source=source, target_uri=outside.as_uri(), files=()))

    assert command.calls == []
    assert pipeline.calls == []


async def test_ssh_transfer_normalizes_pipeline_failure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    source.mkdir()
    remote.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=RecordingCommandRunner(),
        pipeline_runner=FailingPipelineRunner(),
    )

    with pytest.raises(TransferFailed, match="SSH project push failed"):
        await transfer.push(
            TransferPlan(source=source, target_uri=remote.as_uri(), files=("file.txt",))
        )


def test_ssh_transfer_requires_safe_configured_roots(tmp_path: Path) -> None:
    local = tmp_path / "local"
    remote = PurePosixPath("/remote")

    with pytest.raises(ValueError, match="local transfer root"):
        SshProjectTransfer("ustc-cluster", local_roots=(), remote_roots=(remote,))
    with pytest.raises(ValueError, match="remote transfer root"):
        SshProjectTransfer("ustc-cluster", local_roots=(local,), remote_roots=())
    with pytest.raises(ValueError, match="safe absolute POSIX path"):
        SshProjectTransfer(
            "ustc-cluster",
            local_roots=(local,),
            remote_roots=(PurePosixPath("relative/remote"),),
        )


async def test_ssh_transfer_handles_empty_and_missing_push_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    outside = tmp_path / "outside"
    source.mkdir()
    remote.mkdir()
    outside.mkdir()
    command = RecordingCommandRunner()
    pipeline = CopyingPipelineRunner()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=command,
        pipeline_runner=pipeline,
    )

    empty = await transfer.push(TransferPlan(source=source, target_uri=remote.as_uri(), files=()))

    assert empty.transferred == ()
    assert command.calls == []
    assert pipeline.calls == []
    with pytest.raises(ResourceNotFound, match="source"):
        await transfer.push(
            TransferPlan(
                source=source / "missing",
                target_uri=remote.as_uri(),
                files=(),
            )
        )
    with pytest.raises(ResourceNotFound, match="project file"):
        await transfer.push(
            TransferPlan(source=source, target_uri=remote.as_uri(), files=("missing.txt",))
        )
    with pytest.raises(PathOutsideAllowedRoot, match="local transfer path"):
        await transfer.scan(outside, IgnoreRules())


async def test_ssh_transfer_normalizes_remote_and_pipeline_failures(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    downloads = tmp_path / "downloads"
    source.mkdir()
    remote.mkdir()
    downloads.mkdir()
    (source / "file.txt").write_text("payload", encoding="utf-8")
    plan = TransferPlan(source=source, target_uri=remote.as_uri(), files=("file.txt",))
    mkdir_failure = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=FailingCommandRunner(),
        pipeline_runner=CopyingPipelineRunner(),
    )

    with pytest.raises(TransferFailed, match="preparing its target"):
        await mkdir_failure.push(plan)

    push_pipeline = RaisingPipelineRunner()
    push_failure = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        remote_runner=RecordingCommandRunner(),
        pipeline_runner=push_pipeline,
    )
    with pytest.raises(TransferFailed, match="push failed"):
        await push_failure.push(plan)
    assert push_pipeline.writer_arguments is not None
    list_path = next(
        Path(argument.removeprefix("--files-from="))
        for argument in push_pipeline.writer_arguments
        if argument.startswith("--files-from=")
    )
    assert not list_path.exists()

    pull_failure = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(downloads,),
        remote_roots=(PurePosixPath(str(remote)),),
        pipeline_runner=RaisingPipelineRunner(),
    )
    with pytest.raises(TransferFailed, match="pull failed"):
        await pull_failure.pull(
            PullRequest(source_uri=remote.as_uri(), destination=downloads, include=())
        )


@pytest.mark.parametrize(
    "source_uri",
    [
        "ssh://cluster/remote",
        "file://other-host/remote",
        "file:///remote?unexpected=true",
    ],
)
async def test_ssh_transfer_rejects_unsupported_remote_uri(
    tmp_path: Path,
    source_uri: str,
) -> None:
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(downloads,),
        remote_roots=(PurePosixPath("/remote"),),
        pipeline_runner=CopyingPipelineRunner(),
    )

    with pytest.raises(PathOutsideAllowedRoot, match="file URI"):
        await transfer.pull(PullRequest(source_uri=source_uri, destination=downloads, include=()))


async def test_ssh_transfer_rejects_line_break_in_file_list(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    source.mkdir()
    remote.mkdir()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        pipeline_runner=CopyingPipelineRunner(),
    )

    with pytest.raises(PathOutsideAllowedRoot, match="line break"):
        await transfer.push(
            TransferPlan(
                source=source,
                target_uri=remote.as_uri(),
                files=("line\nbreak.txt",),
            )
        )


async def test_ssh_transfer_rejects_symlink_outside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    remote = tmp_path / "remote"
    outside = tmp_path / "outside.txt"
    source.mkdir()
    remote.mkdir()
    outside.write_text("private", encoding="utf-8")
    (source / "escape.txt").symlink_to(outside)
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(source,),
        remote_roots=(PurePosixPath(str(remote)),),
        pipeline_runner=CopyingPipelineRunner(),
    )

    with pytest.raises(PathOutsideAllowedRoot, match="outside its source root"):
        await transfer.push(
            TransferPlan(
                source=source,
                target_uri=remote.as_uri(),
                files=("escape.txt",),
            )
        )
