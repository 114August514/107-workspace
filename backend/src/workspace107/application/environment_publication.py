"""Closed Environment publication and canonical runtime contract."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import replace

from ..domain.enums import (
    EnvironmentAvailability,
    EnvironmentPublicationStatus,
    EnvironmentRuntimeKind,
)
from ..domain.errors import ObjectNotFound, ValidationFailed
from ..domain.ids import ENVIRONMENT_VERSION, new_id
from ..domain.models import EnvironmentPublicationAttempt, EnvironmentVersion
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort

CLUSTER_PROFILE_ID = "107"
MODULE_SYSTEM = "environment_modules"
ACTIVATION_POLICY = "purge_then_ordered_load_v1"
APPTAINER_MODULE = "apptainer/1.4.5"
APPTAINER_EXEC_POLICY = "apptainer_exec_v1"
APPTAINER_BUILD_ARCH_LABEL = "org.label-schema.build-arch"
ALLOWED_MODULES = frozenset(
    {
        "python3.12/3.12",
        "miniconda/py312",
        "cuda/12.6",
        "cuda/13.0",
        APPTAINER_MODULE,
        "go/1.24.5",
        "go/1.25.6",
        "compiler",
        "mkl",
        "mpi",
        "dnnl",
        "ccl",
        "tbb",
    }
)


def canonical_json(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonicalize_modules(modules: list[str]) -> tuple[dict[str, object], dict[str, object]]:
    if not modules:
        raise ValidationFailed("Modules runtime 至少需要一个模块")
    if len(set(modules)) != len(modules):
        raise ValidationFailed("Modules runtime 不允许重复模块")
    invalid = [module for module in modules if module not in ALLOWED_MODULES]
    if invalid:
        raise ValidationFailed(f"平台不支持模块：{', '.join(invalid)}")
    definition: dict[str, object] = {
        "cluster_profile_id": CLUSTER_PROFILE_ID,
        "module_system": MODULE_SYSTEM,
        "activation_policy": ACTIVATION_POLICY,
        "modules": modules,
    }
    execution = {
        "kind": EnvironmentRuntimeKind.MODULES.value,
        "activation_policy": ACTIVATION_POLICY,
        "commands": [["module", "purge"], *[["module", "load", module] for module in modules]],
    }
    return definition, execution


def definition_hash(definition: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(definition).encode()).hexdigest()


class EnvironmentPublicationProcessor:
    def __init__(self, repos: Repositories, storage: StoragePort, clock: Clock) -> None:
        self._repos = repos
        self._storage = storage
        self._clock = clock

    async def claim(self) -> EnvironmentPublicationAttempt | None:
        return await self._repos.environments.claim_pending_attempt(self._clock.now())

    async def process(self, attempt_id: str) -> EnvironmentPublicationAttempt:
        attempt = await self._repos.environments.get_attempt_by_id(attempt_id)
        if attempt is None:
            raise ObjectNotFound("Environment Publication Attempt", attempt_id)
        if attempt.status.is_terminal:
            return attempt
        if attempt.status is not EnvironmentPublicationStatus.PROCESSING:
            raise ValidationFailed("Environment publication attempt 尚未被处理器认领")
        existing_versions = await self._repos.environments.list_versions(attempt.environment_id)
        if any(item.version == attempt.version for item in existing_versions):
            failed = replace(
                attempt,
                status=EnvironmentPublicationStatus.FAILED,
                validation_summary="运行环境校验失败",
                validation_evidence={"validator": "environment_publication_v1"},
                failure_code="version_conflict",
                failure_reason="Environment 版本标签已存在",
                version_id=None,
                finished_at=self._clock.now(),
            )
            await self._repos.environments.update_attempt(failed)
            return failed
        try:
            definition, execution, summary, evidence = await self._validate(attempt)
        except ValidationFailed as exc:
            failed = replace(
                attempt,
                status=EnvironmentPublicationStatus.FAILED,
                validation_summary="运行环境校验失败",
                validation_evidence={"validator": "environment_publication_v1"},
                failure_code="validation_failed",
                failure_reason=str(exc),
                version_id=None,
                finished_at=self._clock.now(),
            )
            await self._repos.environments.update_attempt(failed)
            return failed
        digest = definition_hash(definition)
        version = EnvironmentVersion(
            id=new_id(ENVIRONMENT_VERSION),
            environment_id=attempt.environment_id,
            version=attempt.version,
            description=attempt.description,
            runtime_kind=attempt.runtime_kind,
            definition=definition,
            definition_hash=digest,
            execution_spec=execution,
            validation_summary=summary,
            validation_evidence=evidence,
            availability=EnvironmentAvailability.AVAILABLE,
            availability_reason="validated",
            availability_detail=summary,
            availability_checked_at=self._clock.now(),
        )
        await self._repos.environments.add_version(version)
        succeeded = replace(
            attempt,
            status=EnvironmentPublicationStatus.SUCCEEDED,
            validation_summary=summary,
            validation_evidence=evidence,
            failure_code=None,
            failure_reason=None,
            version_id=version.id,
            finished_at=self._clock.now(),
        )
        await self._repos.environments.update_attempt(succeeded)
        return succeeded

    async def refresh_availability(self, version_id: str) -> EnvironmentVersion:
        version = await self._repos.environments.get_version_by_id(version_id)
        if version is None:
            raise ObjectNotFound("Environment Version", version_id)
        try:
            if version.runtime_kind is EnvironmentRuntimeKind.MODULES:
                raw_modules = version.definition.get("modules")
                if not isinstance(raw_modules, list) or not all(
                    isinstance(item, str) for item in raw_modules
                ):
                    raise ValidationFailed("已发布 Modules 定义非法")
                definition, execution = canonicalize_modules(raw_modules)
                detail = "当前 Modules 定义仍符合 107 精确 allowlist"
            else:
                definition, execution, detail, _ = await self._validate_sif(version.definition)
            if (
                definition != version.definition
                or definition_hash(definition) != version.definition_hash
                or execution != version.execution_spec
            ):
                raise ValidationFailed("已发布 Environment 不可变定义校验不一致")
            availability = EnvironmentAvailability.AVAILABLE
            reason = "refresh_validated"
        except (ObjectNotFound, ValidationFailed) as exc:
            availability = EnvironmentAvailability.UNAVAILABLE
            reason = "refresh_failed"
            detail = str(exc)
        refreshed = await self._repos.environments.update_version_availability(
            version.id,
            availability,
            reason,
            detail,
            self._clock.now(),
        )
        if refreshed is None:  # pragma: no cover - read and update share one transaction
            raise ObjectNotFound("Environment Version", version_id)
        return refreshed

    async def _validate(
        self, attempt: EnvironmentPublicationAttempt
    ) -> tuple[dict[str, object], dict[str, object], str, dict[str, object]]:
        candidate = attempt.candidate_definition
        if attempt.runtime_kind is EnvironmentRuntimeKind.MODULES:
            raw_modules = candidate.get("modules")
            if not isinstance(raw_modules, list) or not all(
                isinstance(item, str) for item in raw_modules
            ):
                raise ValidationFailed("modules 必须是有序字符串列表")
            definition, execution = canonicalize_modules(raw_modules)
            summary = f"已验证 107 Environment Modules：按顺序加载 {', '.join(raw_modules)}"
            return (
                definition,
                execution,
                summary,
                {
                    "validator": "modules_allowlist_v1",
                    "module_count": len(raw_modules),
                    "canonical_definition_sha256": definition_hash(definition),
                },
            )
        return await self._validate_sif(candidate)

    async def _validate_sif(
        self, candidate: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, object], str, dict[str, object]]:
        locator = candidate.get("locator")
        expected_hash = candidate.get("sha256")
        expected_size = candidate.get("size")
        source_uri = candidate.get("source_uri")
        source_digest = candidate.get("source_digest")
        architecture = candidate.get("architecture")
        if (
            not isinstance(locator, str)
            or not isinstance(expected_hash, str)
            or not isinstance(expected_size, int)
        ):
            raise ValidationFailed("SIF 候选缺少 locator、sha256 或 size")
        content = await self._storage.read_blob(locator)
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != expected_hash or len(content) != expected_size:
            raise ValidationFailed("SIF 候选字节的 SHA-256 或大小不一致")
        if architecture not in {"x86_64", "amd64"}:
            raise ValidationFailed("SIF architecture 必须是 x86_64")
        evidence = await _inspect_sif(content)
        definition = {
            "sha256": actual_hash,
            "size": len(content),
            "locator": locator,
            "source_uri": source_uri or "",
            "source_digest": source_digest or "",
            "architecture": "x86_64",
            "launcher_module": APPTAINER_MODULE,
            "exec_policy": APPTAINER_EXEC_POLICY,
        }
        execution = {
            "kind": EnvironmentRuntimeKind.APPTAINER_SIF.value,
            "launcher_module": APPTAINER_MODULE,
            "exec_policy": APPTAINER_EXEC_POLICY,
            "locator": locator,
            "sha256": actual_hash,
        }
        evidence.update(
            {"canonical_definition_sha256": definition_hash(definition), "byte_size": len(content)}
        )
        return definition, execution, "SIF 字节、摘要与 Apptainer inspect 校验通过", evidence


async def _inspect_sif(content: bytes) -> dict[str, object]:
    executable = _find_apptainer()
    if executable is None:
        raise ValidationFailed("未安装 Apptainer CLI，无法验证 SIF；不会降级或伪造成功")
    fd, filename = tempfile.mkstemp(suffix=".sif")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        process = await asyncio.create_subprocess_exec(
            executable,
            "inspect",
            "--json",
            filename,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            raise ValidationFailed(f"Apptainer 拒绝该 SIF：{detail or 'inspect failed'}")
        try:
            inspect_document = json.loads(stdout)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationFailed("Apptainer inspect 未返回有效 JSON") from exc
        if not isinstance(inspect_document, dict):
            raise ValidationFailed("Apptainer inspect JSON 缺少 SIF architecture metadata")
        data = inspect_document.get("data")
        attributes = data.get("attributes") if isinstance(data, dict) else None
        labels = attributes.get("labels") if isinstance(attributes, dict) else None
        inspected_architecture = (
            labels.get(APPTAINER_BUILD_ARCH_LABEL) if isinstance(labels, dict) else None
        )
        if not isinstance(inspected_architecture, str):
            raise ValidationFailed("Apptainer inspect JSON 缺少 SIF architecture metadata")
        normalized_architecture = {
            "amd64": "x86_64",
            "x86_64": "x86_64",
        }.get(inspected_architecture)
        if normalized_architecture != "x86_64":
            raise ValidationFailed(
                f"Apptainer inspect 报告不支持的 SIF architecture：{inspected_architecture}"
            )
        return {
            "validator": "apptainer_inspect_v1",
            "cli": executable,
            "inspect_architecture": inspected_architecture,
            "architecture": normalized_architecture,
            "inspect_sha256": hashlib.sha256(stdout).hexdigest(),
        }
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(filename)


def _find_apptainer() -> str | None:
    from shutil import which

    return which("apptainer")
