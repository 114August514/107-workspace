"""领域对象。

可变对象与不可变版本必须分离（GR-201、GR-202、GR-203）：

    可变：  UserGroup、Membership、Project、ProjectFile、RunConfiguration、Environment
    不可变：ProjectVersion、EnvironmentVersion、RunSnapshot、Artifact 内容

Project Version、Environment Version 和 Run Snapshot 在代码及仓储层都不可变；
Artifact 的内容不可变，但展示元数据和清理状态可以更新。
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from datetime import datetime

from .config_scope import ConfigScope
from .enums import (
    ActivityAction,
    ArtifactStatus,
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
from .errors import ValidationFailed
from .ownership import OwnerKind, OwnerReference
from .secrets import EnvValue

# --------------------------------------------------------------------------
# 身份与协作
# --------------------------------------------------------------------------


@dataclass(slots=True)
class User:
    """A natural-person identity and a legal ownership subject."""

    id: str
    username: str
    display_name: str
    email: str | None = None
    created_at: datetime | None = None

    @property
    def owner_reference(self) -> OwnerReference:
        return OwnerReference(kind=OwnerKind.USER, id=self.id)


@dataclass(slots=True)
class UserGroup:
    """An independent collaboration organization."""

    id: str
    name: str
    description: str = ""
    created_by_id: str | None = None
    created_at: datetime | None = None

    @property
    def owner_reference(self) -> OwnerReference:
        return OwnerReference(kind=OwnerKind.USER_GROUP, id=self.id)


@dataclass(slots=True)
class Membership:
    """A User's role and lifecycle state in one exact User Group."""

    id: str
    user_group_id: str
    user_id: str
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status is MembershipStatus.ACTIVE


@dataclass(slots=True)
class Variable:
    """A non-sensitive value owned by one explicit configuration scope."""

    scope: ConfigScope
    name: str
    value: str


@dataclass(slots=True)
class Secret:
    """Secret metadata; plaintext is never represented in the domain model."""

    scope: ConfigScope
    name: str
    updated_at: datetime | None = None


# --------------------------------------------------------------------------
# Project 与版本
# --------------------------------------------------------------------------


