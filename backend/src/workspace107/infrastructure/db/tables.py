"""SQLAlchemy 表定义。

不可变对象（``project_versions``、``run_snapshots``）在仓储层只有 INSERT，
没有 UPDATE。这里的表结构本身不做额外限制，约束由仓储和领域层保证。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


ID = String(40)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), index=True)
    default_environment_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_workspaces_owner_kind", "owner_id", "kind"),
        # 一个用户只能有一个 Personal Workspace。先查后写挡不住并发——
        # 新用户首屏的几个请求会同时发现「还没有」然后各建一个。
        # 协作空间可以有多个，所以是**部分**唯一索引，只约束 personal。
        # SQLite 和 PostgreSQL 都支持。
        Index(
            "uq_personal_workspace",
            "owner_id",
            unique=True,
            sqlite_where=text("kind = 'personal'"),
            postgresql_where=text("kind = 'personal'"),
        ),
    )


class MembershipRow(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_membership"),)


class WorkspaceVariableRow(Base):
    __tablename__ = "workspace_variables"

    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class WorkspaceSecretRow(Base):
    """Secret 存储。

    ``value`` 只有 :class:`SecretVault` 会读，且只在提交任务的执行边界上使用。
    生产部署应把这张表换成 KMS 或 Vault 之类的外部密钥服务。
    """

    __tablename__ = "workspace_secrets"

    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32))
    environment_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    default_run_configuration_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_project_name"),)


class ProjectFileRow(Base):
    __tablename__ = "project_files"

    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectVersionRow(Base):
    __tablename__ = "project_versions"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "sequence", name="uq_version_sequence"),)


class ProjectVersionFileRow(Base):
    __tablename__ = "project_version_files"

    version_id: Mapped[str] = mapped_column(ID, ForeignKey("project_versions.id"), primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))


class EnvironmentRow(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_workspace_id: Mapped[str | None] = mapped_column(ID, nullable=True)


class EnvironmentVersionRow(Base):
    __tablename__ = "environment_versions"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    environment_id: Mapped[str] = mapped_column(ID, ForeignKey("environments.id"), index=True)
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str] = mapped_column(String(255))
    setup_command: Mapped[str] = mapped_column(Text, default="")
    available: Mapped[bool] = mapped_column(Boolean, default=True)


class ComputePlanRow(Base):
    __tablename__ = "compute_plans"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    default_nodes: Mapped[int] = mapped_column(Integer)
    default_cpus: Mapped[int] = mapped_column(Integer)
    default_memory_mb: Mapped[int] = mapped_column(Integer)
    default_gpus: Mapped[int] = mapped_column(Integer)
    default_time_limit_minutes: Mapped[int] = mapped_column(Integer)
    max_nodes: Mapped[int] = mapped_column(Integer)
    max_cpus: Mapped[int] = mapped_column(Integer)
    max_memory_mb: Mapped[int] = mapped_column(Integer)
    max_gpus: Mapped[int] = mapped_column(Integer)
    max_time_limit_minutes: Mapped[int] = mapped_column(Integer)
    cluster: Mapped[str] = mapped_column(String(64))
    account: Mapped[str] = mapped_column(String(64))
    partition: Mapped[str] = mapped_column(String(64))
    qos: Mapped[str] = mapped_column(String(64))


class ResourceEntitlementRow(Base):
    __tablename__ = "resource_entitlements"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), index=True)
    compute_plan_id: Mapped[str] = mapped_column(ID, ForeignKey("compute_plans.id"))
    max_concurrent_runs: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (UniqueConstraint("workspace_id", "compute_plan_id", name="uq_entitlement"),)


class RunConfigurationRow(Base):
    __tablename__ = "run_configurations"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    working_directory: Mapped[str] = mapped_column(String(1024), default=".")
    command: Mapped[str] = mapped_column(Text)
    environment_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    environment_variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_bindings: Mapped[list[Any]] = mapped_column(JSON, default=list)
    compute_plan_id: Mapped[str] = mapped_column(ID)
    compute_request: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    artifact_rules: Mapped[list[Any]] = mapped_column(JSON, default=list)


class RunSnapshotRow(Base):
    """不可变执行事实。只 INSERT，不 UPDATE（GR-202）。"""

    __tablename__ = "run_snapshots"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','submit_failed')",
            name="ck_runs_status",
        ),
        CheckConstraint(
            "((scheduler_job_id IS NULL AND submitted_at IS NULL) OR "
            "(scheduler_job_id IS NOT NULL AND submitted_at IS NOT NULL))",
            name="ck_runs_scheduler_link",
        ),
        CheckConstraint(
            "status <> 'running' OR scheduler_job_id IS NOT NULL",
            name="ck_runs_running_has_job",
        ),
        CheckConstraint(
            "((status IN ('queued','running') AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','cancelled','submit_failed') "
            "AND finished_at IS NOT NULL))",
            name="ck_runs_finished_at",
        ),
    )
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ID, ForeignKey("run_snapshots.id"))
    # 从快照里冗余出来的一列。快照是 JSON，没法索引也没法跨库稳定地查；
    # 而当前实现的并发上限口径是「Workspace × 算力方案」，
    # 数未结束 Run 时必须能按方案过滤。方案在快照创建时就固定、之后不再变，
    # 冗余是安全的。
    compute_plan_id: Mapped[str] = mapped_column(ID, index=True)
    source_run_configuration_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    scheduler_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ID, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunExecutionIntentRow(Base):
    __tablename__ = "run_execution_intents"
    __table_args__ = (
        CheckConstraint(
            "phase IN ('ready','submitting','monitoring','finalizing','uncertain','complete')",
            name="ck_execution_intent_phase",
        ),
        CheckConstraint("attempt_no >= 0", name="ck_execution_intent_attempt_no"),
        CheckConstraint("lease_generation >= 0", name="ck_execution_intent_lease_generation"),
        CheckConstraint(
            "((lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL))",
            name="ck_execution_intent_lease_tuple",
        ),
        CheckConstraint(
            "((phase = 'complete' AND completed_at IS NOT NULL) OR "
            "(phase <> 'complete' AND completed_at IS NULL))",
            name="ck_execution_intent_completed",
        ),
        Index(
            "ix_execution_intents_claimable",
            "next_attempt_at",
            "lease_expires_at",
            "created_at",
            sqlite_where=text("completed_at IS NULL"),
            postgresql_where=text("completed_at IS NULL"),
        ),
    )

    run_id: Mapped[str] = mapped_column(
        ID, ForeignKey("runs.id", ondelete="RESTRICT"), primary_key=True
    )
    phase: Mapped[str] = mapped_column(String(24))
    correlation: Mapped[str] = mapped_column(String(128), unique=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_generation: Mapped[int] = mapped_column(BigInteger, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uncertainty_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uncertainty_detail: Mapped[str] = mapped_column(Text, default="")
    observed_scheduler_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    observed_exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunSubmissionAttemptRow(Base):
    __tablename__ = "run_submission_attempts"
    __table_args__ = (
        CheckConstraint("attempt_no > 0", name="ck_submission_attempt_no"),
        CheckConstraint(
            "outcome IN ('armed','accepted','rejected','uncertain','reconciled_zero',"
            "'reconciled_one','reconciled_multiple')",
            name="ck_submission_attempt_outcome",
        ),
        Index("ix_submission_attempts_correlation", "correlation", "attempt_no"),
    )

    run_id: Mapped[str] = mapped_column(
        ID, ForeignKey("run_execution_intents.run_id", ondelete="RESTRICT"), primary_key=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    correlation: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(24))
    scheduler_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")


class IdempotencyKeyRow(Base):
    """幂等登记。

    复合主键 ``(workspace_id, key)`` 就是并发下的那道保证：
    第二个同 key 的请求插不进来，会撞唯一约束。
    """

    __tablename__ = "idempotency_keys"

    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunEventRow(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    run_id: Mapped[str] = mapped_column(ID, ForeignKey("runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    run_id: Mapped[str] = mapped_column(ID, ForeignKey("runs.id"), index=True)
    project_id: Mapped[str] = mapped_column(ID, index=True)
    workspace_id: Mapped[str] = mapped_column(ID, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(Integer)
    file_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "source_path", name="uq_artifact_run_source_path"),
    )


class ActivityRow(Base):
    """活动流。

    actor_name 和 target_name 是写入时抄下来的快照，不是外键——
    活动要在对象改名或删除之后仍然读得通（见 domain/models.Activity）。

    两条复合索引对应两种读法：Workspace 活动流和 Project 活动流。
    活动只按时间倒序读，所以时间列进索引。
    """

    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_workspace_created", "workspace_id", "created_at"),
        Index("ix_activities_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ID, ForeignKey("workspaces.id"))
    project_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    actor_id: Mapped[str] = mapped_column(ID)
    actor_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(ID)
    target_name: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationRow(Base):
    """通知。

    索引按收件人 + 时间——通知只有一种读法：「我的，按时间倒序」。
    未读数走同一个索引。
    """

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_created", "recipient_id", "created_at"),)

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(ID)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    workspace_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ForkRelationRow(Base):
    """Fork 来源记录。

    source_* 字段里的名字是写入时抄下来的快照，不做外键——
    源 Project 删掉之后，「这个项目是从哪儿来的」仍然要读得通。

    project_id 唯一：一个 Project 只可能 Fork 自一个地方。
    """

    __tablename__ = "fork_relations"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), unique=True)
    source_project_id: Mapped[str] = mapped_column(ID, index=True)
    source_version_id: Mapped[str] = mapped_column(ID)
    source_workspace_id: Mapped[str] = mapped_column(ID)
    source_project_name: Mapped[str] = mapped_column(String(255))
    source_version_label: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
