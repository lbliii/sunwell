# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Full Loop Test - Goal → DAG → Execution → Verification.

This tests the complete thesis end-to-end:

1. User provides a GOAL
2. System SYNTHESIZES an artifact DAG
3. System EXECUTES the DAG (parallel waves, quality gates)
4. System VERIFIES each artifact against its contract
5. Every output is TRACEABLE to its inputs

If this test fails, the architecture doesn't actually work as a system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec, artifacts_to_tasks


# =============================================================================
# Test Data Classes
# =============================================================================


@dataclass
class ExecutionTrace:
    """Trace of artifact execution for provenance verification."""

    artifact_id: str
    inputs: list[str]
    contract: str
    output_content: str
    output_hash: str
    wave: int
    verified: bool
    verification_confidence: float


@dataclass
class FullLoopResult:
    """Result of a full loop execution."""

    goal: str
    graph: ArtifactGraph
    execution_traces: list[ExecutionTrace]
    all_verified: bool
    total_confidence: float
    execution_waves: list[list[str]]


# =============================================================================
# Mock Implementation for Unit Testing
# =============================================================================


class MockModel:
    """Mock model that returns predefined responses."""

    def __init__(self, artifact_response: str, creation_responses: dict[str, str] | None = None):
        self.artifact_response = artifact_response
        self.creation_responses = creation_responses or {}
        self.calls: list[dict] = []

    async def generate(self, prompt: str, options=None):
        self.calls.append({"prompt": prompt, "options": options})

        class MockResult:
            def __init__(self, content: str):
                self.content = content
                self.text = content

        # Check if this is a creation prompt (contains "ARTIFACT:")
        if "ARTIFACT:" in prompt:
            # Extract artifact ID from prompt
            for artifact_id, response in self.creation_responses.items():
                if artifact_id in prompt:
                    return MockResult(response)
            # Default creation response
            return MockResult("```python\n# Generated code\npass\n```")

        # Check if this is a verification prompt
        if "VERIFICATION" in prompt:
            return MockResult('{"passed": true, "reason": "Looks good", "confidence": 0.9}')

        # Default: artifact discovery
        return MockResult(self.artifact_response)


# =============================================================================
# Test: Full Loop Structure
# =============================================================================


