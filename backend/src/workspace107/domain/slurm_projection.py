"""Recorded Slurm facts and their Compute Plan projection.

This module deliberately models a small, normalized fact fixture rather than a
Slurm client.  A live probe is a separate concern; absent facts stay unknown and
therefore cannot make a plan runnable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .compute import ComputePlan


class SlurmProjectionAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SlurmAssociationFact:
    """A recorded user/account/partition association."""

    cluster: str
    account: str
    partition: str
    user: str | None = None


@dataclass(frozen=True, slots=True)
class SlurmPartitionFact:
    """A recorded partition and its visible AllowQos value.

    ``None`` means the field was not visible in the facts, while an empty tuple
    means the partition explicitly allows no QoS.
    """

    cluster: str
    name: str
    allow_qos: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class SlurmQosLimitsFact:
    """Visible per-job QoS limits in normalized platform units.

    The job-count fields are retained as evidence but intentionally never map to
    ``ResourceEntitlement.max_concurrent_runs``.
    """

    cluster: str
    name: str
    max_nodes: int | None = None
    max_cpus: int | None = None
    max_memory_mb: int | None = None
    max_gpus: int | None = None
    max_time_limit_minutes: int | None = None
    max_jobs: int | None = None
    grp_jobs: int | None = None
    max_submit_jobs: int | None = None


@dataclass(frozen=True, slots=True)
class SlurmFacts:
    associations: tuple[SlurmAssociationFact, ...] = ()
    partitions: tuple[SlurmPartitionFact, ...] = ()
    qos_limits: tuple[SlurmQosLimitsFact, ...] = ()


@dataclass(frozen=True, slots=True)
class SlurmPlanProjection:
    availability: SlurmProjectionAvailability
    reason: str
    detail: str
    plan: ComputePlan | None = None

    @property
    def ok(self) -> bool:
        return self.availability is SlurmProjectionAvailability.AVAILABLE and self.plan is not None


class SlurmProjection:
    """Project recorded facts onto an existing Compute Plan."""

    def __init__(self, facts: SlurmFacts) -> None:
        self._facts = facts

    def project(self, plan: ComputePlan, *, username: str | None = None) -> SlurmPlanProjection:
        mapping = plan.mapping
        if not self._facts.associations:
            return self._unknown("slurm_association_unknown", "没有记录可见的 Slurm association")

        association = next(
            (
                fact
                for fact in self._facts.associations
                if fact.cluster == mapping.cluster
                and fact.account == mapping.account
                and fact.partition == mapping.partition
                and (fact.user in {None, "*"} or fact.user == username)
            ),
            None,
        )
        if association is None:
            return self._unavailable(
                "slurm_association_not_allowed",
                f"Slurm association 不允许 {username or '当前 User'} 使用 "
                f"{mapping.account}/{mapping.partition}",
            )

        partitions = [
            fact
            for fact in self._facts.partitions
            if fact.cluster == mapping.cluster and fact.name == mapping.partition
        ]
        if not self._facts.partitions:
            return self._unknown("slurm_partition_unknown", "没有记录可见的 Slurm partition")
        if not partitions:
            return self._unavailable(
                "slurm_partition_missing", f"Slurm partition {mapping.partition} 不存在于当前事实"
            )
        allow_qos = partitions[0].allow_qos
        if allow_qos is None:
            return self._unknown(
                "slurm_allow_qos_unknown", f"Slurm partition {mapping.partition} 的 AllowQos 不可见"
            )
        if mapping.qos not in allow_qos:
            return self._unavailable(
                "slurm_qos_not_allowed",
                f"Slurm partition {mapping.partition} 的 AllowQos 不包含 QoS {mapping.qos}",
            )

        qos = next(
            (
                fact
                for fact in self._facts.qos_limits
                if fact.cluster == mapping.cluster and fact.name == mapping.qos
            ),
            None,
        )
        if qos is None:
            return self._unknown("slurm_qos_limits_unknown", f"QoS {mapping.qos} limits 不可见")
        values = (
            qos.max_nodes,
            qos.max_cpus,
            qos.max_memory_mb,
            qos.max_gpus,
            qos.max_time_limit_minutes,
        )
        if any(value is None for value in values):
            return self._unknown("slurm_qos_limits_incomplete", f"QoS {mapping.qos} limits 不完整")

        projected = replace(
            plan,
            max_nodes=min(plan.max_nodes, qos.max_nodes),
            max_cpus=min(plan.max_cpus, qos.max_cpus),
            max_memory_mb=min(plan.max_memory_mb, qos.max_memory_mb),
            max_gpus=min(plan.max_gpus, qos.max_gpus),
            max_time_limit_minutes=min(plan.max_time_limit_minutes, qos.max_time_limit_minutes),
        )
        if any(
            requested > limit
            for requested, limit in zip(
                (
                    projected.default_nodes,
                    projected.default_cpus,
                    projected.default_memory_mb,
                    projected.default_gpus,
                    projected.default_time_limit_minutes,
                ),
                (
                    projected.max_nodes,
                    projected.max_cpus,
                    projected.max_memory_mb,
                    projected.max_gpus,
                    projected.max_time_limit_minutes,
                ),
                strict=True,
            )
        ):
            return self._unavailable(
                "slurm_limits_below_defaults",
                f"QoS {mapping.qos} limits 低于 Compute Plan「{plan.name}」默认请求",
            )

        return SlurmPlanProjection(
            availability=SlurmProjectionAvailability.AVAILABLE,
            reason="slurm_projection_available",
            detail=(
                f"association={association.account}/{association.partition}; "
                f"partition AllowQos={','.join(allow_qos)}; qos={qos.name} limits 已确认"
            ),
            plan=projected,
        )

    @staticmethod
    def _unknown(reason: str, detail: str) -> SlurmPlanProjection:
        return SlurmPlanProjection(SlurmProjectionAvailability.UNKNOWN, reason, detail)

    @staticmethod
    def _unavailable(reason: str, detail: str) -> SlurmPlanProjection:
        return SlurmPlanProjection(SlurmProjectionAvailability.UNAVAILABLE, reason, detail)
