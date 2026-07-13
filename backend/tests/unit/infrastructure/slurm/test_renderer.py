from pathlib import PurePosixPath

import pytest

from workspace107.domain.models import ResourceSpec
from workspace107.infrastructure.cluster.slurm.renderer import (
    SlurmMount,
    SlurmRenderSpec,
    render_sbatch,
)


def render_spec(
    *,
    gpus: int = 0,
    environment: dict[str, object] | None = None,
    job_name: str = "workspace107-123",
    partition: str = "Students",
    entrypoint: str = "src/train model.py",
) -> SlurmRenderSpec:
    return SlurmRenderSpec(
        job_name=job_name,
        project_path=PurePosixPath("/cluster/projects/demo project"),
        jobs_root=PurePosixPath("/cluster/workspace jobs"),
        log_root=PurePosixPath("/cluster/logs"),
        entrypoint=entrypoint,
        resources=ResourceSpec(
            cpus=4,
            memory_mb=16384,
            gpus=gpus,
            walltime_seconds=3661,
            account="stu",
            partition=partition,
            qos="qos_stu_default",
        ),
        mounts=(
            SlurmMount(
                source=PurePosixPath("/cluster/datasets/data $(safe)"),
                target="input/training data",
            ),
        ),
        outputs=("results/metrics file.json",),
        environment=environment or {"kind": "uv"},
    )


def test_render_cpu_uv_script_is_strict_and_quotes_shell_values() -> None:
    script = render_sbatch(render_spec())

    assert script.startswith("#!/usr/bin/env bash\n")
    assert "#SBATCH --account=stu" in script
    assert "#SBATCH --partition=Students" in script
    assert "#SBATCH --qos=qos_stu_default" in script
    assert "#SBATCH --cpus-per-task=4" in script
    assert "#SBATCH --mem=16384M" in script
    assert "#SBATCH --time=01:01:01" in script
    assert "#SBATCH --output=/cluster/logs/%j.out" in script
    assert "#SBATCH --error=/cluster/logs/%j.err" in script
    assert "#SBATCH --open-mode=append" in script
    assert "--gres=gpu" not in script
    assert "set -euo pipefail" in script
    assert "jobs_root='/cluster/workspace jobs'" in script
    assert "cp -a -- '/cluster/projects/demo project/.' \"$work_dir/\"" in script
    assert "ln -sfn -- '/cluster/datasets/data $(safe)' 'input/training data'" in script
    assert "mkdir -p -- 'results'" in script
    assert "uv run --project . python -- 'src/train model.py'" in script
    assert "{{" not in script
    assert "{%" not in script


def test_render_gpu_conda_and_system_commands() -> None:
    gpu = render_sbatch(render_spec(gpus=2, environment={"kind": "conda", "name": "vision env"}))
    system = render_sbatch(render_spec(environment={"kind": "system"}))

    assert "#SBATCH --gres=gpu:2" in gpu
    assert "conda run --no-capture-output -n 'vision env' python -- 'src/train model.py'" in gpu
    assert "python -- 'src/train model.py'" in system
    assert "uv run" not in system
    assert "conda run" not in system


def test_render_rejects_job_name_injection() -> None:
    with pytest.raises(ValueError, match="job_name"):
        render_sbatch(render_spec(job_name="x; touch /tmp/pwned"))


def test_render_rejects_directive_newline_injection() -> None:
    with pytest.raises(ValueError, match="partition"):
        render_sbatch(render_spec(partition="Students\n#SBATCH --chdir=/tmp"))


def test_render_rejects_entrypoint_command_substitution() -> None:
    with pytest.raises(ValueError, match="entrypoint"):
        render_sbatch(render_spec(entrypoint="a$(id).py"))


def test_render_rejects_unknown_or_incomplete_environment() -> None:
    with pytest.raises(ValueError, match="environment kind"):
        render_sbatch(render_spec(environment={"kind": "container"}))
    with pytest.raises(ValueError, match="conda environment name"):
        render_sbatch(render_spec(environment={"kind": "conda"}))
