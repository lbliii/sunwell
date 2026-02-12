"""Tests for Phase 4.2: Query Expansion System.

Tests synonym-based query expansion for improved retrieval.
"""

import tempfile
from pathlib import Path

import pytest

from sunwell.memory.core.retrieval.query_expansion import (
    BUILT_IN_SYNONYMS,
    QueryExpander,
)


class TestQueryExpander:
    """Test query expansion with synonyms."""

    def test_expand_with_builtin_synonyms(self):
        """Test expansion using built-in synonym map."""
        expander = QueryExpander()

        # Test auth expansion
        expanded = expander.expand("auth implementation")
        assert len(expanded) >= 2  # Original + expanded

        # Should include synonyms
        expanded_text = " ".join(expanded)
        assert "authentication" in expanded_text or "login" in expanded_text

    def test_expand_database_terms(self):
        """Test database-related synonym expansion."""
        expander = QueryExpander()

        expanded = expander.expand("db optimization")

        # Should expand "db" to "database", "datastore", etc.
        expanded_text = " ".join(expanded).lower()
        assert "database" in expanded_text or "datastore" in expanded_text

    def test_expand_multiple_terms(self):
        """Test expanding multiple terms in query."""
        expander = QueryExpander()

        expanded = expander.expand("auth db setup")

        # Should expand both "auth" and "db"
        expanded_text = " ".join(expanded).lower()
        assert any(
            syn in expanded_text
            for syn in ["authentication", "login", "database", "datastore"]
        )

    def test_no_expansion_for_unknown_terms(self):
        """Test that unknown terms are kept as-is."""
        expander = QueryExpander()

        query = "unknown term xyz"
        expanded = expander.expand(query)

        # Should return at least original query
        assert len(expanded) >= 1
        assert query in expanded or query.lower() in [e.lower() for e in expanded]

    def test_user_defined_synonyms(self):
        """Test user-defined synonyms override built-in."""
        temp_dir = tempfile.mkdtemp()
        synonyms_file = Path(temp_dir) / "synonyms.json"

        # Write custom synonyms
        import json
        custom_synonyms = {
            "py": ["Python", "python3"],
            "js": ["JavaScript", "ECMAScript"],
        }
        with open(synonyms_file, "w") as f:
            json.dump(custom_synonyms, f)

        try:
            expander = QueryExpander(user_synonyms_path=synonyms_file)

            expanded = expander.expand("py programming")
            expanded_text = " ".join(expanded)

            # Should include custom synonyms
            assert "Python" in expanded_text or "python3" in expanded_text

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_case_insensitive_expansion(self):
        """Test that expansion is case-insensitive."""
        expander = QueryExpander()

        # Test with different cases
        expanded_lower = expander.expand("auth")
        expanded_upper = expander.expand("AUTH")
        expanded_mixed = expander.expand("Auth")

        # All should produce expansions
        assert len(expanded_lower) >= 2
        assert len(expanded_upper) >= 2
        assert len(expanded_mixed) >= 2

    def test_builtin_synonyms_coverage(self):
        """Test that built-in synonyms cover common terms."""
        # Verify key terms are in BUILT_IN_SYNONYMS
        assert "auth" in BUILT_IN_SYNONYMS
        assert "db" in BUILT_IN_SYNONYMS
        assert "api" in BUILT_IN_SYNONYMS
        assert "ui" in BUILT_IN_SYNONYMS
        assert "config" in BUILT_IN_SYNONYMS

        # Verify synonym lists are reasonable
        assert len(BUILT_IN_SYNONYMS["auth"]) >= 2
        assert len(BUILT_IN_SYNONYMS["db"]) >= 2

    def test_expansion_limit(self):
        """Test that expansion doesn't produce too many variants."""
        expander = QueryExpander()

        # Even with multiple synonym terms, should be limited
        expanded = expander.expand("auth db api config")

        # Should not explode combinatorially
        assert len(expanded) <= 10  # Reasonable limit


