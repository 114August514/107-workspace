import pytest

from workspace107.domain.config_scope import ConfigScope, SecretReference
from workspace107.domain.models import Variable
from workspace107.infrastructure.db.repositories import SqlRepositories
from workspace107.infrastructure.db.secret_vault import DatabaseSecretVault


@pytest.mark.asyncio
async def test_scoped_variable_repository_isolates_same_names(context, session) -> None:
    repo = SqlRepositories(session).variables
    scopes = [ConfigScope.user("student"), ConfigScope.user_group("grp"), ConfigScope.project("project")]
    for scope in scopes:
        await repo.upsert(Variable(scope=scope, name="SAME", value=scope.id))
    await session.commit()
    for scope in scopes:
        rows = await repo.list_for_scope(scope)
        assert [(item.name, item.value) for item in rows] == [("SAME", scope.id)]
    await repo.delete(scopes[0], "SAME")
    assert await repo.get(scopes[0], "SAME") is None
    assert (await repo.get(scopes[1], "SAME")).value == "grp"


@pytest.mark.asyncio
async def test_secret_vault_resolves_exact_scope_references_without_listing_values(context, session) -> None:
    vault = DatabaseSecretVault(session)
    user = ConfigScope.user("student")
    group = ConfigScope.user_group("grp")
    await vault.set_secret(user, "TOKEN", "user-secret")
    await vault.set_secret(group, "TOKEN", "group-secret")
    await session.commit()
    assert await vault.list_names(user) == {"TOKEN"}
    refs = [SecretReference(user, "TOKEN"), SecretReference(group, "TOKEN")]
    assert await vault.resolve(refs) == {refs[0]: "user-secret", refs[1]: "group-secret"}
    await vault.delete_secret(user, "TOKEN")
    assert await vault.resolve([refs[0]]) == {}
