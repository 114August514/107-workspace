"""Run 状态同步与 Artifact 收集。

当前实现把底层调度系统作为实际状态来源。这里只做「读取调度状态 ->
映射为产品状态」，不提供任何直接把 Run 标记成功的入口。
调度系统查不到任务时保留异常状态并记录事件，不伪造成功。
"""

from __future__ import annotations

import logging
import posixpath

from ..domain import ids
from ..domain.enums import (
    ActivityAction,
    ArtifactStatus,
    RunEventType,
    RunStatus,
    TargetType,
)
from ..domain.models import Artifact, Run, RunEvent
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.scheduler import SchedulerPort, SchedulerState
from ..domain.ports.storage import StoragePort
from ..domain.run_snapshot import RunSnapshot
from .activity import ActivityRecorder, SupportsNestedTransaction
from .notifier import Notifier

logger = logging.getLogger(__name__)


class RunLifecycleService:
    """把调度系统的任务状态同步到 Run，并在结束后收集 Artifact。"""

    def __init__(
        self,
        repos: Repositories,
        clock: Clock,
        storage: StoragePort,
        scheduler: SchedulerPort,
        activity: ActivityRecorder,
        notifier: Notifier,
        session: SupportsNestedTransaction,
    ) -> None:
        self._session = session
        self._repos = repos
        self._clock = clock
        self._storage = storage
        self._scheduler = scheduler
        self._activity = activity
        self._notifier = notifier

    async def sync_all(self) -> int:
        """同步全部未结束的 Run，返回状态发生变化的数量。

        **一个 Run 出错不能拖垮整批。** 早先这里不吞异常，
        任何一次轮询失败都会把整个请求的事务连同其他 Run 的状态更新一起回滚；
        而后台循环每秒跑一次同一批，于是会永远卡在同一个坏 Run 上，
        其他 Run 的状态再也推不动。

        每个 Run 包在自己的 SAVEPOINT 里：光 try/except 不够，
        ORM flush 失败会把整个 session 标记成需要回滚，后面的 Run 一个也写不进去。
        这是活动和通知写入同样需要 SAVEPOINT 的原因。
        """
        changed = 0
        for run in await self._repos.runs.list_unfinished():
            try:
                async with self._session.begin_nested():
                    if await self.sync_run(run.id):
                        changed += 1
            except Exception:
                logger.warning(
                    "同步 Run 失败，跳过这一个继续下一个",
                    extra={"run_id": run.id},
                    exc_info=True,
                )
        return changed

    async def sync_run(self, run_id: str) -> bool:
        run = await self._repos.runs.get(run_id)
        if run is None or run.is_terminal:
            return False
        project = await self._repos.projects.get(run.project_id)
        if project is None:  # pragma: no cover - runs.project_id is a foreign key
            return False
        if not run.scheduler_job_id:
            # 尚未提交成功，没有可同步的调度任务。
            return False

        state = await self._scheduler.poll(run.scheduler_job_id)
        previous = run.status

        match state.state:
            case SchedulerState.PENDING:
                run.status = RunStatus.QUEUED
            case SchedulerState.RUNNING:
                run.status = RunStatus.RUNNING
                if run.started_at is None:
                    run.started_at = state.started_at or self._clock.now()
                    await self._record_event(run.id, RunEventType.STARTED, "任务开始执行")
            case SchedulerState.COMPLETED:
                run.status = (
                    RunStatus.SUCCEEDED if (state.exit_code or 0) == 0 else RunStatus.FAILED
                )
                run.exit_code = state.exit_code
            case SchedulerState.FAILED:
                run.status = RunStatus.FAILED
                run.exit_code = state.exit_code
                run.failure_reason = state.reason or "任务执行失败"
            case SchedulerState.CANCELLED:
                run.status = RunStatus.CANCELLED
                run.failure_reason = state.reason or "任务已被取消"
            case SchedulerState.UNKNOWN:
                # 平台记录与调度系统不一致。保留异常状态，等待同步或人工处置。
                await self._record_event(
                    run.id,
                    RunEventType.ERROR,
                    f"调度系统中查不到任务 {run.scheduler_job_id}，状态待人工确认",
                )
                await self._repos.runs.update(run)
                return False

        if run.status.is_terminal:
            run.started_at = run.started_at or state.started_at
            run.finished_at = state.finished_at or self._clock.now()

            # 抢占终态推进。两次并发同步会同时读到「还在运行」，都判 COMPLETED，
            # 无条件写入的话产物会被收集两遍：重复 Artifact 行、重复存储目录、
            # 重复通知。抢不到说明别人已经推进过了，产物也归他收。
            if not await self._repos.runs.claim_terminal(run):
                return False

            # 收产物**要在落库之前**，而且要传 run 对象本身。
            # 收集可能把状态改成 failed（必需 Artifact 没生成）——
            # 早先这里传的是 run.id，_collect_artifacts 内部重新读出的是
            # 另一个实例，它改的状态外层看不见，于是库里是 failed，
            # 而下面的事件、活动、通知全用陈旧的 succeeded 发出去。
            await self._collect_artifacts(run)
            await self._repos.runs.update(run)
            await self._record_event(
                run.id,
                RunEventType.FINISHED,
                f"任务结束，状态 {run.status}，退出码 {run.exit_code}",
            )
            # 终态只有调度状态轮询路径知道，
            # 所以「跑完了」这条活动也只能在这里记。
            #
            # actor 记的是提交这次 Run 的人。结束不是他「做」的，但这条活动
            # 说的是他那次运行的结果——写成系统账号反而更难读。
            await self._activity.record(
                actor_id=run.initiated_by_user_id,
                owner=project.owner,
                project_id=run.project_id,
                action=ActivityAction.RUN_FINISHED,
                target_type=TargetType.RUN,
                target_id=run.id,
                target_name=run.name,
                detail=str(run.status.value),
            )
            # 终态只有调度状态轮询路径知道，所以结束通知也只能从这里发出。
            # 取消是用户自己刚做的动作，不用再通知一遍。
            if run.status is not RunStatus.CANCELLED:
                await self._notifier.run_finished(
                    recipient_id=run.initiated_by_user_id,
                    run_id=run.id,
                    run_name=run.name,
                    succeeded=run.status is RunStatus.SUCCEEDED,
                    reason=run.failure_reason or "",
                )
        else:
            await self._repos.runs.update(run)

        return run.status is not previous

    # -- Artifact -------------------------------------------------------

    async def _collect_artifacts(self, run: Run) -> None:
        """收集产物，必要时**就地**把 run 改成失败。

        参数是 run 对象而不是 run_id：调用方后面还要用它发事件、记活动、
        发通知，重新读一个新实例会让那些衍生记录用上陈旧状态。
        """
        run_id = run.id
        snapshot = await self._repos.run_snapshots.get(run.snapshot_id)
        if snapshot is None:  # pragma: no cover
            return

        for rule in snapshot.artifact_rules:
            source_path = _join_working_directory(snapshot.working_directory, rule.path)
            artifact_id = ids.new_id(ids.ARTIFACT)
            content = await self._storage.collect_artifact(run_id, artifact_id, source_path)

            if content is None:
                message = f"收集路径 {rule.path} 不存在"
                await self._record_event(run_id, RunEventType.ARTIFACT_MISSING, message)
                if not rule.optional:
                    # 只改内存里的对象，由调用方统一落库——
                    # 这样事件、活动、通知看到的都是这个最终状态。
                    run.status = RunStatus.FAILED
                    run.failure_reason = f"必需的 Artifact {rule.path} 未生成"
                continue

            artifact = Artifact(
                id=artifact_id,
                run_id=run_id,
                project_id=run.project_id,
                name=rule.name or rule.path,
                source_path=rule.path,
                size=content.size,
                file_count=content.file_count,
                content_hash=content.content_hash,
                status=ArtifactStatus.AVAILABLE,
                created_at=self._clock.now(),
            )
            await self._repos.artifacts.add(artifact)
            await self._record_event(
                run_id,
                RunEventType.ARTIFACT_COLLECTED,
                f"已收集 {rule.path}，{content.file_count} 个文件，{content.size} 字节",
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


def _join_working_directory(working_directory: str, path: str) -> str:
    if working_directory in {"", "."}:
        return path
    return posixpath.join(working_directory, path)


def snapshot_working_directory(snapshot: RunSnapshot) -> str:
    """暴露给 api 层展示用，避免上层直接拆 Snapshot 字段。"""
    return snapshot.working_directory or "."
