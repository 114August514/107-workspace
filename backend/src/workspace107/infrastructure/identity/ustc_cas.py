"""USTC CAS reverse-proxy identity adapter.

The adapter only parses identity assertions. Trust is established by deployment:
the backend must be reachable exclusively through a proxy that removes client-supplied
identity headers and injects authenticated values.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.models import ExternalIdentityProfile

USTC_CAS_PROVIDER = "ustc-cas"
LOCAL_PROVIDER = "local"
ALLOWED_PROVIDERS = frozenset({USTC_CAS_PROVIDER, LOCAL_PROVIDER})
USER_ID_HEADER = "X-User-ID"
USER_PROVIDER_HEADER = "X-User-Provider"
USER_NAME_HEADER = "X-User-Name"
USER_EMAIL_HEADER = "X-User-Email"


class USTCCASIdentityProvider:
    """Translate trusted proxy headers into provider-neutral identity attributes."""

    def resolve(self, headers: Mapping[str, str]) -> ExternalIdentityProfile | None:
        provider_user_id = _header(headers, USER_ID_HEADER, max_length=255)
        if provider_user_id is None:
            return None

        provider = _header(headers, USER_PROVIDER_HEADER, max_length=64, optional=True)
        if provider is None:
            return None
        provider = provider or USTC_CAS_PROVIDER
        if provider not in ALLOWED_PROVIDERS:
            return None

        display_name = _header(headers, USER_NAME_HEADER, max_length=128, optional=True)
        email = _header(headers, USER_EMAIL_HEADER, max_length=255, optional=True)
        if display_name is None or email is None:
            return None
        return ExternalIdentityProfile(
            provider=provider,
            provider_user_id=provider_user_id,
            username=provider_user_id,
            display_name=display_name or provider_user_id,
            email=email or None,
        )


def _header(
    headers: Mapping[str, str], name: str, *, max_length: int, optional: bool = False
) -> str | None:
    raw = headers.get(name)
    if raw is None or not raw.strip():
        return "" if optional else None
    value = raw.strip()
    if len(value) > max_length or not value.isprintable():
        return None
    return value