class TestFullLoopStructure:
    """Test that full loop components exist and connect."""

    def test_artifact_graph_converts_to_tasks(self):
        """ArtifactGraph must convert to executable tasks."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))

        tasks = artifacts_to_tasks(graph)

        assert len(tasks) == 2
        assert all(hasattr(t, "id") for t in tasks)
        assert all(hasattr(t, "contract") for t in tasks)

    def test_tasks_preserve_dependency_order(self):
        """Tasks must be ordered so dependencies come first."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))

        tasks = artifacts_to_tasks(graph)
        task_ids = [t.id for t in tasks]

        # A must come before B, B must come before C
        assert task_ids.index("A") < task_ids.index("B")
        assert task_ids.index("B") < task_ids.index("C")

    def test_tasks_have_contract_information(self):
        """Tasks must carry contract information for verification."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(
            id="UserProtocol",
            description="User protocol",
            contract="Protocol with id: int, email: str",
        ))

        tasks = artifacts_to_tasks(graph)
        task = tasks[0]

        assert task.contract == "Protocol with id: int, email: str"


# =============================================================================
# Test: Provenance Tracking
# =============================================================================


class TestProvenanceTracking:
    """Every output must be traceable to its inputs."""

    @pytest.mark.asyncio
    async def test_artifact_creation_records_inputs(self):
        """Artifact creation must know its dependencies."""
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        artifacts_json = json.dumps([
            {"id": "Protocol", "description": "Protocol", "contract": "Interface", "requires": []},
            {"id": "Model", "description": "Model", "contract": "Implements Protocol", "requires": ["Protocol"]},
        ])

        model = MockModel(artifact_response=artifacts_json)
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        # Model must know it depends on Protocol
        model_artifact = graph["Model"]
        assert "Protocol" in model_artifact.requires

    @pytest.mark.asyncio
    async def test_execution_trace_captures_lineage(self):
        """Execution must capture full lineage for each artifact."""
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        artifacts_json = json.dumps([
            {"id": "A", "description": "Base", "contract": "Foundation", "requires": []},
            {"id": "B", "description": "Middle", "contract": "Uses A", "requires": ["A"]},
            {"id": "C", "description": "Top", "contract": "Uses B", "requires": ["B"]},
        ])

        creation_responses = {
            "A": "```python\n# A implementation\nclass A: pass\n```",
            "B": "```python\n# B implementation\nclass B(A): pass\n```",
            "C": "```python\n# C implementation\nclass C(B): pass\n```",
        }

        model = MockModel(artifact_response=artifacts_json, creation_responses=creation_responses)
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        # Build provenance trace
        provenance: dict[str, ExecutionTrace] = {}
        for wave_idx, wave in enumerate(graph.execution_waves()):
            for artifact_id in wave:
                artifact = graph[artifact_id]
                content = await planner.create_artifact(artifact)

                provenance[artifact_id] = ExecutionTrace(
                    artifact_id=artifact_id,
                    inputs=list(artifact.requires),
                    contract=artifact.contract,
                    output_content=content,
                    output_hash=str(hash(content)),
                    wave=wave_idx,
                    verified=True,  # Mock
                    verification_confidence=0.9,
                )

        # Verify lineage is complete
        assert len(provenance) == 3

        # A has no inputs (leaf)
        assert provenance["A"].inputs == []
        assert provenance["A"].wave == 0

        # B depends on A
        assert provenance["B"].inputs == ["A"]
        assert provenance["B"].wave == 1

        # C depends on B
        assert provenance["C"].inputs == ["B"]
        assert provenance["C"].wave == 2


# =============================================================================
# Test: Quality Gates
# =============================================================================


class TestQualityGates:
    """Quality gates must halt execution when confidence is low."""

    @pytest.mark.asyncio
    async def test_verification_produces_confidence(self):
        """Artifact verification must produce a confidence score."""
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner
        from sunwell.planning.naaru.artifacts import VerificationResult

        model = MockModel(artifact_response="[]")
        planner = ArtifactPlanner(model=model)

        artifact = ArtifactSpec(
            id="Test",
            description="Test artifact",
            contract="Must return int",
        )

        # Create content
        content = "def test() -> int:\n    return 42"

        # Verify
        result = await planner.verify_artifact(artifact, content)

        assert isinstance(result, VerificationResult)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.passed, bool)

    def test_verification_result_has_required_fields(self):
        """VerificationResult must have all required fields."""
        from sunwell.planning.naaru.artifacts import VerificationResult

        result = VerificationResult(
            passed=True,
            reason="Contract satisfied",
            gaps=(),
            confidence=0.95,
        )

        assert result.passed is True
        assert result.reason == "Contract satisfied"
        assert result.gaps == ()
        assert result.confidence == 0.95


# =============================================================================
# Test: End-to-End Execution (Mocked)
# =============================================================================


class TestEndToEndExecution:
    """Test the full loop with mocked components."""

    @pytest.mark.asyncio
    async def test_full_loop_simple_goal(self):
        """Full loop should work for a simple goal."""
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        artifacts_json = json.dumps([
            {
                "id": "HelloWorld",
                "description": "Hello world script",
                "contract": "Print 'Hello, World!'",
                "requires": [],
                "produces_file": "hello.py",
            }
        ])

        creation_responses = {
            "HelloWorld": "```python\nprint('Hello, World!')\n```",
        }

        model = MockModel(artifact_response=artifacts_json, creation_responses=creation_responses)
        planner = ArtifactPlanner(model=model)

        # Step 1: Synthesize DAG
        graph = await planner.discover_graph("Create a hello world script")
        assert len(graph) >= 1

        # Step 2: Get execution order
        waves = graph.execution_waves()
        assert len(waves) >= 1

        # Step 3: Execute (create artifacts)
        results: dict[str, str] = {}
        for wave in waves:
            for artifact_id in wave:
                artifact = graph[artifact_id]
                content = await planner.create_artifact(artifact)
                results[artifact_id] = content

        assert "HelloWorld" in results
        assert "Hello, World!" in results["HelloWorld"]

        # Step 4: Verify
        for artifact_id, content in results.items():
            artifact = graph[artifact_id]
            verification = await planner.verify_artifact(artifact, content)
            assert verification.passed or verification.confidence > 0.3

    @pytest.mark.asyncio
    async def test_full_loop_with_dependencies(self):
        """Full loop should handle artifacts with dependencies."""
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        artifacts_json = json.dumps([
            {
                "id": "UserProtocol",
                "description": "User protocol",
                "contract": "Protocol with id, email, name fields",
                "requires": [],
                "produces_file": "protocols/user.py",
                "domain_type": "protocol",
            },
            {
                "id": "UserModel",
                "description": "User model",
                "contract": "Implements UserProtocol with SQLAlchemy",
                "requires": ["UserProtocol"],
                "produces_file": "models/user.py",
                "domain_type": "model",
            },
        ])

        creation_responses = {
            "UserProtocol": '''```python
from typing import Protocol

class UserProtocol(Protocol):
    id: int
    email: str
    name: str
```''',
            "UserModel": '''```python
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)
```''',
        }

        model = MockModel(artifact_response=artifacts_json, creation_responses=creation_responses)
        planner = ArtifactPlanner(model=model)

        # Full loop
        graph = await planner.discover_graph("Build a user system")

        # Verify structure
        assert len(graph) == 2
        assert "UserProtocol" in graph.leaves()
        assert "UserModel" in graph.roots()

        # Execute in order
        waves = graph.execution_waves()
        assert len(waves) == 2  # Protocol first, then Model

        results: dict[str, str] = {}
        for wave in waves:
            for artifact_id in wave:
                artifact = graph[artifact_id]
                content = await planner.create_artifact(artifact)
                results[artifact_id] = content

        # Verify both artifacts created
        assert "Protocol" in results["UserProtocol"]
        assert "class User" in results["UserModel"]


# =============================================================================
# Integration Test: Real Execution (Skip without model)
# =============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestFullLoopIntegration:
    """Integration tests requiring real model and execution.

    These tests verify the complete thesis with actual LLM calls.
    Skip in CI; run manually with: pytest -m integration
    """

    @pytest.mark.asyncio
    async def test_full_loop_with_real_model(self):
        """Full loop with actual model execution."""
        pytest.skip("Requires real model - run manually")

        # This would be the full integration test:
        # 1. Real LLM for discovery
        # 2. Real LLM for artifact creation
        # 3. Real LLM for verification
        # 4. Assert: all artifacts verified, confidence > 0.7
