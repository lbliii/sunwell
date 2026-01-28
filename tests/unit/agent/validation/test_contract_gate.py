"""Tests for CONTRACT validation gate (RFC-034)."""

import tempfile
from pathlib import Path

import pytest

from sunwell.agent.validation.gates import (
    GateType,
    ValidationGate,
    _has_contract,
    _make_contract_gate,
    detect_gates,
)
from sunwell.agent.validation.validation_runner import (
    Artifact,
    ValidationRunner,
)
from sunwell.planning.naaru.types import Task, TaskMode


class TestGateTypeContract:
    """Test that CONTRACT gate type exists and is configured correctly."""

    def test_contract_gate_type_exists(self) -> None:
        """CONTRACT should be a valid GateType."""
        assert GateType.CONTRACT.value == "contract"

    def test_validation_gate_has_contract_fields(self) -> None:
        """ValidationGate should have contract_protocol and contract_file fields."""
        gate = ValidationGate(
            id="test_contract",
            gate_type=GateType.CONTRACT,
            depends_on=("task1",),
            validation="MyProtocol",
            contract_protocol="MyProtocol",
            contract_file="src/protocols.py",
        )
        assert gate.contract_protocol == "MyProtocol"
        assert gate.contract_file == "src/protocols.py"


class TestContractGateDetection:
    """Test automatic detection of contract gates from tasks."""

    def test_has_contract_true_when_contract_set(self) -> None:
        """_has_contract returns True when task has a contract."""
        task = Task(
            id="impl",
            description="Implement UserService",
            mode=TaskMode.GENERATE,
            contract="UserProtocol",
            is_contract=False,
        )
        assert _has_contract(task) is True

    def test_has_contract_false_when_is_contract(self) -> None:
        """_has_contract returns False when task IS the contract definition."""
        task = Task(
            id="protocol",
            description="Define UserProtocol",
            mode=TaskMode.GENERATE,
            contract="UserProtocol",  # Has contract but is_contract=True
            is_contract=True,
        )
        assert _has_contract(task) is False

    def test_has_contract_false_when_no_contract(self) -> None:
        """_has_contract returns False when task has no contract."""
        task = Task(
            id="other",
            description="Do something",
            mode=TaskMode.GENERATE,
        )
        assert _has_contract(task) is False

    def test_make_contract_gate(self) -> None:
        """_make_contract_gate creates a valid CONTRACT gate."""
        impl_task = Task(
            id="impl",
            description="Implement UserService",
            mode=TaskMode.GENERATE,
            contract="UserProtocol",
            target_path="src/user_service.py",
        )
        protocol_task = Task(
            id="protocol",
            description="Define UserProtocol",
            mode=TaskMode.GENERATE,
            is_contract=True,
            target_path="src/protocols.py",
            produces=frozenset(["UserProtocol"]),
        )

        gate = _make_contract_gate(impl_task, [impl_task, protocol_task])

        assert gate.gate_type == GateType.CONTRACT
        assert gate.contract_protocol == "UserProtocol"
        assert gate.contract_file == "src/protocols.py"
        assert "impl" in gate.depends_on

    def test_detect_gates_includes_contract_gates(self) -> None:
        """detect_gates should create CONTRACT gates for implementation tasks."""
        impl_task = Task(
            id="impl",
            description="Implement UserService",
            mode=TaskMode.GENERATE,
            contract="UserProtocol",
            target_path="src/user_service.py",
        )
        protocol_task = Task(
            id="protocol",
            description="Define UserProtocol",
            mode=TaskMode.GENERATE,
            is_contract=True,
            target_path="src/protocols.py",
            produces=frozenset(["UserProtocol"]),
        )

        gates = detect_gates([impl_task, protocol_task])

        contract_gates = [g for g in gates if g.gate_type == GateType.CONTRACT]
        assert len(contract_gates) == 1
        assert contract_gates[0].contract_protocol == "UserProtocol"


