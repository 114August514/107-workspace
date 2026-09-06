"""Recorded Slurm facts projected onto Compute Plans."""

from __future__ import annotations

import pytest

from workspace107.domain.compute import ComputePlan, SchedulerMapping
from workspace107.domain.slurm_projection import (
    SlurmAssociationFact,
    SlurmFacts,
    SlurmPartitionFact,
    SlurmProjection,
    SlurmProjectionAvailability,
    SlurmQosLimitsFact,
)

PLAN = ComputePlan(
    id="plan_gpu",
    code="gpu-standard",
    name="GPU 标准",
    description="",
    default_nodes=1,
    default_cpus=8,
    default_memory_mb=32768,
    default_gpus=1,
    default_time_limit_minutes=240,
    max_nodes=4,
    max_cpus=64,
    max_memory_mb=262144,
    max_gpus=4,
    max_time_limit_minutes=2880,
    mapping=SchedulerMapping(cluster="107", account="undergraduate", partition="gpu", qos="normal"),
)


def facts(**kwargs: object) -> SlurmFacts:
    return SlurmFacts(
        associations=(SlurmAssociationFact("107", "undergraduate", "gpu", "alice"),),
        partitions=(SlurmPartitionFact("107", "gpu", ("normal",)),),
        qos_limits=(
            SlurmQosLimitsFact(
                "107",
                "normal",
                max_nodes=2,
                max_cpus=16,
                max_memory_mb=131072,
                max_gpus=2,
                max_time_limit_minutes=1440,
                **kwargs,
            ),
        ),
    )


def test_projection_intersects_qos_limits_and_keeps_job_counts_out() -> None:
    result = SlurmProjection(facts(max_jobs=0, grp_jobs=0, max_submit_jobs=0)).project(
        PLAN, username="alice"
    )

    assert result.availability is SlurmProjectionAvailability.AVAILABLE
    assert result.plan is not None
    assert result.plan.max_nodes == 2
    assert result.plan.max_cpus == 16
    assert result.plan.max_memory_mb == 131072
    assert result.plan.max_gpus == 2
    assert result.plan.max_time_limit_minutes == 1440


def test_missing_facts_are_unknown_and_not_runnable() -> None:
    result = SlurmProjection(SlurmFacts()).project(PLAN, username="alice")

    assert result.availability is SlurmProjectionAvailability.UNKNOWN
    assert not result.ok
    assert result.reason == "slurm_association_unknown"


def test_allow_qos_conflict_is_unavailable() -> None:
    recorded = facts()
    result = SlurmProjection(
        SlurmFacts(
            associations=recorded.associations,
            partitions=(SlurmPartitionFact("107", "gpu", ("restricted",)),),
            qos_limits=recorded.qos_limits,
        )
    ).project(PLAN, username="alice")

    assert result.availability is SlurmProjectionAvailability.UNAVAILABLE
    assert result.reason == "slurm_qos_not_allowed"


@pytest.mark.parametrize(
    "field",
    ["max_nodes", "max_cpus", "max_memory_mb", "max_gpus", "max_time_limit_minutes"],
)
def test_incomplete_qos_limits_are_unknown(field: str) -> None:
    values = {
        "max_nodes": 2,
        "max_cpus": 16,
        "max_memory_mb": 131072,
        "max_gpus": 2,
        "max_time_limit_minutes": 1440,
    }
    values[field] = None
    result = SlurmProjection(
        SlurmFacts(
            associations=(SlurmAssociationFact("107", "undergraduate", "gpu", "alice"),),
            partitions=(SlurmPartitionFact("107", "gpu", ("normal",)),),
            qos_limits=(SlurmQosLimitsFact("107", "normal", **values),),
        )
    ).project(PLAN, username="alice")

    assert result.availability is SlurmProjectionAvailability.UNKNOWN
    assert result.reason == "slurm_qos_limits_incomplete"
