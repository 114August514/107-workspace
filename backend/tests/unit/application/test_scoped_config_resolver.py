import pytest

from workspace107.application.access import ProjectAccess
from workspace107.application.scoped_config_resolver import ScopedConfigResolver
from workspace107.domain.config_scope import ConfigScope, SecretReference
from workspace107.domain.enums import EnvValueKind, MembershipRole
from workspace107.domain.models import Project, Variable
from workspace107.domain.ownership import OwnerKind, OwnerReference
from workspace107.domain.secrets import EnvValue


class Vars:
    def __init__(self, values):
        self.values = values

    async def get(self, scope, name):
        return self.values.get((scope, name))


class Secrets:
    def __init__(self, values):
        self.values = values

    async def list_names(self, scope):
        return {name for candidate, name in self.values if candidate == scope}


def access(kind=OwnerKind.USER):
    owner = OwnerReference(kind, "owner" if kind is OwnerKind.USER else "group")
    project = Project("project", "p", owner=owner)
    return ProjectAccess(project, MembershipRole.OWNER, owner_scope=True)


@pytest.mark.asyncio
async def test_project_variable_precedence_does_not_query_owner():
    project = ConfigScope.project("project")
    owner = ConfigScope.user("owner")
    variables = Vars(
        {
            (project, "X"): Variable(project, "X", "project"),
            (owner, "X"): Variable(owner, "X", "owner"),
        }
    )
    result = await ScopedConfigResolver(variables, Secrets(set())).resolve(
        access(), "actor", {"X": EnvValue(EnvValueKind.VARIABLE, "X")}
    )
    assert result.literals == {"X": "project"}


@pytest.mark.asyncio
async def test_owner_fallback_and_explicit_user_isolation():
    owner = ConfigScope.user("owner")
    user = ConfigScope.user("actor")
    variables = Vars(
        {
            (owner, "X"): Variable(owner, "X", "owner"),
            (user, "X"): Variable(user, "X", "user"),
        }
    )
    result = await ScopedConfigResolver(variables, Secrets(set())).resolve(
        access(),
        "actor",
        {
            "A": EnvValue(EnvValueKind.VARIABLE, "X"),
            "B": EnvValue(EnvValueKind.VARIABLE, "X", True),
        },
    )
    assert result.literals == {"A": "owner", "B": "user"}


@pytest.mark.asyncio
async def test_secret_exact_scope_and_missing_problem():
    project = ConfigScope.project("project")
    owner = ConfigScope.user("owner")
    secrets = Secrets({(project, "TOKEN"), (owner, "TOKEN")})
    result = await ScopedConfigResolver(Vars({}), secrets).resolve(
        access(), "actor", {"T": EnvValue(EnvValueKind.SECRET, "TOKEN")}
    )
    assert result.secret_refs == {"T": SecretReference(project, "TOKEN")}


@pytest.mark.asyncio
async def test_personal_owner_reference_is_not_valid_for_other_initiator():
    resolver = ScopedConfigResolver(Vars({}), Secrets(set()))
    ref = SecretReference(ConfigScope.user("owner"), "TOKEN")
    values, problems = await resolver.validate_and_resolve(access(), "other", {"T": ref})
    assert values == {}
    assert problems
