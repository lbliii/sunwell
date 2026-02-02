"""Domain registry for multi-purpose agents (RFC-DOMAINS).

Provides domain detection and lookup functionality.
"""

import logging
from typing import TYPE_CHECKING

from sunwell.domains.protocol import DomainType

if TYPE_CHECKING:
    from sunwell.domains.protocol import Domain

logger = logging.getLogger(__name__)


class DomainRegistry:
    """Registry for domain modules.

    Singleton registry that:
    - Registers domain implementations
    - Detects best domain for a goal
    - Provides domain lookup by type

    Usage:
        # Register domains at startup
        DomainRegistry.register(CodeDomain())
        DomainRegistry.register(ResearchDomain())

        # Detect domain from goal
        domain, confidence = DomainRegistry.detect("Build a REST API")
        # → (CodeDomain, 0.9)

        # Direct lookup
        code_domain = DomainRegistry.get(DomainType.CODE)
    """

    _domains: dict[DomainType, Domain] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, domain: Domain) -> None:
        """Register a domain implementation.

        Args:
            domain: Domain instance to register
        """
        cls._domains[domain.domain_type] = domain
        logger.debug("Registered domain: %s", domain.domain_type.value)

    @classmethod
    def detect(cls, goal: str) -> tuple[Domain, float]:
        """Detect best domain for goal with confidence.

        Calls detect_confidence() on all registered domains and
        returns the one with highest confidence.

        Args:
            goal: The user's goal/task description

        Returns:
            Tuple of (best_domain, confidence_score)
            Falls back to GENERAL domain if no good match
        """
        cls._ensure_initialized()

        best: Domain | None = None
        best_conf = 0.0

        for domain in cls._domains.values():
            conf = domain.detect_confidence(goal)
            if conf > best_conf:
                best, best_conf = domain, conf

        # Fallback to GENERAL if no confident match
        if best is None or best_conf < 0.1:
            general = cls._domains.get(DomainType.GENERAL)
            if general:
                return general, 0.0
            # Emergency fallback: return first registered domain
            if cls._domains:
                first = next(iter(cls._domains.values()))
                return first, 0.0
            msg = "No domains registered"
            raise RuntimeError(msg)

        logger.debug(
            "Detected domain %s with confidence %.2f for goal: %s",
            best.domain_type.value,
            best_conf,
            goal[:50],
        )
        return best, best_conf

    @classmethod
    def get(cls, domain_type: DomainType) -> Domain:
        """Get domain by type.

        Args:
            domain_type: The domain type to retrieve

        Returns:
            The registered domain

        Raises:
            KeyError: If domain type not registered
        """
        cls._ensure_initialized()

        if domain_type not in cls._domains:
            available = [d.value for d in cls._domains]
            msg = f"Domain {domain_type.value} not registered. Available: {available}"
            raise KeyError(msg)

        return cls._domains[domain_type]

    @classmethod
    def get_all(cls) -> list[Domain]:
        """Get all registered domains.

        Returns:
            List of all registered domain instances
        """
        cls._ensure_initialized()
        return list(cls._domains.values())

    @classmethod
    def is_registered(cls, domain_type: DomainType) -> bool:
        """Check if a domain type is registered.

        Args:
            domain_type: The domain type to check

        Returns:
            True if registered, False otherwise
        """
        return domain_type in cls._domains

    @classmethod
    def clear(cls) -> None:
        """Clear all registered domains (for testing)."""
        cls._domains.clear()
        cls._initialized = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure default domains are registered.

        Called automatically on first access. Registers built-in
        domains if not already initialized.
        """
        if cls._initialized:
            return

        cls._initialized = True

        # Import and register built-in domains
        # Deferred import to avoid circular dependencies
        try:
            from sunwell.domains.code import CodeDomain

            if DomainType.CODE not in cls._domains:
                cls.register(CodeDomain())
        except ImportError:
            logger.debug("Code domain not available")

        try:
            from sunwell.domains.research import ResearchDomain

            if DomainType.RESEARCH not in cls._domains:
                cls.register(ResearchDomain())
        except ImportError:
            logger.debug("Research domain not available")

        try:
            from sunwell.domains.general import GeneralDomain

            if DomainType.GENERAL not in cls._domains:
                cls.register(GeneralDomain())
        except ImportError:
            # Create minimal general domain as fallback
            from sunwell.domains.protocol import BaseDomain

            general = BaseDomain(
                _domain_type=DomainType.GENERAL,
                _tools_package="sunwell.tools.implementations",
            )
            cls.register(general)  # type: ignore[arg-type]
            logger.debug("Using minimal general domain fallback")
