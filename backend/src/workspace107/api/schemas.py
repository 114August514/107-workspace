"""API 请求与响应模型。

字段名与领域语言保持一致（见 ``docs/product/design.md`` 第 3.1 节），
不在这一层另起别名。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.capabilities import Capability, UserGroupCapability
from ..domain.enums import (
    ActivityAction,
    ArtifactStatus,
    ChangeKind,
    EnvironmentAvailability,
    EnvironmentPublicationStatus,
    EnvironmentRuntimeKind,
    InputSourceType,
    LogStream,
    MembershipRole,
    MembershipStatus,
    NotificationType,
    ProjectStatus,
    ProjectVisibility,
    RunEventType,
    RunStatus,
    TargetType,
)
from ..domain.grant import UseQualificationScope
from ..domain.ownership import OwnerKind


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_attribute_docstrings=True)


class PageOut[T](Model):
    """分页信封。

    全站只有这一种分页模型，只用于「随时间单调增长」的历史类列表；
    由当前状态决定规模的列表（文件、成员、配置）直接返回数组。
    理由见 domain/pagination.py。
    """

    items: list[T]
    page: int
    page_size: int
    total: int
    has_more: bool


# -- Identity and User Group governance --------------------------------------


class UserOut(Model):
    id: str
    username: str
    display_name: str
    email: str | None = None


class UserGroupOut(Model):
    id: str
    name: str
    description: str
    created_by_id: str | None
    created_at: datetime | None
    role: MembershipRole
    capabilities: list[UserGroupCapability] = Field(default_factory=list)


class UserGroupCreateIn(Model):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class UserGroupUpdateIn(Model):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class MemberOut(Model):
    user_id: str
    username: str
    display_name: str
    role: MembershipRole
    status: MembershipStatus
    capabilities: list[UserGroupCapability] = Field(default_factory=list)


class MemberInviteIn(Model):
    model_config = ConfigDict(extra="forbid")
    username: str


class MemberRoleUpdateIn(Model):
    role: MembershipRole


class InvitationResponseIn(Model):
    accept: bool


class VariableOut(Model):
    name: str
    value: str


class VariableIn(Model):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str


class SecretIn(Model):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(min_length=1)


class EntitlementOut(Model):
    id: str
    compute_plan_id: str
    compute_plan_name: str
    max_concurrent_runs: int
    expires_at: str | None


# -- Project ----------------------------------------------------------------


class ProjectOut(Model):
    id: str
    owner: OwnerSummaryOut
    name: str
    description: str
    status: ProjectStatus
    visibility: ProjectVisibility
    environment_version_id: str | None
    default_run_configuration_id: str | None
    created_by: str
    created_at: datetime | None
    updated_at: datetime | None
    capabilities: list[Capability] = Field(default_factory=list)


class ProjectCreateIn(Model):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class ProjectCreateOwnedIn(ProjectCreateIn):
    owner: OwnerReferenceIn
    visibility: ProjectVisibility = ProjectVisibility.OWNER_SCOPE


class ProjectUpdateIn(Model):
    name: str | None = None
    description: str | None = None
    environment_version_id: str | None = None
    default_run_configuration_id: str | None = None
    status: ProjectStatus | None = None
    visibility: ProjectVisibility | None = None


class ProjectFileOut(Model):
    path: str
    size: int
    content_hash: str
    updated_at: datetime | None


class FileWriteIn(Model):
    path: str
    content: str
    """文本内容。二进制文件请使用 multipart 上传接口。"""


class FileMoveIn(Model):
    source: str
    destination: str


class FileCopyIn(Model):
    source: str
    destination: str


class MkdirIn(Model):
    path: str


class DiscardChangesIn(Model):
    paths: list[str] = Field(min_length=1)
    """要放弃的未保存变更路径；不存在的变更按幂等跳过。"""


class FileContentOut(Model):
    path: str
    content: str
    truncated: bool = False


class WorkingChangeOut(Model):
    path: str
    change: ChangeKind


class WorkingChangeDetailOut(Model):
    """单个未保存变更的内容级详情。"""

    path: str
    change: ChangeKind
    previous: FileContentOut | None = None
    """基线（最近保存版本）中的内容预览；新增时为空。"""
    current: FileContentOut | None = None
    """当前工作区内容预览；删除时为空。"""


class ProjectVersionFileOut(Model):
    path: str
    size: int
    content_hash: str


class ProjectVersionOut(Model):
    id: str
    project_id: str
    sequence: int
    label: str
    message: str
    file_count: int
    total_size: int
    created_by: str
    created_at: datetime


class ProjectVersionDetailOut(ProjectVersionOut):
    files: list[ProjectVersionFileOut]


class VersionCreateIn(Model):
    message: str = ""


class VersionDiffOut(Model):
    path: str
    change: ChangeKind


# -- 运行环境与算力 ---------------------------------------------------------


class EnvironmentVersionOut(Model):
    id: str
    environment_id: str
    version: str
    description: str
    runtime_kind: EnvironmentRuntimeKind
    definition: dict[str, object]
    definition_hash: str
    execution_spec: dict[str, object]
    validation_summary: str
    validation_evidence: dict[str, object]
    availability: EnvironmentAvailability
    availability_reason: str
    availability_detail: str
    availability_checked_at: datetime


class ModulesEnvironmentPublicationIn(Model):
    version: str = Field(min_length=1, max_length=64)
    description: str = ""
    modules: list[str] = Field(min_length=1)


class EnvironmentPublicationAttemptOut(Model):
    id: str
    environment_id: str
    status: EnvironmentPublicationStatus
    version: str
    description: str
    runtime_kind: EnvironmentRuntimeKind
    validation_summary: str
    validation_evidence: dict[str, object]
    failure_code: str | None
    failure_reason: str | None
    version_id: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class OwnerReferenceIn(Model):
    """Canonical owner selection for asset creation."""

    kind: OwnerKind
    id: str


class OwnerSummaryOut(Model):
    """Canonical display-ready ownership summary."""

    kind: OwnerKind
    id: str
    display_name: str


class EnvironmentOut(Model):
    id: str
    name: str
    description: str
    owner: OwnerSummaryOut
    versions: list[EnvironmentVersionOut]


class ComputePlanOut(Model):
    id: str
    code: str
    name: str
    description: str
    default_nodes: int
    default_cpus: int
    default_memory_mb: int
    default_gpus: int
    default_time_limit_minutes: int
    max_nodes: int
    max_cpus: int
    max_memory_mb: int
    max_gpus: int
    max_time_limit_minutes: int


# -- Shared Resource --------------------------------------------------------


class UseGrantSummaryOut(Model):
    """One USE Grant contributing to the enclosing qualification."""

    id: str
    target_all: bool
    created_at: datetime


class SharedResourceOwnerQualificationOut(Model):
    """Use in a Project whose Owner is the resource Owner."""

    scope: Literal[UseQualificationScope.OWNER] = UseQualificationScope.OWNER


class SharedResourceGrantQualificationOut(Model):
    """Actor-level Grant qualification, not authorization for a concrete Run.

    ``user_grant`` follows the actor into any Project where they may submit.
    ``user_group_grant`` applies only while the actor is an active member, the
    Grantee User Group owns the consuming Project, and the actor may submit there.
    Grants is non-empty and contains every matching Grant for this one Grantee.
    """

    scope: Literal[
        UseQualificationScope.USER_GRANT,
        UseQualificationScope.USER_GROUP_GRANT,
    ]
    grantee: OwnerSummaryOut
    grants: list[UseGrantSummaryOut] = Field(min_length=1)


SharedResourceUseQualificationOut = Annotated[
    SharedResourceOwnerQualificationOut | SharedResourceGrantQualificationOut,
    Field(discriminator="scope"),
]


class SharedResourceOut(Model):
    id: str
    name: str
    description: str
    owner: OwnerSummaryOut
    created_at: datetime
    use_qualifications: list[SharedResourceUseQualificationOut]
    capabilities: list[Capability] = Field(default_factory=list)


class SharedResourceVersionFileOut(Model):
    path: str
    size: int
    content_hash: str


class SharedResourceVersionOut(Model):
    id: str
    shared_resource_id: str
    sequence: int
    label: str
    description: str
    file_count: int
    total_size: int
    manifest_hash: str
    validation_summary: str
    created_by: str
    created_at: datetime


class SharedResourceVersionDetailOut(SharedResourceVersionOut):
    files: list[SharedResourceVersionFileOut]


class SharedResourceDetailOut(SharedResourceOut):
    versions: list[SharedResourceVersionOut]


class SharedResourcePublicationAttemptOut(Model):
    id: str
    shared_resource_id: str
    status: Literal["pending", "processing", "succeeded", "failed"]
    description: str
    file_count: int
    total_size: int
    validation_summary: str
    failure_reason: str | None
    version_id: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CanonicalSharedResourceCreateIn(Model):
    """Canonical creation payload with an explicit legal owner."""

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4096)
    owner: OwnerReferenceIn


class SharedResourceUpdateIn(Model):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)


# -- Grant ------------------------------------------------------------------


class GrantOut(Model):
    id: str
    grantor: OwnerSummaryOut
    grantee: OwnerSummaryOut
    target_kind: Literal["environment", "shared_resource", "all"]
    target_id: str
    action: Literal["use"]
    granted_by: OwnerSummaryOut
    created_at: datetime


class GrantCreateIn(Model):
    target_kind: Literal["environment", "shared_resource", "all"]
    target_id: str = ""
    grantee: OwnerReferenceIn
    grantor: OwnerReferenceIn | None = None
    """Required for ALL grants (who issues the grant); omitted for asset grants
    (derived from the target asset's current owner)."""


# -- 运行方案 ---------------------------------------------------------------


class ComputeRequestModel(Model):
    nodes: int = 1
    cpus: int = 1
    memory_mb: int = 1024
    gpus: int = 0
    time_limit_minutes: int = 30


class InputBindingModel(Model):
    source_type: InputSourceType = InputSourceType.ARTIFACT
    source_id: str
    access_path: str
    source_subpath: str = ""
    """可选子路径，只取来源内容的一个子目录/文件（设计稿 §3.1.3）；空串取整份内容。

    shared_resource_version 来源的无效子路径在 preflight（配置保存/提交前）即被挡下；
    artifact 来源的无效子路径在 Run 提交物化时才以错误暴露（artifact 无文件清单，
    无法在 preflight 校验存在性）。
    """


class ArtifactRuleModel(Model):
    path: str
    name: str = ""
    optional: bool = True


class RunConfigurationIn(Model):
    name: str = Field(min_length=1, max_length=128)
    command: str = Field(min_length=1)
    compute_plan_id: str
    environment_version_id: str
    """精确引用的 Environment Version；不继承其他对象的默认值。"""
    working_directory: str = "."
    description: str = ""
    environment_variables: dict[str, str] = Field(default_factory=dict)
    input_bindings: list[InputBindingModel] = Field(default_factory=list)
    compute_request: ComputeRequestModel | None = None
    artifact_rules: list[ArtifactRuleModel] = Field(default_factory=list)


class RunConfigurationOut(Model):
    id: str
    project_id: str
    name: str
    description: str
    working_directory: str
    command: str
    environment_version_id: str
    environment_variables: dict[str, str]
    input_bindings: list[InputBindingModel]
    compute_plan_id: str
    compute_request: ComputeRequestModel | None
    artifact_rules: list[ArtifactRuleModel]


# -- Run --------------------------------------------------------------------


class RunDraftIn(Model):
    """一次提交意图。"""

    run_configuration_id: str
    project_version_id: str | None = None
    """None 表示使用 Project 的最新版本。"""
    name: str | None = None
    command_override: str | None = None
    working_directory_override: str | None = None
    environment_version_id_override: str | None = None
    input_bindings_override: list[InputBindingModel] | None = None
    compute_request_override: ComputeRequestModel | None = None


class AdjustedRerunIn(Model):
    """从历史 Run Snapshot 调整后创建新 Run 的完整提交事实。"""

    name: str = Field(min_length=1, max_length=255)
    project_version_id: str = Field(min_length=1)
    environment_version_id: str = Field(min_length=1)
    working_directory: str = "."
    command: str = Field(min_length=1)
    input_bindings: list[InputBindingModel] = Field(default_factory=list)
    compute_request: ComputeRequestModel


class PreflightOut(Model):
    ok: bool
    problems: list[str]
    project_version_id: str | None
    environment_version: EnvironmentVersionOut | None
    compute_plan_id: str | None
    compute_request: ComputeRequestModel | None
    resolved_environment_variables: dict[str, str]
    secret_references: dict[str, str]
    """环境变量名 -> Secret 名称。永远只有名称，没有值。"""


class RunOut(Model):
    id: str
    project_id: str
    snapshot_id: str
    source_run_configuration_id: str | None
    project_version_id: str
    project_version_label: str
    source_run_id: str | None
    name: str
    status: RunStatus
    scheduler_job_id: str | None
    exit_code: int | None
    failure_reason: str
    initiated_by_user_id: str
    """发起本次 Run 的 User（GR-307）：执行身份、并发额度与通知接收方。"""
    initiated_by_username: str | None
    """当前权威 User.username；User 记录无法解析时为 null。"""
    created_at: datetime | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    queued_seconds: float | None = None
    running_seconds: float | None = None
    capabilities: list[Capability] = Field(default_factory=list)


class RunEventOut(Model):
    id: str
    type: RunEventType
    message: str
    created_at: datetime


class ArtifactOut(Model):
    id: str
    run_id: str
    name: str
    source_path: str
    size: int
    file_count: int
    status: ArtifactStatus
    description: str
    created_at: datetime | None


class ResolvedSchedulerOut(Model):
    """已解析的最终调度配置。

    刻意不用 dict[str, object]：那样在 OpenAPI 里只是个自由字典，
    前端拿到 unknown，只能靠猜字段名。
    """

    cluster: str
    account: str
    partition: str
    qos: str
    nodes: int
    cpus: int
    memory_mb: int
    gpus: int
    time_limit_minutes: int


class RunSnapshotOut(Model):
    """完整执行快照，用于复现信息展示。"""

    id: str
    project_id: str
    project_version_id: str
    source_run_configuration_id: str | None
    working_directory: str
    command: str
    environment_version_id: str
    environment_definition_hash: str
    environment_execution_spec: dict[str, object]
    environment_variables: dict[str, str]
    secret_references: dict[str, str]
    input_bindings: list[InputBindingModel]
    compute_plan_id: str
    compute_request: ComputeRequestModel
    scheduler: ResolvedSchedulerOut
    artifact_rules: list[ArtifactRuleModel]
    initiated_by_user_id: str
    created_at: datetime


class RunDetailOut(Model):
    run: RunOut
    snapshot: RunSnapshotOut
    events: list[RunEventOut]
    artifacts: list[ArtifactOut]


class LogChunkOut(Model):
    stream: LogStream
    content: str
    truncated: bool


class ArtifactEntryOut(Model):
    path: str
    size: int


class SyncOut(Model):
    changed: int


# -- 首页 -------------------------------------------------------------------


class PersonalExecutionContextOut(Model):
    """The current User's direct ownership and compute entitlement context."""

    owner: OwnerSummaryOut
    entitlements: list[EntitlementOut]


class HomeOut(Model):
    user: UserOut
    user_groups: list[UserGroupOut]
    personal_execution_context: PersonalExecutionContextOut
    recent_projects: list[ProjectOut]
    recent_runs: list[RunOut]


class HealthOut(Model):
    status: str
    version: str
    scheduler: str
    env: str
    request_id: str = ""


class ReadinessOut(Model):
    ready: bool
    database: bool
    detail: str = ""
    request_id: str = ""


class ActivityOut(Model):
    """活动流里的一条。

    ``actor_name`` 和 ``target_name`` 是操作发生时抄下来的名字，不是当前名字——
    活动是历史事实，对象改名或删除之后这句话仍然要读得通。
    """

    id: str
    owner: OwnerReferenceIn
    project_id: str | None
    actor_id: str
    actor_name: str
    action: ActivityAction
    target_type: TargetType
    target_id: str
    target_name: str
    detail: str
    created_at: datetime


class NotificationOut(Model):
    """一条通知。

    ``title`` / ``body`` 是产生时就写好的文本，不是模板参数——
    通知是「当时告诉过你这件事」的记录，事后对象改名不该改写它。
    """

    id: str
    type: NotificationType
    title: str
    body: str
    target_type: TargetType | None
    target_id: str | None
    mandatory: bool
    """不可关闭的重要通知。当前迁移实现尚未提供偏好设置，标记先带上。"""
    created_at: datetime
    read_at: datetime | None


class UnreadCountOut(Model):
    unread: int


class ForkIn(Model):
    target_owner: OwnerReferenceIn
    name: str = ""
    """留空表示沿用源 Project 的名称。"""
    description: str = ""


class ForkSourceOut(Model):
    """Project 的来源记录。

    名字是 Fork 那一刻抄下来的，源 Project 改名或删除之后仍然读得通。
    ``source_project_id`` 用来生成链接，链不过去时前端只显示文字。
    """

    source_project_id: str
    source_version_id: str
    source_owner: OwnerReferenceIn
    source_project_name: str
    source_version_label: str
    created_at: datetime


class InvitationOut(Model):
    """A pending User Group invitation without group-owned private content."""

    user_group_id: str
    user_group_name: str
    user_group_description: str
    role: MembershipRole
    invited_at: datetime | None


class ErrorOut(Model):
    """统一错误响应。

    ``request_id`` 是把用户看到的报错和服务端日志连起来的线索：
    用户把它报过来，照着去日志里搜就能找到这次请求的完整经过。
    """

    code: str
    message: str
    problems: list[str] = Field(default_factory=list)
    request_id: str = ""
