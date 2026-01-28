"""Tests for ContractVerifier class."""

import tempfile
from pathlib import Path

import pytest

from sunwell.planning.naaru.verification import (
    ContractVerificationResult,
    ContractVerifier,
    VerificationStatus,
    VerificationTier,
)


class TestContractVerifier:
    """Tests for ContractVerifier class."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def simple_protocol_file(self, temp_workspace: Path) -> Path:
        """Create a simple Protocol file."""
        protocol = '''from typing import Protocol

class UserProtocol(Protocol):
    """Protocol for user services."""
    
    def get_id(self) -> str:
        """Get user ID."""
        ...
    
    def get_name(self) -> str:
        """Get user name."""
        ...
'''
        path = temp_workspace / "protocols.py"
        path.write_text(protocol)
        return path

    @pytest.fixture
    def valid_implementation_file(self, temp_workspace: Path) -> Path:
        """Create a valid implementation file."""
        impl = '''class UserService:
    """Implementation of UserProtocol."""
    
    def get_id(self) -> str:
        return "user-123"
    
    def get_name(self) -> str:
        return "Test User"
'''
        path = temp_workspace / "service.py"
        path.write_text(impl)
        return path

    @pytest.fixture
    def invalid_implementation_file(self, temp_workspace: Path) -> Path:
        """Create an invalid implementation file (missing method)."""
        impl = '''class PartialService:
    """Incomplete implementation."""
    
    def get_id(self) -> str:
        return "user-123"
    
    # Missing get_name method!
'''
        path = temp_workspace / "partial_service.py"
        path.write_text(impl)
        return path

    @pytest.fixture
    def async_mismatch_file(self, temp_workspace: Path) -> Path:
        """Create implementation with async mismatch."""
        impl = '''class AsyncMismatch:
    """Has sync method where async is expected."""
    
    def get_id(self) -> str:
        return "123"
    
    def get_name(self) -> str:
        return "Test"
'''
        path = temp_workspace / "async_mismatch.py"
        path.write_text(impl)
        return path

    @pytest.mark.asyncio
    async def test_verify_valid_implementation(
        self,
        temp_workspace: Path,
        simple_protocol_file: Path,
        valid_implementation_file: Path,
    ) -> None:
        """Valid implementation passes AST verification."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=valid_implementation_file,
            contract_file=simple_protocol_file,
            protocol_name="UserProtocol",
            impl_class_name="UserService",
        )

        # Should pass AST check
        assert len(result.tier_results) >= 1
        ast_result = result.tier_results[0]
        assert ast_result.tier == VerificationTier.AST
        assert ast_result.passed is True

    @pytest.mark.asyncio
    async def test_verify_missing_method(
        self,
        temp_workspace: Path,
        simple_protocol_file: Path,
        invalid_implementation_file: Path,
    ) -> None:
        """Implementation missing method fails verification."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=invalid_implementation_file,
            contract_file=simple_protocol_file,
            protocol_name="UserProtocol",
            impl_class_name="PartialService",
        )

        assert result.status == VerificationStatus.FAILED
        assert len(result.all_mismatches) > 0

        # Should find missing get_name method
        method_names = [m.method_name for m in result.all_mismatches]
        assert "get_name" in method_names

    @pytest.mark.asyncio
    async def test_verify_missing_implementation_file(
        self,
        temp_workspace: Path,
        simple_protocol_file: Path,
    ) -> None:
        """Missing implementation file returns error."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=temp_workspace / "nonexistent.py",
            contract_file=simple_protocol_file,
            protocol_name="UserProtocol",
        )

        assert result.status == VerificationStatus.ERROR
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_verify_missing_contract_file(
        self,
        temp_workspace: Path,
        valid_implementation_file: Path,
    ) -> None:
        """Missing contract file returns error."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=valid_implementation_file,
            contract_file=temp_workspace / "nonexistent_protocol.py",
            protocol_name="UserProtocol",
        )

        assert result.status == VerificationStatus.ERROR
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_auto_detect_impl_class(
        self,
        temp_workspace: Path,
        simple_protocol_file: Path,
        valid_implementation_file: Path,
    ) -> None:
        """Auto-detect implementation class name."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=valid_implementation_file,
            contract_file=simple_protocol_file,
            protocol_name="UserProtocol",
            impl_class_name=None,  # Should auto-detect
        )

        # Should find UserService class
        assert result.status != VerificationStatus.ERROR

    @pytest.mark.asyncio
    async def test_result_summary(
        self,
        temp_workspace: Path,
        simple_protocol_file: Path,
        valid_implementation_file: Path,
    ) -> None:
        """Result summary is human-readable."""
        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=valid_implementation_file,
            contract_file=simple_protocol_file,
            protocol_name="UserProtocol",
            impl_class_name="UserService",
        )

        summary = result.summary
        assert "UserProtocol" in summary

    @pytest.mark.asyncio
    async def test_relative_path_resolution(
        self,
        temp_workspace: Path,
    ) -> None:
        """Relative paths are resolved against workspace."""
        # Create files
        protocol_content = '''from typing import Protocol

class SimpleProtocol(Protocol):
    def method(self) -> None:
        ...
'''
        impl_content = '''class SimpleImpl:
    def method(self) -> None:
        pass
'''
        (temp_workspace / "src").mkdir()
        (temp_workspace / "src" / "protocol.py").write_text(protocol_content)
        (temp_workspace / "src" / "impl.py").write_text(impl_content)

        verifier = ContractVerifier(
            workspace=temp_workspace,
            skip_llm=True,
        )

        result = await verifier.verify(
            implementation_file=Path("src/impl.py"),  # Relative path
            contract_file=Path("src/protocol.py"),  # Relative path
            protocol_name="SimpleProtocol",
            impl_class_name="SimpleImpl",
        )

        assert result.status != VerificationStatus.ERROR


