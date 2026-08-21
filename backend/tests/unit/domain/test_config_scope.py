from workspace107.domain.config_scope import ConfigScope, ConfigScopeKind, SecretReference


def test_scope_identity_covers_all_supported_scopes() -> None:
    assert ConfigScope.user("u").kind is ConfigScopeKind.USER
    assert ConfigScope.user_group("g").kind is ConfigScopeKind.USER_GROUP
    assert ConfigScope.project("p").kind is ConfigScopeKind.PROJECT


def test_secret_reference_is_scope_qualified() -> None:
    ref = SecretReference(ConfigScope.user_group("g"), "TOKEN")
    assert ref.as_key() == "user_group:g:TOKEN"
