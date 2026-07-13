from workspace107.domain.models import FileSignature
from workspace107.infrastructure.transfer.manifest import diff_manifests


def signature(path: str, size: int, mtime: int) -> FileSignature:
    return FileSignature(path=path, size_bytes=size, mtime_ns=mtime)


def test_manifest_diff_classifies_every_path() -> None:
    previous = {
        "changed.py": signature("changed.py", 1, 1),
        "removed.py": signature("removed.py", 2, 2),
        "same.py": signature("same.py", 3, 3),
    }
    current = {
        "added.py": signature("added.py", 4, 4),
        "changed.py": signature("changed.py", 10, 10),
        "same.py": signature("same.py", 3, 3),
    }

    difference = diff_manifests(previous, current)

    assert difference.added == ("added.py",)
    assert difference.changed == ("changed.py",)
    assert difference.unchanged == ("same.py",)
    assert difference.removed == ("removed.py",)
    assert difference.upload_paths == ("added.py", "changed.py")
    assert not set(difference.removed) & set(difference.upload_paths)
