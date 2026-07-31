"""算力方案、算力请求与调度解析。"""

from __future__ import annotations

import pytest

from workspace107.domain.compute import (
    ComputePlan,
    ComputeRequest,
    ResourceEntitlement,
    SchedulerMapping,
    check_request_against_plan,
    resolve_scheduler_configuration,
)
from workspace107.domain.errors import ValidationFailed

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
    max_nodes=1,
    max_cpus=16,
    max_memory_mb=131072,
    max_gpus=2,
    max_time_limit_minutes=1440,
    mapping=SchedulerMapping(cluster="107", account="undergraduate", partition="gpu", qos="normal"),
)


@pytest.mark.parametrize(
    "payload",
    [
        {"nodes": 0, "cpus": 1, "memory_mb": 1, "gpus": 0, "time_limit_minutes": 1},
        {"nodes": 1, "cpus": 0, "memory_mb": 1, "gpus": 0, "time_limit_minutes": 1},
        {"nodes": 1, "cpus": 1, "memory_mb": 0, "gpus": 0, "time_limit_minutes": 1},
        {"nodes": 1, "cpus": 1, "memory_mb": 1, "gpus": -1, "time_limit_minutes": 1},
        {"nodes": 1, "cpus": 1, "memory_mb": 1, "gpus": 0, "time_limit_minutes": 0},
    ],
)
def test_非法资源请求在构造时就被拒绝(payload: dict[str, int]) -> None:
    with pytest.raises(ValidationFailed):
        ComputeRequest(**payload)


def test_方案默认值本身是合法请求() -> None:
    assert check_request_against_plan(PLAN, PLAN.default_request()) == []


def test_超出方案上限时逐项给出原因() -> None:
    request = ComputeRequest(nodes=4, cpus=64, memory_mb=262144, gpus=8, time_limit_minutes=4320)
    problems = check_request_against_plan(PLAN, request)

    assert len(problems) == 5
    assert any("节点数" in p for p in problems)
    assert any("GPU 数" in p for p in problems)
    assert all("GPU 标准" in p for p in problems)


def test_解析出的调度配置来自方案映射() -> None:
    config = resolve_scheduler_configuration(PLAN, PLAN.default_request())

    assert config.cluster == "107"
    assert config.partition == "gpu"
    assert config.qos == "normal"
    assert config.account == "undergraduate"
    assert config.gpus == 1


def test_越权请求不会被解析成调度配置() -> None:
    """即使调用方跳过了校验，解析这一步也会再拦一次。"""
    request = ComputeRequest(nodes=1, cpus=8, memory_mb=1024, gpus=8, time_limit_minutes=10)
    with pytest.raises(ValidationFailed):
        resolve_scheduler_configuration(PLAN, request)


def test_权益过期判断() -> None:
    entitlement = ResourceEntitlement(
        id="ent_1",
        workspace_id="ws_1",
        compute_plan_id=PLAN.id,
        max_concurrent_runs=2,
        expires_at="2026-01-01T00:00:00+00:00",
    )
    assert entitlement.is_expired("2026-07-26T00:00:00+00:00")
    assert not entitlement.is_expired("2025-12-01T00:00:00+00:00")


def test_没有到期时间的权益永不过期() -> None:
    entitlement = ResourceEntitlement(
        id="ent_1", workspace_id="ws_1", compute_plan_id=PLAN.id, max_concurrent_runs=2
    )
    assert not entitlement.is_expired("2099-01-01T00:00:00+00:00")
