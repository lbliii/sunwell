"""Tests for domain protocol and BaseDomain."""

import pytest

from sunwell.domains.protocol import BaseDomain, DomainType, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_passed_result(self) -> None:
        result = ValidationResult(
            passed=True,
            validator_name="test",
            message="All good",
        )
        assert result.passed is True
        assert result.validator_name == "test"
        assert result.errors == ()

    def test_failed_result_with_errors(self) -> None:
        result = ValidationResult(
            passed=False,
            validator_name="lint",
            message="2 errors",
            errors=({"line": 1, "msg": "error 1"}, {"line": 2, "msg": "error 2"}),
        )
        assert result.passed is False
        assert len(result.errors) == 2

    def test_auto_fixed_flag(self) -> None:
        result = ValidationResult(
            passed=True,
            validator_name="lint",
            message="Fixed",
            auto_fixed=True,
        )
        assert result.auto_fixed is True


class TestBaseDomainConfidence:
    """Tests for BaseDomain.detect_confidence tiered keyword scoring."""

    def test_no_keywords_returns_zero(self) -> None:
        domain = BaseDomain()
        assert domain.detect_confidence("anything") == 0.0

    def test_high_confidence_keywords(self) -> None:
        domain = BaseDomain(
            _high_conf_keywords=frozenset({"implement", "refactor"}),
        )
        # Single high-conf keyword = 0.4
        assert domain.detect_confidence("implement feature") == pytest.approx(0.4)
        # Two high-conf keywords = 0.8
        assert domain.detect_confidence("implement and refactor") == pytest.approx(0.8)

    def test_medium_confidence_keywords(self) -> None:
        domain = BaseDomain(
            _medium_conf_keywords=frozenset({"code", "function"}),
        )
        # Single medium-conf keyword = 0.25
        assert domain.detect_confidence("write code") == pytest.approx(0.25)
        # Two medium-conf keywords = 0.5
        assert domain.detect_confidence("code function") == pytest.approx(0.5)

    def test_low_confidence_keywords(self) -> None:
        domain = BaseDomain(
            _keywords=frozenset({"python", "javascript"}),
        )
        # Single low-conf keyword = 0.15
        assert domain.detect_confidence("python script") == pytest.approx(0.15)
        # Two low-conf keywords = 0.3
        assert domain.detect_confidence("python and javascript") == pytest.approx(0.3)

    def test_mixed_tiers(self) -> None:
        domain = BaseDomain(
            _high_conf_keywords=frozenset({"implement"}),
            _medium_conf_keywords=frozenset({"code"}),
            _keywords=frozenset({"implement", "code", "python"}),
        )
        # implement (0.4) + code (0.25) + python (0.15) = 0.8
        assert domain.detect_confidence("implement code in python") == pytest.approx(0.8)

    def test_caps_at_one(self) -> None:
        domain = BaseDomain(
            _high_conf_keywords=frozenset({"a", "b", "c", "d"}),
        )
        # 4 * 0.4 = 1.6, should cap at 1.0
        result = domain.detect_confidence("a b c d")
        assert result == 1.0

    def test_case_insensitive(self) -> None:
        domain = BaseDomain(
            _high_conf_keywords=frozenset({"implement"}),
        )
        assert domain.detect_confidence("IMPLEMENT feature") == pytest.approx(0.4)
        assert domain.detect_confidence("Implement Feature") == pytest.approx(0.4)

    def test_low_conf_excludes_higher_tiers(self) -> None:
        """Keywords in high/medium tiers are not double-counted in low tier."""
        domain = BaseDomain(
            _high_conf_keywords=frozenset({"implement"}),
            _medium_conf_keywords=frozenset({"code"}),
            _keywords=frozenset({"implement", "code", "python"}),
        )
        # Only python is in low-conf (implement and code excluded)
        # implement (0.4) + code (0.25) + python (0.15) = 0.8
        result = domain.detect_confidence("implement code python")
        assert result == pytest.approx(0.8)


class TestBaseDomainProperties:
    """Tests for BaseDomain property accessors."""

    def test_default_values(self) -> None:
        domain = BaseDomain()
        assert domain.domain_type == DomainType.GENERAL
        assert domain.tools_package == "sunwell.tools.implementations"
        assert domain.validators == []
        assert domain.default_validator_names == frozenset()

    def test_custom_values(self) -> None:
        domain = BaseDomain(
            _domain_type=DomainType.CODE,
            _tools_package="my.tools",
            _default_validator_names=frozenset({"lint"}),
        )
        assert domain.domain_type == DomainType.CODE
        assert domain.tools_package == "my.tools"
        assert domain.default_validator_names == frozenset({"lint"})

    def test_extract_learnings_default(self) -> None:
        domain = BaseDomain()
        assert domain.extract_learnings("any artifact") == []
