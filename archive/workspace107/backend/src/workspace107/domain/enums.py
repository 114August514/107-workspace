"""领域枚举。

取值一律使用小写下划线形式，与数据库和 API 表示保持一致。
"""

from __future__ import annotations

from enum import StrEnum


class WorkspaceKind(StrEnum):
    """Workspace 类型。

    Course 不构成第三种类型：Course Workspace 是启用了 Course Profile 的
    Collaborative Workspace。
    """

    PERSONAL = "personal"
    COLLABORATIVE = "collaborative"


class WorkspaceRole(StrEnum):
    """成员在 Workspace 中的角色。

    角色本身不携带权限语义——它只是一组能力的命名集合，
    具体能做什么见 :mod:`workspace107.domain.capabilities`。
    判断权限时永远问「有没有这个能力」，不要问「是不是某个角色」。
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


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


class RunStatus(StrEnum):
    """Run 执行状态。

    状态只能由调度系统的轮询结果驱动（GR-015），
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

    清理只删除存储内容并置为 cleaned，不删除记录本身（GR-016）。
    """

    AVAILABLE = "available"
    CLEANED = "cleaned"


class InputSourceType(StrEnum):
    """Input Binding 的来源类型。

    M1 只支持 artifact；shared_resource_version 已建模但能力未开放。
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

    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_UPDATED = "workspace_updated"
    MEMBER_INVITED = "member_invited"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_FORKED = "project_forked"
    VERSION_SAVED = "version_saved"
    VERSION_RESTORED = "version_restored"
    RUN_SUBMITTED = "run_submitted"
    RUN_CANCELLED = "run_cancelled"
    RUN_FINISHED = "run_finished"


class TargetType(StrEnum):
    """一条记录指向的对象类型。前端据此决定链接跳到哪里。

    活动和通知共用这一套：两者指向的都是同一批领域对象，
    分成两个枚举只会让前端的跳转逻辑写两遍。
    """

    WORKSPACE = "workspace"
    MEMBER = "member"
    PROJECT = "project"
    PROJECT_VERSION = "project_version"
    RUN = "run"


class NotificationType(StrEnum):
    """通知的种类。前端据此选图标，V1 加偏好设置时也按它分组。

    和 :class:`ActivityAction` 刻意分开：**不是一一对应的**。
    一次操作可能产生一条活动和零条通知（比如自己改自己的空间设置），
    也可能产生一条活动和多条通知。硬凑成一个枚举会逼着两边互相迁就。
    """

    WORKSPACE_INVITED = "workspace_invited"
    MEMBER_REMOVED = "member_removed"
    ROLE_CHANGED = "role_changed"
    OWNERSHIP_RECEIVED = "ownership_received"
    RUN_SUCCEEDED = "run_succeeded"
    RUN_FAILED = "run_failed"
    RUN_SUBMIT_FAILED = "run_submit_failed"
