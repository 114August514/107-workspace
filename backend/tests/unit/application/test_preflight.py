from dataclasses import replace
from uuid import uuid4

import pytest

from workspace107.application.preflight import (
    PreflightDataset,
    PreflightInput,
    check_preflight,
)
from workspace107.domain.models import PreflightCheck, ResourceSpec


def candidate() -> PreflightInput:
    return PreflightInput(
        project_archived=False,
        template_archived=False,
        entrypoint="train.py",
        project_files=frozenset({"train.py", "src/model.py"}),
        datasets=(
            PreflightDataset(
                dataset_id=uuid4(),
                archived=False,
                mount_path="input/data",
            ),
        ),
        outputs=("results/metrics.json",),
        resources=ResourceSpec(
            cpus=4,
            memory_mb=4096,
            gpus=1,
            walltime_seconds=3600,
        ),
    )


def by_code(checks: tuple[PreflightCheck, ...]) -> dict[str, PreflightCheck]:
    return {check.code: check for check in checks}


def test_missing_entrypoint_is_a_failed_check() -> None:
    checks = by_code(check_preflight(replace(candidate(), entrypoint="missing.py")))

    assert not checks["entrypoint_exists"].passed


@pytest.mark.parametrize("field", ["project_archived", "template_archived"])
def test_archived_project_or_template_is_a_failed_check(field: str) -> None:
    checks = by_code(check_preflight(replace(candidate(), **{field: True})))

    assert not checks[field.removesuffix("_archived") + "_active"].passed


def test_archived_dataset_is_a_failed_check() -> None:
    current = candidate()
    archived = replace(current.datasets[0], archived=True)

    checks = by_code(check_preflight(replace(current, datasets=(archived,))))

    assert not checks["datasets_active"].passed


def test_duplicate_normalized_mount_is_a_failed_check() -> None:
    current = candidate()
    duplicate = PreflightDataset(
        dataset_id=uuid4(),
        archived=False,
        mount_path="input/data/.",
    )

    checks = by_code(check_preflight(replace(current, datasets=(*current.datasets, duplicate))))

    assert not checks["mounts_unique"].passed


def test_mount_traversal_is_a_failed_check() -> None:
    current = candidate()
    unsafe = replace(current.datasets[0], mount_path="../private")

    checks = by_code(check_preflight(replace(current, datasets=(unsafe,))))

    assert not checks["mounts_valid"].passed


def test_output_traversal_is_a_failed_check() -> None:
    checks = by_code(check_preflight(replace(candidate(), outputs=("../private",))))

    assert not checks["outputs_valid"].passed


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("cpus", 0, "cpus_positive"),
        ("memory_mb", 0, "memory_positive"),
        ("walltime_seconds", 0, "walltime_positive"),
        ("gpus", -1, "gpus_non_negative"),
    ],
)
def test_invalid_resource_is_a_failed_check(field: str, value: int, code: str) -> None:
    current = candidate()
    resources = replace(current.resources, **{field: value})

    checks = by_code(check_preflight(replace(current, resources=resources)))

    assert not checks[code].passed


def test_success_returns_complete_named_check_list() -> None:
    checks = check_preflight(candidate())

    assert tuple(check.code for check in checks) == (
        "project_active",
        "template_active",
        "datasets_active",
        "entrypoint_valid",
        "entrypoint_exists",
        "mounts_valid",
        "mounts_unique",
        "outputs_valid",
        "cpus_positive",
        "memory_positive",
        "walltime_positive",
        "gpus_non_negative",
    )
    assert all(check.passed for check in checks)
