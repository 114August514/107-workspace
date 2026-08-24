from __future__ import annotations

from datetime import UTC, datetime

import pytest

from workspace107.application.access import ProjectAccess
from workspace107.application.scoped_config_resolver import ScopedConfigResolver
from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.config_scope import ConfigScope, SecretReference
from workspace107.domain.enums import EnvValueKind, LegacyWorkspaceKind, MembershipRole
from workspace107.domain.models import LegacyWorkspace, Project, Variable
from workspace107.domain.ownership import OwnerKind, OwnerReference
from workspace107.domain.run_snapshot import build_snapshot
from workspace107.domain.secrets import EnvValue, ResolvedEnv, parse_env_map
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.secret_vault import DatabaseSecretVault


def _access() -> ProjectAccess:
    return ProjectAccess(
        Project("project", "workspace", "Project", owner=OwnerReference(OwnerKind.USER, "owner")),
        LegacyWorkspace("workspace", LegacyWorkspaceKind.PERSONAL, "Personal", owner_id="owner"),
        MembershipRole.OWNER,
        owner_scope=True,
    )


@pytest.mark.asyncio
async def test_real_values_freeze_and_secret_rotation(context, session) -> None:
    repos = SqlRepositories(session)
    vault = DatabaseSecretVault(session)
    project = ConfigScope.project("project")
    await repos.variables.upsert(Variable(project, "LEVEL", "before"))
    await vault.set_secret(project, "TOKEN", "first")
    await session.commit()
    resolver = ScopedConfigResolver(repos.variables, vault)
    resolved = await resolver.resolve(
        _access(),
        "owner",
        {
            "LEVEL": EnvValue(EnvValueKind.VARIABLE, "LEVEL"),
            "TOKEN": EnvValue(EnvValueKind.SECRET, "TOKEN"),
        },
    )
    snapshot = build_snapshot(
        snapshot_id="snapshot",
        project_id="project",
        project_version_id="version",
        source_run_configuration_id=None,
        working_directory=".",
        command="echo ok",
        environment_version_id="env",
        environment_image="image",
        environment_setup_command="",
        resolved_env=ResolvedEnv(resolved.literals, resolved.secret_refs),
        input_bindings=(),
        compute_plan_id="plan",
        compute_request=ComputeRequest(1, 1, 1, 0, 1),
        scheduler=ResolvedSchedulerConfiguration("c", "a", "p", "q", 1, 1, 1, 0, 1),
        artifact_rules=(),
        initiated_by_user_id="owner",
        created_at=datetime.now(UTC),
    )
    await repos.variables.upsert(Variable(project, "LEVEL", "after"))
    await vault.set_secret(project, "TOKEN", "rotated")
    await session.commit()
    current, problems = await resolver.validate_and_resolve(
        _access(), "owner", snapshot.env_secret_refs
    )
    assert problems == []
    assert snapshot.env_literals == {"LEVEL": "before"}
    assert current == {"TOKEN": "rotated"}
    assert "rotated" not in str(snapshot.to_payload())


@pytest.mark.asyncio
async def test_deleted_project_secret_never_falls_back_to_owner(context, session) -> None:
    repos = SqlRepositories(session)
    vault = DatabaseSecretVault(session)
    project = ConfigScope.project("project")
    await vault.set_secret(project, "TOKEN", "project-value")
    await vault.set_secret(ConfigScope.user("owner"), "TOKEN", "owner-value")
    await session.commit()
    ref = SecretReference(project, "TOKEN")
    await vault.delete_secret(project, "TOKEN")
    await session.commit()
    values, problems = await ScopedConfigResolver(repos.variables, vault).validate_and_resolve(
        _access(), "owner", {"TOKEN": ref}
    )
    assert values == {}
    assert problems


def test_fork_expression_only_preserves_standard_and_user_namespaces() -> None:
    expressions = parse_env_map(
        {
            "A": "${{ vars.LEVEL }}",
            "B": "${{ secrets.TOKEN }}",
            "C": "${{ user.vars.LEVEL }}",
            "D": "${{ user.secrets.TOKEN }}",
        }
    )
    assert {name: value.expression for name, value in expressions.items()} == {
        "A": "${{ vars.LEVEL }}",
        "B": "${{ secrets.TOKEN }}",
        "C": "${{ user.vars.LEVEL }}",
        "D": "${{ user.secrets.TOKEN }}",
    }
