from pathlib import Path

import pytest

from workspace107.application.inference import (
    detect_entries,
    infer_environment,
    infer_resources,
    parse_pyproject_dependencies,
)
from workspace107.domain.models import FileSignature, ProjectSnapshot, ResourceSpec


def snapshot(source: Path, *paths: str) -> ProjectSnapshot:
    return ProjectSnapshot(
        source=source,
        files=tuple(
            FileSignature(path=path, size_bytes=index, mtime_ns=index)
            for index, path in enumerate(paths)
        ),
    )


def test_detect_entries_prefers_training_then_python_then_notebooks(tmp_path: Path) -> None:
    project = snapshot(
        tmp_path,
        "README.md",
        "z.py",
        "train.py",
        "z.ipynb",
        "main.py",
        "a.py",
        "notebooks/a.ipynb",
    )

    assert detect_entries(project) == (
        "train.py",
        "main.py",
        "a.py",
        "z.py",
        "notebooks/a.ipynb",
        "z.ipynb",
    )


def test_parse_pep621_dependencies_including_optional_groups() -> None:
    document = """
[project]
name = "demo"
dependencies = [
  "Torch>=2.0",
  "scikit_learn[plots]>=1.4; python_version >= '3.12'",
]

[project.optional-dependencies]
notebooks = ["Jupyter.Lab", "Keras>=3"]
"""

    assert parse_pyproject_dependencies(document) == {
        "torch",
        "scikit-learn",
        "jupyter-lab",
        "keras",
    }


@pytest.mark.parametrize("dependency", ["Torch", "TensorFlow", "JAX", "tf_keras"])
def test_gpu_frameworks_infer_one_gpu(dependency: str) -> None:
    resources = infer_resources({dependency})

    assert resources == ResourceSpec(
        cpus=4,
        memory_mb=16_384,
        gpus=1,
        walltime_seconds=7_200,
    )


def test_non_gpu_dependencies_infer_cpu_defaults() -> None:
    assert infer_resources({"numpy", "scikit_learn"}) == ResourceSpec(
        cpus=2,
        memory_mb=4_096,
        gpus=0,
        walltime_seconds=3_600,
    )


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (("pyproject.toml", "environment.yml"), "uv"),
        (("requirements.txt",), "uv"),
        (("environment.yml",), "conda"),
        (("main.py",), "system"),
    ],
)
def test_infer_environment_from_project_files(
    tmp_path: Path, files: tuple[str, ...], expected: str
) -> None:
    assert infer_environment(snapshot(tmp_path, *files)) == expected
