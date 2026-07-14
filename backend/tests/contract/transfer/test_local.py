from pathlib import Path

import pytest

from workspace107.domain.errors import PathOutsideAllowedRoot
from workspace107.domain.models import (
    FileSignature,
    IgnoreRules,
    ProjectSnapshot,
    PullRequest,
    TransferPlan,
)
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.infrastructure.transfer.manifest import diff_manifests


def manifest(snapshot: ProjectSnapshot) -> dict[str, FileSignature]:
    return {signature.path: signature for signature in snapshot.files}


async def test_local_transfer_incremental_push_and_pull(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    downloads = tmp_path / "downloads"
    source.mkdir()
    target.mkdir()
    downloads.mkdir()
    (source / "keep.py").write_text("one\n", encoding="utf-8")
    (source / "old.py").write_text("old\n", encoding="utf-8")
    (source / "结果.txt").write_text("first\n", encoding="utf-8")
    transfer = LocalProjectTransfer((source, target, downloads))

    first_snapshot = await transfer.scan(source, IgnoreRules())
    first = await transfer.push(
        TransferPlan(
            source=source,
            target_uri=target.as_uri(),
            files=tuple(signature.path for signature in first_snapshot.files),
        )
    )

    assert first.transferred == ("keep.py", "old.py", "结果.txt")
    assert (target / "keep.py").read_text(encoding="utf-8") == "one\n"
    assert (target / "结果.txt").read_text(encoding="utf-8") == "first\n"

    (source / "keep.py").write_text("two and changed\n", encoding="utf-8")
    (source / "old.py").unlink()
    (source / "new.py").write_text("new\n", encoding="utf-8")
    second_snapshot = await transfer.scan(source, IgnoreRules())
    difference = diff_manifests(manifest(first_snapshot), manifest(second_snapshot))
    second = await transfer.push(
        TransferPlan(
            source=source,
            target_uri=target.as_uri(),
            files=difference.upload_paths,
            removed=difference.removed,
        )
    )

    assert second.transferred == ("keep.py", "new.py")
    assert second.removed == ("old.py",)
    assert (target / "old.py").read_text(encoding="utf-8") == "old\n"
    assert (target / "keep.py").read_text(encoding="utf-8") == "two and changed\n"
    assert not tuple(target.rglob(".workspace107-*.tmp"))

    (target / "results").mkdir()
    (target / "results" / "metrics.json").write_text('{"accuracy": 1}\n', encoding="utf-8")
    pulled = await transfer.pull(
        PullRequest(
            source_uri=target.as_uri(),
            destination=downloads,
            include=("results/metrics.json",),
        )
    )

    assert pulled.transferred == ("results/metrics.json",)
    assert (downloads / "results" / "metrics.json").read_text(encoding="utf-8") == (
        '{"accuracy": 1}\n'
    )


async def test_local_transfer_rejects_paths_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "file.txt").write_text("outside\n", encoding="utf-8")
    transfer = LocalProjectTransfer((allowed,))

    with pytest.raises(PathOutsideAllowedRoot):
        await transfer.scan(outside, IgnoreRules())

    with pytest.raises(PathOutsideAllowedRoot):
        await transfer.push(
            TransferPlan(
                source=allowed,
                target_uri=outside.as_uri(),
                files=(),
            )
        )