class TestContractVerificationResult:
    """Tests for ContractVerificationResult dataclass."""

    def test_passed_property(self) -> None:
        """Test passed property for different statuses."""
        passed_result = ContractVerificationResult(
            status=VerificationStatus.PASSED,
            protocol_name="TestProtocol",
            implementation_file="/path/impl.py",
            contract_file="/path/protocol.py",
        )
        assert passed_result.passed is True

        failed_result = ContractVerificationResult(
            status=VerificationStatus.FAILED,
            protocol_name="TestProtocol",
            implementation_file="/path/impl.py",
            contract_file="/path/protocol.py",
        )
        assert failed_result.passed is False

    def test_all_mismatches_aggregation(self) -> None:
        """Test all_mismatches aggregates from all tiers."""
        from sunwell.planning.naaru.verification.types import MethodMismatch, TierResult

        result = ContractVerificationResult(
            status=VerificationStatus.FAILED,
            protocol_name="TestProtocol",
            implementation_file="/path/impl.py",
            contract_file="/path/protocol.py",
            tier_results=(
                TierResult(
                    tier=VerificationTier.AST,
                    passed=False,
                    message="AST check failed",
                    mismatches=(
                        MethodMismatch(
                            method_name="method_a",
                            issue="Missing",
                        ),
                    ),
                ),
                TierResult(
                    tier=VerificationTier.TYPE_CHECK,
                    passed=False,
                    message="Type check failed",
                    mismatches=(
                        MethodMismatch(
                            method_name="method_b",
                            issue="Type error",
                        ),
                    ),
                ),
            ),
        )

        all_mismatches = result.all_mismatches
        assert len(all_mismatches) == 2
        assert {m.method_name for m in all_mismatches} == {"method_a", "method_b"}

    def test_summary_for_each_status(self) -> None:
        """Test summary generation for each status."""
        base_kwargs = {
            "protocol_name": "TestProtocol",
            "implementation_file": "/impl.py",
            "contract_file": "/protocol.py",
        }

        passed = ContractVerificationResult(
            status=VerificationStatus.PASSED,
            final_tier=VerificationTier.AST,
            **base_kwargs,
        )
        assert "PASSED" in passed.summary

        failed = ContractVerificationResult(
            status=VerificationStatus.FAILED,
            **base_kwargs,
        )
        assert "FAILED" in failed.summary

        error = ContractVerificationResult(
            status=VerificationStatus.ERROR,
            error_message="Something went wrong",
            **base_kwargs,
        )
        assert "ERROR" in error.summary
        assert "Something went wrong" in error.summary

        skipped = ContractVerificationResult(
            status=VerificationStatus.SKIPPED,
            **base_kwargs,
        )
        assert "SKIPPED" in skipped.summary
