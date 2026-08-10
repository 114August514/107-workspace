"""Run 查询，以及在请求事务内固定 Snapshot、QUEUED Run 与执行意图。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.compute import (
    ComputePlan,
    ComputeRequest,
    ResourceEntitlement,
    check_request_against_plan,
    resolve_scheduler_configuration,
)
from ..domain.enums import (
    ActivityAction,
    LogStream,
    RunEventType,
    RunStatus,
    TargetType,
)
from ..domain.errors import ConflictError, ObjectNotFound, PreflightRejected
from ..domain.execution import ExecutionIntent
from ..domain.models import (
    Artifact,
    EnvironmentVersion,
    Project,
    ProjectVersion,
    Run,
    RunConfiguration,
    RunEvent,
    RunLogChunk,
)
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.secret_vault import SecretVault
from ..domain.ports.storage import ArtifactEntry, StoragePort
from ..domain.run_snapshot import RunSnapshot, build_snapshot
from ..domain.secrets import ResolvedEnv, redact, resolve_env
from .access import AccessGuard
from .activity import ActivityRecorder

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
    compute_request_override: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """提交前检查结果。"""

    problems: list[str] = field(default_factory=list)
    project_version: ProjectVersion | None = None
    environment_version: EnvironmentVersion | None = None
    compute_plan: ComputePlan | None = None
    compute_request: ComputeRequest | None = None
    resolved_env_literals: dict[str, str] = field(default_factory=dict)
    resolved_env_secret_refs: dict[str, str] = field(default_factory=dict)

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
class RunDetail:
    run: Run
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
        secrets: SecretVault,
        activity: ActivityRecorder,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._storage = storage
        self._secrets = secrets
        self._activity = activity

    # -- 查询 -----------------------------------------------------------

    async def list_for_project(self, user_id: str, project_id: str, page: PageRequest) -> Page[Run]:
        await self._guard.project(user_id, project_id)
        return await self._repos.runs.list_for_project(project_id, page)

    async def list_recent_for_user(self, user_id: str, *, limit: int = 10) -> list[Run]:
        return await self._repos.runs.list_for_user(user_id, limit=limit)

    async def get_detail(self, user_id: str, run_id: str) -> RunDetail:
        access = await self._guard.run(user_id, run_id)
        snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        if snapshot is None:  # pragma: no cover - 数据损坏才会发生
            raise ObjectNotFound("Run Snapshot", access.run.snapshot_id)
        return RunDetail(
            run=access.run,
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
        secret_values: list[str] = []
        if snapshot is not None and snapshot.env_secret_refs:
            resolved = await self._secrets.resolve(
                access.workspace.id, sorted(set(snapshot.env_secret_refs.values()))
            )
            secret_values = list(resolved.values())

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

    # -- Artifact 内容 --------------------------------------------------

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
            access.project, configuration, problems
        )

        plan = await self._repos.compute_plans.get(configuration.compute_plan_id)
        request: ComputeRequest | None = None
        if plan is None:
            problems.append("运行方案引用的算力方案已不存在")
        else:
            entitlement = await self._repos.entitlements.get_for_plan(access.workspace.id, plan.id)
            if entitlement is None:
                problems.append(f"当前 Workspace 没有算力方案「{plan.name}」的使用权益")
            elif entitlement.is_expired(self._clock.now().isoformat()):
                problems.append(f"算力方案「{plan.name}」的资源权益已过期")
            else:
                problems.extend(await self._check_concurrency(access.workspace.id, entitlement))

            request = self._resolve_compute_request(plan, configuration, draft)
            problems.extend(check_request_against_plan(plan, request))

        command = (draft.command_override or configuration.command).strip()
        if not command:
            problems.append("执行命令不能为空")

        variables = {
            v.name: v.value
            for v in await self._repos.variables.list_for_workspace(access.workspace.id)
        }
        resolved_env, env_problems = resolve_env(
            configuration.environment_variables,
            variables=variables,
            available_secrets=await self._secrets.list_names(access.workspace.id),
        )
        problems.extend(env_problems)

        problems.extend(await self._check_inputs(configuration, access.workspace.id))

        return PreflightResult(
            problems=problems,
            project_version=version,
            environment_version=environment_version,
            compute_plan=plan,
            compute_request=request,
            resolved_env_literals=resolved_env.literals,
            resolved_env_secret_refs=resolved_env.secret_refs,
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
        """在当前请求事务中创建 immutable Snapshot、QUEUED Run 与执行意图。

        Git/FS/Scheduler 副作用全部由独立 Worker 在事务提交后执行。
        """
        access = await self._guard.project(user_id, project_id, needs=Capability.RUN_SUBMIT)

        replayed = await self._replay_or_reserve(
            access.workspace.id, idempotency_key, "create_run", project_id=project_id
        )
        if replayed is not None:
            return RunSubmission(run=replayed, created=False)

        configuration = await self._repos.run_configurations.get(draft.run_configuration_id)
        if configuration is None or configuration.project_id != project_id:
            raise ObjectNotFound("Run Configuration", draft.run_configuration_id)

        # 先独占这个 Workspace 在该算力方案上的权益行，再做提交前检查。
        #
        # 并发上限是「数一数还有几个名额 -> 创建 Run」，这两步之间不能被别的请求
        # 插进来，否则两个请求会同时读到「还没到上限」，然后都创建成功——
        # 上限就形同虚设。锁一直持有到本次请求的事务结束。
        await self._repos.entitlements.lock_for_plan(
            access.workspace.id, configuration.compute_plan_id
        )

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
            environment_image=result.environment_version.image,
            environment_setup_command=result.environment_version.setup_command,
            resolved_env=_as_resolved_env(
                result.resolved_env_literals, result.resolved_env_secret_refs
            ),
            input_bindings=configuration.input_bindings,
            compute_plan_id=result.compute_plan.id,
            compute_request=result.compute_request,
            scheduler=resolve_scheduler_configuration(result.compute_plan, result.compute_request),
            artifact_rules=configuration.artifact_rules,
            created_by=user_id,
            created_at=now,
        )
        await self._repos.run_snapshots.add(snapshot)

        run = Run(
            id=ids.new_id(ids.RUN),
            project_id=project_id,
            workspace_id=access.workspace.id,
            snapshot_id=snapshot.id,
            compute_plan_id=snapshot.compute_plan_id,
            source_run_configuration_id=configuration.id,
            source_run_id=None,
            name=draft.name.strip() or f"{access.project.name} · {result.project_version.label}",
            status=RunStatus.QUEUED,
            created_by=user_id,
            created_at=now,
        )
        await self._repos.runs.add(run)
        await self._repos.execution_intents.add(_new_execution_intent(run.id, now))
        await self._record_event(run.id, RunEventType.CREATED, "已固定 Run Snapshot")
        await self._attach_idempotency(access.workspace.id, idempotency_key, run.id)

        # 请求返回前不准备目录、不解析 Secret、不调用 Scheduler。
        await self._record_run_activity(user_id, run, ActivityAction.RUN_SUBMITTED)
        return RunSubmission(run=run, created=True)

    async def rerun(
        self,
        user_id: str,
        run_id: str,
        *,
        name: str = "",
        idempotency_key: str | None = None,
    ) -> RunSubmission:
        """使用相同代码快照和配置重新运行。

        必须创建新的 Run 和新的 Run Snapshot，不能重启原有 Run（GR-306）。
        同时按重新执行时的权限和资源资格重新校验全部引用（设计稿 §3.4.3）。
        """
        access = await self._guard.run(user_id, run_id, needs=Capability.RUN_SUBMIT)

        replayed = await self._replay_or_reserve(
            access.workspace.id, idempotency_key, "rerun", source_run_id=run_id
        )
        if replayed is not None:
            return RunSubmission(run=replayed, created=False)

        source_snapshot = await self._repos.run_snapshots.get(access.run.snapshot_id)
        if source_snapshot is None:  # pragma: no cover
            raise ObjectNotFound("Run Snapshot", access.run.snapshot_id)

        # 和 create 一样要先独占权益行——重跑同样占用并发名额。
        await self._repos.entitlements.lock_for_plan(
            access.workspace.id, source_snapshot.compute_plan_id
        )

        problems = await self._revalidate_snapshot(source_snapshot, access.workspace.id)
        if problems:
            raise PreflightRejected(problems)

        environment_version = await self._repos.environments.get_version(
            source_snapshot.environment_version_id
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
            environment_image=environment_version.image,
            environment_setup_command=environment_version.setup_command,
            resolved_env=_as_resolved_env(
                source_snapshot.env_literals, source_snapshot.env_secret_refs
            ),
            input_bindings=source_snapshot.input_bindings,
            compute_plan_id=plan.id,
            compute_request=source_snapshot.compute_request,
            scheduler=resolve_scheduler_configuration(plan, source_snapshot.compute_request),
            artifact_rules=source_snapshot.artifact_rules,
            created_by=user_id,
            created_at=now,
        )
        await self._repos.run_snapshots.add(snapshot)

        run = Run(
            id=ids.new_id(ids.RUN),
            project_id=access.run.project_id,
            workspace_id=access.workspace.id,
            snapshot_id=snapshot.id,
            compute_plan_id=snapshot.compute_plan_id,
            source_run_configuration_id=source_snapshot.source_run_configuration_id,
            source_run_id=access.run.id,
            name=name.strip() or f"{access.run.name}（重跑）",
            status=RunStatus.QUEUED,
            created_by=user_id,
            created_at=now,
        )
        await self._repos.runs.add(run)
        await self._repos.execution_intents.add(_new_execution_intent(run.id, now))
        await self._record_event(run.id, RunEventType.CREATED, f"基于 Run {access.run.id} 重新运行")
        await self._attach_idempotency(access.workspace.id, idempotency_key, run.id)

        # 重跑同样只创建持久执行意图，外部副作用交给 Worker。
        await self._record_run_activity(
            user_id, run, ActivityAction.RUN_SUBMITTED, detail=f"重跑自 {access.run.name}"
        )
        return RunSubmission(run=run, created=True)

    async def cancel(self, user_id: str, run_id: str) -> Run:
        access = await self._guard.run(user_id, run_id, needs=Capability.RUN_CANCEL)
        run = access.run
        if run.is_terminal:
            raise ConflictError(f"Run 已处于终态 {run.status}，无法取消")

        if not await self._repos.execution_intents.request_cancel(run.id):
            raise ConflictError("Run 的执行意图已完成，无法取消")
        await self._record_event(run.id, RunEventType.CANCEL_REQUESTED, "用户请求取消")
        return run

    # -- 内部 -----------------------------------------------------------

    async def _record_run_activity(
        self, user_id: str, run: Run, action: ActivityAction, detail: str = ""
    ) -> None:
        await self._activity.record(
            actor_id=user_id,
            workspace_id=run.workspace_id,
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
        self, project: Project, configuration: RunConfiguration, problems: list[str]
    ) -> EnvironmentVersion | None:
        """按 运行方案 -> Project -> Workspace 默认 的顺序解析实际环境。"""
        workspace = await self._repos.workspaces.get(project.workspace_id)
        candidate_id = (
            configuration.environment_version_id
            or project.environment_version_id
            or (workspace.default_environment_version_id if workspace else None)
        )
        if candidate_id is None:
            problems.append("没有可用的运行环境，请为 Project 或 Workspace 选择默认环境")
            return None

        version = await self._repos.environments.get_version(candidate_id)
        if version is None:
            problems.append("引用的运行环境版本已不存在")
            return None
        if not version.available:
            problems.append(f"运行环境版本 {version.version} 当前不可用")
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
        workspace_id: str,
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

        **命中之后要确认这是同一件事，不能只看键相同。** 键的作用域是
        Workspace，而一个 Workspace 里有很多 Project；客户端复用同一个键
        （比如写死成常量，或者按天生成）在不同 Project 上提交时，
        光按键查会把别人的 Run 原样返回——用户以为提交成功了，
        实际上这次提交**根本没有执行**，而且他拿到的是另一个项目的结果。
        重跑和创建混用同一个键也是一样的问题。

        所以命中之后再对一次：动作类型要一致，指向的 Run 也要真的属于
        这次请求说的那个对象。对不上就报冲突，让客户端换一个键——
        报错比静默返回错的东西好。
        """
        if not key:
            return None

        record = await self._repos.idempotency.find(workspace_id, key)
        if record is None:
            await self._repos.idempotency.reserve(workspace_id, key, endpoint)
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

    async def _attach_idempotency(self, workspace_id: str, key: str | None, run_id: str) -> None:
        if key:
            await self._repos.idempotency.attach_run(workspace_id, key, run_id)

    async def _check_concurrency(
        self, workspace_id: str, entitlement: ResourceEntitlement
    ) -> list[str]:
        """检查并发上限。

        **数的范围必须和锁的范围一致**：额度按「Workspace × 算力方案」授予，
        锁的是那一条权益行，所以数的也只能是那个方案上的 Run。
        早先这里数的是整个 Workspace，比锁的范围大，于是两个请求提交到
        不同方案时锁不到一起，却读同一个计数，双双通过——上限形同虚设。
        顺带还会串味：CPU 作业占掉 GPU 的名额。

        调用方必须已经通过 ``entitlements.lock_for_plan`` 独占了权益行，
        否则这里数出来的结果在返回之前就可能过期。
        """
        active = await self._repos.runs.count_unfinished_for_plan(
            workspace_id, entitlement.compute_plan_id
        )
        if active < entitlement.max_concurrent_runs:
            return []
        return [
            f"当前 Workspace 在这个算力方案上已有 {active} 个未结束的 Run，"
            f"达到并发上限 {entitlement.max_concurrent_runs}"
        ]

    async def _check_inputs(self, configuration: RunConfiguration, workspace_id: str) -> list[str]:
        del workspace_id
        if not configuration.input_bindings:
            return []
        return ["M1 只接受无 Input Binding 的 Run；Shared Resource 与完整输入属于 M3"]

    async def _revalidate_snapshot(self, snapshot: RunSnapshot, workspace_id: str) -> list[str]:
        """重跑之前按当前权限和资源资格重新校验历史快照中的每一个引用。"""
        problems: list[str] = []

        version = await self._repos.project_versions.get(snapshot.project_version_id)
        if version is None:
            problems.append("来源 Project Version 已不存在")

        environment_version = await self._repos.environments.get_version(
            snapshot.environment_version_id
        )
        if environment_version is None:
            problems.append("来源运行环境版本已不存在")
        elif not environment_version.available:
            problems.append(f"运行环境版本 {environment_version.version} 当前不可用")

        plan = await self._repos.compute_plans.get(snapshot.compute_plan_id)
        if plan is None:
            problems.append("来源算力方案已不存在")
        else:
            entitlement = await self._repos.entitlements.get_for_plan(workspace_id, plan.id)
            if entitlement is None:
                problems.append(f"当前 Workspace 已不再拥有算力方案「{plan.name}」的使用权益")
            elif entitlement.is_expired(self._clock.now().isoformat()):
                problems.append(f"算力方案「{plan.name}」的资源权益已过期")
            else:
                # 重跑同样要占并发名额。漏掉这一条，用户就能靠反复点「重新运行」
                # 绕过上限——权益检查在最容易被反复触发的路径上失效。
                problems.extend(await self._check_concurrency(workspace_id, entitlement))
            problems.extend(check_request_against_plan(plan, snapshot.compute_request))

        available_secrets = await self._secrets.list_names(workspace_id)
        for env_name, secret_name in snapshot.env_secret_refs.items():
            if secret_name not in available_secrets:
                problems.append(f"环境变量 {env_name} 引用的 Workspace Secret {secret_name} 不存在")

        if snapshot.input_bindings:
            problems.append("M1 只接受无 Input Binding 的 Run；Shared Resource 与完整输入属于 M3")

        return problems


def _new_execution_intent(run_id: str, now: datetime) -> ExecutionIntent:
    return ExecutionIntent(
        run_id=run_id,
        correlation=f"workspace107:{run_id}",
        attempt_no=0,
        next_action_at=now,
        created_at=now,
        updated_at=now,
    )


def _as_resolved_env(literals: dict[str, str], secret_refs: dict[str, str]) -> ResolvedEnv:
    return ResolvedEnv(literals=dict(literals), secret_refs=dict(secret_refs))
