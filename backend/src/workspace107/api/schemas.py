"""API 请求与响应模型。

字段名与领域语言保持一致（见 ``docs/product/design.md`` 第 3.1 节），
不在这一层另起别名。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..domain.capabilities import Capability
from ..domain.enums import (
    ActivityAction,
    ArtifactStatus,
    ChangeKind,
    InputSourceType,
    LogStream,
    MembershipStatus,
    NotificationType,
    ProjectStatus,
    RunEventType,
    RunStatus,
    TargetType,
    WorkspaceKind,
    WorkspaceRole,
)


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


# -- 身份与空间 -------------------------------------------------------------


class UserOut(Model):
    id: str
    username: str
    display_name: str
    email: str | None = None


class WorkspaceOut(Model):
    id: str
    kind: WorkspaceKind
    name: str
    description: str
    owner_id: str
    default_environment_version_id: str | None
    created_at: datetime | None
    role: WorkspaceRole | None = None
    capabilities: list[Capability] = Field(default_factory=list)
    """当前用户在这个空间里能做什么。前端据此决定显不显示入口，
    但真正的拦截在后端——前端权限是体验，后端权限才是边界。"""


class WorkspaceCreateIn(Model):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class WorkspaceUpdateIn(Model):
    name: str | None = None
    description: str | None = None
    default_environment_version_id: str | None = None


class MemberOut(Model):
    user_id: str
    username: str
    display_name: str
    role: WorkspaceRole
    status: MembershipStatus


class MemberInviteIn(Model):
    username: str
    role: WorkspaceRole = WorkspaceRole.MEMBER


class MemberRoleUpdateIn(Model):
    role: WorkspaceRole


class InvitationResponseIn(Model):
    accept: bool


class VariableOut(Model):
    name: str
    value: str


class VariableIn(Model):
    name: str = Field(min_length=1, max_length=128)
    value: str


class SecretIn(Model):
    name: str = Field(min_length=1, max_length=128)
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
    workspace_id: str
    name: str
    description: str
    status: ProjectStatus
    environment_version_id: str | None
    default_run_configuration_id: str | None
    created_by: str
    created_at: datetime | None
    updated_at: datetime | None


class ProjectCreateIn(Model):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class ProjectUpdateIn(Model):
    name: str | None = None
    description: str | None = None
    environment_version_id: str | None = None
    inherit_workspace_environment: bool | None = None
    default_run_configuration_id: str | None = None
    status: ProjectStatus | None = None


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


class FileContentOut(Model):
    path: str
    content: str
    truncated: bool = False


class WorkingChangeOut(Model):
    path: str
    change: ChangeKind


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
    image: str
    setup_command: str
    available: bool


class EnvironmentOut(Model):
    id: str
    name: str
    description: str
    owner_workspace_id: str | None
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


class SharedResourceOut(Model):
    id: str
    name: str
    description: str
    owner_workspace_id: str | None
    is_platform_owned: bool
    created_at: datetime


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
    created_by: str
    created_at: datetime


class SharedResourceVersionDetailOut(SharedResourceVersionOut):
    files: list[SharedResourceVersionFileOut]


class SharedResourceDetailOut(SharedResourceOut):
    versions: list[SharedResourceVersionOut]


class SharedResourceCreateIn(Model):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4096)


class SharedResourceUpdateIn(Model):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)


class SharedResourceVersionCreateIn(Model):
    description: str = Field(default="", max_length=4096)


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


class ArtifactRuleModel(Model):
    path: str
    name: str = ""
    optional: bool = True


class RunConfigurationIn(Model):
    name: str = Field(min_length=1, max_length=128)
    command: str = Field(min_length=1)
    compute_plan_id: str
    working_directory: str = "."
    description: str = ""
    environment_version_id: str | None = None
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
    environment_version_id: str | None
    environment_variables: dict[str, str]
    input_bindings: list[InputBindingModel]
    compute_plan_id: str
    compute_request: ComputeRequestModel | None
    artifact_rules: list[ArtifactRuleModel]


# -- Run --------------------------------------------------------------------


class RunDraftIn(Model):
    """一次提交意图。

    除 run_configuration_id 外都可以不传——不传就用运行方案里的值。
    这些字段用 ``| None`` 而不是空字符串默认值，是为了让契约如实表达
    「可以不传」，生成的前端类型才不会要求调用方硬塞一个空串。
    """

    run_configuration_id: str
    project_version_id: str | None = None
    name: str | None = None
    command_override: str | None = None
    working_directory_override: str | None = None
    compute_request_override: ComputeRequestModel | None = None


class PreflightOut(Model):
    ok: bool
    problems: list[str]
    project_version_id: str | None
    environment_version_id: str | None
    compute_plan_id: str | None
    compute_request: ComputeRequestModel | None
    resolved_environment_variables: dict[str, str]
    secret_references: dict[str, str]
    """环境变量名 -> Secret 名称。永远只有名称，没有值。"""


class RunOut(Model):
    id: str
    project_id: str
    workspace_id: str
    snapshot_id: str
    source_run_configuration_id: str | None
    source_run_id: str | None
    name: str
    status: RunStatus
    scheduler_job_id: str | None
    exit_code: int | None
    failure_reason: str
    created_by: str
    created_at: datetime | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    queued_seconds: float | None = None
    running_seconds: float | None = None


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
    environment_image: str
    environment_setup_command: str
    environment_variables: dict[str, str]
    secret_references: dict[str, str]
    input_bindings: list[InputBindingModel]
    compute_plan_id: str
    compute_request: ComputeRequestModel
    scheduler: ResolvedSchedulerOut
    artifact_rules: list[ArtifactRuleModel]
    created_by: str
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


class HomeOut(Model):
    user: UserOut
    workspaces: list[WorkspaceOut]
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
    workspace_id: str
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
    workspace_id: str | None
    target_type: TargetType | None
    target_id: str | None
    mandatory: bool
    """不可关闭的重要通知。当前迁移实现尚未提供偏好设置，标记先带上。"""
    created_at: datetime
    read_at: datetime | None


class UnreadCountOut(Model):
    unread: int


class ForkIn(Model):
    target_workspace_id: str
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
    source_workspace_id: str
    source_project_name: str
    source_version_label: str
    created_at: datetime


class InvitationOut(Model):
    """一条待处理的邀请。只够用来做决定，不暴露空间内容。"""

    workspace_id: str
    workspace_name: str
    workspace_description: str
    role: WorkspaceRole
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
