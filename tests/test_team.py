"""Tests for Team Intelligence - RFC-052.

Tests team knowledge store, conflict resolution, propagation, and onboarding.
"""

from datetime import datetime
from pathlib import Path

import pytest

from sunwell.team import (
    ConflictResolver,
    KnowledgeConflict,
    OnboardingSummary,
    RejectedOption,
    TeamConfig,
    TeamDecision,
    TeamFailure,
    TeamKnowledgeStore,
    TeamOnboarding,
    TeamOwnership,
    TeamPatterns,
    UnifiedIntelligence,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def team_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for team knowledge."""
    (tmp_path / ".sunwell" / "team").mkdir(parents=True)
    # Initialize git repo for git operations
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


@pytest.fixture
def store(team_dir: Path) -> TeamKnowledgeStore:
    """Create a TeamKnowledgeStore instance."""
    return TeamKnowledgeStore(team_dir)


@pytest.fixture
def sample_decision() -> TeamDecision:
    """Create a sample team decision."""
    return TeamDecision(
        id="test123",
        category="database",
        question="Which database should we use?",
        choice="PostgreSQL",
        rejected=(
            RejectedOption(
                option="MySQL",
                reason="Licensing concerns",
                might_reconsider_when="If licensing changes",
            ),
            RejectedOption(
                option="SQLite",
                reason="Not suitable for production scale",
            ),
        ),
        rationale="Better scalability and JSONB support",
        confidence=0.9,
        author="alice@example.com",
        timestamp=datetime.now(),
        endorsements=("bob@example.com",),
        tags=("infrastructure", "backend"),
    )


@pytest.fixture
def sample_failure() -> TeamFailure:
    """Create a sample team failure."""
    return TeamFailure(
        id="fail123",
        description="Redis caching with connection pooling",
        error_type="runtime_error",
        root_cause="Connection exhaustion under load",
        prevention="Use connection limits and circuit breaker",
        author="carol@example.com",
        timestamp=datetime.now(),
        occurrences=3,
        affected_files=("src/cache.py", "src/api/endpoints.py"),
    )


# =============================================================================
# TYPES TESTS
# =============================================================================


class TestTeamDecision:
    """Tests for TeamDecision type."""

    def test_to_dict(self, sample_decision: TeamDecision) -> None:
        """Test serialization to dict."""
        data = sample_decision.to_dict()

        assert data["id"] == "test123"
        assert data["category"] == "database"
        assert data["choice"] == "PostgreSQL"
        assert len(data["rejected"]) == 2
        assert data["confidence"] == 0.9
        assert data["author"] == "alice@example.com"
        assert "bob@example.com" in data["endorsements"]

    def test_from_dict(self, sample_decision: TeamDecision) -> None:
        """Test deserialization from dict."""
        data = sample_decision.to_dict()
        restored = TeamDecision.from_dict(data)

        assert restored.id == sample_decision.id
        assert restored.category == sample_decision.category
        assert restored.choice == sample_decision.choice
        assert len(restored.rejected) == len(sample_decision.rejected)
        assert restored.confidence == sample_decision.confidence

    def test_to_text(self, sample_decision: TeamDecision) -> None:
        """Test text conversion for embedding."""
        text = sample_decision.to_text()

        assert "database" in text.lower()
        assert "PostgreSQL" in text
        assert "MySQL" in text
        assert "alice@example.com" in text


class TestTeamFailure:
    """Tests for TeamFailure type."""

    def test_to_dict(self, sample_failure: TeamFailure) -> None:
        """Test serialization to dict."""
        data = sample_failure.to_dict()

        assert data["id"] == "fail123"
        assert data["error_type"] == "runtime_error"
        assert data["occurrences"] == 3
        assert len(data["affected_files"]) == 2

    def test_from_dict(self, sample_failure: TeamFailure) -> None:
        """Test deserialization from dict."""
        data = sample_failure.to_dict()
        restored = TeamFailure.from_dict(data)

        assert restored.id == sample_failure.id
        assert restored.occurrences == sample_failure.occurrences


class TestTeamPatterns:
    """Tests for TeamPatterns type."""

    def test_defaults(self) -> None:
        """Test default values."""
        patterns = TeamPatterns()

        assert patterns.import_style == "absolute"
        assert patterns.docstring_style == "google"
        assert patterns.enforcement_level == "suggest"

    def test_to_dict_from_dict(self) -> None:
        """Test round-trip serialization."""
        patterns = TeamPatterns(
            naming_conventions={"function": "snake_case"},
            import_style="relative",
            enforcement_level="warn",
        )
        data = patterns.to_dict()
        restored = TeamPatterns.from_dict(data)

        assert restored.naming_conventions == patterns.naming_conventions
        assert restored.import_style == patterns.import_style
        assert restored.enforcement_level == patterns.enforcement_level


class TestTeamOwnership:
    """Tests for TeamOwnership type."""

    def test_to_dict_from_dict(self) -> None:
        """Test round-trip serialization."""
        ownership = TeamOwnership(
            owners={"src/billing/*": ["alice", "bob"]},
            expertise={"alice": ["billing", "payments"]},
            required_reviewers={"src/billing/*": ["alice"]},
        )
        data = ownership.to_dict()
        restored = TeamOwnership.from_dict(data)

        assert restored.owners == ownership.owners
        assert restored.expertise == ownership.expertise


# =============================================================================
# STORE TESTS
# =============================================================================


class TestTeamKnowledgeStore:
    """Tests for TeamKnowledgeStore."""

    @pytest.mark.asyncio
    async def test_record_decision(
        self,
        store: TeamKnowledgeStore,
        sample_decision: TeamDecision,
    ) -> None:
        """Test recording a decision."""
        await store.record_decision(sample_decision, auto_commit=False)

        decisions = await store.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].choice == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_create_decision(self, store: TeamKnowledgeStore) -> None:
        """Test creating a decision via helper method."""
        decision = await store.create_decision(
            category="auth",
            question="Which auth method?",
            choice="OAuth 2.0",
            rationale="Enterprise SSO support",
            author="test@example.com",
            rejected=[("JWT", "No SSO support")],
            auto_commit=False,
        )

        assert decision.category == "auth"
        assert decision.choice == "OAuth 2.0"
        assert len(decision.rejected) == 1

        # Verify persisted
        decisions = await store.get_decisions()
        assert len(decisions) == 1

    @pytest.mark.asyncio
    async def test_get_decisions_by_category(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test filtering decisions by category."""
        await store.create_decision(
            category="database",
            question="Q1",
            choice="A1",
            rationale="R1",
            author="test@example.com",
            auto_commit=False,
        )
        await store.create_decision(
            category="auth",
            question="Q2",
            choice="A2",
            rationale="R2",
            author="test@example.com",
            auto_commit=False,
        )

        db_decisions = await store.get_decisions(category="database")
        assert len(db_decisions) == 1
        assert db_decisions[0].category == "database"

        auth_decisions = await store.get_decisions(category="auth")
        assert len(auth_decisions) == 1
        assert auth_decisions[0].category == "auth"

    @pytest.mark.asyncio
    async def test_find_relevant_decisions(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test keyword-based decision search."""
        await store.create_decision(
            category="database",
            question="Which database for user data?",
            choice="PostgreSQL",
            rationale="JSONB support",
            author="test@example.com",
            auto_commit=False,
        )
        await store.create_decision(
            category="cache",
            question="Which caching strategy?",
            choice="LRU",
            rationale="Simple and effective",
            author="test@example.com",
            auto_commit=False,
        )

        # Search for database-related
        results = await store.find_relevant_decisions("database postgresql")
        assert len(results) >= 1
        assert results[0].category == "database"

    @pytest.mark.asyncio
    async def test_check_contradiction(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test contradiction detection."""
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="test@example.com",
            rejected=[("MySQL", "Licensing")],
            auto_commit=False,
        )

        # Check if MySQL contradicts
        conflict = await store.check_contradiction("MySQL database", "database")
        assert conflict is not None
        assert conflict.choice == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_endorse_decision(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test adding endorsement."""
        decision = await store.create_decision(
            category="database",
            question="Q1",
            choice="A1",
            rationale="R1",
            author="alice@example.com",
            auto_commit=False,
        )

        updated = await store.endorse_decision(
            decision.id,
            "bob@example.com",
            auto_commit=False,
        )

        assert updated is not None
        assert "bob@example.com" in updated.endorsements
        assert updated.confidence > decision.confidence

    @pytest.mark.asyncio
    async def test_record_failure(
        self,
        store: TeamKnowledgeStore,
        sample_failure: TeamFailure,
    ) -> None:
        """Test recording a failure."""
        await store.record_failure(sample_failure, auto_commit=False)

        failures = await store.get_failures()
        assert len(failures) == 1
        assert failures[0].description == sample_failure.description

    @pytest.mark.asyncio
    async def test_failure_occurrence_increment(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test that similar failures increment occurrence count."""
        failure1 = await store.create_failure(
            description="Redis connection issue",
            error_type="runtime_error",
            root_cause="Connection pool exhaustion",
            prevention="Use connection limits",
            author="alice@example.com",
            auto_commit=False,
        )

        # Record similar failure
        similar = TeamFailure(
            id="different_id",
            description="Redis connection issue",  # Same description
            error_type="runtime_error",
            root_cause="Same issue",
            prevention="Same fix",
            author="bob@example.com",
            timestamp=datetime.now(),
        )
        await store.record_failure(similar, auto_commit=False)

        failures = await store.get_failures()
        # Should be deduplicated
        assert len(failures) >= 1
        # First one should have incremented count
        redis_failure = [f for f in failures if "Redis" in f.description][0]
        assert redis_failure.occurrences >= 2

    @pytest.mark.asyncio
    async def test_patterns(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test patterns CRUD."""
        patterns = TeamPatterns(
            naming_conventions={"function": "snake_case"},
            docstring_style="numpy",
            enforcement_level="warn",
        )

        await store.update_patterns(patterns, auto_commit=False)

        loaded = await store.get_patterns()
        assert loaded.docstring_style == "numpy"
        assert loaded.enforcement_level == "warn"

    @pytest.mark.asyncio
    async def test_ownership(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test ownership CRUD."""
        ownership = TeamOwnership(
            owners={"src/billing/*": ["alice"]},
            expertise={"alice": ["billing"]},
        )

        await store.update_ownership(ownership, auto_commit=False)

        loaded = await store.get_ownership()
        assert "src/billing/*" in loaded.owners

    @pytest.mark.asyncio
    async def test_get_owners(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test getting owners for a file path."""
        ownership = TeamOwnership(
            owners={"src/billing/*": ["alice", "bob"]},
        )
        await store.update_ownership(ownership, auto_commit=False)

        owners = await store.get_owners(Path("src/billing/invoice.py"))
        assert "alice" in owners
        assert "bob" in owners

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test statistics gathering."""
        await store.create_decision(
            category="database",
            question="Q1",
            choice="A1",
            rationale="R1",
            author="test@example.com",
            auto_commit=False,
        )
        await store.create_failure(
            description="Test failure",
            error_type="test",
            root_cause="test",
            prevention="test",
            author="test@example.com",
            auto_commit=False,
        )

        stats = await store.get_stats()
        assert stats["total_decisions"] == 1
        assert stats["total_failures"] == 1


# =============================================================================
# CONFLICT RESOLUTION TESTS
# =============================================================================


class TestConflictResolver:
    """Tests for ConflictResolver."""

    @pytest.fixture
    def resolver(self, store: TeamKnowledgeStore) -> ConflictResolver:
        """Create a ConflictResolver instance."""
        return ConflictResolver(store)

    @pytest.mark.asyncio
    async def test_resolve_same_decision_merges_endorsements(
        self,
        resolver: ConflictResolver,
    ) -> None:
        """Test that same decisions merge endorsements."""
        local = TeamDecision(
            id="d1",
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rejected=(),
            rationale="R1",
            confidence=0.8,
            author="alice@example.com",
            timestamp=datetime.now(),
            endorsements=("alice@example.com",),
        )
        remote = TeamDecision(
            id="d2",
            category="database",
            question="Which database?",
            choice="PostgreSQL",  # Same choice
            rejected=(),
            rationale="R2",
            confidence=0.85,
            author="bob@example.com",
            timestamp=datetime.now(),
            endorsements=("bob@example.com",),
        )

        result = await resolver.resolve_decision_conflict(local, remote)

        assert isinstance(result, TeamDecision)
        assert "alice@example.com" in result.endorsements
        assert "bob@example.com" in result.endorsements

    @pytest.mark.asyncio
    async def test_resolve_different_choices_creates_conflict(
        self,
        resolver: ConflictResolver,
    ) -> None:
        """Test that different choices create a conflict."""
        local = TeamDecision(
            id="d1",
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rejected=(),
            rationale="R1",
            confidence=0.8,
            author="alice@example.com",
            timestamp=datetime.now(),
        )
        remote = TeamDecision(
            id="d2",
            category="database",
            question="Which database?",
            choice="MySQL",  # Different choice
            rejected=(),
            rationale="R2",
            confidence=0.8,
            author="bob@example.com",
            timestamp=datetime.now(),
        )

        result = await resolver.resolve_decision_conflict(local, remote)

        assert isinstance(result, KnowledgeConflict)
        assert result.type == "decision_contradiction"
        assert "PostgreSQL" in (result.local_version or "")
        assert "MySQL" in (result.remote_version or "")


# =============================================================================
# UNIFIED INTELLIGENCE TESTS
# =============================================================================


class TestUnifiedIntelligence:
    """Tests for UnifiedIntelligence."""

    @pytest.fixture
    def unified(self, store: TeamKnowledgeStore) -> UnifiedIntelligence:
        """Create a UnifiedIntelligence instance."""
        return UnifiedIntelligence(team_store=store)

    @pytest.mark.asyncio
    async def test_find_relevant_decision(
        self,
        unified: UnifiedIntelligence,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test finding relevant decisions."""
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="test@example.com",
            auto_commit=False,
        )

        decision = await unified.find_relevant_decision("database")
        assert decision is not None
        assert decision.choice == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_check_approach_with_failure(
        self,
        unified: UnifiedIntelligence,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test checking approach against failures."""
        await store.create_failure(
            description="Redis caching approach",
            error_type="runtime_error",
            root_cause="Connection issues",
            prevention="Use connection pooling",
            author="test@example.com",
            auto_commit=False,
        )

        check = await unified.check_approach("use Redis caching")
        assert not check.safe
        assert len(check.warnings) > 0

    @pytest.mark.asyncio
    async def test_get_team_summary(
        self,
        unified: UnifiedIntelligence,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test getting team summary."""
        await store.create_decision(
            category="database",
            question="Q1",
            choice="A1",
            rationale="R1",
            author="alice@example.com",
            auto_commit=False,
        )

        summary = await unified.get_team_summary()
        assert summary["decisions"]["total"] == 1
        assert "database" in summary["decisions"]["by_category"]


# =============================================================================
# ONBOARDING TESTS
# =============================================================================


class TestTeamOnboarding:
    """Tests for TeamOnboarding."""

    @pytest.fixture
    def onboarding(self, store: TeamKnowledgeStore) -> TeamOnboarding:
        """Create a TeamOnboarding instance."""
        return TeamOnboarding(store)

    @pytest.mark.asyncio
    async def test_generate_summary(
        self,
        onboarding: TeamOnboarding,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test generating onboarding summary."""
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="alice@example.com",
            auto_commit=False,
        )
        await store.create_failure(
            description="Test failure",
            error_type="test",
            root_cause="Test",
            prevention="Test",
            author="bob@example.com",
            auto_commit=False,
        )

        summary = await onboarding.generate_onboarding_summary()

        assert summary.total_decisions == 1
        assert "database" in summary.decisions_by_category
        assert len(summary.critical_failures) == 1
        assert "alice@example.com" in summary.top_contributors

    @pytest.mark.asyncio
    async def test_format_welcome_message(
        self,
        onboarding: TeamOnboarding,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test welcome message formatting."""
        await store.create_decision(
            category="auth",
            question="Auth method?",
            choice="OAuth",
            rationale="SSO support",
            author="alice@example.com",
            auto_commit=False,
        )

        summary = await onboarding.generate_onboarding_summary()
        message = summary.format_welcome_message()

        assert "Welcome" in message
        assert "1 recorded" in message
        assert "auth" in message

    @pytest.mark.asyncio
    async def test_get_quick_tips(
        self,
        onboarding: TeamOnboarding,
        store: TeamKnowledgeStore,
    ) -> None:
        """Test getting quick tips."""
        patterns = TeamPatterns(docstring_style="google")
        await store.update_patterns(patterns, auto_commit=False)

        tips = await onboarding.get_quick_tips()
        assert any("google" in tip.lower() for tip in tips)


# =============================================================================
# CONFIG TESTS
# =============================================================================


class TestTeamConfig:
    """Tests for TeamConfig."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = TeamConfig()

        assert config.enabled is True
        assert config.sync.auto_commit is True
        assert config.sync.auto_push is False
        assert config.enforcement.patterns == "warn"

    def test_from_dict(self) -> None:
        """Test loading from dictionary."""
        data = {
            "enabled": True,
            "sync": {"auto_push": True},
            "enforcement": {"patterns": "enforce"},
        }
        config = TeamConfig.from_dict(data)

        assert config.sync.auto_push is True
        assert config.enforcement.patterns == "enforce"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        config = TeamConfig()
        data = config.to_dict()

        assert "enabled" in data
        assert "sync" in data
        assert data["sync"]["auto_commit"] is True
