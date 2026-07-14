import json
import shlex
from pathlib import Path, PurePosixPath
from typing import cast

import pytest
from fastapi import Request

from workspace107.api.errors import domain_error_handler
from workspace107.domain.errors import ExternalCommandFailed, TransferFailed
from workspace107.domain.models import PullRequest, ResourceSpec
from workspace107.infrastructure.cluster.slurm.renderer import SlurmRenderSpec, render_sbatch
from workspace107.infrastructure.cluster.slurm.transports.local import LocalCommandRunner
from workspace107.infrastructure.cluster.slurm.transports.ssh import ssh_argv
from workspace107.infrastructure.transfer.ssh import SshProjectTransfer
from workspace107.infrastructure.transfer.tar_stream import PipelineResult


class RecordingPipelineRunner:
    def __init__(self) -> None:
        self.writer_arguments: tuple[str, ...] | None = None

    async def run(
        self,
        writer_arguments: tuple[str, ...],
        reader_arguments: tuple[str, ...],
    ) -> PipelineResult:
        del reader_arguments
        self.writer_arguments = writer_arguments
        return PipelineResult.completed()


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            ExternalCommandFailed("secret command and credentials"),
            503,
            "An external cluster command failed.",
        ),
        (
            TransferFailed("secret path and host"),
            502,
            "The project transfer failed.",
        ),
    ],
)
async def test_external_failures_use_sanitized_problem_details(
    error: ExternalCommandFailed | TransferFailed,
    status: int,
    detail: str,
) -> None:
    response = await domain_error_handler(cast(Request, object()), error)
    response_body = bytes(response.body)
    body = cast(dict[str, object], json.loads(response_body))

    assert response.status_code == status
    assert body["code"] == error.code
    assert body["detail"] == detail
    assert "secret" not in response_body.decode()


def test_renderer_rejects_directive_injection_without_side_effect(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    spec = SlurmRenderSpec(
        job_name=f"x; touch {marker}",
        project_path=PurePosixPath("/projects/demo"),
        jobs_root=PurePosixPath("/cluster/jobs"),
        log_root=PurePosixPath("/cluster/logs"),
        entrypoint="train.py",
        resources=ResourceSpec(cpus=1, memory_mb=1024, gpus=0, walltime_seconds=60),
        mounts=(),
        outputs=("result.json",),
        environment={"kind": "system"},
    )

    with pytest.raises(ValueError, match="job_name"):
        render_sbatch(spec)
    assert not marker.exists()


async def test_remote_command_quotes_injection_as_one_argument(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    payload = f"x; touch {marker}"
    remote_command = ssh_argv("ustc-cluster", ("printf", "%s", payload))[-1]

    result = await LocalCommandRunner().run(("sh", "-c", remote_command))

    assert result.exit_code == 0
    assert result.stdout.decode() == payload
    assert not marker.exists()


def test_renderer_terminates_python_options_for_entrypoint() -> None:
    spec = SlurmRenderSpec(
        job_name="safe-job",
        project_path=PurePosixPath("/projects/demo"),
        jobs_root=PurePosixPath("/cluster/jobs"),
        log_root=PurePosixPath("/cluster/logs"),
        entrypoint="-c",
        resources=ResourceSpec(cpus=1, memory_mb=1024, gpus=0, walltime_seconds=60),
        mounts=(),
        outputs=("result.json",),
        environment={"kind": "system"},
    )

    script = render_sbatch(spec)

    assert "python -- '-c'" in script


async def test_ssh_pull_terminates_tar_options_before_selected_paths(tmp_path: Path) -> None:
    remote = tmp_path / "remote"
    downloads = tmp_path / "downloads"
    remote.mkdir()
    downloads.mkdir()
    pipeline = RecordingPipelineRunner()
    transfer = SshProjectTransfer(
        "ustc-cluster",
        local_roots=(downloads,),
        remote_roots=(PurePosixPath(str(remote)),),
        pipeline_runner=pipeline,
    )
    option_like_path = "--checkpoint-action=exec=touch pwned"

    await transfer.pull(
        PullRequest(
            source_uri=remote.as_uri(),
            destination=downloads,
            include=(option_like_path,),
        )
    )

    assert pipeline.writer_arguments is not None
    remote_arguments = shlex.split(pipeline.writer_arguments[-1])
    selection_index = remote_arguments.index("-C") + 2
    assert remote_arguments[selection_index:] == ["--", option_like_path]
