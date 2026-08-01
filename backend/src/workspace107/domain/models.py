"""领域对象。

可变对象与不可变版本必须分离（GR-201、GR-202、GR-203）：

    可变：  Workspace、Project、ProjectFile、RunConfiguration、Environment
    不可变：ProjectVersion、EnvironmentVersion、RunSnapshot、Artifact 内容

Project Version、Environment Version 和 Run Snapshot 在代码及仓储层都不可变；
Artifact 的内容不可变，但展示元数据和清理状态可以更新。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import (
    ActivityAction,
    ArtifactStatus,
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
from .errors import ValidationFailed
from .secrets import EnvValue

# --------------------------------------------------------------------------
# 身份与空间
# --------------------------------------------------------------------------


@dataclass(slots=True)
class User:
    """平台中的自然人身份。

    User 本身不是 Project、Run 或资源的所有权边界——用户创建的对象归属于
    操作发生时所在的 Workspace 层级（设计稿 §3.2.1）。
    """

    id: str
    username: str
    display_name: str
    email: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class Workspace:
    """成员、权限、Project、资源权益和治理规则的归属边界。"""

    id: str
    kind: WorkspaceKind
    name: str
    description: str = ""
    owner_id: str = ""
    default_environment_version_id: str | None = None
    created_at: datetime | None = None

    @property
    def is_personal(self) -> bool:
        return self.kind is WorkspaceKind.PERSONAL


@dataclass(slots=True)
class Membership:
    """User 在 Workspace 中的身份。

    Membership 只在对应 Workspace 内生效，不会传播到用户的 Personal
    Workspace 或其他 Collaborative Workspace。
    """

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    status: MembershipStatus
    created_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status is MembershipStatus.ACTIVE


@dataclass(slots=True)
class WorkspaceVariable:
    """由 Workspace 管理、可直接查看和引用的非敏感键值配置。"""

    workspace_id: str
    name: str
    value: str


@dataclass(slots=True)
class WorkspaceSecret:
    """由 Workspace 安全保存的敏感键值配置。

    领域对象里刻意不携带秘密值：读取路径只暴露名称，
    值的获取由 ``SecretVault`` 端口在执行阶段完成（设计稿 §3.1.4）。
    """

    workspace_id: str
    name: str
    updated_at: datetime | None = None


# --------------------------------------------------------------------------
# Project 与版本
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Project:
    """Workspace 下可编辑、可版本化、可运行的计算项目。"""

    id: str
    workspace_id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    environment_version_id: str | None = None
    """None 表示继承 Workspace 默认环境。"""
    default_run_configuration_id: str | None = None
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ProjectFile:
    """Project Working Tree 中的一个文件。

    内容存放在存储层，这里只保存元数据和内容摘要。
    """

    project_id: str
    path: str
    size: int
    content_hash: str
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProjectVersionFile:
    """Project Version 中的一个文件条目。不可变。"""

    path: str
    size: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ProjectVersion:
    """Project 在确定时刻保存的不可变内容版本。

    被归档或源 Project 后续变化，都不改变已有版本的内容。
    """

    id: str
    project_id: str
    sequence: int
    """在该 Project 内自增，用于展示为 v1、v2……"""
    message: str
    files: tuple[ProjectVersionFile, ...]
    created_by: str
    created_at: datetime

    @property
    def label(self) -> str:
        return f"v{self.sequence}"

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)


# --------------------------------------------------------------------------
# 运行环境
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Environment:
    """可被多个 Project 引用的独立运行基础。"""

    id: str
    name: str
    description: str = ""
    owner_workspace_id: str | None = None
    """None 表示平台提供的公共环境。"""


@dataclass(frozen=True, slots=True)
class EnvironmentVersion:
    """Environment 已发布的确定版本。发布后不可修改。"""

    id: str
    environment_id: str
    version: str
    description: str
    image: str
    """底层执行基础的标识，例如容器镜像或 module 集合。"""
    setup_command: str = ""
    """执行用户命令之前运行的准备命令，可为空。"""
    available: bool = True


# --------------------------------------------------------------------------
# 运行方案
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InputBinding:
    """把一份确定内容绑定到 Run 中指定访问路径的关系。

    统一引用一份确定内容，不针对来源类型设计不同结构。
    绑定的内容只读提供给 Run（GR-404）。
    """

    source_type: InputSourceType
    source_id: str
    access_path: str
    source_subpath: str = ""

    def __post_init__(self) -> None:
        if not self.access_path.startswith("/"):
            raise ValidationFailed(f"输入访问路径 {self.access_path!r} 必须是绝对路径")
        if ".." in self.access_path.split("/"):
            raise ValidationFailed(f"输入访问路径 {self.access_path!r} 不允许包含 ..")

    def as_payload(self) -> dict[str, str]:
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "access_path": self.access_path,
            "source_subpath": self.source_subpath,
        }


@dataclass(frozen=True, slots=True)
class ArtifactCollectionRule:
    """Run 结束后把哪些输出保存为 Artifact。"""

    path: str
    """相对于工作目录的路径，可以是文件或目录。"""
    name: str = ""
    optional: bool = True
    """为 False 时，路径不存在会让 Run 被标记为失败。"""

    def __post_init__(self) -> None:
        if self.path.startswith("/"):
            raise ValidationFailed(f"收集路径 {self.path!r} 必须相对于工作目录")
        if ".." in self.path.split("/"):
            raise ValidationFailed(f"收集路径 {self.path!r} 不允许包含 ..")

    def as_payload(self) -> dict[str, object]:
        return {"path": self.path, "name": self.name, "optional": self.optional}


@dataclass(slots=True)
class RunConfiguration:
    """Project 下可命名、可编辑、可复用的运行方案。

    它描述「以后准备怎样运行」；「本次实际怎样运行」由 RunSnapshot 记录。
    修改运行方案不影响已经创建的 Run。
    """

    id: str
    project_id: str
    name: str
    working_directory: str = "."
    command: str = ""
    environment_version_id: str | None = None
    """None 表示继承 Project 的有效环境。"""
    environment_variables: dict[str, EnvValue] = field(default_factory=dict)
    input_bindings: tuple[InputBinding, ...] = ()
    compute_plan_id: str = ""
    compute_request: object | None = None
    """:class:`~workspace107.domain.compute.ComputeRequest`，None 表示使用方案默认值。"""
    artifact_rules: tuple[ArtifactCollectionRule, ...] = ()
    description: str = ""


# --------------------------------------------------------------------------
# Run 与执行产物
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Run:
    """Project 的一次独立计算执行记录。

    ``snapshot_id`` 指向不可变的执行事实；其余字段是随执行过程更新的执行信息。
    """

    id: str
    project_id: str
    workspace_id: str
    snapshot_id: str
    compute_plan_id: str
    """本次运行占用的算力方案。当前实现按「Workspace × 方案」计算并发额度。"""
    source_run_configuration_id: str | None
    """仅用于来源追踪和配置复用，不作为执行依据。"""
    source_run_id: str | None
    """重跑或派生执行时指向来源 Run。"""
    name: str
    status: RunStatus
    scheduler_job_id: str | None = None
    exit_code: int | None = None
    failure_reason: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal


@dataclass(frozen=True, slots=True)
class RunEvent:
    """平台产生的执行事件，区别于用户程序的 stdout / stderr。"""

    id: str
    run_id: str
    type: RunEventType
    message: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """一次幂等提交的登记。

    客户端为一次「提交意图」生成一个 key，重试时复用同一个 key。
    平台据此判断这是不是同一次提交——网络抖动、用户双击、前端自动重试，
    都不应该变成两次真实的计算。

    ``run_id`` 为 None 表示登记了但还没创建出 Run，也就是上一次请求
    还在处理中（或者已经失败回滚了）。
    """

    workspace_id: str
    key: str
    endpoint: str
    run_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RunLogChunk:
    """一段日志内容及其来源流。"""

    stream: LogStream
    content: str
    truncated: bool = False


@dataclass(slots=True)
class Artifact:
    """某次 Run 产生并保存的不可变结果。

    内容不可修改；名称和说明等展示元数据可以在允许范围内修改。
    当前清理流程只删除存储内容并置 ``status = cleaned``，记录本身保留。
    """

    id: str
    run_id: str
    project_id: str
    workspace_id: str
    name: str
    source_path: str
    """收集规则中相对于工作目录的来源路径。"""
    size: int
    file_count: int
    content_hash: str
    status: ArtifactStatus = ArtifactStatus.AVAILABLE
    description: str = ""
    created_at: datetime | None = None
    cleaned_at: datetime | None = None

    @property
    def is_available(self) -> bool:
        return self.status is ArtifactStatus.AVAILABLE


@dataclass(frozen=True, slots=True)
class Activity:
    """「这里最近发生了什么」的一条记录。

    面向对象（Workspace / Project），不面向人——面向人的是 Notification。
    两者是两条独立的数据流：Activity 回答「这里发生了什么」，Notification
    回答「这个人需要关注什么」。

    **actor_name 和 target_name 是写入时抄下来的，不是查出来的。**
    活动是历史事实：「alice 删掉了 Project foo」这句话在 foo 已经不存在之后
    仍然要读得通，而且要说 foo 当时的名字，不是改名后的名字。
    join 出来的名字做不到这两点——对象删了就 join 不到，改名了就变成另一句话。

    ``target_id`` 仍然保留，用来生成跳转链接；对象已经不在时链接会 404，
    这是可接受的：文字本身已经把事情说清楚了。

    写完不改。没有「已读」状态，那是通知的事。
    """

    id: str
    workspace_id: str
    actor_id: str
    actor_name: str
    """执行者在操作发生时的用户名。"""
    action: ActivityAction
    target_type: TargetType
    target_id: str
    target_name: str
    """对象在操作发生时的名称。"""
    created_at: datetime
    project_id: str | None = None
    """Project 级活动同时出现在所属 Workspace 的活动流里。"""
    detail: str = ""
    """补充说明，比如角色从什么改成什么。不放结构化数据——
    活动是给人读的，需要结构化查询时说明该建的是别的东西。"""


@dataclass(frozen=True, slots=True)
class Notification:
    """「有什么需要我关注」的一条记录。

    面向人，不面向对象——面向对象的是 :class:`Activity`。两者是两条独立的
    数据流。关键差别在数量关系：一次「移除成员」产生
    **一条活动**（这个空间少了个人），但要产生**两条通知**（被移除的人要知道，
    Owner 要有记录）。

    ``title`` 和 ``body`` 是产生时就写好的文本，不是模板参数。
    理由同 Activity 的名字快照：通知是「当时告诉过你这件事」的记录，
    事后对象改名或删除都不该改写它。

    **收件人能读到自己的通知，与他现在还能不能看见相关对象无关。**
    被移除的成员移除之后已经看不到那个 Workspace，但那条「你被移除了」
    的通知必须还能读到——否则他根本不知道发生了什么。
    """

    id: str
    recipient_id: str
    type: NotificationType
    title: str
    body: str
    created_at: datetime
    workspace_id: str | None = None
    target_type: TargetType | None = None
    target_id: str | None = None
    mandatory: bool = False
    """不可关闭的重要通知（设计稿 §2.10 C）。

    当前迁移实现还没有偏好设置，但标记要先带上——否则后续增加偏好时，
    历史数据分不出哪些是当初就不允许屏蔽的。
    """
    read_at: datetime | None = None

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


@dataclass(frozen=True, slots=True)
class ForkRelation:
    """新 Project 与它来源版本之间的一条**不可变来源记录**。

    只是记录，**不是同步通道**（GR-502）：源内容后续变化不影响副本，
    副本后续变化也不影响源内容。「看看来源有没有出新版本」属于 V2，
    而且即使做了也是用户主动发起的一次性比较，不是自动跟随。

    源对象的名字在这里抄了一份。理由和 :class:`Activity` 一样：
    源 Project 可能被改名或删除，而「这个项目是从哪儿来的」是历史事实，
    删掉源之后这句话仍然要读得通。``source_project_id`` 保留用来生成链接，
    链不过去时前端只显示文字。
    """

    id: str
    project_id: str
    """Fork 出来的新 Project。一个 Project 最多一条来源记录。"""
    source_project_id: str
    source_version_id: str
    source_workspace_id: str
    source_project_name: str
    source_version_label: str
    """来源版本的展示名，形如 ``v3``。"""
    created_by: str
    created_at: datetime
