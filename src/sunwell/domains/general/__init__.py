"""General domain fallback (RFC-DOMAINS).

The general domain handles goals that don't match any specific domain.
It provides basic file operations and general-purpose tools.
"""

from sunwell.domains.protocol import BaseDomain, DomainType, DomainValidator


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

    @property
    def domain_type(self) -> DomainType:
        return self._domain_type

    @property
    def tools_package(self) -> str:
        return self._tools_package

    @property
    def validators(self) -> list[DomainValidator]:
        return self._validators

    @property
    def default_validator_names(self) -> frozenset[str]:
        return self._default_validator_names

    def detect_confidence(self, goal: str) -> float:
        """General domain never matches proactively."""
        return 0.0

    def extract_learnings(self, artifact: str, file_path: str | None = None) -> list:
        """No domain-specific learning extraction."""
        return []


__all__ = ["GeneralDomain"]
