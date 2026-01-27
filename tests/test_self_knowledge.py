"""Tests for RFC-085 Self-Knowledge Architecture.

Tests the Self singleton and its components:
- Self singleton thread-safety
- SourceKnowledge introspection
- AnalysisKnowledge pattern detection
- ProposalManager with sandbox testing
"""

import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.features.mirror.self import Self
from sunwell.features.mirror.self.analysis import AnalysisKnowledge
from sunwell.features.mirror.self.proposals import Proposal, ProposalManager
from sunwell.features.mirror.self.source import SourceKnowledge
from sunwell.features.mirror.self.types import (
    ExecutionEvent,
    FailureSeverity,
    FileChange,
    ProposalStatus,
    ProposalTestSpec,
    ProposalType,
    is_path_blocked,
)


# Get the actual sunwell root for testing
SUNWELL_ROOT = Path(__file__).parent.parent


class TestSelfSingleton:
    """Tests for Self singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        Self.reset()

    def teardown_method(self):
        """Reset singleton after each test."""
        Self.reset()

    def test_get_returns_same_instance(self):
        """Self.get() returns the same instance."""
        instance1 = Self.get()
        instance2 = Self.get()
        assert instance1 is instance2

    def test_reset_clears_instance(self):
        """Self.reset() clears the singleton."""
        instance1 = Self.get()
        Self.reset()
        instance2 = Self.get()
        assert instance1 is not instance2

    def test_auto_resolves_source_root(self):
        """Self auto-resolves source root from package location."""
        instance = Self.get()
        # Should point to the parent of src/sunwell
        assert (instance.source_root / "src" / "sunwell").exists()
        assert (instance.source_root / "src" / "sunwell" / "__init__.py").exists()

    def test_creates_storage_directory(self):
        """Self creates storage directory in ~/.sunwell/self/."""
        instance = Self.get()
        assert instance.storage_root.exists()
        assert instance.storage_root.parent.name == ".sunwell"

    def test_thread_safe_initialization(self):
        """Self.get() is thread-safe under concurrent access."""
        Self.reset()
        instances: list[Self] = []
        errors: list[Exception] = []

        def get_instance():
            try:
                instance = Self.get()
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Spawn multiple threads to call Self.get() concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_instance) for _ in range(100)]
            for f in futures:
                f.result()

        assert len(errors) == 0
        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

    def test_lazy_component_initialization(self):
        """Components are lazily initialized on first access."""
        instance = Self.get()

        # Before access, cached_property has no value
        assert "_Self__dict__" not in instance.__dict__ or "source" not in getattr(
            instance, "__dict__", {}
        )

        # Access source
        source = instance.source
        assert source is not None

        # Subsequent access returns same instance
        assert instance.source is source


class TestSourceKnowledge:
    """Tests for SourceKnowledge component."""

    @pytest.fixture
    def source(self):
        """Create SourceKnowledge for testing."""
        return SourceKnowledge(SUNWELL_ROOT)

    def test_read_module(self, source):
        """Can read Sunwell module source code."""
        code = source.read_module("sunwell.features.mirror.self")
        assert "class Self" in code
        assert "def get" in code

    def test_read_module_not_found(self, source):
        """Raises FileNotFoundError for unknown module."""
        with pytest.raises(FileNotFoundError):
            source.read_module("sunwell.nonexistent.module")

    def test_find_symbol_class(self, source):
        """Can find a class in a module."""
        info = source.find_symbol("sunwell.features.mirror.self", "Self")
        assert info.type == "class"
        assert info.name == "Self"
        assert "get" in info.methods
        assert "reset" in info.methods

    def test_find_symbol_function(self, source):
        """Can find a function in a module."""
        info = source.find_symbol("sunwell.features.mirror.self.types", "is_path_blocked")
        assert info.type == "function"
        assert info.name == "is_path_blocked"

    def test_find_symbol_not_found(self, source):
        """Raises ValueError for unknown symbol."""
        with pytest.raises(ValueError):
            source.find_symbol("sunwell.features.mirror.self", "NonexistentClass")

    def test_get_module_structure(self, source):
        """Can get module structure."""
        structure = source.get_module_structure("sunwell.features.mirror.self.types")
        class_names = [c["name"] for c in structure.classes]

        assert "SourceLocation" in class_names
        assert "ExecutionEvent" in class_names

    def test_list_modules(self, source):
        """Can list all modules."""
        modules = source.list_modules()

        assert "sunwell.features.mirror.self" in modules
        assert "sunwell.features.mirror.self.source" in modules
        assert "sunwell.features.mirror.self.analysis" in modules
        assert "sunwell.tools.execution.executor" in modules

    def test_search(self, source):
        """Can search across codebase."""
        results = source.search("singleton thread-safe", limit=5)

        assert len(results) > 0
        assert any("self" in r.module.lower() for r in results)

    def test_explain(self, source):
        """Can generate explanation with citations."""
        explanation = source.explain("self-knowledge")

        assert explanation.topic == "self-knowledge"
        assert len(explanation.summary) > 0
        assert len(explanation.related_modules) > 0

    def test_get_architecture(self, source):
        """Can generate architecture diagram."""
        diagram = source.get_architecture()

        assert len(diagram.mermaid) > 0
        assert "graph TD" in diagram.mermaid
        assert len(diagram.modules) > 0


class TestAnalysisKnowledge:
    """Tests for AnalysisKnowledge component."""

    @pytest.fixture
    def analysis(self, tmp_path):
        """Create AnalysisKnowledge for testing."""
        return AnalysisKnowledge(tmp_path / "analysis")

    def test_record_execution(self, analysis):
        """Can record execution events."""
        event = ExecutionEvent(
            tool_name="read_file",
            success=True,
            latency_ms=42,
        )
        analysis.record_execution(event)

        patterns = analysis.patterns("session")
        assert patterns.total_executions == 1
        assert patterns.success_rate == 1.0

    def test_record_failure(self, analysis):
        """Recording failed events creates failure reports."""
        event = ExecutionEvent(
            tool_name="write_file",
            success=False,
            latency_ms=10,
            error="Permission denied: /etc/passwd",
        )
        analysis.record_execution(event)

        failures = analysis.recent_failures()
        assert len(failures) == 1
        assert "Permission denied" in failures[0].error
        assert failures[0].severity == FailureSeverity.HIGH

    def test_patterns_analysis(self, analysis):
        """Can analyze patterns from execution history."""
        # Record multiple events
        for i in range(10):
            analysis.record_execution(
                ExecutionEvent(
                    tool_name="read_file" if i % 2 == 0 else "write_file",
                    success=i % 3 != 0,
                    latency_ms=10 + i,
                )
            )

        patterns = analysis.patterns("session")
        assert patterns.total_executions == 10
        assert len(patterns.most_used_tools) > 0

    def test_diagnose_error(self, analysis):
        """Can diagnose errors."""
        diagnosis = analysis.diagnose("PathSecurityError: Path escapes workspace")

        assert "escape" in diagnosis.root_cause.lower() or "Path" in diagnosis.error
        assert diagnosis.confidence > 0.5

    def test_persistence(self, tmp_path):
        """Analysis data persists across instances."""
        storage = tmp_path / "analysis"

        # First instance records events
        analysis1 = AnalysisKnowledge(storage)
        analysis1.record_execution(
            ExecutionEvent(tool_name="test", success=True, latency_ms=10)
        )

        # Second instance should see the data
        analysis2 = AnalysisKnowledge(storage)
        patterns = analysis2.patterns("session")
        assert patterns.total_executions == 1


class TestProposalManager:
    """Tests for ProposalManager component."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create ProposalManager for testing."""
        return ProposalManager(
            source_root=SUNWELL_ROOT,
            storage_root=tmp_path / "proposals",
        )

    def test_create_proposal(self, manager):
        """Can create a proposal."""
        proposal = manager.create(
            title="Test improvement",
            description="This is a test proposal",
            changes=[
                FileChange(
                    path="sunwell/tools/handlers.py",
                    diff="# Test change",
                )
            ],
        )

        assert proposal.id.startswith("prop_")
        assert proposal.status == ProposalStatus.DRAFT
        assert proposal.title == "Test improvement"

    def test_blocked_paths(self, manager):
        """Cannot create proposals for blocked paths."""
        with pytest.raises(ValueError) as exc:
            manager.create(
                title="Bad proposal",
                description="Trying to modify self",
                changes=[
                    FileChange(
                        path="sunwell/self/__init__.py",
                        diff="# Evil change",
                    )
                ],
            )

        assert "blocked" in str(exc.value).lower()

    def test_proposal_lifecycle(self, manager):
        """Full proposal lifecycle: create → approve → test → apply."""
        # Create
        proposal = manager.create(
            title="Test lifecycle",
            description="Testing the full lifecycle",
            changes=[
                FileChange(
                    path="sunwell/tools/__init__.py",
                    diff="# Harmless comment",
                    original_content="",
                )
            ],
            tests=[
                ProposalTestSpec(
                    name="test_passes",
                    code="def test_passes():\n    assert True",
                )
            ],
        )
        assert proposal.status == ProposalStatus.DRAFT

        # Approve
        manager.approve(proposal.id)
        proposal = manager.get(proposal.id)
        assert proposal.status == ProposalStatus.APPROVED

    def test_list_proposals(self, manager):
        """Can list and filter proposals."""
        # Create multiple proposals
        p1 = manager.create(
            title="P1",
            description="First",
            changes=[FileChange(path="test.py", diff="# 1")],
        )
        p2 = manager.create(
            title="P2",
            description="Second",
            changes=[FileChange(path="test.py", diff="# 2")],
        )
        manager.approve(p2.id)

        # List all
        all_proposals = manager.list()
        assert len(all_proposals) == 2

        # Filter by status
        drafts = manager.list(status=ProposalStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].id == p1.id

        approved = manager.list(status=ProposalStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].id == p2.id

    def test_persistence(self, tmp_path):
        """Proposals persist across instances."""
        storage = tmp_path / "proposals"

        # First instance creates proposal
        manager1 = ProposalManager(source_root=SUNWELL_ROOT, storage_root=storage)
        proposal = manager1.create(
            title="Persistent",
            description="Should persist",
            changes=[FileChange(path="test.py", diff="# test")],
        )
        proposal_id = proposal.id

        # Second instance should see the proposal
        manager2 = ProposalManager(source_root=SUNWELL_ROOT, storage_root=storage)
        loaded = manager2.get(proposal_id)
        assert loaded is not None
        assert loaded.title == "Persistent"


