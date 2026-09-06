import pytest

from workspace107.domain.config_scope import ConfigScope, SecretReference
from workspace107.domain.errors import ValidationFailed


def test_secret_reference_is_scope_qualified() -> None:
    ref = SecretReference(ConfigScope.user_group("g"), "TOKEN")
    assert ref.as_key() == "user_group:g:TOKEN"


@pytest.mark.parametrize(
    "value", ["", "user", "wat:id:NAME", "user:id:", "user:id:bad-name", "user:id:NAME:extra"]
)
def test_secret_reference_rejects_malformed_keys(value: str) -> None:
    with pytest.raises(ValidationFailed):
        SecretReference.from_key(value)


def test_secret_reference_rejects_delimiter_ambiguity() -> None:
    with pytest.raises(ValidationFailed):
        SecretReference(ConfigScope.user("u:other"), "TOKEN").as_key()


def test_secret_reference_rejects_invalid_name_on_serialization() -> None:
    with pytest.raises(ValidationFailed):
        SecretReference(ConfigScope.user("u"), "foo-bar").as_key()
