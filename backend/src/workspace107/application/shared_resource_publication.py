"""Durable Shared Resource candidate validation and atomic publication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import timedelta

from ..domain import ids
from ..domain.enums import ActivityAction, SharedResourcePublicationStatus, TargetType
from ..domain.errors import ObjectNotFound, ValidationFailed
from ..domain.models import (
    SharedResourceFile,
    SharedResourcePublicationAttempt,
    SharedResourceVersion,
)
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort
from .activity import ActivityRecorder
from .shared_resource_service import normalize_shared_resource_path


class SharedResourcePublicationProcessor:
    """Processes durable attempts for the supported single-publication-loop deployment.

    A separately committed claim makes restart recovery explicit; terminal reprocessing is
    idempotent. Row locks are defensive transaction guards, not a multi-replica worker or
    fencing contract. A future multi-worker or long-running validator requires a distinct
    lease/heartbeat design.
    """

    def __init__(
        self,
        repos: Repositories,
        clock: Clock,
        storage: StoragePort,
        activity: ActivityRecorder,
        *,
        recovery_seconds: float,
    ) -> None:
        self._repos = repos
        self._clock = clock
        self._storage = storage
        self._activity = activity
        self._recovery_seconds = recovery_seconds

    async def claim_next(self) -> SharedResourcePublicationAttempt | None:
        now = self._clock.now()
        return await self._repos.shared_resources.claim_next_attempt(
            now=now,
            recover_before=now - timedelta(seconds=self._recovery_seconds),
        )

    async def process(self, attempt_id: str) -> SharedResourcePublicationAttempt:
        attempt = await self._repos.shared_resources.get_attempt_by_id(attempt_id)
        if attempt is None:
            raise ObjectNotFound("Shared Resource Publication Attempt", attempt_id)
        if attempt.status.is_terminal:
            return attempt
        if attempt.status is not SharedResourcePublicationStatus.PROCESSING:
            raise ValidationFailed("发布尝试尚未被处理器认领")

        expected_version_id = self._version_id_for_attempt(attempt.id)
        existing = await self._repos.shared_resources.get_version_by_id(expected_version_id)
        if existing is not None:
            succeeded = replace(
                attempt,
                status=SharedResourcePublicationStatus.SUCCEEDED,
                validation_summary=existing.validation_summary,
                failure_reason=None,
                version_id=existing.id,
                finished_at=self._clock.now(),
            )
            await self._repos.shared_resources.update_attempt(succeeded)
            return succeeded

        try:
            manifest_hash, summary = await self._validate(attempt.files)
        except ValidationFailed as exc:
            failed = replace(
                attempt,
                status=SharedResourcePublicationStatus.FAILED,
                validation_summary="候选内容校验失败",
                failure_reason=str(exc),
                version_id=None,
                finished_at=self._clock.now(),
            )
            await self._repos.shared_resources.update_attempt(failed)
            return failed

        resource = await self._repos.shared_resources.get_by_id(attempt.shared_resource_id)
        if resource is None:  # protected by the attempt foreign key
            raise ObjectNotFound("Shared Resource", attempt.shared_resource_id)
        sequence = await self._repos.shared_resources.next_version_sequence_for_publication(
            attempt.shared_resource_id
        )
        version = SharedResourceVersion(
            id=expected_version_id,
            shared_resource_id=attempt.shared_resource_id,
            sequence=sequence,
            description=attempt.description,
            files=attempt.files,
            manifest_hash=manifest_hash,
            validation_summary=summary,
            created_by=attempt.created_by,
            created_at=self._clock.now(),
        )
        await self._repos.shared_resources.add_version(version)
        succeeded = replace(
            attempt,
            status=SharedResourcePublicationStatus.SUCCEEDED,
            validation_summary=summary,
            failure_reason=None,
            version_id=version.id,
            finished_at=self._clock.now(),
        )
        await self._repos.shared_resources.update_attempt(succeeded)
        await self._activity.record(
            actor_id=attempt.created_by,
            owner=resource.owner,
            action=ActivityAction.SHARED_RESOURCE_VERSION_PUBLISHED,
            target_type=TargetType.SHARED_RESOURCE_VERSION,
            target_id=version.id,
            target_name=f"{resource.name} · {version.label}",
            detail=version.description,
        )
        return succeeded

    async def _validate(self, files: tuple[SharedResourceFile, ...]) -> tuple[str, str]:
        """Validate the normalized manifest against every content-addressed blob."""
        seen: set[str] = set()
        total_size = 0
        canonical: list[dict[str, object]] = []
        for entry in sorted(files, key=lambda item: item.path):
            normalized = normalize_shared_resource_path(entry.path)
            if normalized != entry.path:
                raise ValidationFailed(f"文件 {entry.path!r} 的候选路径未规范化")
            if normalized in seen:
                raise ValidationFailed(f"候选清单中存在重复路径 {normalized!r}")
            try:
                content = await self._storage.read_blob(entry.content_hash)
            except ObjectNotFound as exc:
                raise ValidationFailed(f"文件 {entry.path} 的候选内容不存在") from exc
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != entry.content_hash:
                raise ValidationFailed(f"文件 {entry.path} 的内容哈希不一致")
            if len(content) != entry.size:
                raise ValidationFailed(f"文件 {entry.path} 的内容大小不一致")
            seen.add(normalized)
            total_size += entry.size
            canonical.append(
                {"path": entry.path, "size": entry.size, "content_hash": entry.content_hash}
            )
        if not canonical:
            raise ValidationFailed("候选清单必须至少包含一个文件")
        encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()
        manifest_hash = hashlib.sha256(encoded).hexdigest()
        summary = f"已校验 {len(canonical)} 个文件，共 {total_size} 字节；内容哈希与大小一致"
        return manifest_hash, summary

    @staticmethod
    def _version_id_for_attempt(attempt_id: str) -> str:
        return f"{ids.SHARED_RESOURCE_VERSION}_{attempt_id.split('_', 1)[1]}"
