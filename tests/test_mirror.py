"""Tests for RFC-015 Mirror Neurons."""

from pathlib import Path
import pytest
import tempfile
import json

from sunwell.mirror.introspection import (
    SourceIntrospector,
    LensIntrospector,
    SimulacrumIntrospector,
    ExecutionIntrospector,
)
from sunwell.mirror.analysis import PatternAnalyzer, FailureAnalyzer
from sunwell.mirror.proposals import Proposal, ProposalStatus, ProposalType, ProposalManager
from sunwell.mirror.safety import SafetyChecker, validate_diff_safety, DANGEROUS_PATTERNS
from sunwell.mirror.handler import MirrorHandler


# Get the actual sunwell root
SUNWELL_ROOT = Path(__file__).parent.parent


class TestSourceIntrospector:
    """Tests for source code introspection."""
    
    def test_get_module_source(self):
        """Can read Sunwell's own source code."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        # Should be able to read the mirror module
        source = introspector.get_module_source("sunwell.mirror.introspection")
        assert "class SourceIntrospector" in source
        assert "def get_module_source" in source
    
    def test_find_symbol_class(self):
        """Can find a class in a module."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        result = introspector.find_symbol("sunwell.mirror.introspection", "SourceIntrospector")
        assert result["type"] == "class"
        assert result["docstring"] is not None
        assert "get_module_source" in result["methods"]
    
    def test_find_symbol_function(self):
        """Can find a function in a module."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        result = introspector.find_symbol("sunwell.mirror.safety", "validate_diff_safety")
        assert result["type"] == "function"
        assert result["docstring"] is not None
    
    def test_get_module_structure(self):
        """Can get the structure of a module."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        structure = introspector.get_module_structure("sunwell.mirror.analysis")
        assert "PatternAnalyzer" in [c["name"] for c in structure["classes"]]
        assert "FailureAnalyzer" in [c["name"] for c in structure["classes"]]
    
    def test_list_modules(self):
        """Can list all available modules."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        modules = introspector.list_modules()
        assert "sunwell.mirror.introspection" in modules
        assert "sunwell.tools.executor" in modules
    
    def test_module_not_found(self):
        """Raises FileNotFoundError for unknown modules."""
        introspector = SourceIntrospector(SUNWELL_ROOT)
        
        with pytest.raises(FileNotFoundError):
            introspector.get_module_source("sunwell.nonexistent.module")


class TestPatternAnalyzer:
    """Tests for pattern analysis."""
    
    def test_analyze_tool_usage_empty(self):
        """Handles empty audit log."""
        analyzer = PatternAnalyzer()
        result = analyzer.analyze_tool_usage([], "session")
        
        assert result["tool_counts"] == {}
        assert result["total_calls"] == 0
    
    def test_analyze_tool_usage(self):
        """Analyzes tool usage patterns."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class MockEntry:
            tool_name: str
            success: bool
            execution_time_ms: int
            timestamp: datetime
            error: str | None = None
        
        entries = [
            MockEntry("read_file", True, 10, datetime.now()),
            MockEntry("read_file", True, 15, datetime.now()),
            MockEntry("write_file", True, 20, datetime.now()),
            MockEntry("read_file", False, 5, datetime.now(), "Not found"),
        ]
        
        analyzer = PatternAnalyzer()
        result = analyzer.analyze_tool_usage(entries, "session")
        
        assert result["tool_counts"]["read_file"] == 3
        assert result["tool_counts"]["write_file"] == 1
        assert result["success_rates"]["write_file"] == 1.0
        assert result["success_rates"]["read_file"] == pytest.approx(0.67, rel=0.1)
    
    def test_analyze_latency(self):
        """Analyzes latency patterns."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class MockEntry:
            tool_name: str
            success: bool
            execution_time_ms: int
            timestamp: datetime
        
        entries = [
            MockEntry("read_file", True, 10, datetime.now()),
            MockEntry("read_file", True, 20, datetime.now()),
            MockEntry("read_file", True, 30, datetime.now()),
        ]
        
        analyzer = PatternAnalyzer()
        result = analyzer.analyze_latency(entries, "session")
        
        assert result["overall"]["avg_ms"] == 20.0
        assert result["overall"]["min_ms"] == 10
        assert result["overall"]["max_ms"] == 30


class TestFailureAnalyzer:
    """Tests for failure analysis."""
    
    def test_analyze_permission_error(self):
        """Recognizes permission errors."""
        analyzer = FailureAnalyzer()
        result = analyzer.analyze("Permission denied: /etc/passwd")
        
        assert result["category"] == "security"
        assert result["confidence"] == 0.9
    
    def test_analyze_not_found_error(self):
        """Recognizes not found errors."""
        analyzer = FailureAnalyzer()
        result = analyzer.analyze("File not found: config.yaml")
        
        assert result["category"] == "file_system"
    
    def test_analyze_unknown_error(self):
        """Handles unknown errors gracefully."""
        analyzer = FailureAnalyzer()
        result = analyzer.analyze("Something weird happened")
        
        assert result["category"] == "unknown"
        assert result["confidence"] == 0.3


class TestProposalManager:
    """Tests for proposal management."""
    
    def test_create_proposal(self, tmp_path):
        """Can create a proposal."""
        manager = ProposalManager(tmp_path)
        
        proposal = manager.create_proposal(
            proposal_type="heuristic",
            title="Add brevity check",
            rationale="Responses are too verbose",
            evidence=["Session avg 847 tokens"],
            diff="+ brevity_check: true",
        )
        
        assert proposal.id.startswith("prop_")
        assert proposal.status == ProposalStatus.DRAFT
        assert proposal.type == ProposalType.HEURISTIC
    
    def test_proposal_workflow(self, tmp_path):
        """Full proposal workflow: create → submit → approve → apply."""
        manager = ProposalManager(tmp_path)
        
        # Create
        proposal = manager.create_proposal(
            proposal_type="config",
            title="Test proposal",
            rationale="Testing",
            evidence=["test"],
            diff="test diff",
        )
        assert proposal.status == ProposalStatus.DRAFT
        
        # Submit
        proposal = manager.submit_for_review(proposal.id)
        assert proposal.status == ProposalStatus.PENDING_REVIEW
        
        # Approve
        proposal = manager.approve_proposal(proposal.id)
        assert proposal.status == ProposalStatus.APPROVED
        
        # Apply
        proposal = manager.apply_proposal(proposal.id, "rollback data")
        assert proposal.status == ProposalStatus.APPLIED
        assert proposal.applied_at is not None
        
        # Rollback
        rollback = manager.rollback_proposal(proposal.id)
        assert rollback == "rollback data"
        
        # Verify status
        proposal = manager.get_proposal(proposal.id)
        assert proposal.status == ProposalStatus.ROLLED_BACK
    
    def test_list_proposals(self, tmp_path):
        """Can list and filter proposals."""
        manager = ProposalManager(tmp_path)
        
        # Create some proposals
        p1 = manager.create_proposal("heuristic", "H1", "R1", [], "d1")
        p2 = manager.create_proposal("validator", "V1", "R2", [], "d2")
        manager.submit_for_review(p2.id)
        
        # List all
        all_proposals = manager.list_proposals()
        assert len(all_proposals) == 2
        
        # Filter by status
        drafts = manager.list_proposals(status=ProposalStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].id == p1.id
        
        pending = manager.list_proposals(status=ProposalStatus.PENDING_REVIEW)
        assert len(pending) == 1
        assert pending[0].id == p2.id


class TestSafetyChecker:
    """Tests for safety constraints."""
    
    def test_validate_safe_diff(self):
        """Accepts safe diffs."""
        is_safe, reason = validate_diff_safety("+ new_heuristic: check_length")
        assert is_safe
        assert reason == "OK"
    
    def test_block_dangerous_patterns(self):
        """Blocks dangerous patterns."""
        for pattern in ["eval(", "exec(", "__import__", "os.system"]:
            is_safe, reason = validate_diff_safety(f"code = {pattern}something)")
            assert not is_safe
            assert "Dangerous pattern" in reason
    
    def test_block_trust_modifications(self):
        """Blocks trust level modifications."""
        is_safe, reason = validate_diff_safety("trust_level = FULL")
        assert not is_safe
        # Caught by DANGEROUS_PATTERNS which checks first
        assert "trust_level" in reason
    
    def test_block_safety_policy_modifications(self):
        """Blocks safety policy modifications."""
        is_safe, reason = validate_diff_safety("safety_policy.max_applications = 999")
        assert not is_safe
    
    def test_rate_limiting(self, tmp_path):
        """Enforces rate limits."""
        checker = SafetyChecker()
        checker.policy.max_proposals_per_hour = 2
        
        # First two should pass
        assert checker._check_proposal_rate()
        assert checker._check_proposal_rate()
        
        # Third should fail
        assert not checker._check_proposal_rate()
    
    def test_requires_confirmation(self):
        """Identifies operations requiring confirmation."""
        checker = SafetyChecker()
        
        assert checker.requires_confirmation("apply_proposal")
        assert checker.requires_confirmation("rollback_proposal")
        assert not checker.requires_confirmation("list_proposals")


class TestMirrorHandler:
    """Integration tests for the mirror handler."""
    
    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        return MirrorHandler(
            workspace=SUNWELL_ROOT,  # RFC-085: renamed from sunwell_root
            storage_path=tmp_path,
        )
    
    @pytest.mark.asyncio
    async def test_introspect_source(self, handler):
        """Can introspect source code via handler."""
        result = await handler.handle("introspect_source", {
            "module": "sunwell.mirror.tools",
        })
        
        data = json.loads(result)
        assert "error" not in data
        assert "structure" in data
        assert data["module"] == "sunwell.mirror.tools"
    
    @pytest.mark.asyncio
    async def test_introspect_source_with_symbol(self, handler):
        """Can find specific symbol."""
        result = await handler.handle("introspect_source", {
            "module": "sunwell.mirror.safety",
            "symbol": "SafetyChecker",
        })
        
        data = json.loads(result)
        assert "error" not in data
        assert data["type"] == "class"
        assert data["symbol"] == "SafetyChecker"
    
    @pytest.mark.asyncio
    async def test_propose_and_list(self, handler):
        """Can create and list proposals."""
        # Create
        result = await handler.handle("propose_improvement", {
            "scope": "heuristic",
            "problem": "Test problem",
            "evidence": ["Evidence 1"],
            "diff": "+ test: true",
        })
        
        data = json.loads(result)
        assert "error" not in data
        assert "proposal_id" in data
        
        # List
        result = await handler.handle("list_proposals", {"status": "draft"})
        data = json.loads(result)
        assert data["count"] >= 1
    
    @pytest.mark.asyncio
    async def test_blocks_dangerous_proposal(self, handler):
        """Rejects proposals with dangerous patterns."""
        result = await handler.handle("propose_improvement", {
            "scope": "config",
            "problem": "Test",
            "evidence": [],
            "diff": "exec(user_input)",
        })
        
        data = json.loads(result)
        assert "error" in data
        assert "Safety check failed" in data["error"]
    
    def test_list_available_modules(self, handler):
        """Can list available modules."""
        modules = handler.list_available_modules()
        assert "sunwell.mirror" in modules or any("mirror" in m for m in modules)
    
    def test_get_rate_limits(self, handler):
        """Can get rate limit status."""
        limits = handler.get_rate_limits()
        assert "proposals" in limits
        assert "applications" in limits
        assert "remaining" in limits["proposals"]
