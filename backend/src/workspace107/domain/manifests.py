from collections.abc import Mapping
from dataclasses import dataclass

from workspace107.domain.models import FileSignature


@dataclass(frozen=True, slots=True)
class ManifestDiff:
    added: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def upload_paths(self) -> tuple[str, ...]:
        return (*self.added, *self.changed)


def diff_manifests(
    previous: Mapping[str, FileSignature],
    current: Mapping[str, FileSignature],
) -> ManifestDiff:
    previous_paths = set(previous)
    current_paths = set(current)
    common = previous_paths & current_paths
    return ManifestDiff(
        added=tuple(sorted(current_paths - previous_paths)),
        changed=tuple(sorted(path for path in common if previous[path] != current[path])),
        unchanged=tuple(sorted(path for path in common if previous[path] == current[path])),
        removed=tuple(sorted(previous_paths - current_paths)),
    )
