import re
import tomllib
from typing import Literal, cast

from workspace107.domain.models import ProjectSnapshot, ResourceSpec

_DISTRIBUTION_NAME = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")
_NORMALIZE_DISTRIBUTION = re.compile(r"[-_.]+")
_GPU_DISTRIBUTIONS = frozenset(
    {
        "flax",
        "jax",
        "jaxlib",
        "keras",
        "pytorch",
        "tensorflow",
        "tf-keras",
        "torch",
        "torchaudio",
        "torchvision",
    }
)


def _normalize_distribution_name(value: str) -> str:
    return _NORMALIZE_DISTRIBUTION.sub("-", value).lower()


def _dependency_name(specifier: str) -> str | None:
    match = _DISTRIBUTION_NAME.match(specifier)
    if match is None:
        return None
    return _normalize_distribution_name(match.group(1))


def detect_entries(snapshot: ProjectSnapshot) -> tuple[str, ...]:
    paths = {signature.path for signature in snapshot.files}
    python_files = sorted(path for path in paths if path.endswith(".py"))
    notebooks = sorted(path for path in paths if path.endswith(".ipynb"))
    preferred = tuple(path for path in ("train.py", "main.py") if path in paths)
    remaining = tuple(path for path in python_files if path not in preferred)
    return (*preferred, *remaining, *notebooks)


def parse_pyproject_dependencies(document: str) -> set[str]:
    parsed = cast(dict[str, object], tomllib.loads(document))
    project_value = parsed.get("project")
    if not isinstance(project_value, dict):
        return set()
    project = cast(dict[str, object], project_value)

    specifiers: list[str] = []
    dependencies = project.get("dependencies")
    if isinstance(dependencies, list):
        specifiers.extend(
            value for value in cast(list[object], dependencies) if isinstance(value, str)
        )

    optional_value = project.get("optional-dependencies")
    if isinstance(optional_value, dict):
        optional = cast(dict[object, object], optional_value)
        for group in optional.values():
            if isinstance(group, list):
                specifiers.extend(
                    value for value in cast(list[object], group) if isinstance(value, str)
                )

    return {name for specifier in specifiers if (name := _dependency_name(specifier)) is not None}


def infer_resources(dependencies: set[str]) -> ResourceSpec:
    normalized = {_normalize_distribution_name(value) for value in dependencies}
    if normalized & _GPU_DISTRIBUTIONS:
        return ResourceSpec(cpus=4, memory_mb=16_384, gpus=1, walltime_seconds=7_200)
    return ResourceSpec(cpus=2, memory_mb=4_096, gpus=0, walltime_seconds=3_600)


def infer_environment(snapshot: ProjectSnapshot) -> Literal["uv", "conda", "system"]:
    paths = {signature.path for signature in snapshot.files}
    if paths & {"pyproject.toml", "requirements.txt"}:
        return "uv"
    if "environment.yml" in paths:
        return "conda"
    return "system"
