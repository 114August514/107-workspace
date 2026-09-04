"""领域错误。

api 层负责把这些错误映射为 HTTP 状态码，领域层不感知 HTTP。

调用方没有**发现权限**时必须抛 ``ObjectNotFound``，
而不是 ``PermissionDenied``——否则错误码本身就泄露了对象是否存在。
只有在调用方已经能看见对象、但无权执行该操作时才用 ``PermissionDenied``。
"""

from __future__ import annotations


class DomainError(Exception):
    """所有领域错误的基类。"""

    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ObjectNotFound(DomainError):
    """对象不存在，或当前用户没有发现权限。"""

    code = "not_found"

    def __init__(self, kind: str, identifier: str | None = None) -> None:
        detail = f"{kind} 不存在" if identifier is None else f"{kind} {identifier} 不存在"
        super().__init__(detail)
        self.kind = kind
        self.identifier = identifier


class PermissionDenied(DomainError):
    """对象可见，但当前角色无权执行该操作。"""

    code = "permission_denied"


class ValidationFailed(DomainError):
    """输入不满足领域约束。"""

    code = "validation_failed"


class ConflictError(DomainError):
    """与现有状态冲突，例如重名或状态不允许。"""

    code = "conflict"

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message)
        self.problems = problems or []


class ImmutableObjectError(ConflictError):
    """试图修改不可变的 Version、Run Snapshot 或 Artifact 内容（GR-201、GR-202、GR-203）。"""

    code = "immutable_object"


class PreflightRejected(DomainError):
    """提交前检查未通过，附带全部阻止提交的问题。"""

    code = "preflight_rejected"

    def __init__(self, problems: list[str]) -> None:
        super().__init__("提交前检查未通过：" + "；".join(problems))
        self.problems = problems


class SharedResourceUnavailable(DomainError):
    """一个确定的 Shared Resource Version 在提交或物化时不可用。"""

    code = "shared_resource_unavailable"

    def __init__(self, version_id: str, message: str) -> None:
        super().__init__(message)
        self.version_id = version_id


class SchedulerError(DomainError):
    """底层调度系统返回错误。"""

    code = "scheduler_error"
