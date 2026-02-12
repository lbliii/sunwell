"""Query expansion with synonym maps for Phase 4: Optimization.

Improves recall by expanding queries with synonyms, without requiring an LLM.

Part of Hindsight-inspired memory enhancements.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Built-in synonym map (no LLM required)
# Maps terms to their synonyms/related terms
BUILT_IN_SYNONYMS = {
    # Authentication & Authorization
    "auth": ["authentication", "login", "signin", "sign-in"],
    "authentication": ["auth", "login", "credential", "identity"],
    "login": ["signin", "sign-in", "authentication", "auth"],
    "logout": ["signout", "sign-out"],
    "permission": ["authorization", "access", "privilege"],
    "authorization": ["permission", "access", "privilege"],
    # Database
    "db": ["database", "datastore", "persistence"],
    "database": ["db", "datastore", "storage"],
    "sql": ["query", "database"],
    "query": ["search", "find", "select"],
    "table": ["relation", "entity"],
    "column": ["field", "attribute"],
    "row": ["record", "tuple"],
    # API & Web
    "api": ["endpoint", "service", "interface"],
    "endpoint": ["route", "api", "service"],
    "rest": ["api", "http", "restful"],
    "http": ["web", "request", "api"],
    "request": ["call", "query", "fetch"],
    "response": ["result", "output", "reply"],
    "json": ["data", "payload"],
    # Programming Concepts
    "function": ["method", "procedure", "routine"],
    "method": ["function", "procedure"],
    "class": ["object", "type", "entity"],
    "object": ["instance", "class"],
    "variable": ["var", "field", "property"],
    "parameter": ["param", "argument", "arg"],
    "argument": ["param", "parameter", "arg"],
    "return": ["output", "result"],
    # Error Handling
    "error": ["exception", "failure", "bug"],
    "exception": ["error", "failure"],
    "bug": ["error", "issue", "defect"],
    "fail": ["error", "crash", "break"],
    # Data Structures
    "array": ["list", "collection", "sequence"],
    "list": ["array", "collection", "sequence"],
    "dict": ["dictionary", "map", "hash"],
    "dictionary": ["dict", "map", "hash"],
    "map": ["dictionary", "dict", "hash"],
    "set": ["collection", "group"],
    "queue": ["buffer", "stack"],
    # Testing
    "test": ["unittest", "spec", "check"],
    "unittest": ["test", "spec"],
    "mock": ["stub", "fake", "dummy"],
    "assert": ["check", "verify", "validate"],
    # Frontend
    "ui": ["interface", "frontend", "gui"],
    "interface": ["ui", "frontend", "gui"],
    "frontend": ["ui", "client", "interface"],
    "component": ["widget", "element", "module"],
    "render": ["display", "show", "draw"],
    # Backend
    "backend": ["server", "service", "api"],
    "server": ["backend", "service", "host"],
    "service": ["api", "backend", "server"],
    # State Management
    "state": ["data", "store", "model"],
    "store": ["state", "data", "cache"],
    "cache": ["store", "buffer", "memory"],
    # Configuration
    "config": ["configuration", "settings", "options"],
    "configuration": ["config", "settings", "options"],
    "settings": ["config", "configuration", "options"],
    "option": ["setting", "parameter", "flag"],
    # File Operations
    "file": ["document", "data", "resource"],
    "directory": ["folder", "dir", "path"],
    "folder": ["directory", "dir"],
    "path": ["location", "directory", "route"],
    # Common Abbreviations
    "impl": ["implementation", "implement"],
    "implementation": ["impl", "code"],
    "docs": ["documentation", "doc"],
    "documentation": ["docs", "doc"],
    "repo": ["repository", "codebase"],
    "repository": ["repo", "codebase"],
    "env": ["environment", "config"],
    "environment": ["env", "context"],
    # Technologies (expanded from entity extractor)
    "react": ["reactjs", "react.js"],
    "reactjs": ["react", "react.js"],
    "python": ["py", "python3"],
    "py": ["python", "python3"],
    "javascript": ["js", "node"],
    "js": ["javascript", "node"],
    "typescript": ["ts", "javascript"],
    "ts": ["typescript", "javascript"],
    "docker": ["container", "containerization"],
    "kubernetes": ["k8s", "orchestration"],
    "k8s": ["kubernetes", "orchestration"],
    "postgres": ["postgresql", "database"],
    "postgresql": ["postgres", "database"],
    "mongo": ["mongodb", "database"],
    "mongodb": ["mongo", "database"],
}


class QueryExpander:
    """Expands queries with synonyms for better recall.

    Uses built-in synonym map (no LLM required) and optionally
    user-defined synonyms from config.
    """

    def __init__(
        self,
        user_synonyms: dict[str, list[str]] | None = None,
        user_synonyms_path: Path | None = None,
    ):
        """Initialize query expander.

        Args:
            user_synonyms: Optional user-defined synonym map
            user_synonyms_path: Optional path to user synonyms JSON file
        """
        self._synonyms = dict(BUILT_IN_SYNONYMS)

        # Load user-defined synonyms
        if user_synonyms:
            self._merge_synonyms(user_synonyms)

        if user_synonyms_path and user_synonyms_path.exists():
            try:
                with open(user_synonyms_path) as f:
                    user_syns = json.load(f)
                    self._merge_synonyms(user_syns)
                logger.info(f"Loaded user synonyms from {user_synonyms_path}")
            except Exception as e:
                logger.warning(f"Failed to load user synonyms: {e}")

    def _merge_synonyms(self, user_synonyms: dict[str, list[str]]) -> None:
        """Merge user synonyms into built-in map.

        Args:
            user_synonyms: User-defined synonym map
        """
        for term, synonyms in user_synonyms.items():
            term_lower = term.lower()
            if term_lower in self._synonyms:
                # Merge with existing
                existing = set(self._synonyms[term_lower])
                existing.update(syn.lower() for syn in synonyms)
                self._synonyms[term_lower] = list(existing)
            else:
                # Add new
                self._synonyms[term_lower] = [syn.lower() for syn in synonyms]

    def expand(
        self,
        query: str,
        max_expansions: int = 3,
        include_original: bool = True,
    ) -> list[str]:
        """Expand query with synonyms.

        Args:
            query: Original query string
            max_expansions: Maximum synonyms per term
            include_original: Include original query in results

        Returns:
            List of query variants (original + expanded)
        """
        # Tokenize query
        terms = query.lower().split()

        # Generate expanded variants
        variants = []

        if include_original:
            variants.append(query)

        # For each term, try to expand with synonyms
        expanded_terms_sets = []
        for term in terms:
            if term in self._synonyms:
                # Add term + top N synonyms
                synonyms = self._synonyms[term][:max_expansions]
                expanded_terms_sets.append([term] + synonyms)
            else:
                expanded_terms_sets.append([term])

        # Generate variants by combining synonyms
        # For simplicity, just create a few key combinations
        if len(expanded_terms_sets) > 0:
            # Strategy 1: Replace each term one at a time
            for i, term_variants in enumerate(expanded_terms_sets):
                for variant in term_variants[1:]:  # Skip original
                    new_terms = terms.copy()
                    new_terms[i] = variant
                    variants.append(" ".join(new_terms))

        # Remove duplicates and limit
        unique_variants = []
        seen = set()
        for variant in variants:
            if variant not in seen:
                unique_variants.append(variant)
                seen.add(variant)

        return unique_variants[:10]  # Limit to 10 variants

    def expand_single_term(self, term: str) -> list[str]:
        """Expand a single term with its synonyms.

        Args:
            term: Term to expand

        Returns:
            List of [term] + synonyms
        """
        term_lower = term.lower()
        if term_lower in self._synonyms:
            return [term_lower] + self._synonyms[term_lower]
        return [term_lower]

    def has_synonyms(self, term: str) -> bool:
        """Check if a term has synonyms.

        Args:
            term: Term to check

        Returns:
            True if synonyms exist, False otherwise
        """
        return term.lower() in self._synonyms

    def get_synonyms(self, term: str) -> list[str]:
        """Get synonyms for a term.

        Args:
            term: Term to get synonyms for

        Returns:
            List of synonyms (empty if none)
        """
        return self._synonyms.get(term.lower(), [])

    def stats(self) -> dict:
        """Get expander statistics.

        Returns:
            Dict with stats
        """
        return {
            "total_terms": len(self._synonyms),
            "total_synonyms": sum(len(syns) for syns in self._synonyms.values()),
            "avg_synonyms_per_term": round(
                sum(len(syns) for syns in self._synonyms.values()) / len(self._synonyms),
                2,
            ) if self._synonyms else 0,
        }


# Factory function
def create_query_expander(
    workspace: Path | None = None,
    user_synonyms: dict[str, list[str]] | None = None,
) -> QueryExpander:
    """Create a query expander.

    Args:
        workspace: Optional workspace path (looks for .sunwell/config/synonyms.json)
        user_synonyms: Optional user-defined synonyms

    Returns:
        QueryExpander instance
    """
    user_synonyms_path = None
    if workspace:
        user_synonyms_path = Path(workspace) / ".sunwell" / "config" / "synonyms.json"

    return QueryExpander(
        user_synonyms=user_synonyms,
        user_synonyms_path=user_synonyms_path,
    )