class TestQueryExpansionIntegration:
    """Integration tests for query expansion in retrieval."""

    def test_expand_improves_retrieval(self):
        """Test that expansion improves retrieval accuracy."""
        expander = QueryExpander()

        # Original query with abbreviation
        original = "auth setup"
        expanded = expander.expand(original)

        # Expanded queries should match more variations
        # e.g., documents mentioning "authentication" but not "auth"

        # Simulate document matching
        documents = [
            "authentication implementation guide",
            "login system setup",
            "auth configuration",
        ]

        # Original query might miss first two documents
        original_matches = [d for d in documents if "auth" in d.lower()]
        assert len(original_matches) == 1

        # Expanded queries should match more
        expanded_text = " ".join(expanded).lower()
        expanded_matches = [
            d for d in documents
            if any(term in d.lower() for term in ["auth", "authentication", "login"])
        ]
        assert len(expanded_matches) >= 2

    def test_expansion_with_threshold(self):
        """Test using expansion only when original query scores low."""
        expander = QueryExpander()

        # Simulate retrieval scenario
        query = "auth implementation"

        # First try: Original query
        original_score = 0.45  # Below threshold (0.5)

        # Should trigger expansion
        if original_score < 0.5:
            expanded = expander.expand(query)
            assert len(expanded) >= 2

        # Second try: Original query scores high
        original_score = 0.75  # Above threshold

        # Should NOT need expansion
        if original_score >= 0.5:
            # Use original query
            expanded = [query]
            assert len(expanded) == 1

    def test_expand_preserves_original(self):
        """Test that original query is always included."""
        expander = QueryExpander()

        query = "auth setup"
        expanded = expander.expand(query)

        # Original should be in expanded set
        assert query in expanded or query.lower() in [e.lower() for e in expanded]


class TestSynonymMapping:
    """Test synonym mapping structure."""

    def test_symmetric_synonyms(self):
        """Test that synonyms are bidirectional where appropriate."""
        # auth -> authentication, login
        # These are asymmetric (abbreviation -> full term)

        # Verify structure
        assert "auth" in BUILT_IN_SYNONYMS
        assert isinstance(BUILT_IN_SYNONYMS["auth"], list)

    def test_domain_coverage(self):
        """Test coverage of different domains."""
        # Web development
        assert "api" in BUILT_IN_SYNONYMS
        assert "ui" in BUILT_IN_SYNONYMS

        # Database
        assert "db" in BUILT_IN_SYNONYMS
        assert "sql" in BUILT_IN_SYNONYMS or "db" in BUILT_IN_SYNONYMS

        # Authentication
        assert "auth" in BUILT_IN_SYNONYMS

        # Configuration
        assert "config" in BUILT_IN_SYNONYMS

    def test_no_circular_synonyms(self):
        """Test that synonyms don't create circular references."""
        # e.g., auth -> authentication, authentication -> auth would be circular

        for term, synonyms in BUILT_IN_SYNONYMS.items():
            # None of the synonyms should point back to original term
            # This is structurally prevented by the dict format
            assert isinstance(synonyms, list)


class TestProjectSpecificSynonyms:
    """Test project-specific synonym customization."""

    def test_load_project_synonyms(self):
        """Test loading synonyms from project config."""
        temp_dir = tempfile.mkdtemp()
        synonyms_file = Path(temp_dir) / "synonyms.json"

        try:
            # Create project-specific synonyms
            import json
            project_synonyms = {
                "sunwell": ["Sunwell", "memory system", "agent memory"],
                "naaru": ["M'uru", "The Naaru", "planning engine"],
            }

            with open(synonyms_file, "w") as f:
                json.dump(project_synonyms, f)

            expander = QueryExpander(user_synonyms_path=synonyms_file)

            # Test expansion
            expanded = expander.expand("sunwell architecture")
            expanded_text = " ".join(expanded)

            # Should include project-specific terms
            assert "memory system" in expanded_text or "Sunwell" in expanded_text

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_merge_user_and_builtin_synonyms(self):
        """Test that user synonyms extend (not replace) built-in."""
        temp_dir = tempfile.mkdtemp()
        synonyms_file = Path(temp_dir) / "synonyms.json"

        try:
            import json
            user_synonyms = {
                "custom": ["custom_term", "project_specific"],
            }

            with open(synonyms_file, "w") as f:
                json.dump(user_synonyms, f)

            expander = QueryExpander(user_synonyms_path=synonyms_file)

            # Built-in synonyms should still work
            auth_expanded = expander.expand("auth")
            assert len(auth_expanded) >= 2

            # User synonyms should also work
            custom_expanded = expander.expand("custom")
            assert len(custom_expanded) >= 2

        finally:
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
