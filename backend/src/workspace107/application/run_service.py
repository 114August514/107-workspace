"""Run 创建、提交与查询用例。

创建 Run 的顺序（设计稿 §3.1.6 规则 6）::

    校验与解析 -> 固定 Run Snapshot -> 准备工作目录 -> 提交调度任务
    -> 关联 Scheduler Job -> 更新执行状态

创建或重新执行 Run 时都要按当前权限和资源资格重新校验引用；
历史上曾经成功使用，不代表当前仍然可以使用（设计稿 §3.4.3）。
"""

from __future__ import annotations

import codecs
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.compute import (
    ComputePlan,
    ComputeRequest,
    ResourceEntitlement,
    SchedulerMapping,
    check_request_against_plan,
    resolve_scheduler_configuration,
)
from ..domain.config_scope import SecretReference
from ..domain.enums import (
    ActivityAction,
    InputSourceType,
    LogStream,
    RunEventType,
    RunStatus,
    TargetType,
)
from ..domain.errors import (
    ConflictError,
    ObjectNotFound,
    PermissionDenied,
    PreflightRejected,
    SchedulerError,
    SharedResourceUnavailable,
    ValidationFailed,
)
from ..domain.models import (
    Artifact,
    EnvironmentVersion,
    InputBinding,
    ProjectVersion,
    Run,
    RunConfiguration,
    RunEvent,
    RunLogChunk,
)
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.scheduler import SchedulerPort, SchedulerSubmission
from ..domain.ports.secret_vault import SecretVault
from ..domain.ports.storage import ArtifactEntry, RunInput, StoragePort
from ..domain.run_snapshot import RunSnapshot, build_snapshot
from ..domain.secrets import ResolvedEnv, redact
from ..domain.slurm_projection import SlurmPlanProjection, SlurmProjection
from .access import AccessGuard, ProjectAccess
from .activity import ActivityRecorder
from .asset_use import (
    environment_version_for_owner_use,
    shared_resource_version_for_owner_use,
)
from .notifier import Notifier
from .scoped_config_resolver import ScopedConfigResolver

MAX_LOG_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class RunDraft:
    """一次 Run 的提交意图。"""

    run_configuration_id: str
    project_version_id: str | None = None
    """None 表示使用 Project 的最新版本。"""
    name: str = ""
    command_override: str = ""
    working_directory_override: str = ""
    environment_version_id_override: str = ""
    input_bindings_override: tuple[InputBinding, ...] | None = None
    compute_request_override: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """提交前检查结果。"""

    problems: list[str] = field(default_factory=list)
    project_version: ProjectVersion | None = None
    environment_version: EnvironmentVersion | None = None
    compute_plan: ComputePlan | None = None
    compute_request: ComputeRequest | None = None
    slurm_projection: SlurmPlanProjection | None = None
    resolved_env_literals: dict[str, str] = field(default_factory=dict)
    resolved_env_secret_refs: dict[str, SecretReference] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass(frozen=True, slots=True)
class RunSubmission:
    """一次提交的结果。

    ``created`` 为 False 表示这次是幂等重放：返回的是之前那次提交的 Run，
    没有产生新的计算。
    """

    run: Run
    created: bool


@dataclass(frozen=True, slots=True)
class RunView:
    """A Run plus its current authoritative User username projection."""

    run: Run
    initiated_by_username: str | None


@dataclass(frozen=True, slots=True)
class RunDetail:
    run: RunView
    snapshot: RunSnapshot
    events: list[RunEvent]
    artifacts: list[Artifact]


