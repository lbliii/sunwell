"""General domain fallback (RFC-DOMAINS).

The general domain handles goals that don't match any specific domain.
It provides basic file operations and general-purpose tools.
"""

from sunwell.domains.protocol import BaseDomain, DomainType


class GeneralDomain(BaseDomain):
    """General-purpose fallback domain.

    Used when no specific domain is detected with high confidence.
    Provides access to basic tools without domain-specific validators.
    """

    def __init__(self) -> None:
        super().__init__()
        self._domain_type = DomainType.GENERAL
        self._tools_package = "sunwell.tools.implementations"
        self._validators = []
        self._default_validator_names = frozenset()
        self._keywords = frozenset()  # No keywords - fallback only


__all__ = ["GeneralDomain"]
