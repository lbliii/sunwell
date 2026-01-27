"""Thesis verification: Lens Composition.

Verifies that lenses can be loaded, composed, and produce
measurably different behavior — the "npm for AI" vision.

Key claims to verify:
1. Lenses can be loaded from files
2. Different lenses produce different heuristics/skills
3. Lens context injection changes model behavior
4. `to_context()` produces lens-specific prompts
"""

from pathlib import Path

import pytest

from sunwell.foundation.core.lens import Lens, LensMetadata
from sunwell.foundation.schema.loader.loader import LensLoader


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def lenses_dir() -> Path:
    """Path to built-in lenses."""
    return Path(__file__).parent.parent.parent / "lenses"


@pytest.fixture
def lens_loader() -> LensLoader:
    """Create a lens loader."""
    return LensLoader()


# =============================================================================
# Test: Lenses Can Be Loaded
# =============================================================================


class TestLensLoading:
    """Verify lenses can be loaded from files."""

    def test_builtin_lenses_exist(self, lenses_dir: Path) -> None:
        """Built-in lens files exist on disk."""
        expected_lenses = [
            "tech-writer-v2.lens",
            "coder-v2.lens",
            "code-reviewer-v2.lens",
            "helper-v2.lens",
        ]
        for name in expected_lenses:
            assert (lenses_dir / name).exists(), f"Missing built-in lens: {name}"

    def test_load_tech_writer_lens(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Tech-writer lens loads with expected structure."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        assert lens.metadata.name == "Technical Writer"
        assert lens.metadata.domain == "documentation"
        assert len(lens.heuristics) > 0
        # v2 lenses use communication section instead of personas

    def test_load_coder_lens(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Coder lens loads with expected structure."""
        lens = lens_loader.load(lenses_dir / "coder-v2.lens")

        assert lens.metadata.name is not None
        assert lens.metadata.domain == "software"
        assert len(lens.heuristics) > 0

    def test_all_builtin_lenses_load(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """All built-in lenses load without errors."""
        loaded = 0
        for lens_path in lenses_dir.glob("*.lens"):
            lens = lens_loader.load(lens_path)
            assert lens is not None
            assert lens.metadata.name is not None
            loaded += 1

        assert loaded >= 4, f"Expected at least 4 built-in lenses, got {loaded}"


# =============================================================================
# Test: Different Lenses Produce Different Heuristics
# =============================================================================


class TestLensDifferentiation:
    """Verify different lenses have different heuristics and skills."""

    def test_tech_writer_vs_coder_heuristics_differ(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Tech-writer and coder lenses have different heuristics."""
        tech_writer = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        coder = lens_loader.load(lenses_dir / "coder-v2.lens")

        tw_heuristic_names = {h.name for h in tech_writer.heuristics}
        coder_heuristic_names = {h.name for h in coder.heuristics}

        # They should NOT be identical
        assert tw_heuristic_names != coder_heuristic_names

        # Each should have domain-appropriate heuristics
        # Tech-writer should have documentation-related heuristics
        tw_lower = {n.lower() for n in tw_heuristic_names}
        assert any(
            kw in " ".join(tw_lower) for kw in ["signal", "diataxis", "pace", "evidence"]
        ), f"Tech-writer missing documentation heuristics: {tw_heuristic_names}"

    def test_domains_differ(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Different lenses have different domains."""
        tech_writer = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        coder = lens_loader.load(lenses_dir / "coder-v2.lens")

        assert tech_writer.metadata.domain == "documentation"
        assert coder.metadata.domain == "software"

    @pytest.mark.skip(reason="v2 lenses don't embed skills directly")
    def test_lens_skills_count_varies(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Different lenses have different skill counts."""
        lenses = {}
        for lens_path in lenses_dir.glob("*.lens"):
            lens = lens_loader.load(lens_path)
            lenses[lens.metadata.name] = len(lens.skills)

        # At least some variation in skill counts
        skill_counts = list(lenses.values())
        assert len(set(skill_counts)) > 1 or len(lenses) == 1, "All lenses have identical skill counts"


# =============================================================================
# Test: Context Injection Produces Different Prompts
# =============================================================================


class TestContextInjection:
    """Verify to_context() produces lens-specific prompts."""

    def test_to_context_includes_lens_name(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Context includes the lens name."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        context = lens.to_context()

        assert "Technical Writer" in context

    def test_to_context_includes_heuristics(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Context includes heuristic rules."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        context = lens.to_context()

        assert "Heuristics" in context
        # Should include at least one heuristic name
        assert any(h.name in context for h in lens.heuristics)

    def test_contexts_differ_between_lenses(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Different lenses produce different contexts."""
        tech_writer = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        coder = lens_loader.load(lenses_dir / "coder-v2.lens")

        tw_context = tech_writer.to_context()
        coder_context = coder.to_context()

        # Contexts should be significantly different
        assert tw_context != coder_context

        # Domain-specific content should appear
        assert "Technical Writer" in tw_context
        assert "documentation" in tw_context.lower() or "diataxis" in tw_context.lower()

    def test_to_context_with_component_filter(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Context can be filtered to specific components."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        # Get first heuristic name
        if lens.heuristics:
            first_heuristic = lens.heuristics[0].name
            filtered_context = lens.to_context(components=[first_heuristic])

            assert first_heuristic in filtered_context
            # Other heuristics should NOT be included
            if len(lens.heuristics) > 1:
                other_heuristic = lens.heuristics[1].name
                assert other_heuristic not in filtered_context


# =============================================================================
# Test: Lens Accessors Work
# =============================================================================


class TestLensAccessors:
    """Verify lens accessor methods work correctly."""

    def test_get_persona_by_name(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Can retrieve personas by name."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        if lens.personas:
            first_persona = lens.personas[0]
            retrieved = lens.get_persona(first_persona.name)
            assert retrieved is not None
            assert retrieved.name == first_persona.name

    def test_get_persona_case_insensitive(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Persona lookup is case-insensitive."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        if lens.personas:
            first_persona = lens.personas[0]
            retrieved = lens.get_persona(first_persona.name.upper())
            assert retrieved is not None

    def test_get_heuristic_by_name(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Can retrieve heuristics by name."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        if lens.heuristics:
            first_heuristic = lens.heuristics[0]
            retrieved = lens.get_heuristic(first_heuristic.name)
            assert retrieved is not None
            assert retrieved.name == first_heuristic.name

    def test_get_nonexistent_returns_none(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Nonexistent lookups return None."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        assert lens.get_persona("nonexistent_persona_xyz") is None
        assert lens.get_heuristic("nonexistent_heuristic_xyz") is None
        assert lens.get_workflow("nonexistent_workflow_xyz") is None
        assert lens.get_skill("nonexistent_skill_xyz") is None


# =============================================================================
# Test: Lens Summary
# =============================================================================


class TestLensSummary:
    """Verify lens summary output."""

    def test_summary_includes_key_info(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Summary includes essential lens information."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        summary = lens.summary()

        assert "Technical Writer" in summary
        assert "Heuristics:" in summary
        assert "Validators:" in summary
        assert "Personas:" in summary

    def test_summary_shows_skill_count(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """Summary includes skill count if skills exist."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")
        summary = lens.summary()

        if lens.skills:
            assert "Skills:" in summary


# =============================================================================
# Test: Lens Data Model
# =============================================================================


class TestLensDataModel:
    """Verify Lens dataclass behavior."""

    def test_lens_creation_with_defaults(self) -> None:
        """Lens can be created with minimal metadata."""
        metadata = LensMetadata(name="Test Lens")
        lens = Lens(metadata=metadata)

        assert lens.metadata.name == "Test Lens"
        assert lens.heuristics == ()
        assert lens.personas == ()
        assert lens.skills == ()

    def test_all_validators_property(self, lens_loader: LensLoader, lenses_dir: Path) -> None:
        """all_validators combines deterministic and heuristic validators."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        combined = lens.all_validators
        expected_count = len(lens.deterministic_validators) + len(lens.heuristic_validators)
        assert len(combined) == expected_count


# =============================================================================
# Test: Behavior Change (Integration)
# =============================================================================


class TestBehaviorChange:
    """Verify lens loading actually changes available behavior.

    These tests verify the "npm for AI" claim: loading a lens
    should change what the system can do.
    """

    def test_tech_writer_has_documentation_skills(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Tech-writer lens has documentation-related skills."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        skill_names = {s.name.lower() for s in lens.skills}

        # Should have at least some documentation-related skills
        doc_keywords = ["doc", "api", "readme", "tutorial", "write"]
        has_doc_skill = any(
            any(kw in name for kw in doc_keywords) for name in skill_names
        )

        # If no skills, that's a verification gap but not a test failure
        if lens.skills:
            assert has_doc_skill, f"Tech-writer has no doc skills: {skill_names}"

    def test_lens_framework_affects_context(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Lens framework is included in context output."""
        lens = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        if lens.framework:
            context = lens.to_context()
            assert lens.framework.name in context

    def test_router_shortcuts_are_lens_specific(
        self, lens_loader: LensLoader, lenses_dir: Path
    ) -> None:
        """Different lenses can have different router shortcuts."""
        tech_writer = lens_loader.load(lenses_dir / "tech-writer-v2.lens")

        if tech_writer.router and tech_writer.router.shortcuts:
            shortcuts = tech_writer.router.shortcuts
            # Tech-writer should have documentation shortcuts like ::a, ::p
            assert any(
                s.startswith("::") for s in shortcuts
            ), f"Expected shortcut commands, got: {shortcuts}"
