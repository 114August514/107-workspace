from workspace107.infrastructure.identity.ustc_cas import (
    LOCAL_PROVIDER,
    USTC_CAS_PROVIDER,
    USTCCASIdentityProvider,
)


def test_missing_user_id_is_not_an_identity() -> None:
    assert USTCCASIdentityProvider().resolve({}) is None


def test_cas_headers_default_to_ustc_provider() -> None:
    profile = USTCCASIdentityProvider().resolve({"X-User-ID": "20260001"})
    assert profile is not None
    assert profile.provider == USTC_CAS_PROVIDER
    assert profile.provider_user_id == "20260001"


def test_local_provider_header_is_distinct_from_cas() -> None:
    profile = USTCCASIdentityProvider().resolve(
        {"X-User-ID": "platform-admin", "X-User-Provider": "local", "X-User-Name": "平台管理员"}
    )
    assert profile is not None
    assert profile.provider == LOCAL_PROVIDER
    assert profile.display_name == "平台管理员"


def test_unknown_provider_is_rejected() -> None:
    assert (
        USTCCASIdentityProvider().resolve({"X-User-ID": "anyone", "X-User-Provider": "github"})
        is None
    )
