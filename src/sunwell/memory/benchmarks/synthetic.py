"""Synthetic benchmark scenarios for Phase 4.

Creates test scenarios with known ground truth for measuring
retrieval accuracy and performance.

Part of Hindsight-inspired memory enhancements.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.turn import Learning


@dataclass(slots=True)
class BenchmarkScenario:
    """A benchmark scenario with queries and ground truth."""

    name: str
    """Scenario name."""

    description: str
    """What this scenario tests."""

    learnings: list[Learning]
    """Learnings to populate memory with."""

    test_cases: list[tuple[str, list[str]]]
    """List of (query, expected_learning_ids) tuples."""


def create_authentication_scenario() -> BenchmarkScenario:
    """Create authentication-themed benchmark scenario.

    Returns:
        BenchmarkScenario
    """
    from sunwell.memory.simulacrum.core.turn import Learning

    learnings = [
        Learning(
            id="auth_1",
            fact="Use JWT tokens for authentication in the API",
            category="constraint",
            confidence=0.9,
        ),
        Learning(
            id="auth_2",
            fact="Never store passwords in plain text",
            category="constraint",
            confidence=1.0,
        ),
        Learning(
            id="auth_3",
            fact="Use bcrypt for password hashing",
            category="pattern",
            confidence=0.85,
        ),
        Learning(
            id="auth_4",
            fact="Implement rate limiting on login endpoints",
            category="constraint",
            confidence=0.8,
        ),
        Learning(
            id="auth_5",
            fact="OAuth 2.0 is preferred for third-party authentication",
            category="preference",
            confidence=0.75,
        ),
        # Noise learnings (unrelated)
        Learning(
            id="noise_1",
            fact="Use React hooks for state management",
            category="pattern",
            confidence=0.9,
        ),
        Learning(
            id="noise_2",
            fact="Database queries should be indexed",
            category="constraint",
            confidence=0.85,
        ),
    ]

    test_cases = [
        # Exact keyword match
        ("JWT authentication", ["auth_1", "auth_5"]),
        # Synonym match
        ("login security", ["auth_2", "auth_3", "auth_4"]),
        # Constraint retrieval
        ("password storage", ["auth_2", "auth_3"]),
        # Pattern retrieval
        ("authentication patterns", ["auth_3", "auth_5"]),
    ]

    return BenchmarkScenario(
        name="authentication",
        description="Tests retrieval of authentication-related learnings",
        learnings=learnings,
        test_cases=test_cases,
    )


def create_database_scenario() -> BenchmarkScenario:
    """Create database-themed benchmark scenario.

    Returns:
        BenchmarkScenario
    """
    from sunwell.memory.simulacrum.core.turn import Learning

    learnings = [
        Learning(
            id="db_1",
            fact="Use PostgreSQL for relational data",
            category="preference",
            confidence=0.9,
        ),
        Learning(
            id="db_2",
            fact="Add indexes on foreign key columns",
            category="constraint",
            confidence=0.95,
        ),
        Learning(
            id="db_3",
            fact="Use connection pooling for better performance",
            category="pattern",
            confidence=0.85,
        ),
        Learning(
            id="db_4",
            fact="Never run migrations in production without backup",
            category="constraint",
            confidence=1.0,
        ),
        Learning(
            id="db_5",
            fact="Use transactions for multi-step operations",
            category="pattern",
            confidence=0.9,
        ),
        # Noise
        Learning(
            id="noise_3",
            fact="Use TypeScript for type safety",
            category="preference",
            confidence=0.8,
        ),
    ]

    test_cases = [
        ("database choice", ["db_1"]),
        ("query performance", ["db_2", "db_3"]),
        ("database safety", ["db_4", "db_5"]),
        ("postgresql setup", ["db_1", "db_2", "db_3"]),
    ]

    return BenchmarkScenario(
        name="database",
        description="Tests retrieval of database-related learnings",
        learnings=learnings,
        test_cases=test_cases,
    )


def create_react_scenario() -> BenchmarkScenario:
    """Create React-themed benchmark scenario.

    Returns:
        BenchmarkScenario
    """
    from sunwell.memory.simulacrum.core.turn import Learning

    learnings = [
        Learning(
            id="react_1",
            fact="Use hooks for state management in functional components",
            category="pattern",
            confidence=0.95,
        ),
        Learning(
            id="react_2",
            fact="Don't use global state in components",
            category="constraint",
            confidence=0.9,
        ),
        Learning(
            id="react_3",
            fact="Avoid side effects in render functions",
            category="constraint",
            confidence=0.95,
        ),
        Learning(
            id="react_4",
            fact="Use useCallback for memoizing functions",
            category="pattern",
            confidence=0.8,
        ),
        Learning(
            id="react_5",
            fact="Components should be pure functions of props and state",
            category="constraint",
            confidence=1.0,
        ),
        # Noise
        Learning(
            id="noise_4",
            fact="Use SQLAlchemy for database ORM",
            category="preference",
            confidence=0.85,
        ),
    ]

    test_cases = [
        ("react state", ["react_1", "react_2", "react_5"]),
        ("functional components", ["react_1", "react_3", "react_5"]),
        ("react performance", ["react_4", "react_1"]),
        ("react constraints", ["react_2", "react_3", "react_5"]),
    ]

    return BenchmarkScenario(
        name="react",
        description="Tests retrieval of React-related learnings",
        learnings=learnings,
        test_cases=test_cases,
    )


def create_performance_scenario() -> BenchmarkScenario:
    """Create large-scale performance benchmark scenario.

    Returns:
        BenchmarkScenario with 1000+ learnings
    """
    from sunwell.memory.simulacrum.core.turn import Learning

    learnings = []

    # Create 100 categories with 10 learnings each
    for category_idx in range(100):
        category_name = f"category_{category_idx}"
        for learning_idx in range(10):
            learnings.append(
                Learning(
                    id=f"{category_name}_{learning_idx}",
                    fact=f"Learning about {category_name} item {learning_idx}",
                    category="fact",
                    confidence=0.8,
                )
            )

    # Add some high-value learnings
    for i in range(10):
        learnings.append(
            Learning(
                id=f"important_{i}",
                fact=f"Critical constraint for system {i}",
                category="constraint",
                confidence=1.0,
            )
        )

    test_cases = [
        (f"category_{i}", [f"category_{i}_{j}" for j in range(5)])
        for i in range(10)
    ]
    test_cases.extend([
        ("critical constraint", [f"important_{i}" for i in range(5)]),
        ("system requirements", [f"important_{i}" for i in range(5)]),
    ])

    return BenchmarkScenario(
        name="performance",
        description="Tests retrieval performance with 1000+ learnings",
        learnings=learnings,
        test_cases=test_cases,
    )


# All scenarios
ALL_SCENARIOS = [
    create_authentication_scenario,
    create_database_scenario,
    create_react_scenario,
    create_performance_scenario,
]


def get_scenario(name: str) -> BenchmarkScenario:
    """Get a scenario by name.

    Args:
        name: Scenario name

    Returns:
        BenchmarkScenario

    Raises:
        ValueError: If scenario not found
    """
    scenarios = {
        "authentication": create_authentication_scenario,
        "database": create_database_scenario,
        "react": create_react_scenario,
        "performance": create_performance_scenario,
    }

    if name not in scenarios:
        raise ValueError(f"Unknown scenario: {name}")

    return scenarios[name]()


def get_all_scenarios() -> list[BenchmarkScenario]:
    """Get all benchmark scenarios.

    Returns:
        List of BenchmarkScenario
    """
    return [create_fn() for create_fn in ALL_SCENARIOS]
