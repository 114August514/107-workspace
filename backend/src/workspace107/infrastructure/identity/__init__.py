"""External authentication provider adapters."""

from .ustc_cas import LOCAL_PROVIDER, USTC_CAS_PROVIDER, USTCCASIdentityProvider

__all__ = ["LOCAL_PROVIDER", "USTC_CAS_PROVIDER", "USTCCASIdentityProvider"]