class RunService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        storage: StoragePort,
        scheduler: SchedulerPort,
        slurm_projection: SlurmProjection | None,
        secrets: SecretVault,
        activity: ActivityRecorder,
        notifier: Notifier,
        config_resolver: ScopedConfigResolver,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._storage = storage
        self._scheduler = scheduler
        self._slurm_projection = slurm_projection
        self._secrets = secrets
        self._config_resolver = config_resolver
        self._activity = activity
        self._notifier = notifier

    # -- 查询 -----------------------------------------------------------

    async def list_for_project(
        self, user_id: str, project_id: str, page: PageRequest
    ) -> Page[RunView]:
        await self._guard.project(user_id, project_id, owner_scope=True)
        runs = await self._repos.runs.list_for_project(project_id, page)
        return Page(
            items=await self._views(runs.items),
            page=runs.page,
            page_size=runs.page_size,
            total=runs.total,
        )

    async def list_recent_for_user(self, user_id: str, *, limit: int = 10) -> list[RunView]:
        return await self._views(await self._repos.runs.list_for_user(user_id, limit=limit))

    async def view(self, run: Run) -> RunView:
        """Resolve one Run without substituting the current viewer's identity."""

        user = await self._repos.users.get(run.initiated_by_user_id)
        return RunView(
            run=run,
            initiated_by_username=user.username if user is not None else None,
        )

    async def _views(self, runs: list[Run]) -> list[RunView]:
        users = await self._repos.users.list_by_ids({run.initiated_by_user_id for run in runs})
        return [
            RunView(
                run=run,
                initiated_by_username=(
                    users[run.initiated_by_user_id].username
                    if run.initiated_by_user_id in users
                    else None
                ),
            )
            for run in runs
        ]

    async def get_detail(self, user_id: str, run_id: str) -> RunDetail:
        access = await self._guard.run(user_id, run_id)
        snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        if snapshot is None:  # pragma: no cover - 数据损坏才会发生
            raise ObjectNotFound("Run Snapshot", access.run.snapshot_id)
        return RunDetail(
            run=await self.view(access.run),
            snapshot=snapshot,
            events=await self._repos.run_events.list_for_run(run_id),
            artifacts=await self._repos.artifacts.list_for_run(run_id),
        )

    async def read_logs(self, user_id: str, run_id: str) -> list[RunLogChunk]:
        """读取 stdout 和 stderr。

        返回之前会把已知 Secret 明文抹掉——用户程序自己把 Token 打到 stdout
        时，这是保护日志不展示 Secret 明文的最后一道防线（设计稿 §3.1.4）。
        """
        access = await self._guard.run(user_id, run_id)
        snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        secret_values = await self._log_secret_values(access.run, snapshot)

        chunks: list[RunLogChunk] = []
        for stream in (LogStream.STDOUT, LogStream.STDERR):
            content, truncated = await self._storage.read_log(
                run_id, stream, max_bytes=MAX_LOG_BYTES
            )
            chunks.append(
                RunLogChunk(
                    stream=stream,
                    content=redact(content, secret_values),
                    truncated=truncated,
                )
            )
        return chunks

    async def stream_logs(self, user_id: str, run_id: str, stream: str) -> AsyncIterator[bytes]:
        """授权后流式返回完整日志，避免下载受尾部预览限制或占满内存。"""
        access = await self._guard.run(user_id, run_id)
        snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        secret_values = await self._log_secret_values(access.run, snapshot)
        streams = (
            (LogStream.STDOUT, LogStream.STDERR) if stream == "combined" else (LogStream(stream),)
        )

        async def chunks() -> AsyncIterator[bytes]:
            for index, selected in enumerate(streams):
                if index and stream == "combined":
                    yield b"\n\n--- stderr ---\n"
                async for chunk in self._redacted_log_chunks(run_id, selected, secret_values):
                    yield chunk

        return chunks()

    async def _log_secret_values(self, run: Run, snapshot: RunSnapshot | None) -> list[str]:
        secret_values = await self._secrets.redaction_values(run.id)
        if (
            run.submitted_at is not None
            and snapshot is not None
            and snapshot.env_secret_refs
            and not secret_values
        ):
            raise ValidationFailed("Run Secret redaction retention is unavailable")
        return secret_values

    async def _redacted_log_chunks(
        self, run_id: str, stream: LogStream, secret_values: list[str]
    ) -> AsyncIterator[bytes]:
        """Redact complete secrets while retaining only possible secret prefixes."""
        values = [value for value in secret_values if value]
        if not values:
            async for raw in self._storage.iter_log(run_id, stream, chunk_size=64 * 1024):
                yield raw
            return

        pattern = re.compile(
            "|".join(
                re.escape(value) for value in sorted(dict.fromkeys(values), key=len, reverse=True)
            )
        )
        pending = ""
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        async for raw in self._storage.iter_log(run_id, stream, chunk_size=64 * 1024):
            pending += decoder.decode(raw)
            while pending:
                uncertain_start = len(pending) - _secret_prefix_suffix_length(pending, values)
                match = pattern.search(pending)
                if match is None:
                    if uncertain_start == 0:
                        break
                    safe, pending = pending[:uncertain_start], pending[uncertain_start:]
                elif match.end() <= uncertain_start:
                    safe, pending = pending[: match.end()], pending[match.end() :]
                elif uncertain_start and match.start() >= uncertain_start:
                    safe, pending = pending[:uncertain_start], pending[uncertain_start:]
                else:
                    break
                if safe:
                    yield redact(safe, values).encode("utf-8")

        pending += decoder.decode(b"", final=True)
        if pending:
            yield redact(pending, values).encode("utf-8")

    async def list_artifact_files(self, user_id: str, artifact_id: str) -> list[ArtifactEntry]:
        artifact = await self._require_artifact(user_id, artifact_id)
        return await self._storage.list_artifact_files(artifact.id)

    async def read_artifact_file(
        self, user_id: str, artifact_id: str, path: str
    ) -> tuple[bytes, str]:
        """读取 Artifact 中的一个文件，返回内容和建议的文件名。"""
        artifact = await self._require_artifact(user_id, artifact_id)
        data = await self._storage.read_artifact_file(artifact.id, path)
        return data, path.rsplit("/", 1)[-1]

    async def stream_artifact(
        self, user_id: str, artifact_id: str, path: str | None
    ) -> tuple[AsyncIterator[bytes], str]:
        artifact = await self._require_artifact(user_id, artifact_id)
        if path:
            return (
                self._storage.iter_artifact_file(artifact.id, path, chunk_size=64 * 1024),
                path.rsplit("/", 1)[-1],
            )
        filename = f"{artifact.name or artifact.id}.zip"
        return (
            self._storage.iter_artifact_archive(artifact.id, chunk_size=64 * 1024),
            filename,
        )

    async def _require_artifact(self, user_id: str, artifact_id: str) -> Artifact:
        """取 Artifact 并校验访问权。

        Artifact 归属于产生它的 Run（设计稿 §3.2.1），所以权限沿 Run 的链路判断。
        无权访问和不存在返回同一种错误，避免通过错误类型探测对象是否存在。
        """
        artifact = await self._repos.artifacts.get(artifact_id)
        if artifact is None:
            raise ObjectNotFound("Artifact", artifact_id)
        try:
            await self._guard.run(user_id, artifact.run_id)
        except ObjectNotFound as exc:
            raise ObjectNotFound("Artifact", artifact_id) from exc
        if not artifact.is_available:
            raise ObjectNotFound("Artifact 内容", artifact_id)
        return artifact

    # -- 提交前检查 -----------------------------------------------------

    async def preflight(self, user_id: str, project_id: str, draft: RunDraft) -> PreflightResult:
        """执行提交前检查，返回全部阻止提交的问题。

        这里只读不写，前端可以在用户点击「提交」之前先调用一次。
        """
        access = await self._guard.project(user_id, project_id, needs=Capability.RUN_SUBMIT)
        problems: list[str] = []

        configuration = await self._repos.run_configurations.get(draft.run_configuration_id)
        if configuration is None or configuration.project_id != project_id:
            raise ObjectNotFound("Run Configuration", draft.run_configuration_id)

        version = await self._resolve_project_version(project_id, draft.project_version_id)
        if version is None:
            problems.append("Project 还没有保存过版本，请先保存一个 Project Version")

        environment_version = await self._resolve_environment_version(
            user_id,
            configuration,
            access.project.owner,
            problems,
            draft.environment_version_id_override,
        )

        plan = await self._repos.compute_plans.get(configuration.compute_plan_id)
        request: ComputeRequest | None = None
        if plan is None:
            problems.append("运行方案引用的算力方案已不存在")
        else:
            entitlement = await self._repos.entitlements.get_for_plan(user_id, plan.id)
            if entitlement is None:
                problems.append(f"你没有算力方案「{plan.name}」的使用权益")
            elif entitlement.is_expired(self._clock.now().isoformat()):
                problems.append(f"算力方案「{plan.name}」的资源权益已过期")
            else:
                problems.extend(await self._check_concurrency(user_id, entitlement))

            slurm_projection = None
            if self._scheduler.name == "slurm":
                assert self._slurm_projection is not None
                user = await self._repos.users.get(user_id)
                slurm_projection = self._slurm_projection.project(
                    plan, username=user.username if user is not None else None
                )
                if not slurm_projection.ok:
                    problems.append(
                        f"算力方案「{plan.name}」当前不可用："
                        f"{slurm_projection.detail}（{slurm_projection.reason}）"
                    )
                else:
                    assert slurm_projection.plan is not None
                    plan = slurm_projection.plan

            request = self._resolve_compute_request(plan, configuration, draft)
            problems.extend(check_request_against_plan(plan, request))

        command = (draft.command_override or configuration.command).strip()
        if not command:
            problems.append("执行命令不能为空")
        resolved = await self._config_resolver.resolve(
            access,
            user_id,
            configuration.environment_variables,
        )
        problems.extend(resolved.problems)

        problems.extend(
            await self._check_inputs(
                user_id,
                configuration,
                access.project.owner,
                draft.input_bindings_override,
            )
        )

        return PreflightResult(
            problems=problems,
            project_version=version,
            environment_version=environment_version,
            compute_plan=plan,
            compute_request=request,
            slurm_projection=slurm_projection,
            resolved_env_literals=resolved.literals,
            resolved_env_secret_refs=resolved.secret_refs,
        )

    # -- 创建与提交 -----------------------------------------------------

    async def create(
        self,
        user_id: str,
        project_id: str,
        draft: RunDraft,
        *,
        idempotency_key: str | None = None,
    ) -> RunSubmission:
        """创建 Run 并提交给调度系统。

        提交失败不会回滚 Run——失败本身也是需要被记录和排查的历史事实。

        带幂等键时，同一个键的重复请求返回上一次的结果，不会再跑一次。
        """
        access = await self._guard.project(user_id, project_id, needs=Capability.RUN_SUBMIT)

        replayed = await self._replay_or_reserve(
            user_id, idempotency_key, "create_run", project_id=project_id
        )
        if replayed is not None:
            return RunSubmission(run=replayed, created=False)

        configuration = await self._repos.run_configurations.get(draft.run_configuration_id)
        if configuration is None or configuration.project_id != project_id:
            raise ObjectNotFound("Run Configuration", draft.run_configuration_id)

        # 先独占发起 User 在该算力方案上的权益行，再做提交前检查。
        #
        # 并发上限是「数一数还有几个名额 -> 创建 Run」，这两步之间不能被别的请求
        # 插进来，否则两个请求会同时读到「还没到上限」，然后都创建成功——
        # 上限就形同虚设。锁一直持有到本次请求的事务结束。
        await self._repos.entitlements.lock_for_plan(user_id, configuration.compute_plan_id)

        result = await self.preflight(user_id, project_id, draft)
        if not result.ok:
            raise PreflightRejected(result.problems)

        assert result.project_version is not None
        assert result.environment_version is not None
        assert result.compute_plan is not None
        assert result.compute_request is not None

        now = self._clock.now()
        snapshot = build_snapshot(
            snapshot_id=ids.new_id(ids.RUN_SNAPSHOT),
            project_id=project_id,
            project_version_id=result.project_version.id,
            source_run_configuration_id=configuration.id,
            working_directory=(draft.working_directory_override or configuration.working_directory),
            command=(draft.command_override or configuration.command).strip(),
            environment_version_id=result.environment_version.id,
            environment_definition_hash=result.environment_version.definition_hash,
            environment_execution_spec=result.environment_version.execution_spec,
            resolved_env=_as_resolved_env(
                result.resolved_env_literals, result.resolved_env_secret_refs
            ),
            input_bindings=(
                draft.input_bindings_override
                if draft.input_bindings_override is not None
                else configuration.input_bindings
            ),
            compute_plan_id=result.compute_plan.id,
            compute_request=result.compute_request,
            scheduler=resolve_scheduler_configuration(result.compute_plan, result.compute_request),
            artifact_rules=configuration.artifact_rules,
            initiated_by_user_id=user_id,
            created_at=now,
        )
        await self._repos.run_snapshots.add(snapshot)
        run = Run(
            id=ids.new_id(ids.RUN),
            project_id=project_id,
            snapshot_id=snapshot.id,
            compute_plan_id=snapshot.compute_plan_id,
            project_version_id=snapshot.project_version_id,
            project_version_label=result.project_version.label,
            source_run_configuration_id=configuration.id,
            source_run_id=None,
            name=draft.name.strip() or f"{access.project.name} · {result.project_version.label}",
            status=RunStatus.QUEUED,
            initiated_by_user_id=user_id,
            created_at=now,
        )
        await self._repos.runs.add(run)
        await self._record_event(run.id, RunEventType.CREATED, "已固定 Run Snapshot")
        await self._attach_idempotency(user_id, idempotency_key, run.id)

        await self._submit(run, snapshot, result.project_version)
        await self._record_run_activity(
            user_id, run, access.project.owner, ActivityAction.RUN_SUBMITTED
        )
        return RunSubmission(run=run, created=True)

    async def rerun(
        self,
        user_id: str,
        run_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> RunSubmission:
        """使用相同代码快照和配置重新运行。

        必须创建新的 Run 和新的 Run Snapshot，不能重启原有 Run（GR-306）。
        同时按重新执行时的权限和资源资格重新校验全部引用（设计稿 §3.4.3）。
        """
        access = await self._guard.run(user_id, run_id, needs=Capability.RUN_SUBMIT)

        replayed = await self._replay_or_reserve(
            user_id, idempotency_key, "rerun", source_run_id=run_id
        )
        if replayed is not None:
            return RunSubmission(run=replayed, created=False)

        source_snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        if source_snapshot is None:  # pragma: no cover
            raise ObjectNotFound("Run Snapshot", access.run.snapshot_id)

        # 和 create 一样要先独占权益行——重跑同样占用并发名额。
        await self._repos.entitlements.lock_for_plan(user_id, source_snapshot.compute_plan_id)

        problems = await self._revalidate_snapshot(source_snapshot, access, user_id)
        if problems:
            raise PreflightRejected(problems)

        environment_version = await environment_version_for_owner_use(
            self._repos,
            user_id,
            source_snapshot.environment_version_id,
            access.project.owner,
        )
        plan = await self._repos.compute_plans.get(source_snapshot.compute_plan_id)
        project_version = await self._repos.project_versions.get(source_snapshot.project_version_id)
        assert environment_version is not None and plan is not None and project_version is not None

        now = self._clock.now()
        snapshot = build_snapshot(
            snapshot_id=ids.new_id(ids.RUN_SNAPSHOT),
            project_id=source_snapshot.project_id,
            project_version_id=source_snapshot.project_version_id,
            source_run_configuration_id=source_snapshot.source_run_configuration_id,
            working_directory=source_snapshot.working_directory,
            command=source_snapshot.command,
            environment_version_id=environment_version.id,
            environment_definition_hash=environment_version.definition_hash,
            environment_execution_spec=environment_version.execution_spec,
            resolved_env=_as_resolved_env(
                source_snapshot.env_literals, source_snapshot.env_secret_refs
            ),
            input_bindings=source_snapshot.input_bindings,
            compute_plan_id=plan.id,
            compute_request=source_snapshot.compute_request,
            scheduler=source_snapshot.scheduler,
            artifact_rules=source_snapshot.artifact_rules,
            initiated_by_user_id=user_id,
            created_at=now,
        )
        await self._repos.run_snapshots.add(snapshot)

        run = Run(
            id=ids.new_id(ids.RUN),
            project_id=access.run.project_id,
            project_version_id=source_snapshot.project_version_id,
            project_version_label=project_version.label,
            snapshot_id=snapshot.id,
            compute_plan_id=snapshot.compute_plan_id,
            source_run_configuration_id=source_snapshot.source_run_configuration_id,
            source_run_id=access.run.id,
            name=access.run.name,
            status=RunStatus.QUEUED,
            initiated_by_user_id=user_id,
            created_at=now,
        )
        await self._repos.runs.add(run)
        await self._record_event(run.id, RunEventType.CREATED, f"基于 Run {access.run.id} 重新运行")
        await self._attach_idempotency(user_id, idempotency_key, run.id)

        await self._submit(run, snapshot, project_version)
        await self._record_run_activity(
            user_id,
            run,
            access.project.owner,
            ActivityAction.RUN_SUBMITTED,
            detail=f"重跑自 {access.run.name}",
        )
        return RunSubmission(run=run, created=True)

    async def adjusted_rerun(
        self,
        user_id: str,
        run_id: str,
        draft: RunDraft,
        *,
        idempotency_key: str | None = None,
    ) -> RunSubmission:
        """以历史 Snapshot 为基线，调整配置后创建新的 Run。"""
        access = await self._guard.run(user_id, run_id, needs=Capability.RUN_SUBMIT)
        replayed = await self._replay_or_reserve(
            user_id, idempotency_key, "adjusted_rerun", source_run_id=run_id
        )
        if replayed is not None:
            return RunSubmission(run=replayed, created=False)

        source = await self._repos.run_snapshots.get(access.run.snapshot_id)
        if source is None:  # pragma: no cover - 数据损坏才会发生
            raise ObjectNotFound("Run Snapshot", access.run.snapshot_id)
        await self._repos.entitlements.lock_for_plan(user_id, source.compute_plan_id)

        project_version = await self._repos.project_versions.get(draft.project_version_id or "")
        environment_version = await environment_version_for_owner_use(
            self._repos,
            user_id,
            draft.environment_version_id_override or source.environment_version_id,
            access.project.owner,
        )
        plan = await self._repos.compute_plans.get(source.compute_plan_id)
        problems: list[str] = []
        if not draft.command_override.strip():
            problems.append("执行命令不能为空")
        if project_version is None or project_version.project_id != source.project_id:
            problems.append("调整后的 Project Version 不存在或不属于当前 Project")
        if environment_version is None:
            problems.append("调整后的运行环境版本不存在或无权供当前 Project 使用")
        elif environment_version.availability.value != "available":
            problems.append(f"运行环境版本 {environment_version.version} 当前不可用")
        if plan is None:
            problems.append("来源算力方案已不存在")
        if problems:
            raise PreflightRejected(problems)
        assert project_version is not None and environment_version is not None and plan is not None

        request = (
            ComputeRequest(**draft.compute_request_override)
            if draft.compute_request_override is not None
            else source.compute_request
        )
        bindings = draft.input_bindings_override
        candidate = build_snapshot(
            snapshot_id=ids.new_id(ids.RUN_SNAPSHOT),
            project_id=source.project_id,
            project_version_id=project_version.id,
            source_run_configuration_id=source.source_run_configuration_id,
            working_directory=draft.working_directory_override or source.working_directory,
            command=(draft.command_override or source.command).strip(),
            environment_version_id=environment_version.id,
            environment_definition_hash=environment_version.definition_hash,
            environment_execution_spec=environment_version.execution_spec,
            resolved_env=_as_resolved_env(source.env_literals, source.env_secret_refs),
            input_bindings=bindings if bindings is not None else source.input_bindings,
            compute_plan_id=plan.id,
            compute_request=request,
            scheduler=resolve_scheduler_configuration(plan, request),
            artifact_rules=source.artifact_rules,
            initiated_by_user_id=user_id,
            created_at=self._clock.now(),
        )
        problems = await self._revalidate_snapshot(candidate, access, user_id)
        if problems:
            raise PreflightRejected(problems)

        await self._repos.run_snapshots.add(candidate)
        run = Run(
            id=ids.new_id(ids.RUN),
            project_id=source.project_id,
            project_version_id=project_version.id,
            project_version_label=project_version.label,
            snapshot_id=candidate.id,
            compute_plan_id=candidate.compute_plan_id,
            source_run_configuration_id=source.source_run_configuration_id,
            source_run_id=access.run.id,
            name=draft.name.strip() or access.run.name,
            status=RunStatus.QUEUED,
            initiated_by_user_id=user_id,
            created_at=candidate.created_at,
        )
        await self._repos.runs.add(run)
        await self._record_event(
            run.id, RunEventType.CREATED, f"基于 Run {access.run.id} 调整后重新运行"
        )
        await self._attach_idempotency(user_id, idempotency_key, run.id)
        await self._submit(run, candidate, project_version)
        await self._record_run_activity(
            user_id,
            run,
            access.project.owner,
            ActivityAction.RUN_SUBMITTED,
            detail=f"调整后重跑自 {access.run.name}",
        )
        return RunSubmission(run=run, created=True)

    async def cancel(self, user_id: str, run_id: str) -> Run:
        access = await self._guard.run(user_id, run_id, needs=Capability.RUN_CANCEL)
        run = access.run
        if run.is_terminal:
            raise ConflictError(f"Run 已处于终态 {run.status}，无法取消")

        await self._record_event(run.id, RunEventType.CANCEL_REQUESTED, "用户请求取消")
        if run.scheduler_job_id:
            await self._scheduler.cancel(run.scheduler_job_id)
        else:
            # 还没提交成功就取消，直接落到终态。
            run.status = RunStatus.CANCELLED
            run.finished_at = self._clock.now()
            await self._repos.runs.update(run)
            await self._record_event(run.id, RunEventType.CANCELLED, "任务尚未提交，已直接取消")
        await self._record_run_activity(
            user_id, run, access.project.owner, ActivityAction.RUN_CANCELLED
        )
        return run

    # -- 内部 -----------------------------------------------------------
    async def validate_execution_context(
        self, run: Run, snapshot: RunSnapshot
    ) -> tuple[ProjectAccess, dict[str, str]]:
        """Revalidate persisted execution identity and every exact external reference.

        This boundary deliberately reads ``run.initiated_by_user_id`` and
        ``run.project_id`` again instead of trusting request-time access. A delayed
        Worker can call the same seam immediately before materialization.
        """
        try:
            access = await self._guard.project(
                run.initiated_by_user_id,
                run.project_id,
                needs=Capability.RUN_SUBMIT,
                owner_scope=True,
            )
        except (ObjectNotFound, PermissionDenied) as exc:
            raise ValidationFailed("Run 发起 User 当前已无权在来源 Project 执行") from exc

        problems: list[str] = []
        environment_version = await environment_version_for_owner_use(
            self._repos,
            run.initiated_by_user_id,
            snapshot.environment_version_id,
            access.project.owner,
        )
        if environment_version is None:
            problems.append("来源运行环境版本已不存在或无权供当前 Project 使用")
        elif environment_version.availability.value != "available":
            problems.append(f"运行环境版本 {environment_version.version} 当前不可用")
        elif (
            environment_version.definition_hash != snapshot.environment_definition_hash
            or environment_version.execution_spec != snapshot.environment_execution_spec
        ):
            problems.append("运行环境版本定义与 Run Snapshot 不一致，拒绝回退或替换")

        for binding in snapshot.input_bindings:
            if binding.source_type is InputSourceType.ARTIFACT:
                problem = await self._artifact_input_problem(
                    binding.source_id,
                    binding.access_path,
                    access.project.owner,
                )
            else:
                problem = await self._check_shared_resource_version_input(
                    run.initiated_by_user_id,
                    binding.source_id,
                    binding.access_path,
                    binding.source_subpath,
                    access.project.owner,
                    raise_unavailable=True,
                )
            if problem is not None:
                problems.append(problem)

        secret_values, secret_problems = await self._config_resolver.validate_and_resolve(
            access,
            run.initiated_by_user_id,
            snapshot.env_secret_refs,
        )
        problems.extend(secret_problems)
        if problems:
            raise ValidationFailed("; ".join(problems))
        return access, secret_values

    async def _submit(
        self,
        run: Run,
        snapshot: RunSnapshot,
        version: ProjectVersion,
    ) -> None:
        # 执行身份以持久化的 Run 记录为准（GR-307），不从调用参数传递——
        # 快照校验、Secret 解析和通知收件人都读同一个字段。
        scheduler_submit_attempted = False
        try:
            _, values = await self.validate_execution_context(run, snapshot)
            if values:
                await self._secrets.retain_for_redaction(run.id, list(values.values()))
            inputs = await self._materialize_inputs(snapshot.input_bindings)
            paths = await self._storage.prepare_run_directory(
                run.id,
                files=[(f.path, f.content_hash) for f in version.files],
                inputs=inputs,
            )
            environment = dict(snapshot.env_literals)
            # 输入内容在执行环境中的根目录。Input Binding 的 access_path 是
            # 相对于它的绝对路径，例如 /inputs/train -> $WORKSPACE107_INPUTS_DIR/inputs/train。
            environment.setdefault("WORKSPACE107_INPUTS_DIR", str(paths.inputs))
            for env_name in snapshot.env_secret_refs:
                environment[env_name] = values[env_name]

            work_dir = paths.work
            if snapshot.working_directory not in {"", "."}:
                work_dir = paths.work / snapshot.working_directory

            execution_spec = dict(snapshot.environment_execution_spec)
            if execution_spec.get("kind") == "apptainer_sif":
                locator = execution_spec.get("locator")
                if not isinstance(locator, str):
                    raise ValidationFailed("Apptainer execution spec 缺少 CAS locator")
                execution_spec["locator"] = str(await self._storage.resolve_blob_path(locator))

            scheduler_submit_attempted = True
            job_id = await self._scheduler.submit(
                SchedulerSubmission(
                    run_id=run.id,
                    job_name=run.name,
                    work_dir=work_dir,
                    command=snapshot.command,
                    environment_execution_spec=execution_spec,
                    stdout_path=paths.stdout,
                    stderr_path=paths.stderr,
                    configuration=snapshot.scheduler,
                    environment=environment,
                )
            )
        except (
            SharedResourceUnavailable,
            SchedulerError,
            OSError,
            ObjectNotFound,
            ValidationFailed,
        ) as exc:
            run.status = RunStatus.SUBMIT_FAILED
            run.failure_reason = str(exc)
            run.finished_at = self._clock.now()
            await self._repos.runs.update(run)
            await self._record_event(run.id, RunEventType.SUBMIT_FAILED, str(exc))
            # 提交失败是「交上去就没下文了」，用户不主动刷新根本不知道。
            # 收件人是 Run 的发起人——即使就是当前操作者也要发。
            await self._notifier.run_submit_failed(
                recipient_id=run.initiated_by_user_id,
                run_id=run.id,
                run_name=run.name,
                reason=str(exc),
            )
            if isinstance(exc, SchedulerError) and scheduler_submit_attempted:
                await self._notifier.platform_incident(
                    recipient_id=run.initiated_by_user_id,
                    title="平台调度服务异常",
                    body="本次 Run 未能提交到调度系统，请稍后重试。",
                )
            if isinstance(exc, SharedResourceUnavailable):
                await self._notify_shared_resource_consumers(run, exc.version_id, str(exc))
            return

        run.scheduler_job_id = job_id
        run.submitted_at = self._clock.now()
        await self._repos.runs.update(run)
        await self._record_event(
            run.id,
            RunEventType.SUBMITTED,
            f"已提交到 {snapshot.scheduler.cluster}/{snapshot.scheduler.partition}，"
            f"调度任务 {job_id}",
        )

    async def _record_run_activity(
        self,
        user_id: str,
        run: Run,
        owner: OwnerReference,
        action: ActivityAction,
        detail: str = "",
    ) -> None:
        await self._activity.record(
            actor_id=user_id,
            owner=owner,
            project_id=run.project_id,
            action=action,
            target_type=TargetType.RUN,
            target_id=run.id,
            target_name=run.name,
            detail=detail,
        )

    async def _record_event(self, run_id: str, event_type: RunEventType, message: str) -> None:
        await self._repos.run_events.add(
            RunEvent(
                id=ids.new_id(ids.EVENT),
                run_id=run_id,
                type=event_type,
                message=message,
                created_at=self._clock.now(),
            )
        )

    async def _notify_shared_resource_consumers(
        self, run: Run, version_id: str, detail: str
    ) -> None:
        """通知使用了当前不可用精确版本的 Project。

        Shared Resource Version 没有独立的 availability 状态；Core 触发契约是：
        Run 提交或物化阶段发现精确版本/内容不可用时，通知该 Project 的当前成员。
        ``version_id`` 来自实际失败的 binding，不从整个 Snapshot 猜测。
        """
        project = await self._repos.projects.get(run.project_id)
        if project is None:
            return
        if project.owner.kind is OwnerKind.USER:
            recipients = [project.owner.id]
        else:
            recipients = [
                member.user_id
                for member in await self._repos.memberships.list_for_user_group(project.owner.id)
                if member.is_active
            ]
        for recipient_id in recipients:
            await self._notifier.shared_resource_unavailable(
                recipient_id=recipient_id,
                project_id=project.id,
                project_name=project.name,
                asset_label=version_id,
                detail=detail,
            )

    async def _resolve_project_version(
        self, project_id: str, version_id: str | None
    ) -> ProjectVersion | None:
        if version_id is None:
            return await self._repos.project_versions.latest(project_id)
        version = await self._repos.project_versions.get(version_id)
        if version is None or version.project_id != project_id:
            raise ObjectNotFound("Project Version", version_id)
        return version

    async def _resolve_environment_version(
        self,
        user_id: str,
        configuration: RunConfiguration,
        project_owner: OwnerReference,
        problems: list[str],
        override_id: str = "",
    ) -> EnvironmentVersion | None:
        """Resolve the exact Environment Version selected for this submission."""
        version_id = override_id or configuration.environment_version_id
        version = await environment_version_for_owner_use(
            self._repos, user_id, version_id, project_owner
        )
        if version is None:
            problems.append("运行方案引用的运行环境版本不存在或无权供当前 Project 使用")
            return None
        if version.availability.value != "available":
            problems.append(
                f"运行环境版本 {version.version} 当前{version.availability.value}："
                f"{version.availability_detail or version.availability_reason}"
            )
            return None
        return version

    def _resolve_compute_request(
        self, plan: ComputePlan, configuration: RunConfiguration, draft: RunDraft
    ) -> ComputeRequest:
        if draft.compute_request_override is not None:
            return ComputeRequest(**draft.compute_request_override)
        if isinstance(configuration.compute_request, ComputeRequest):
            return configuration.compute_request
        return plan.default_request()

    async def _replay_or_reserve(
        self,
        user_id: str,
        key: str | None,
        endpoint: str,
        *,
        project_id: str | None = None,
        source_run_id: str | None = None,
    ) -> Run | None:
        """处理幂等键：命中就返回原来的 Run，没命中就先把键登记下来。

        登记必须**在提交调度任务之前**完成并落库。否则并发的第二个请求会先把
        作业提交出去，再因为键冲突回滚——数据库是干净的，但集群上已经多跑了
        一个作业，而且没人知道它属于谁。因此去重登记必须先于外部副作用落库。

        键的作用域是发起 User（#41）：``(initiated_by_user_id, key)`` 唯一。

        **命中之后要确认这是同一件事，不能只看键相同。** 同一个 User 会在
        多个 Project 上复用同一个键（比如写死成常量，或者按天生成），
        光按键查会把上一次的 Run 原样返回——用户以为提交成功了，
        实际上这次提交**根本没有执行**，而且他拿到的是另一个项目的结果。
        重跑和创建混用同一个键也是一样的问题。

        所以命中之后再对一次：动作类型要一致，指向的 Run 也要真的属于
        这次请求说的那个对象。对不上就报冲突，让客户端换一个键——
        报错比静默返回错的东西好。
        """
        if not key:
            return None

        record = await self._repos.idempotency.find(user_id, key)
        if record is None:
            await self._repos.idempotency.reserve(user_id, key, endpoint)
            return None

        if record.endpoint != endpoint:
            raise ConflictError(
                f"这个幂等键上次用在了「{record.endpoint}」上，"
                "换一个键，或者确认是不是复用了不该复用的键"
            )

        if record.run_id is None:
            # 登记了但没有 Run：上一次请求还在处理，或者中途失败回滚了。
            raise ConflictError("相同的提交请求正在处理中，请稍后查看 Run 列表，不要重复提交")

        run = await self._repos.runs.get(record.run_id)
        if run is None:  # pragma: no cover - 登记指向的 Run 被删了才会发生
            raise ObjectNotFound("Run", record.run_id)

        if project_id is not None and run.project_id != project_id:
            raise ConflictError(
                "这个幂等键上次用在了另一个 Project 上。"
                "重放会返回那次的 Run，这次提交就没执行了——请换一个键"
            )
        if source_run_id is not None and run.source_run_id != source_run_id:
            raise ConflictError("这个幂等键上次重跑的是另一个 Run，请换一个键")
        return run

    async def _attach_idempotency(self, user_id: str, key: str | None, run_id: str) -> None:
        if key:
            await self._repos.idempotency.attach_run(user_id, key, run_id)

    async def _check_concurrency(self, user_id: str, entitlement: ResourceEntitlement) -> list[str]:
        """检查并发上限。

        **数的范围必须和锁的范围一致**：额度按「User × 算力方案」授予，
        锁的是那个 User 的那一条权益行，所以数的也只能是该 User 在那个方案上
        发起的 Run。数到别人的 Run 会互相挤占名额；数到别的方案则会串味：
        CPU 作业占掉 GPU 的名额。

        调用方必须已经通过 ``entitlements.lock_for_plan`` 独占了权益行，
        否则这里数出来的结果在返回之前就可能过期。
        """
        active = await self._repos.runs.count_unfinished_for_plan(
            user_id, entitlement.compute_plan_id
        )
        if active < entitlement.max_concurrent_runs:
            return []
        return [
            f"你在这个算力方案上已有 {active} 个未结束的 Run，"
            f"达到并发上限 {entitlement.max_concurrent_runs}"
        ]

    async def _check_inputs(
        self,
        user_id: str,
        configuration: RunConfiguration,
        project_owner: OwnerReference,
        bindings: tuple[InputBinding, ...] | None = None,
    ) -> list[str]:
        problems: list[str] = []
        selected = bindings if bindings is not None else configuration.input_bindings
        for binding in selected:
            if binding.source_type is InputSourceType.ARTIFACT:
                problem = await self._artifact_input_problem(
                    binding.source_id, binding.access_path, project_owner
                )
                if problem is not None:
                    problems.append(problem)
            elif binding.source_type is InputSourceType.SHARED_RESOURCE_VERSION:
                problem = await self._check_shared_resource_version_input(
                    user_id,
                    binding.source_id,
                    binding.access_path,
                    binding.source_subpath,
                    project_owner,
                )
                if problem is not None:
                    problems.append(problem)
        return problems

    async def _artifact_input_problem(
        self, artifact_id: str, access_path: str, project_owner: OwnerReference
    ) -> str | None:
        """Artifact 直接输入仅限同一 Project Owner（GR-405）。

        跨 Owner 的输入必须先发布成 Shared Resource 并走 USE Grant；
        不满足 Owner 边界的按「不存在」处理，避免泄露其他 Owner 的对象。
        """
        artifact = await self._repos.artifacts.get(artifact_id)
        if artifact is None:
            return f"输入 {access_path} 引用的 Artifact 不存在或无权访问"
        source_project = await self._repos.projects.get(artifact.project_id)
        if source_project is None or source_project.owner != project_owner:
            return f"输入 {access_path} 引用的 Artifact 不存在或无权访问"
        if not artifact.is_available:
            return f"输入 {access_path} 引用的 Artifact 内容已被清理"
        return None

    async def _check_shared_resource_version_input(
        self,
        user_id: str,
        version_id: str,
        access_path: str,
        subpath: str,
        project_owner: OwnerReference,
        *,
        raise_unavailable: bool = False,
    ) -> str | None:
        """Validate actor discovery and exact Project-owner asset use."""
        version = await shared_resource_version_for_owner_use(
            self._repos, user_id, version_id, project_owner
        )
        if version is None:
            message = f"输入 {access_path} 引用的 Shared Resource Version 不存在或无权访问"
            trusted_version = await self._repos.shared_resources.get_version_by_id(version_id)
            resource_exists = (
                trusted_version is not None
                and await self._repos.shared_resources.get_by_id(trusted_version.shared_resource_id)
                is not None
            )
            if raise_unavailable and not resource_exists:
                raise SharedResourceUnavailable(version_id, message)
            return message
        if subpath and not version.contains_subpath(subpath):
            return f"输入 {access_path} 引用的子路径 {subpath!r} 不存在"
        return None

    async def _materialize_inputs(self, bindings: tuple[InputBinding, ...]) -> list[RunInput]:
        """把 InputBinding 翻译成 storage 层的 RunInput。

        - Artifact：直接按 ``artifact_id`` 让 storage 从产物目录拷贝。
        - Shared Resource Version：从仓储取出 ``(path, content_hash)`` 列表，
          让 storage 从 blob 池物化——版本本身没有独立存储目录。
        """
        inputs: list[RunInput] = []
        for binding in bindings:
            if binding.source_type is InputSourceType.ARTIFACT:
                inputs.append(
                    RunInput(
                        source_type=binding.source_type,
                        source_id=binding.source_id,
                        access_path=binding.access_path,
                        source_subpath=binding.source_subpath,
                    )
                )
            elif binding.source_type is InputSourceType.SHARED_RESOURCE_VERSION:
                version = await self._repos.shared_resources.get_version_by_id(binding.source_id)
                if version is None:  # pragma: no cover - 提交前检查已校验过
                    raise SharedResourceUnavailable(
                        binding.source_id,
                        f"输入 {binding.access_path} 引用的 Shared Resource Version 不存在",
                    )
                inputs.append(
                    RunInput(
                        source_type=binding.source_type,
                        source_id=binding.source_id,
                        access_path=binding.access_path,
                        files=tuple((f.path, f.content_hash) for f in version.files),
                        source_subpath=binding.source_subpath,
                    )
                )
        return inputs

    async def _revalidate_snapshot(
        self, snapshot: RunSnapshot, access: ProjectAccess, initiated_by_user_id: str
    ) -> list[str]:
        """重跑之前按当前权限和资源资格重新校验历史快照中的每一个引用。"""
        user_id = initiated_by_user_id
        project_owner = access.project.owner
        problems: list[str] = []

        version = await self._repos.project_versions.get(snapshot.project_version_id)
        if version is None:
            problems.append("来源 Project Version 已不存在")

        environment_version = await environment_version_for_owner_use(
            self._repos, user_id, snapshot.environment_version_id, project_owner
        )
        if environment_version is None:
            problems.append("来源运行环境版本已不存在或无权供当前 Project 使用")
        elif environment_version.availability.value != "available":
            problems.append(f"运行环境版本 {environment_version.version} 当前不可用")
        elif (
            environment_version.definition_hash != snapshot.environment_definition_hash
            or environment_version.execution_spec != snapshot.environment_execution_spec
        ):
            problems.append("运行环境版本定义与 Run Snapshot 不一致，拒绝回退或替换")

        plan = await self._repos.compute_plans.get(snapshot.compute_plan_id)
        if plan is None:
            problems.append("来源算力方案已不存在")
        else:
            entitlement = await self._repos.entitlements.get_for_plan(user_id, plan.id)
            if entitlement is None:
                problems.append(f"你已不再拥有算力方案「{plan.name}」的使用权益")
            elif entitlement.is_expired(self._clock.now().isoformat()):
                problems.append(f"算力方案「{plan.name}」的资源权益已过期")
            else:
                # 重跑同样要占并发名额。漏掉这一条，用户就能靠反复点「重新运行」
                # 绕过上限——权益检查在最容易被反复触发的路径上失效。
                problems.extend(await self._check_concurrency(user_id, entitlement))

            if self._scheduler.name == "slurm":
                assert self._slurm_projection is not None
                user = await self._repos.users.get(user_id)
                historical_mapping = SchedulerMapping(
                    cluster=snapshot.scheduler.cluster,
                    account=snapshot.scheduler.account,
                    partition=snapshot.scheduler.partition,
                    qos=snapshot.scheduler.qos,
                )
                projection_plan = replace(plan, mapping=historical_mapping)
                projection = self._slurm_projection.project(
                    projection_plan, username=user.username if user is not None else None
                )
                if not projection.ok:
                    problems.append(
                        f"算力方案「{plan.name}」当前不可用：{projection.detail}（{projection.reason}）"
                    )
                    projected_plan = plan
                else:
                    assert projection.plan is not None
                    projected_plan = projection.plan
                problems.extend(
                    check_request_against_plan(projected_plan, snapshot.compute_request)
                )
            else:
                problems.extend(check_request_against_plan(plan, snapshot.compute_request))

        _, secret_problems = await self._config_resolver.validate_and_resolve(
            access, initiated_by_user_id, snapshot.env_secret_refs
        )
        problems.extend(secret_problems)

        for binding in snapshot.input_bindings:
            if binding.source_type is InputSourceType.ARTIFACT:
                problem = await self._artifact_input_problem(
                    binding.source_id, binding.access_path, project_owner
                )
                if problem is not None:
                    problems.append(problem)
            elif binding.source_type is InputSourceType.SHARED_RESOURCE_VERSION:
                problem = await self._check_shared_resource_version_input(
                    user_id,
                    binding.source_id,
                    binding.access_path,
                    binding.source_subpath,
                    project_owner,
                )
                if problem is not None:
                    problems.append(problem)

        return problems


def _secret_prefix_suffix_length(text: str, secret_values: list[str]) -> int:
    """Return the longest suffix that can still grow into a known Secret."""
    longest = 0
    for value in secret_values:
        for length in range(min(len(value) - 1, len(text)), longest, -1):
            if text.endswith(value[:length]):
                longest = length
                break
    return longest


def _as_resolved_env(
    literals: dict[str, str], secret_refs: dict[str, SecretReference]
) -> ResolvedEnv:
    return ResolvedEnv(literals=dict(literals), secret_refs=dict(secret_refs))
