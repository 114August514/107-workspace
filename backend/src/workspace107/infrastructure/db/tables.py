"""SQLAlchemy 表定义。

不可变对象（``project_versions``、``run_snapshots``）在仓储层只有 INSERT，
没有 UPDATE。这里的表结构本身不做额外限制，约束由仓储和领域层保证。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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


class UserGroupRow(Base):
    __tablename__ = "user_groups"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MembershipRow(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_group_id: Mapped[str] = mapped_column(ID, ForeignKey("user_groups.id"), index=True)
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_group_id", "user_id", name="uq_user_group_membership"),
        Index(
            "uq_membership_active_owner",
            "user_group_id",
            unique=True,
            sqlite_where=text("role = 'owner' AND status = 'active'"),
            postgresql_where=text("role = 'owner' AND status = 'active'"),
        ),
    )


class VariableRow(Base):
    __tablename__ = "variables"

    scope_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class SecretRow(Base):
    """Scoped secret storage; values are read only at execution boundaries."""

    __tablename__ = "secrets"

    scope_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    owner_user_group_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("user_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32))
    visibility: Mapped[str] = mapped_column(String(32), default="owner_scope")
    environment_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    default_run_configuration_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_projects_owner_user_name",
            "owner_user_id",
            "name",
            unique=True,
            sqlite_where=text("owner_user_id IS NOT NULL"),
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        Index(
            "uq_projects_owner_user_group_name",
            "owner_user_group_id",
            "name",
            unique=True,
            sqlite_where=text("owner_user_group_id IS NOT NULL"),
            postgresql_where=text("owner_user_group_id IS NOT NULL"),
        ),
        CheckConstraint(
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
            name="ck_projects_exactly_one_owner",
        ),
    )


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
    owner_user_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    owner_user_group_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("user_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
            name="ck_environments_exactly_one_owner",
        ),
    )


class EnvironmentVersionRow(Base):
    __tablename__ = "environment_versions"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    environment_id: Mapped[str] = mapped_column(ID, ForeignKey("environments.id"), index=True)
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    runtime_kind: Mapped[str] = mapped_column(String(32), default="modules")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    definition_hash: Mapped[str] = mapped_column(String(64), default="test-definition")
    execution_spec: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=lambda: {"kind": "modules", "commands": []}
    )
    validation_summary: Mapped[str] = mapped_column(Text, default="test fixture")
    validation_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    availability: Mapped[str] = mapped_column(String(32), default="available")
    availability_reason: Mapped[str] = mapped_column(String(128), default="test_fixture")
    availability_detail: Mapped[str] = mapped_column(Text, default="")
    availability_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now().astimezone()
    )

    __table_args__ = (
        UniqueConstraint("environment_id", "version", name="uq_environment_version_label"),
        CheckConstraint(
            "runtime_kind IN ('modules', 'apptainer_sif')",
            name="ck_environment_versions_runtime_kind",
        ),
        CheckConstraint(
            "availability IN ('available', 'unavailable', 'deprecated')",
            name="ck_environment_versions_availability",
        ),
    )


class EnvironmentPublicationAttemptRow(Base):
    __tablename__ = "environment_publication_attempts"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    environment_id: Mapped[str] = mapped_column(ID, ForeignKey("environments.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    runtime_kind: Mapped[str] = mapped_column(String(32))
    candidate_definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_summary: Mapped[str] = mapped_column(Text)
    validation_evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("environment_versions.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed')",
            name="ck_environment_publication_attempts_status",
        ),
        CheckConstraint(
            "runtime_kind IN ('modules', 'apptainer_sif')",
            name="ck_environment_publication_attempts_runtime_kind",
        ),
    )


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
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), index=True)
    compute_plan_id: Mapped[str] = mapped_column(ID, ForeignKey("compute_plans.id"))
    max_concurrent_runs: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "compute_plan_id", name="uq_entitlement"),)


class RunConfigurationRow(Base):
    __tablename__ = "run_configurations"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    working_directory: Mapped[str] = mapped_column(String(1024), default=".")
    command: Mapped[str] = mapped_column(Text)
    environment_version_id: Mapped[str] = mapped_column(ID)
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
    project_id: Mapped[str] = mapped_column(ID, ForeignKey("projects.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ID, ForeignKey("run_snapshots.id"))
    # 从快照里冗余出来的一列。快照是 JSON，没法索引也没法跨库稳定地查；
    # 而并发上限口径是「Initiated By User × 算力方案」（GR-307），
    # 数未结束 Run 时必须能按方案过滤。方案在快照创建时就固定、之后不再变，
    # 冗余是安全的。
    compute_plan_id: Mapped[str] = mapped_column(ID, index=True)
    # 从快照里冗余出来的列——project_version_id 只存在于快照 JSON 里，
    # 无法在 Run 列表查询中直接获取。冗余到列后 Run History 可直接展示
    # 对应的 Project 版本（design L192）。模式同 compute_plan_id。
    project_version_id: Mapped[str] = mapped_column(ID, index=True)
    # label = f"v{sequence}" 是计算属性，sequence 受
    # UniqueConstraint("project_id", "sequence") 约束且版本不可变（GR-201），
    # 冗余到 runs 表不会漂移，与 GR-205 一致。
    # 先例：fork_relations.source_version_label 已采用同样的 label 冗余。
    project_version_label: Mapped[str] = mapped_column(String(32))
    source_run_configuration_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    scheduler_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    initiated_by_user_id: Mapped[str] = mapped_column(ID, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunSecretRedactionRow(Base):
    """Internal SecretVault retention for historical log redaction only."""

    __tablename__ = "run_secret_redactions"

    run_id: Mapped[str] = mapped_column(
        ID, ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    value_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class IdempotencyKeyRow(Base):
    """幂等登记。

    复合主键 ``(initiated_by_user_id, key)`` 就是并发下的那道保证：
    第二个同 User 同 key 的请求插不进来，会撞唯一约束。
    """

    __tablename__ = "idempotency_keys"

    initiated_by_user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), primary_key=True)
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
    name: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(Integer)
    file_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityRow(Base):
    """Current Owner-scoped activity history with immutable display snapshots."""

    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(ID, ForeignKey("users.id"), nullable=True)
    owner_user_group_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("user_groups.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    actor_id: Mapped[str] = mapped_column(ID)
    actor_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(ID)
    target_name: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
            name="ck_activities_exactly_one_owner",
        ),
        Index("ix_activities_owner_user_created", "owner_user_id", "created_at"),
        Index("ix_activities_owner_user_group_created", "owner_user_group_id", "created_at"),
        Index("ix_activities_project_created", "project_id", "created_at"),
    )


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
    source_owner_user_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    source_owner_user_group_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    source_project_name: Mapped[str] = mapped_column(String(255))
    source_version_label: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "((source_owner_user_id IS NOT NULL AND source_owner_user_group_id IS NULL) "
            "OR (source_owner_user_id IS NULL AND source_owner_user_group_id IS NOT NULL))",
            name="ck_fork_relations_exactly_one_source_owner",
        ),
    )


class SharedResourceRow(Base):
    """共享资源；owner 只能是一个 User 或一个 UserGroup。"""

    __tablename__ = "shared_resources"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    owner_user_group_id: Mapped[str | None] = mapped_column(
        ID, ForeignKey("user_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
            name="ck_shared_resources_exactly_one_owner",
        ),
    )


class SharedResourceVersionRow(Base):
    """Shared Resource 的不可变版本（GR-201）。

    内容按 ``(path, size, content_hash)`` 三元组列表固化在
    ``shared_resource_version_files`` 表里。文件正文存在存储层的
    blob store（按内容寻址），与 Project Version 共用同一个 blob 池——
    因此本表不需要存储路径列，也不需要单独的存储目录。
    """

    __tablename__ = "shared_resource_versions"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    shared_resource_id: Mapped[str] = mapped_column(
        ID, ForeignKey("shared_resources.id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("shared_resource_id", "sequence", name="uq_shared_resource_version_seq"),
    )


class SharedResourceVersionFileRow(Base):
    """Shared Resource Version 的文件条目。不可变。"""

    __tablename__ = "shared_resource_version_files"

    version_id: Mapped[str] = mapped_column(
        ID, ForeignKey("shared_resource_versions.id"), primary_key=True
    )
    path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))


class GrantRow(Base):
    """跨 Owner 使用许可（Issue #40）。

    Grantor 和 Grantee 都是 "User 或 UserGroup" 的判别联合，用 ``kind``+``id``
    两列表示，与 Activity 表的 ``target_type``+``target_id`` 模式一致。

    ``target_kind`` 可以是 ``"all"``、``"environment"`` 或 ``"shared_resource"``。
    当 ``target_kind == "all"`` 时 ``target_id`` 为空字符串，表示授权 Grantor
    当前及未来拥有的全部可授权资产。

    Grant target 可能引用未来被删除的资产，因此不对 environments/shared_resources
    加 FK——删除资产时需在应用层清理指向该资产的 Grant 行。
    """

    __tablename__ = "grants"

    id: Mapped[str] = mapped_column(ID, primary_key=True)
    grantor_kind: Mapped[str] = mapped_column(String(16))  # 'user' | 'user_group'
    grantor_id: Mapped[str] = mapped_column(ID)
    grantee_kind: Mapped[str] = mapped_column(String(16))  # 'user' | 'user_group'
    grantee_id: Mapped[str] = mapped_column(ID)
    target_kind: Mapped[str] = mapped_column(
        String(32)
    )  # 'all' | 'environment' | 'shared_resource'
    target_id: Mapped[str] = mapped_column(ID, default="")  # '' when target_kind == 'all'
    action: Mapped[str] = mapped_column(String(16))  # 'use'
    granted_by_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "grantor_kind",
            "grantor_id",
            "grantee_kind",
            "grantee_id",
            "target_kind",
            "target_id",
            "action",
            name="uq_grant_grantor_grantee_target_action",
        ),
        Index("ix_grants_target", "target_kind", "target_id"),
        Index("ix_grants_grantee", "grantee_kind", "grantee_id"),
        Index("ix_grants_grantor", "grantor_kind", "grantor_id"),
    )