@dataclass(slots=True)
class Project:
    """A versioned project with a canonical User/User Group owner."""

    id: str
    name: str
    owner: OwnerReference
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    visibility: ProjectVisibility = ProjectVisibility.OWNER_SCOPE
    environment_version_id: str | None = None
    """None 表示 Project 未选择默认 Environment Version。"""
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
    """可被多个 Project 引用、由一个 User 或 UserGroup 持有的独立运行基础。"""

    id: str
    name: str
    owner: OwnerReference
    description: str = ""


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

    ``source_subpath`` 可选地只取来源内容的一个子路径（设计稿 §3.1.3）：例如
    ``dataset-v2`` 的 ``train/`` 子目录，绑定后只在 Run 中暴露该子目录。空串表示
    取整份内容。这里把子路径规范化成与 ``SharedResourceFile.path`` 一致的形式
    （``posixpath.normpath``，无尾斜杠、无 ``.``/``..``/``//``），否则物化时按规范
    路径匹配会静默落空。因为是 frozen dataclass，规范化后用 ``object.__setattr__`` 写回。
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
        if self.source_subpath:
            candidate = self.source_subpath.strip().replace("\\", "/").lstrip("/")
            if not candidate:
                # 纯空白/纯斜杠：等同于不指定子路径，物化整份内容。
                object.__setattr__(self, "source_subpath", "")
            else:
                normalized = posixpath.normpath(candidate)
                if normalized in {".", ".."} or normalized.startswith("../"):
                    raise ValidationFailed(f"输入子路径 {self.source_subpath!r} 越出了来源根目录")
                # frozen dataclass：__post_init__ 里改字段只能走 object.__setattr__。
                # 在此规范化（单一真相源）而非每个匹配点都规范化，避免静默落空。
                object.__setattr__(self, "source_subpath", normalized)

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
    environment_version_id: str
    """本次运行使用的精确 Environment Version；不继承其他对象的默认值。"""
    working_directory: str = "."
    command: str = ""
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
    snapshot_id: str
    compute_plan_id: str
    """本次运行占用的算力方案。并发额度按「Initiated By User × 方案」计算（GR-307）。"""
    project_version_id: str
    """本次运行基于的 Project 版本。冗余自快照，用于 Run History 展示。"""
    project_version_label: str
    """版本的人类可读标签（f"v{sequence}"），冗余自快照，避免列表 N+1 查询。"""
    source_run_configuration_id: str | None
    """仅用于来源追踪和配置复用，不作为执行依据。"""
    source_run_id: str | None
    """重跑或派生执行时指向来源 Run。"""
    name: str
    status: RunStatus
    scheduler_job_id: str | None = None
    exit_code: int | None = None
    failure_reason: str = ""
    initiated_by_user_id: str = ""
    """发起本次 Run 的 User（GR-307）。执行身份、并发额度、通知接收方都以它为准。"""
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
    key 的作用域是发起 User：``(initiated_by_user_id, key)`` 唯一。
    平台据此判断这是不是同一次提交——网络抖动、用户双击、前端自动重试，
    都不应该变成两次真实的计算。

    ``run_id`` 为 None 表示登记了但还没创建出 Run，也就是上一次请求
    还在处理中（或者已经失败回滚了）。
    """

    initiated_by_user_id: str
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
    """A current-owner activity fact with immutable display-name snapshots.

    ``owner`` is the authorization and aggregation boundary. ``project_id`` narrows
    Project activity without inventing a second authority model. Actor and target
    names are copied at write time so renames do not rewrite historical sentences.
    """

    id: str
    owner: OwnerReference
    actor_id: str
    actor_name: str
    action: ActivityAction
    target_type: TargetType
    target_id: str
    target_name: str
    created_at: datetime
    project_id: str | None = None
    detail: str = ""


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
    被移除的成员仍然可以读取通知；target 只使用当前 User Group、Project 或 Run 路由。
    """

    id: str
    recipient_id: str
    type: NotificationType
    title: str
    body: str
    created_at: datetime
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
    source_owner: OwnerReference
    source_project_name: str
    source_version_label: str
    """来源版本的展示名，形如 ``v3``。"""
    created_by: str
    created_at: datetime


# --------------------------------------------------------------------------
# Shared Resource
# --------------------------------------------------------------------------


@dataclass(slots=True)
class SharedResource:
    """独立于 Project、可版本化、由一个 User 或 UserGroup 持有的内容资源。

    典型用途：数据集、预训练权重、语料库、预处理脚本。本对象的名称和说明可变，
    但其中的版本一旦发布即不可变（GR-201）。
    """

    id: str
    name: str
    owner: OwnerReference
    description: str = ""
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SharedResourceFile:
    """Shared Resource Version 中的一个文件条目。不可变。"""

    path: str
    size: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class SharedResourceVersion:
    """Shared Resource 已发布的不可变内容版本（GR-201）。

    版本内容按 ``(path, size, content_hash)`` 三元组列表固化，
    实际文件内容存在存储层的 blob store 中，按内容寻址——
    因此 Shared Resource Version 不需要单独的存储目录，复用 Project
    Version 已经在用的 blob 池。

    发布后内容不得原地修改；要改内容只能发布新版本（设计稿 §3.3 GR-201）。
    """

    id: str
    shared_resource_id: str
    sequence: int
    """在该 Shared Resource 内自增，用于展示为 v1、v2……"""
    description: str
    files: tuple[SharedResourceFile, ...]
    created_by: str
    created_at: datetime

    @property
    def label(self) -> str:
        return f"v{self.sequence}"

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def file_count(self) -> int:
        return len(self.files)
