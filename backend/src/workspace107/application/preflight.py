from dataclasses import dataclass
from uuid import UUID

from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.models import PreflightCheck, ResourceSpec
from workspace107.domain.values import relative_posix_path


@dataclass(frozen=True, slots=True)
class PreflightDataset:
    dataset_id: UUID
    archived: bool
    mount_path: str


@dataclass(frozen=True, slots=True)
class PreflightInput:
    project_archived: bool
    template_archived: bool
    entrypoint: str
    project_files: frozenset[str]
    datasets: tuple[PreflightDataset, ...]
    outputs: tuple[str, ...]
    resources: ResourceSpec


def _check(code: str, passed: bool, success: str, failure: str) -> PreflightCheck:
    return PreflightCheck(
        code=code,
        passed=passed,
        message=success if passed else failure,
    )


def _normalize_paths(values: tuple[str, ...]) -> tuple[bool, tuple[str, ...]]:
    normalized: list[str] = []
    valid = True
    for value in values:
        try:
            normalized.append(str(relative_posix_path(value)))
        except InvalidRelativePath:
            valid = False
    return valid, tuple(normalized)


def check_preflight(candidate: PreflightInput) -> tuple[PreflightCheck, ...]:
    archived_datasets = tuple(
        sorted(str(dataset.dataset_id) for dataset in candidate.datasets if dataset.archived)
    )

    try:
        entrypoint = str(relative_posix_path(candidate.entrypoint))
        entrypoint_valid = True
    except InvalidRelativePath:
        entrypoint = ""
        entrypoint_valid = False

    _, project_files = _normalize_paths(tuple(candidate.project_files))
    mounts_valid, mounts = _normalize_paths(
        tuple(dataset.mount_path for dataset in candidate.datasets)
    )
    outputs_valid, _ = _normalize_paths(candidate.outputs)

    return (
        _check(
            "project_active",
            not candidate.project_archived,
            "Project is active.",
            "Project is archived.",
        ),
        _check(
            "template_active",
            not candidate.template_archived,
            "Run template is active.",
            "Run template is archived.",
        ),
        _check(
            "datasets_active",
            not archived_datasets,
            "Datasets are active.",
            f"Archived datasets: {', '.join(archived_datasets)}.",
        ),
        _check(
            "entrypoint_valid",
            entrypoint_valid,
            "Entrypoint is a safe relative path.",
            "Entrypoint is not a safe relative path.",
        ),
        _check(
            "entrypoint_exists",
            entrypoint_valid and entrypoint in project_files,
            "Entrypoint exists in the project snapshot.",
            "Entrypoint is missing from the project snapshot.",
        ),
        _check(
            "mounts_valid",
            mounts_valid,
            "Dataset mount paths are safe.",
            "A dataset mount path is not a safe relative path.",
        ),
        _check(
            "mounts_unique",
            len(mounts) == len(set(mounts)),
            "Dataset mount paths are unique.",
            "Dataset mount paths must be unique.",
        ),
        _check(
            "outputs_valid",
            outputs_valid,
            "Output paths are safe.",
            "An output path is not a safe relative path.",
        ),
        _check(
            "cpus_positive",
            candidate.resources.cpus > 0,
            "CPU count is positive.",
            "CPU count must be positive.",
        ),
        _check(
            "memory_positive",
            candidate.resources.memory_mb > 0,
            "Memory is positive.",
            "Memory must be positive.",
        ),
        _check(
            "walltime_positive",
            candidate.resources.walltime_seconds > 0,
            "Wall time is positive.",
            "Wall time must be positive.",
        ),
        _check(
            "gpus_non_negative",
            candidate.resources.gpus >= 0,
            "GPU count is non-negative.",
            "GPU count must be non-negative.",
        ),
    )
