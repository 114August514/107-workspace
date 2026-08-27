"""算力方案、算力请求与调度解析。

解析链路（设计稿 §3.1.5）::

    Resource Entitlement + Compute Plan + Compute Request + Scheduler Mapping
            ↓
    Resolved Scheduler Configuration
            ↓
    提交并执行 Run

普通用户不直接配置底层调度参数，Scheduler Mapping 由平台管理。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationFailed


@dataclass(frozen=True, slots=True)
class SchedulerMapping:
    """把算力方案映射到底层调度参数的平台规则。"""

    cluster: str
    account: str
    partition: str
    qos: str


@dataclass(frozen=True, slots=True)
class ComputePlan:
    """平台面向用户提供的命名资源与运行限制组合。

    ``max_*`` 是该方案允许的上限，``default_*`` 是用户不做调整时的取值。
    """

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
    mapping: SchedulerMapping

    def default_request(self) -> ComputeRequest:
        return ComputeRequest(
            nodes=self.default_nodes,
            cpus=self.default_cpus,
            memory_mb=self.default_memory_mb,
            gpus=self.default_gpus,
            time_limit_minutes=self.default_time_limit_minutes,
        )


@dataclass(frozen=True, slots=True)
class ComputeRequest:
    """一次运行声明的具体资源需求。"""

    nodes: int
    cpus: int
    memory_mb: int
    gpus: int
    time_limit_minutes: int

    def __post_init__(self) -> None:
        if self.nodes < 1:
            raise ValidationFailed("节点数至少为 1")
        if self.cpus < 1:
            raise ValidationFailed("CPU 核数至少为 1")
        if self.memory_mb < 1:
            raise ValidationFailed("内存至少为 1 MB")
        if self.gpus < 0:
            raise ValidationFailed("GPU 数不能为负")
        if self.time_limit_minutes < 1:
            raise ValidationFailed("最长运行时间至少为 1 分钟")

    def as_payload(self) -> dict[str, int]:
        return {
            "nodes": self.nodes,
            "cpus": self.cpus,
            "memory_mb": self.memory_mb,
            "gpus": self.gpus,
            "time_limit_minutes": self.time_limit_minutes,
        }


@dataclass(frozen=True, slots=True)
class ResourceEntitlement:
    """User 获得的算力方案使用资格（设计稿 §Resource Entitlement）。

    只表示 User 对 Compute Plan 的算力使用资格，不代表数据访问权限；
    User Group Ownership / Membership 不转移这个资格。
    """

    id: str
    user_id: str
    compute_plan_id: str
    max_concurrent_runs: int
    expires_at: str | None = None

    def is_expired(self, now_iso: str) -> bool:
        return self.expires_at is not None and self.expires_at <= now_iso


@dataclass(frozen=True, slots=True)
class ResolvedSchedulerConfiguration:
    """创建 Run 时解析并固定的最终调度与资源参数。"""

    cluster: str
    account: str
    partition: str
    qos: str
    nodes: int
    cpus: int
    memory_mb: int
    gpus: int
    time_limit_minutes: int

    def as_payload(self) -> dict[str, object]:
        return {
            "cluster": self.cluster,
            "account": self.account,
            "partition": self.partition,
            "qos": self.qos,
            "nodes": self.nodes,
            "cpus": self.cpus,
            "memory_mb": self.memory_mb,
            "gpus": self.gpus,
            "time_limit_minutes": self.time_limit_minutes,
        }


def check_request_against_plan(plan: ComputePlan, request: ComputeRequest) -> list[str]:
    """检查资源请求是否符合所选算力方案的范围和限制。"""
    problems: list[str] = []
    checks = (
        ("节点数", request.nodes, plan.max_nodes, "个"),
        ("CPU 核数", request.cpus, plan.max_cpus, "核"),
        ("内存", request.memory_mb, plan.max_memory_mb, "MB"),
        ("GPU 数", request.gpus, plan.max_gpus, "张"),
        ("最长运行时间", request.time_limit_minutes, plan.max_time_limit_minutes, "分钟"),
    )
    for label, requested, limit, unit in checks:
        if requested > limit:
            problems.append(
                f"{label} {requested}{unit} 超出算力方案「{plan.name}」的上限 {limit}{unit}"
            )
    return problems


def resolve_scheduler_configuration(
    plan: ComputePlan, request: ComputeRequest
) -> ResolvedSchedulerConfiguration:
    """把算力方案和算力请求解析为最终调度配置。

    调用方必须先通过 :func:`check_request_against_plan` 校验；
    这里再断言一次，避免越权配置被静默提交给调度系统。
    """
    problems = check_request_against_plan(plan, request)
    if problems:
        raise ValidationFailed("；".join(problems))

    return ResolvedSchedulerConfiguration(
        cluster=plan.mapping.cluster,
        account=plan.mapping.account,
        partition=plan.mapping.partition,
        qos=plan.mapping.qos,
        nodes=request.nodes,
        cpus=request.cpus,
        memory_mb=request.memory_mb,
        gpus=request.gpus,
        time_limit_minutes=request.time_limit_minutes,
    )
