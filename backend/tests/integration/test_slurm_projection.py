"""Run preflight applies Slurm projection only for the Slurm scheduler."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import (
    create_project_with_version,
    grant_test_entitlement,
    use_default_environment,
)
from workspace107.api.deps import AppContext
from workspace107.domain.slurm_projection import (
    SlurmAssociationFact,
    SlurmFacts,
    SlurmPartitionFact,
    SlurmProjection,
    SlurmQosLimitsFact,
)
from workspace107.infrastructure.scheduler.mock import MockScheduler


class SlurmTestScheduler(MockScheduler):
    name = "slurm"


def available_projection() -> SlurmProjection:
    return SlurmProjection(
        SlurmFacts(
            associations=tuple(
                SlurmAssociationFact("107", "undergraduate", partition, "*")
                for partition in ("debug", "cpu", "gpu")
            ),
            partitions=tuple(
                SlurmPartitionFact("107", partition, ("normal",))
                for partition in ("debug", "cpu", "gpu")
            ),
            qos_limits=(
                SlurmQosLimitsFact(
                    "107",
                    "normal",
                    max_nodes=2,
                    max_cpus=32,
                    max_memory_mb=131072,
                    max_gpus=2,
                    max_time_limit_minutes=1440,
                ),
            ),
        )
    )


async def _prepare(client: httpx.AsyncClient, session: AsyncSession) -> tuple[str, str]:
    headers = {"X-User": "student"}
    _, environment_version_id = await use_default_environment(session, client, headers=headers)
    project = await create_project_with_version(client, headers=headers)
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "Slurm projection run",
            "command": "python -V",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
        },
        headers=headers,
    )
    response.raise_for_status()
    return project["id"], response.json()["id"]


@pytest.mark.asyncio
async def test_mock_preflight_does_not_require_slurm_facts(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    project_id, configuration_id = await _prepare(client, session)
    await grant_test_entitlement(session, "student")

    response = await client.post(
        f"/api/v1/projects/{project_id}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers={"X-User": "student"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["slurm_projection"] is None


@pytest.mark.asyncio
async def test_slurm_preflight_requires_independent_entitlement_and_slurm_facts(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    project_id, configuration_id = await _prepare(client, session)
    context.scheduler = SlurmTestScheduler()
    context.slurm_projection = SlurmProjection(SlurmFacts())

    response = await client.post(
        f"/api/v1/projects/{project_id}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers={"X-User": "student"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert any("使用权益" in problem for problem in body["problems"])
    assert body["slurm_projection"]["availability"] == "unknown"
    assert body["slurm_projection"]["reason"] == "slurm_association_unknown"


@pytest.mark.asyncio
async def test_create_freezes_projected_scheduler_configuration(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    project_id, configuration_id = await _prepare(client, session)
    context.scheduler = SlurmTestScheduler()
    context.slurm_projection = available_projection()
    await grant_test_entitlement(session, "student")

    preflight = await client.post(
        f"/api/v1/projects/{project_id}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers={"X-User": "student"},
    )
    assert preflight.status_code == 200
    assert preflight.json()["slurm_projection"]["availability"] == "available"

    created = await client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"run_configuration_id": configuration_id},
        headers={"X-User": "student"},
    )
    assert created.status_code == 201, created.text
    detail = await client.get(f"/api/v1/runs/{created.json()['id']}")
    detail.raise_for_status()
    scheduler = detail.json()["snapshot"]["scheduler"]
    assert scheduler["cluster"] == "107"
    assert scheduler["account"] == "undergraduate"
    assert scheduler["partition"] == "debug"
    assert scheduler["qos"] == "normal"
