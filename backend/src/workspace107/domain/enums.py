from enum import StrEnum


class WorkspaceKind(StrEnum):
    PERSONAL = "personal"
    COURSE = "course"
    EXPERIMENT = "experiment"
    TEAM = "team"
    PROJECT = "project"
    PUBLIC = "public"


class WorkspaceRole(StrEnum):
    VIEWER = "viewer"
    MEMBER = "member"
    MANAGER = "manager"
    OWNER = "owner"


class RunStatus(StrEnum):
    SUBMITTING = "submitting"
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(StrEnum):
    LOG = "log"
    RESULT = "result"
    REPORT = "report"
