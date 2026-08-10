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


class ImmutableObjectError(ConflictError):
    """试图修改不可变的 Version、Run Snapshot 或 Artifact 内容（GR-201、GR-202、GR-203）。"""

    code = "immutable_object"


class PreflightRejected(DomainError):
    """提交前检查未通过，附带全部阻止提交的问题。"""

    code = "preflight_rejected"

    def __init__(self, problems: list[str]) -> None:
        super().__init__("提交前检查未通过：" + "；".join(problems))
        self.problems = problems


class SchedulerError(DomainError):
    """底层调度系统返回错误。"""

    code = "scheduler_error"


class SchedulerProtocolError(SchedulerError):
    """调度 API 返回的成功响应不符合已配置的 schema profile。"""

    code = "scheduler_protocol_error"


class SchedulerSubmissionRejected(SchedulerError):
    """调度端明确拒绝提交，调用方可确定没有拿到 job id。"""

    code = "scheduler_submission_rejected"


class SchedulerSubmissionUncertain(SchedulerError):
    """提交可能已经被接受，必须按 correlation 恢复，禁止盲目重试。"""

    code = "scheduler_submission_uncertain"


class SchedulerJobNotFound(SchedulerError):
    """指定 job id 在调度端不可见；不能当作取消成功。"""

    code = "scheduler_job_not_found"