class TestContractValidationRunner:
    """Test CONTRACT gate execution through ValidationRunner."""

    @pytest.mark.asyncio
    async def test_contract_check_with_valid_implementation(
        self, tmp_path: Path
    ) -> None:
        """Contract validation should pass for valid implementations."""
        # Create protocol file
        protocol_file = tmp_path / "protocols.py"
        protocol_file.write_text("""
from typing import Protocol

class UserProtocol(Protocol):
    def get_name(self) -> str: ...
    def get_age(self) -> int: ...
""")

        # Create implementation file
        impl_file = tmp_path / "user_service.py"
        impl_file.write_text("""
class UserService:
    def get_name(self) -> str:
        return "Alice"
    
    def get_age(self) -> int:
        return 30
""")

        runner = ValidationRunner(cwd=tmp_path)
        gate = ValidationGate(
            id="test_contract",
            gate_type=GateType.CONTRACT,
            depends_on=(),
            validation="UserProtocol",
            contract_protocol="UserProtocol",
            contract_file=str(protocol_file),
        )
        artifacts = [Artifact(path=impl_file, content=impl_file.read_text())]

        # Run contract check
        result = await runner._check_contract(gate, artifacts)
        passed, message = result

        assert passed, f"Contract validation failed: {message}"
        assert "passed" in message.lower() or "PASSED" in message

    @pytest.mark.asyncio
    async def test_contract_check_with_missing_method(
        self, tmp_path: Path
    ) -> None:
        """Contract validation should fail when implementation is missing methods."""
        # Create protocol file
        protocol_file = tmp_path / "protocols.py"
        protocol_file.write_text("""
from typing import Protocol

class UserProtocol(Protocol):
    def get_name(self) -> str: ...
    def get_age(self) -> int: ...
""")

        # Create incomplete implementation
        impl_file = tmp_path / "user_service.py"
        impl_file.write_text("""
class UserService:
    def get_name(self) -> str:
        return "Alice"
    # Missing get_age!
""")

        runner = ValidationRunner(cwd=tmp_path)
        gate = ValidationGate(
            id="test_contract",
            gate_type=GateType.CONTRACT,
            depends_on=(),
            validation="UserProtocol",
            contract_protocol="UserProtocol",
            contract_file=str(protocol_file),
        )
        artifacts = [Artifact(path=impl_file, content=impl_file.read_text())]

        result = await runner._check_contract(gate, artifacts)
        passed, message = result

        assert not passed, f"Contract validation should have failed: {message}"
        assert "get_age" in message.lower() or "failed" in message.lower()

    @pytest.mark.asyncio
    async def test_contract_check_requires_protocol_name(
        self, tmp_path: Path
    ) -> None:
        """Contract validation should fail if protocol name is missing."""
        runner = ValidationRunner(cwd=tmp_path)
        gate = ValidationGate(
            id="test_contract",
            gate_type=GateType.CONTRACT,
            depends_on=(),
            validation="",
            contract_protocol="",  # Missing!
        )

        result = await runner._check_contract(gate, [])
        passed, message = result

        assert not passed
        assert "contract_protocol" in message.lower()

    @pytest.mark.asyncio
    async def test_contract_check_skips_non_python(
        self, tmp_path: Path
    ) -> None:
        """Contract validation should skip non-Python files."""
        runner = ValidationRunner(cwd=tmp_path)
        gate = ValidationGate(
            id="test_contract",
            gate_type=GateType.CONTRACT,
            depends_on=(),
            validation="MyProtocol",
            contract_protocol="MyProtocol",
        )
        # Only non-Python files
        artifacts = [
            Artifact(path=tmp_path / "data.json", content="{}"),
            Artifact(path=tmp_path / "readme.md", content="# Test"),
        ]

        result = await runner._check_contract(gate, artifacts)
        passed, message = result

        assert passed  # Should pass since nothing to verify
        assert "No Python files" in message


class TestLoopStateContractContext:
    """Test that LoopState supports contract context."""

    def test_loop_state_has_contract_fields(self) -> None:
        """LoopState should have contract_protocol and contract_file fields."""
        from sunwell.agent.loop.config import LoopState

        state = LoopState()
        state.contract_protocol = "MyProtocol"
        state.contract_file = "src/protocols.py"

        assert state.contract_protocol == "MyProtocol"
        assert state.contract_file == "src/protocols.py"

    def test_loop_config_has_contract_validation_flag(self) -> None:
        """LoopConfig should have enable_contract_validation flag."""
        from sunwell.agent.loop.config import LoopConfig

        config = LoopConfig()
        assert hasattr(config, "enable_contract_validation")
        assert config.enable_contract_validation is True  # Default enabled
