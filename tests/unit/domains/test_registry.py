"""Tests for DomainRegistry."""

import pytest

from sunwell.domains.protocol import BaseDomain, DomainType
from sunwell.domains.registry import DomainRegistry


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Clear registry before each test."""
    DomainRegistry.clear()
    yield
    DomainRegistry.clear()


class TestDomainRegistry:
    """Tests for DomainRegistry class methods."""

    def test_register_and_get(self) -> None:
        domain = BaseDomain(_domain_type=DomainType.CODE)
        DomainRegistry.register(domain)

        retrieved = DomainRegistry.get(DomainType.CODE)
        assert retrieved is domain

    def test_get_unregistered_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            DomainRegistry.get(DomainType.WRITING)

    def test_is_registered(self) -> None:
        assert DomainRegistry.is_registered(DomainType.CODE) is False

        domain = BaseDomain(_domain_type=DomainType.CODE)
        DomainRegistry.register(domain)

        assert DomainRegistry.is_registered(DomainType.CODE) is True

    def test_get_all(self) -> None:
        d1 = BaseDomain(_domain_type=DomainType.CODE)
        d2 = BaseDomain(_domain_type=DomainType.RESEARCH)
        DomainRegistry.register(d1)
        DomainRegistry.register(d2)

        all_domains = DomainRegistry.get_all()
        # May include auto-initialized GENERAL domain
        assert len(all_domains) >= 2
        assert d1 in all_domains
        assert d2 in all_domains


class TestDomainDetection:
    """Tests for DomainRegistry.detect."""

    def test_detect_best_match(self) -> None:
        code = BaseDomain(
            _domain_type=DomainType.CODE,
            _high_conf_keywords=frozenset({"implement", "refactor"}),
        )
        research = BaseDomain(
            _domain_type=DomainType.RESEARCH,
            _high_conf_keywords=frozenset({"research", "investigate"}),
        )
        general = BaseDomain(_domain_type=DomainType.GENERAL)

        DomainRegistry.register(code)
        DomainRegistry.register(research)
        DomainRegistry.register(general)

        domain, conf = DomainRegistry.detect("implement a new feature")
        assert domain.domain_type == DomainType.CODE
        assert conf > 0.3

        domain, conf = DomainRegistry.detect("research the topic")
        assert domain.domain_type == DomainType.RESEARCH
        assert conf > 0.3

    def test_detect_fallback_to_general(self) -> None:
        code = BaseDomain(
            _domain_type=DomainType.CODE,
            _high_conf_keywords=frozenset({"implement"}),
        )
        general = BaseDomain(_domain_type=DomainType.GENERAL)

        DomainRegistry.register(code)
        DomainRegistry.register(general)

        # No keywords match, should fall back to general
        domain, conf = DomainRegistry.detect("hello world")
        assert domain.domain_type == DomainType.GENERAL
        assert conf == 0.0

    def test_detect_low_confidence_fallback(self) -> None:
        """When no domain matches well, falls back to GENERAL with 0.0 confidence."""
        general = BaseDomain(_domain_type=DomainType.GENERAL)
        DomainRegistry.register(general)

        domain, conf = DomainRegistry.detect("xyzzy gibberish")
        assert domain.domain_type == DomainType.GENERAL
        assert conf == 0.0


class TestAutoInitialization:
    """Tests for automatic domain initialization."""

    def test_auto_initializes_builtin_domains(self) -> None:
        # First access triggers initialization
        domains = DomainRegistry.get_all()

        # Should have at least CODE, RESEARCH, GENERAL
        types = {d.domain_type for d in domains}
        assert DomainType.CODE in types
        assert DomainType.RESEARCH in types
        assert DomainType.GENERAL in types