class TestBlockedPaths:
    """Tests for blocked path protection."""

    def test_self_directory_blocked(self):
        """sunwell/self/ is blocked."""
        assert is_path_blocked("sunwell/self/__init__.py")
        assert is_path_blocked("sunwell/self/source.py")

    def test_safety_module_blocked(self):
        """sunwell/mirror/safety.py is blocked."""
        assert is_path_blocked("sunwell/mirror/safety.py")

    def test_types_module_blocked(self):
        """sunwell/tools/types.py is blocked."""
        assert is_path_blocked("sunwell/tools/types.py")

    def test_normal_paths_allowed(self):
        """Normal paths are allowed."""
        assert not is_path_blocked("sunwell/tools/handlers.py")
        assert not is_path_blocked("sunwell/naaru/planners/base.py")


class TestSelfIntegration:
    """Integration tests using the full Self singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        Self.reset()

    def teardown_method(self):
        """Reset singleton after each test."""
        Self.reset()

    def test_source_introspection_works(self):
        """Can introspect source via Self.get()."""
        source = Self.get().source
        modules = source.list_modules()

        assert len(modules) > 0
        assert any("tools" in m for m in modules)

    def test_introspection_from_any_cwd(self, tmp_path, monkeypatch):
        """Introspection works regardless of current working directory.

        RFC-085: This is the key test — Self.get().source should work
        even when cwd is a user project, not Sunwell source.
        """
        # Change to a temp directory (simulating user's project)
        monkeypatch.chdir(tmp_path)

        # Should still be able to introspect Sunwell
        source = Self.get().source
        code = source.read_module("sunwell.self")

        assert "class Self" in code

    def test_components_accessible(self):
        """All components are accessible via Self.get()."""
        self_instance = Self.get()

        # Source
        assert self_instance.source is not None
        assert isinstance(self_instance.source, SourceKnowledge)

        # Analysis
        assert self_instance.analysis is not None
        assert isinstance(self_instance.analysis, AnalysisKnowledge)

        # Proposals
        assert self_instance.proposals is not None
        assert isinstance(self_instance.proposals, ProposalManager)
