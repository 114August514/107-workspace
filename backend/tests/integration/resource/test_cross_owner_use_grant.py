"""Issue #40 cross-owner USE Grant enables asset use across ownership boundaries."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import grant_test_entitlement, process_shared_resource_publication
from workspace107.api.deps import AppContext
from workspace107.domain import ids
from workspace107.infrastructure.db.tables import (
    EnvironmentRow,
    EnvironmentVersionRow,
    GrantRow,
    RunConfigurationRow,
)

ALICE = {"X-User": "alice"}
BOB = {"X-User": "bob"}


async def _create_group(
    client: httpx.AsyncClient, name: str, *, headers: dict | None = None
) -> str:
    response = await client.post(
        "/api/v1/user-groups", json={"name": name}, headers=headers or ALICE
    )
    response.raise_for_status()
    return str(response.json()["id"])


async def _create_project_with_version(
    client: httpx.AsyncClient, user_group_id: str, *, name: str, headers: dict | None = None
) -> dict:
    response = await client.post(
        "/api/v1/projects",
        json={"owner": {"kind": "user_group", "id": user_group_id}, "name": name},
        headers=headers or ALICE,
    )
    response.raise_for_status()
    project = response.json()
    response = await client.put(
        f"/api/v1/projects/{project['id']}/files",
        json={"path": "main.py", "content": "print('ok')"},
        headers=headers or ALICE,
    )
    response.raise_for_status()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/versions",
        json={"message": "v1"},
        headers=headers or ALICE,
    )
    response.raise_for_status()
    project["_version_id"] = response.json()["id"]
    return project


async def _create_resource_version(
    client: httpx.AsyncClient, context: AppContext, user_group_id: str
) -> tuple[str, str]:
    """Create Shared Resource + Version owned by ``user_group_id``. Returns (id, version_id)."""
    response = await client.post(
        "/api/v1/shared-resources",
        json={
            "owner": {"kind": "user_group", "id": user_group_id},
            "name": f"resource-{user_group_id[:8]}",
        },
        headers=ALICE,
    )
    response.raise_for_status()
    resource_id = str(response.json()["id"])
    response = await client.post(
        f"/api/v1/shared-resources/{resource_id}/versions",
        data={"description": "v1"},
        files={"files": ("data.txt", b"data", "text/plain")},
        headers=ALICE,
    )
    response.raise_for_status()
    version_id = await process_shared_resource_publication(context, str(response.json()["id"]))
    return resource_id, version_id


async def _create_environment_version(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    owner_user_group_id: str | None = None,
) -> tuple[str, str]:
    """Create an Environment + Version. Returns (environment_id, version_id)."""
    environment_id = ids.new_id(ids.ENVIRONMENT)
    version_id = ids.new_id(ids.ENVIRONMENT_VERSION)
    session.add(
        EnvironmentRow(
            id=environment_id,
            name=f"{environment_id} environment",
            description="",
            owner_user_id=owner_user_id,
            owner_user_group_id=owner_user_group_id,
        )
    )
    await session.flush()
    session.add(
        EnvironmentVersionRow(
            id=version_id,
            environment_id=environment_id,
            version="1",
            description="",
        )
    )
    await session.commit()
    return environment_id, version_id


async def _set_group_environment(
    session: AsyncSession, client: httpx.AsyncClient, user_group_id: str
) -> str:
    _, version_id = await _create_environment_version(session, owner_user_group_id=user_group_id)
    return version_id


async def _insert_grant(
    session: AsyncSession,
    *,
    grantee_kind: str,
    grantee_id: str,
    target_kind: str,
    target_id: str,
    granted_by_id: str,
    grantor_kind: str,
    grantor_id: str,
) -> str:
    """Insert a GrantRow directly."""
    grant_id = ids.new_id(ids.GRANT)
    session.add(
        GrantRow(
            id=grant_id,
            grantor_kind=grantor_kind,
            grantor_id=grantor_id,
            grantee_kind=grantee_kind,
            grantee_id=grantee_id,
            target_kind=target_kind,
            target_id=target_id,
            action="use",
            granted_by_id=granted_by_id,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return grant_id


async def _get_user_id(client: httpx.AsyncClient, headers: dict) -> str:
    """Get the internal user id for a dev-user header."""
    response = await client.get("/api/v1/me", headers=headers)
    response.raise_for_status()
    return str(response.json()["user"]["id"])


# ---------------------------------------------------------------------------
# Test 1: User Grant enables cross-owner Shared Resource use
# ---------------------------------------------------------------------------


async def test_user_grant_enables_cross_owner_shared_resource_use(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """A User-level USE Grant lets Alice reference Group B's resource from Group A's project."""
    group_a = await _create_group(client, "Grant Group A")
    group_b = await _create_group(client, "Grant Group B")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    alice_id = await _get_user_id(client, ALICE)

    # Without a Grant: creating a run-configuration referencing B's resource → 404.
    attempted = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "cross-owner",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert attempted.status_code == 404, attempted.text

    # Insert a User → B-resource USE Grant.
    await _insert_grant(
        session,
        grantee_kind="user",
        grantee_id=alice_id,
        target_kind="shared_resource",
        target_id=resource_b_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    # With Grant: same request succeeds.
    attempted = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "cross-owner-granted",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert attempted.status_code == 201, attempted.text


# ---------------------------------------------------------------------------
# Test 2: User Group Grant enables cross-owner Environment use
# ---------------------------------------------------------------------------


async def test_user_group_grant_enables_cross_owner_environment_use(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """A UserGroup-level USE Grant lets Group A use Group B's environment."""
    group_a = await _create_group(client, "Env Grant Group A")
    group_b = await _create_group(client, "Env Grant Group B")
    await _set_group_environment(session, client, group_a)
    env_b_id, env_b_version_id = await _create_environment_version(
        session, owner_user_group_id=group_b
    )
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A env project")
    alice_id = await _get_user_id(client, ALICE)

    # Without Grant: assigning B's environment to A's project → 404.
    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": env_b_version_id},
        headers=ALICE,
    )
    assert response.status_code == 404, response.text
    await _insert_grant(
        session,
        grantee_kind="user_group",
        grantee_id=group_a,
        target_kind="environment",
        target_id=env_b_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    # With Grant: assignment succeeds.
    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": env_b_version_id},
        headers=ALICE,
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Test 3: User Group Grantee — inactive member cannot use
# ---------------------------------------------------------------------------


async def test_user_group_grant_inactive_member_cannot_use(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Grant exists but Alice is removed from Group A; preflight and run create must reject."""
    from workspace107.infrastructure.db.tables import MembershipRow

    group_a = await _create_group(client, "Inactive Member Group A")
    group_b = await _create_group(client, "Inactive Member Group B")
    env_a = await _set_group_environment(session, client, group_a)
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")

    alice_id = await _get_user_id(client, ALICE)

    # Insert UserGroup(A) → B-resource USE Grant.
    await _insert_grant(
        session,
        grantee_kind="user_group",
        grantee_id=group_a,
        target_kind="shared_resource",
        target_id=resource_b_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    # Remove Alice from Group A (set membership status to REMOVED).
    membership = (
        await session.execute(
            select(MembershipRow).where(
                MembershipRow.user_group_id == group_a,
                MembershipRow.user_id == alice_id,
            )
        )
    ).scalar_one()
    membership.status = "removed"
    await session.commit()

    # Create a bypassed run-configuration to test preflight and run create.
    configuration_id = "rc_inactive_member"
    session.add(
        RunConfigurationRow(
            id=configuration_id,
            project_id=project["id"],
            name="bypassed",
            description="",
            working_directory=".",
            command="python main.py",
            environment_version_id=env_a,
            environment_variables={},
            input_bindings=[
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                    "source_subpath": "",
                }
            ],
            compute_plan_id="plan_cpu_quick",
            compute_request=None,
            artifact_rules=[],
        )
    )
    await session.commit()

    # Alice is no longer an active member of Group A, so the project is not visible.
    # Preflight and run-create should reject — AccessGuard already blocks at the project level.
    preflight = await client.post(
        f"/api/v1/projects/{project['id']}/runs/preflight",
        json={"run_configuration_id": configuration_id},
        headers=ALICE,
    )
    assert preflight.status_code == 404, preflight.text

    create = await client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"run_configuration_id": configuration_id},
        headers=ALICE,
    )
    assert create.status_code == 404, create.text


# ---------------------------------------------------------------------------
# Test 4: Grant target must be top-level, not version
# ---------------------------------------------------------------------------


async def test_grant_target_must_be_top_level_not_version(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """``target_kind='shared_resource_version'`` is rejected at the schema layer (422)."""
    group_b = await _create_group(client, "Schema Validation Group B")
    _, resource_b_version_id = await _create_resource_version(client, context, group_b)

    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource_version",
            "target_id": resource_b_version_id,
            "grantee": {"kind": "user", "id": "usr_someuser"},
        },
        headers=ALICE,
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Test 5: Grant does not grant management permission
# ---------------------------------------------------------------------------


async def test_grant_does_not_grant_management_permission(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """A USE Grant does not let the grantee manage (PATCH) the resource."""
    await _create_group(client, "Mgmt Group A")
    group_b = await _create_group(client, "Mgmt Group B")
    resource_b_id, _ = await _create_resource_version(client, context, group_b)

    alice_id = await _get_user_id(client, ALICE)

    # Alice owns Group B resource; create a User → B-resource USE Grant for Alice.
    # (Alice is already the owner, but the point is: even with a Grant, a non-owner
    # non-member cannot PATCH.)
    # Use the grants API to create the grant.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user", "id": alice_id},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Alice can already manage because she's the owner via group B membership.
    # To test that Grant ≠ management, we need a user who is NOT a B member.
    # Bob has no group B membership; the Grant for Alice doesn't help Bob.
    # But we can verify the API: create a grant for Bob, then Bob tries to PATCH.
    bob_id = await _get_user_id(client, BOB)

    # Create a User → B-resource USE Grant for Bob.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user", "id": bob_id},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Bob tries to PATCH the resource — must fail: a USE Grant adds no management
    # capability. Since grant-extended discovery makes the resource visible to Bob,
    # the denial surfaces as 403 rather than 404.
    response = await client.patch(
        f"/api/v1/shared-resources/{resource_b_id}",
        json={"name": "hacked by bob"},
        headers=BOB,
    )
    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Test 6: Revoke Grant blocks subsequent use
# ---------------------------------------------------------------------------


async def test_revoke_grant_blocks_subsequent_use(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """After revoking a Grant, creating a run-configuration referencing the asset → 404."""
    group_a = await _create_group(client, "Revoke Group A")
    group_b = await _create_group(client, "Revoke Group B")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    alice_id = await _get_user_id(client, ALICE)

    # Create a grant via the API.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user", "id": alice_id},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    grant_id = response.json()["id"]

    # With Grant: run-configuration creation succeeds.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "with-grant",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Revoke the grant.
    response = await client.delete(f"/api/v1/grants/{grant_id}", headers=ALICE)
    assert response.status_code == 204, response.text

    # After revoke: same request → 404.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "after-revoke",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Test 7: Same-owner use requires no grant (Issue #39 regression)
# ---------------------------------------------------------------------------


async def test_same_owner_use_requires_no_grant(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Owner-scope self-use still works without any Grant (Issue #39 regression)."""
    group_a = await _create_group(client, "Same Owner Group A")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A self-use project")
    _, resource_a_version_id = await _create_resource_version(client, context, group_a)

    # No Grant needed: same-owner use succeeds.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "same-owner",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_a_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Test 8: Ownership transfer invalidates grants issued under old owner (GR-408)
# ---------------------------------------------------------------------------


async def test_ownership_transfer_invalidates_grant(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """After asset Ownership transfers to a new Owner, grants issued under the
    old Owner no longer authorize use (GR-408).
    """
    group_a = await _create_group(client, "Transfer Group A")
    group_b = await _create_group(client, "Transfer Group B")
    group_c = await _create_group(client, "Transfer Group C")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    alice_id = await _get_user_id(client, ALICE)

    # Create a UserGroup(A) → B-resource USE Grant issued under group_b's ownership.
    await _insert_grant(
        session,
        grantee_kind="user_group",
        grantee_id=group_a,
        target_kind="shared_resource",
        target_id=resource_b_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    # With grant: run-configuration creation succeeds.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "before-transfer",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Transfer ownership of resource_b from group_b to group_c.
    from workspace107.infrastructure.db.tables import SharedResourceRow

    resource_row = (
        await session.execute(
            select(SharedResourceRow).where(SharedResourceRow.id == resource_b_id)
        )
    ).scalar_one()
    resource_row.owner_user_group_id = group_c
    resource_row.owner_user_id = None
    await session.commit()

    # After transfer: the grant issued under group_b is now invalid → 404.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "after-transfer",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Test 9: Grant to nonexistent grantee is rejected (404)
# ---------------------------------------------------------------------------


async def test_grant_to_nonexistent_grantee_rejected(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Creating a grant for a nonexistent User or UserGroup returns 404."""
    group_b = await _create_group(client, "Grantee Validation Group B")
    resource_b_id, _ = await _create_resource_version(client, context, group_b)

    # Grant to a nonexistent User.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user", "id": "usr_nonexistent0000000000001"},
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text

    # Grant to a nonexistent UserGroup.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user_group", "id": "ugp_nonexistent0000000000001"},
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Test 10: ALL grant covers current and future assets (GR-401)
# ---------------------------------------------------------------------------


async def test_all_grant_covers_current_and_future_assets(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """An ALL grant from a Grantor covers all current and future assets."""
    group_a = await _create_group(client, "ALL Grant Group A")
    group_b = await _create_group(client, "ALL Grant Group B")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    _resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    # Without grant: referencing B's resource → 404.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "no-grant",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text

    # Create an ALL grant: Group B → Group A via the Grant API.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "all",
            "target_id": "",
            "grantee": {"kind": "user_group", "id": group_a},
            "grantor": {"kind": "user_group", "id": group_b},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # With ALL grant: same resource now works.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "all-grant-existing",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Create a NEW resource under Group B — ALL grant should cover it too.
    _resource_b2_id, resource_b2_version_id = await _create_resource_version(
        client, context, group_b
    )
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "all-grant-future",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b2_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Create an environment under Group B — ALL grant should cover it too.
    env_b_id, env_b_version_id = await _create_environment_version(
        session, owner_user_group_id=group_b
    )
    response = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"environment_version_id": env_b_version_id},
        headers=ALICE,
    )
    assert response.status_code == 200, response.text
    catalog = await client.get(
        f"/api/v1/projects/{project['id']}/environments",
        headers=ALICE,
    )
    assert catalog.status_code == 200
    assert env_b_id in {environment["id"] for environment in catalog.json()}


# ---------------------------------------------------------------------------
# Test 11: New owner can re-grant after ownership transfer (GR-408)
# ---------------------------------------------------------------------------


async def test_new_owner_can_re_grant_after_transfer(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """After asset ownership transfers, the new owner can issue a fresh grant."""
    group_a = await _create_group(client, "ReGrant Group A")
    group_b = await _create_group(client, "ReGrant Group B")
    group_c = await _create_group(client, "ReGrant Group C")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    # Grant: Group B → Group A via the Grant API (grantor derived from resource owner).
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user_group", "id": group_a},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "before-transfer",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Transfer ownership: group_b → group_c.
    from workspace107.infrastructure.db.tables import SharedResourceRow

    resource_row = (
        await session.execute(
            select(SharedResourceRow).where(SharedResourceRow.id == resource_b_id)
        )
    ).scalar_one()
    resource_row.owner_user_group_id = group_c
    resource_row.owner_user_id = None
    await session.commit()

    # Old grant no longer works.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "after-transfer-old-grant",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text

    # New owner (group_c) re-grants to group_a via the Grant API.
    # Alice is an OWNER of group_c, so she has GRANT_MANAGE on the new owner.
    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user_group", "id": group_a},
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "after-transfer-regrant",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Test 12: UserGroup internal OWNER role transfer does not invalidate grants
# ---------------------------------------------------------------------------


async def test_usergroup_owner_role_transfer_preserves_grant(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Transferring the UserGroup OWNER role does not affect asset grants;
    the asset still belongs to the same UserGroup."""
    group_a = await _create_group(client, "RoleTransfer Group A")
    group_b = await _create_group(client, "RoleTransfer Group B")
    environment_version_id = await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    project = await _create_project_with_version(client, group_a, name="A project")
    resource_b_id, resource_b_version_id = await _create_resource_version(client, context, group_b)

    alice_id = await _get_user_id(client, ALICE)

    # Grant: Group B → Group A.
    await _insert_grant(
        session,
        grantee_kind="user_group",
        grantee_id=group_a,
        target_kind="shared_resource",
        target_id=resource_b_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    # Grant works.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "before-role-transfer",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    # Transfer OWNER role within Group B: Alice → Bob.
    from workspace107.domain.enums import MembershipStatus
    from workspace107.infrastructure.db.tables import MembershipRow

    # Ensure Bob exists (API call) before opening a write transaction on the
    # test session — SQLite file-level lock would otherwise block the API.
    bob_id = await _get_user_id(client, BOB)

    # Demote Alice from OWNER to ADMIN in Group B first (uq_membership_active_owner
    # allows only one active owner per group).
    alice_membership = (
        await session.execute(
            select(MembershipRow).where(
                MembershipRow.user_group_id == group_b,
                MembershipRow.user_id == alice_id,
            )
        )
    ).scalar_one()
    alice_membership.role = "admin"
    await session.flush()

    # Add Bob as the new OWNER of Group B.
    session.add(
        MembershipRow(
            id=ids.new_id("mbr"),
            user_group_id=group_b,
            user_id=bob_id,
            role="owner",
            status=MembershipStatus.ACTIVE.value,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()

    # Grant still works — asset is still owned by Group B.
    response = await client.post(
        f"/api/v1/projects/{project['id']}/run-configurations",
        json={
            "name": "after-role-transfer",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_version_id,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_b_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Test 13: ALL grant with non-empty target_id is rejected
# ---------------------------------------------------------------------------


async def test_all_grant_with_nonempty_target_id_rejected(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """ALL grant must have empty target_id; non-empty → 422."""
    group_a = await _create_group(client, "RejectAllA")
    group_b = await _create_group(client, "RejectAllB")
    await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    _resource_b_id, _ = await _create_resource_version(client, context, group_b)

    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "all",
            "target_id": "shr_should_be_empty",
            "grantee": {"kind": "user_group", "id": group_a},
            "grantor": {"kind": "user_group", "id": group_b},
        },
        headers=ALICE,
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Test 14: Explicit grantor for asset-specific grant is rejected
# ---------------------------------------------------------------------------


async def test_explicit_grantor_for_asset_grant_rejected(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Asset-specific grants must not carry an explicit grantor; it is derived
    from the target asset's current owner.  An explicit grantor → 422."""
    group_a = await _create_group(client, "RejectExplicitA")
    group_b = await _create_group(client, "RejectExplicitB")
    await _set_group_environment(session, client, group_a)
    await grant_test_entitlement(session, "alice")
    resource_b_id, _ = await _create_resource_version(client, context, group_b)

    response = await client.post(
        "/api/v1/grants",
        json={
            "target_kind": "shared_resource",
            "target_id": resource_b_id,
            "grantee": {"kind": "user_group", "id": group_a},
            "grantor": {"kind": "user_group", "id": group_a},
        },
        headers=ALICE,
    )
    assert response.status_code == 422, response.text


async def test_group_grant_matches_exact_project_owner_while_user_grant_follows_actor(
    client: httpx.AsyncClient, session: AsyncSession, context: AppContext
) -> None:
    """Qualification source does not replace authorization in a concrete Project context."""
    group_a = await _create_group(client, "Context Group A")
    group_b = await _create_group(client, "Context Grantor Group B")
    group_c = await _create_group(client, "Context Group C")
    environment_a = await _set_group_environment(session, client, group_a)
    environment_c = await _set_group_environment(session, client, group_c)
    await grant_test_entitlement(session, "alice")
    project_a = await _create_project_with_version(client, group_a, name="Context A project")
    project_c = await _create_project_with_version(client, group_c, name="Context C project")
    resource_id, resource_version_id = await _create_resource_version(client, context, group_b)
    alice_id = await _get_user_id(client, ALICE)

    await _insert_grant(
        session,
        grantee_kind="user_group",
        grantee_id=group_a,
        target_kind="shared_resource",
        target_id=resource_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )

    response = await client.post(
        f"/api/v1/projects/{project_a['id']}/run-configurations",
        json={
            "name": "group-a-authorized",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_a,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        f"/api/v1/projects/{project_c['id']}/run-configurations",
        json={
            "name": "group-c-not-authorized",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_c,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 404, response.text

    await _insert_grant(
        session,
        grantee_kind="user",
        grantee_id=alice_id,
        target_kind="shared_resource",
        target_id=resource_id,
        granted_by_id=alice_id,
        grantor_kind="user_group",
        grantor_id=group_b,
    )
    response = await client.post(
        f"/api/v1/projects/{project_c['id']}/run-configurations",
        json={
            "name": "group-c-user-authorized",
            "command": "python main.py",
            "compute_plan_id": "plan_cpu_quick",
            "environment_version_id": environment_c,
            "input_bindings": [
                {
                    "source_type": "shared_resource_version",
                    "source_id": resource_version_id,
                    "access_path": "/inputs/data",
                }
            ],
        },
        headers=ALICE,
    )
    assert response.status_code == 201, response.text
