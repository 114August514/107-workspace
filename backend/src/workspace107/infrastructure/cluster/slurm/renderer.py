import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from jinja2 import Environment, StrictUndefined

from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.models import ResourceSpec
from workspace107.domain.values import relative_posix_path

_DIRECTIVE_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
_SHELL_META = frozenset(";$`|&<>\r\n\x00")
_JINJA = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
_TEMPLATE = _JINJA.from_string(
    """#!/usr/bin/env bash
#SBATCH --job-name={{ job_name }}
#SBATCH --account={{ account }}
#SBATCH --partition={{ partition }}
#SBATCH --qos={{ qos }}
#SBATCH --cpus-per-task={{ cpus }}
#SBATCH --mem={{ memory_mb }}M
{% if gpus > 0 %}#SBATCH --gres=gpu:{{ gpus }}
{% endif %}#SBATCH --time={{ walltime }}
#SBATCH --output={{ stdout_path }}
#SBATCH --error={{ stderr_path }}
#SBATCH --open-mode=append

set -euo pipefail

jobs_root={{ jobs_root }}
run_dir="$jobs_root/$SLURM_JOB_ID"
work_dir="$run_dir/workspace"
mkdir -p -- "$work_dir"
cp -a -- {{ project_copy_source }} "$work_dir/"
cd -- "$work_dir"
{% for mount in mounts %}
mkdir -p -- {{ mount.parent }}
ln -sfn -- {{ mount.source }} {{ mount.target }}
{% endfor %}
{% for parent in output_parents %}
mkdir -p -- {{ parent }}
{% endfor %}

_workspace107_finish() {
    status=$?
    trap - EXIT
    if [ "$status" -eq 0 ]; then
        state=succeeded
    else
        state=failed
    fi
    printf '[workspace107] %s job %s\\n' "$state" "$SLURM_JOB_ID"
    exit "$status"
}
trap _workspace107_finish EXIT
printf '[workspace107] running job %s\\n' "$SLURM_JOB_ID"
{{ command }}
"""
)


@dataclass(frozen=True, slots=True)
class SlurmMount:
    source: PurePosixPath
    target: str


@dataclass(frozen=True, slots=True)
class SlurmRenderSpec:
    job_name: str
    project_path: PurePosixPath
    jobs_root: PurePosixPath
    log_root: PurePosixPath
    entrypoint: str
    resources: ResourceSpec
    mounts: tuple[SlurmMount, ...]
    outputs: tuple[str, ...]
    environment: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _QuotedMount:
    source: str
    target: str
    parent: str


def _directive(value: str, name: str) -> str:
    if not _DIRECTIVE_VALUE.fullmatch(value):
        raise ValueError(f"{name} contains unsupported characters")
    return value


def _absolute_path(value: PurePosixPath, name: str, *, directive: bool = False) -> str:
    rendered = str(value)
    if not value.is_absolute() or any(character in rendered for character in "\r\n\x00"):
        raise ValueError(f"{name} must be an absolute POSIX path without control characters")
    if directive and (any(character.isspace() for character in rendered) or "#" in rendered):
        raise ValueError(f"{name} cannot contain whitespace or # in a Slurm directive")
    return rendered


def _relative_path(value: str, name: str) -> str:
    try:
        normalized = str(relative_posix_path(value))
    except InvalidRelativePath as error:
        raise ValueError(f"{name} must be a safe relative POSIX path") from error
    if any(character in normalized for character in _SHELL_META):
        raise ValueError(f"{name} contains unsupported shell characters")
    if "{{" in normalized or "{%" in normalized:
        raise ValueError(f"{name} contains a template marker")
    return normalized


def _quote(value: str) -> str:
    quoted = shlex.quote(value)
    return f"'{value}'" if quoted == value else quoted


def _walltime(seconds: int) -> str:
    if seconds <= 0:
        raise ValueError("walltime_seconds must be positive")
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def _command(environment: Mapping[str, object], entrypoint: str) -> str:
    kind = environment.get("kind")
    quoted_entrypoint = _quote(entrypoint)
    if kind == "uv":
        return f"uv run --project . python -- {quoted_entrypoint}"
    if kind == "system":
        return f"python -- {quoted_entrypoint}"
    if kind == "conda":
        name = environment.get("name")
        if (
            not isinstance(name, str)
            or not name
            or any(character in name for character in "\r\n\x00")
        ):
            raise ValueError("conda environment name is required")
        return f"conda run --no-capture-output -n {_quote(name)} python -- {quoted_entrypoint}"
    raise ValueError("environment kind must be uv, conda, or system")


def render_sbatch(spec: SlurmRenderSpec) -> str:
    resources = spec.resources
    if resources.cpus <= 0:
        raise ValueError("cpus must be positive")
    if resources.memory_mb <= 0:
        raise ValueError("memory_mb must be positive")
    if resources.gpus < 0:
        raise ValueError("gpus cannot be negative")

    entrypoint = _relative_path(spec.entrypoint, "entrypoint")
    outputs = tuple(_relative_path(output, "output") for output in spec.outputs)
    project_path = _absolute_path(spec.project_path, "project_path")
    jobs_root = _absolute_path(spec.jobs_root, "jobs_root")
    log_root = _absolute_path(spec.log_root, "log_root", directive=True).rstrip("/")
    mounts: list[_QuotedMount] = []
    for mount in spec.mounts:
        target = _relative_path(mount.target, "mount target")
        source = _absolute_path(mount.source, "mount source")
        mounts.append(
            _QuotedMount(
                source=_quote(source),
                target=_quote(target),
                parent=_quote(str(PurePosixPath(target).parent)),
            )
        )
    output_parents = tuple(
        _quote(parent)
        for parent in sorted({str(PurePosixPath(output).parent) for output in outputs})
    )

    script = _TEMPLATE.render(
        job_name=_directive(spec.job_name, "job_name"),
        account=_directive(resources.account, "account"),
        partition=_directive(resources.partition, "partition"),
        qos=_directive(resources.qos, "qos"),
        cpus=resources.cpus,
        memory_mb=resources.memory_mb,
        gpus=resources.gpus,
        walltime=_walltime(resources.walltime_seconds),
        stdout_path=f"{log_root}/%j.out",
        stderr_path=f"{log_root}/%j.err",
        jobs_root=_quote(jobs_root),
        project_copy_source=_quote(f"{project_path.rstrip('/')}/."),
        mounts=tuple(mounts),
        output_parents=output_parents,
        command=_command(spec.environment, entrypoint),
    )
    if "{{" in script or "{%" in script:
        raise ValueError("rendered Slurm script contains an unresolved template marker")
    return script
