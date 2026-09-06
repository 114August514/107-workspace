"""领域枚举。

取值一律使用小写下划线形式，与数据库和 API 表示保持一致。
"""

from __future__ import annotations

from enum import StrEnum


class EnvironmentRuntimeKind(StrEnum):
    MODULES = "modules"
    APPTAINER_SIF = "apptainer_sif"


class EnvironmentAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"


class EnvironmentPublicationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED}


class MembershipRole(StrEnum):
    """A User's role in one exact User Group."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MembershipStatus(StrEnum):
    """Membership 生命周期：Invited -> Active -> Left / Removed。"""

    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"


class ProjectStatus(StrEnum):
    """Project 生命周期：Active -> Archived。"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectVisibility(StrEnum):
    """Project discovery boundary, independent from operation permissions."""

    OWNER_SCOPE = "owner_scope"
    PUBLIC = "public"


class RunStatus(StrEnum):
    """Run 执行状态。

    当前实现中状态只能由调度系统的轮询结果驱动，
    平台自身不提供「把 Run 直接标记为成功」的路径。
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUBMIT_FAILED = "submit_failed"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_RUN_STATUSES


_TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.SUBMIT_FAILED,
    }
)


class RunEventType(StrEnum):
    """平台产生的执行事件，区别于用户程序的 stdout / stderr。"""

    CREATED = "created"
    SUBMITTED = "submitted"
    SUBMIT_FAILED = "submit_failed"
    STARTED = "started"
    FINISHED = "finished"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    ARTIFACT_COLLECTED = "artifact_collected"
    ARTIFACT_MISSING = "artifact_missing"
    ERROR = "error"


class LogStream(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"


class ArtifactStatus(StrEnum):
    """Artifact 状态。

    当前清理流程只删除存储内容并置为 cleaned，不删除记录本身。
    """

    AVAILABLE = "available"
    CLEANED = "cleaned"


class SharedResourcePublicationStatus(StrEnum):
    """Durable publication attempt state."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {
            SharedResourcePublicationStatus.SUCCEEDED,
            SharedResourcePublicationStatus.FAILED,
        }


class InputSourceType(StrEnum):
    """Input Binding 的来源类型。

    两种来源都已实现：``artifact`` 从产物目录物化，``shared_resource_version``
    从版本的文件清单按 blob 物化（设计稿 §3.1.3、§2.6）。
    """

    ARTIFACT = "artifact"
    SHARED_RESOURCE_VERSION = "shared_resource_version"


class EnvValueKind(StrEnum):
    """Run Configuration 中环境变量取值的种类。"""

    LITERAL = "literal"
    VARIABLE = "variable"
    SECRET = "secret"


class ChangeKind(StrEnum):
    """文件在两次快照之间的变化类型。"""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ActivityAction(StrEnum):
    """活动流里的业务动作。

    命名是 ``对象_动词``，和能力枚举（``对象.动作``）刻意用不同的分隔符——
    两者容易混淆，但**不是一回事**：能力管「能不能做」，动作管「做了什么」。
    有的动作没有对应能力（比如接受邀请），有的能力不产生活动（比如查看）。

    取值只增不改。已经写进库的活动会一直用旧值，改名等于让历史记录读不出来。
    """

    USER_GROUP_CREATED = "user_group_created"
    USER_GROUP_UPDATED = "user_group_updated"
    USER_GROUP_DELETED = "user_group_deleted"
    MEMBER_INVITED = "member_invited"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_FORKED = "project_forked"
    PROJECT_DELETED = "project_deleted"
    VERSION_SAVED = "version_saved"
    VERSION_RESTORED = "version_restored"
    RUN_SUBMITTED = "run_submitted"
    RUN_CANCELLED = "run_cancelled"
    RUN_FINISHED = "run_finished"
    SHARED_RESOURCE_CREATED = "shared_resource_created"
    SHARED_RESOURCE_UPDATED = "shared_resource_updated"
    SHARED_RESOURCE_VERSION_PUBLISHED = "shared_resource_version_published"


class TargetType(StrEnum):
    """一条记录指向的对象类型。前端据此决定链接跳到哪里。

    活动和通知共用这一套：两者指向的都是同一批领域对象，
    分成两个枚举只会让前端的跳转逻辑写两遍。
    """

    USER_GROUP = "user_group"
    MEMBER = "member"
    PROJECT = "project"
    PROJECT_VERSION = "project_version"
    RUN = "run"
    SHARED_RESOURCE = "shared_resource"
    SHARED_RESOURCE_VERSION = "shared_resource_version"


class NotificationType(StrEnum):
    """通知的种类。前端据此选图标，V1 加偏好设置时也按它分组。

    和 :class:`ActivityAction` 刻意分开：**不是一一对应的**。
    一次操作可能产生一条活动和零条通知（比如自己改自己的空间设置），
    也可能产生一条活动和多条通知。硬凑成一个枚举会逼着两边互相迁就。
    """

    USER_GROUP_INVITED = "user_group_invited"
    MEMBER_REMOVED = "member_removed"
    ROLE_CHANGED = "role_changed"
    OWNERSHIP_RECEIVED = "ownership_received"
    RUN_SUCCEEDED = "run_succeeded"
    RUN_FAILED = "run_failed"
    RUN_SUBMIT_FAILED = "run_submit_failed"
    ENVIRONMENT_UNAVAILABLE = "environment_unavailable"
    SHARED_RESOURCE_UNAVAILABLE = "shared_resource_unavailable"
    PLATFORM_INCIDENT = "platform_incident"
