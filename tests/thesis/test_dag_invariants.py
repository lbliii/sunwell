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

"""DAG Invariants - Properties that must hold for any synthesized artifact graph.

These tests verify the fundamental claim:
> Given ANY goal, Sunwell can synthesize a VALID artifact DAG.

A valid DAG must:
1. Have at least one artifact
2. Be acyclic (no circular dependencies)
3. Have at least one leaf (starting point)
4. Have at least one root (ending point)
5. Execution waves must cover all artifacts
6. Contracts must not depend on implementations

If any of these invariants fail, the architecture is broken.
"""

from __future__ import annotations

import pytest

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec, CyclicDependencyError


# =============================================================================
# Test Fixtures
# =============================================================================


class MockModel:
    """Mock model that returns predefined artifact responses."""

    def __init__(self, response: str = "[]"):
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str, options=None):
        self.calls.append(prompt)

        class MockResult:
            def __init__(self, content: str):
                self.content = content
                self.text = content

        return MockResult(self.response)


def mock_model_with_artifacts(artifacts: list[dict]) -> MockModel:
    """Create a mock model that returns the given artifacts as JSON."""
    import json
    return MockModel(response=json.dumps(artifacts))


# =============================================================================
# Invariant 1: Valid Graph Structure
# =============================================================================


class TestGraphStructureInvariants:
    """Invariants for ArtifactGraph structure."""

    def test_empty_graph_has_no_leaves_or_roots(self):
        """Empty graph edge case."""
        graph = ArtifactGraph()
        assert len(graph) == 0
        assert graph.leaves() == []
        assert graph.roots() == []

    def test_single_artifact_is_both_leaf_and_root(self):
        """Single artifact with no dependencies is both leaf and root."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(
            id="Solo",
            description="Standalone artifact",
            contract="Must exist",
        ))

        assert len(graph) == 1
        assert graph.leaves() == ["Solo"]
        assert graph.roots() == ["Solo"]
        assert graph.detect_cycle() is None

    def test_linear_chain_has_one_leaf_one_root(self):
        """A → B → C should have A as leaf, C as root."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))

        assert graph.leaves() == ["A"]
        assert graph.roots() == ["C"]
        assert graph.detect_cycle() is None

    def test_diamond_dependency_has_correct_structure(self):
        """Diamond: A → (B, C) → D should have A as leaf, D as root."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="D", description="D", contract="D", requires=frozenset(["B", "C"])))

        assert graph.leaves() == ["A"]
        assert graph.roots() == ["D"]
        assert graph.detect_cycle() is None

    def test_multiple_leaves_parallel_start(self):
        """Multiple independent starting points."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B"))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["A", "B"])))

        leaves = set(graph.leaves())
        assert leaves == {"A", "B"}
        assert graph.roots() == ["C"]


# =============================================================================
# Invariant 2: Acyclicity
# =============================================================================


class TestAcyclicityInvariants:
    """Cycles must be detected and prevented."""

    def test_direct_cycle_detected(self):
        """A → B → A should be detected as cycle."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A", requires=frozenset(["B"])))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))

        cycle = graph.detect_cycle()
        assert cycle is not None
        assert set(cycle) == {"A", "B"}

    def test_transitive_cycle_detected(self):
        """A → B → C → A should be detected as cycle."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A", requires=frozenset(["C"])))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))

        cycle = graph.detect_cycle()
        assert cycle is not None
        assert set(cycle) == {"A", "B", "C"}

    def test_topological_sort_raises_on_cycle(self):
        """Topological sort must raise CyclicDependencyError on cycles."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A", requires=frozenset(["B"])))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))

        with pytest.raises(CyclicDependencyError):
            graph.topological_sort()

    def test_self_reference_detected(self):
        """A → A (self-reference) should be detected."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A", requires=frozenset(["A"])))

        cycle = graph.detect_cycle()
        assert cycle is not None
        assert "A" in cycle


# =============================================================================
# Invariant 3: Execution Waves Cover All Artifacts
# =============================================================================


class TestExecutionWavesInvariants:
    """Execution waves must cover all artifacts exactly once."""

    def test_single_wave_for_independent_artifacts(self):
        """All independent artifacts should be in wave 1."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B"))
        graph.add(ArtifactSpec(id="C", description="C", contract="C"))

        waves = graph.execution_waves()
        assert len(waves) == 1
        assert set(waves[0]) == {"A", "B", "C"}

    def test_waves_respect_dependencies(self):
        """Dependencies must be in earlier waves."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))

        waves = graph.execution_waves()
        assert len(waves) == 3
        assert waves[0] == ["A"]
        assert waves[1] == ["B"]
        assert waves[2] == ["C"]

    def test_waves_cover_all_artifacts(self):
        """All artifacts must appear in exactly one wave."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="D", description="D", contract="D", requires=frozenset(["B", "C"])))

        waves = graph.execution_waves()

        # Flatten and check coverage
        all_in_waves = [aid for wave in waves for aid in wave]
        assert set(all_in_waves) == {"A", "B", "C", "D"}
        assert len(all_in_waves) == 4  # No duplicates

    def test_parallel_artifacts_in_same_wave(self):
        """Independent artifacts at same depth should be in same wave."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["A"])))

        waves = graph.execution_waves()
        assert len(waves) == 2
        assert waves[0] == ["A"]
        assert set(waves[1]) == {"B", "C"}


# =============================================================================
# Invariant 4: Contracts Before Implementations
# =============================================================================


class TestContractFirstInvariants:
    """Contracts (protocols/interfaces) should not depend on implementations."""

    def test_protocol_is_leaf(self):
        """Artifacts with domain_type='protocol' should typically be leaves."""
        graph = ArtifactGraph()
        protocol = ArtifactSpec(
            id="UserProtocol",
            description="User protocol",
            contract="Protocol with id, email",
            domain_type="protocol",
        )
        graph.add(protocol)

        assert protocol.is_leaf()
        assert protocol.is_contract()

    def test_implementation_requires_protocol(self):
        """Implementations should depend on their protocols."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(
            id="UserProtocol",
            description="User protocol",
            contract="Protocol with id, email",
            domain_type="protocol",
        ))
        graph.add(ArtifactSpec(
            id="UserModel",
            description="User implementation",
            contract="Implements UserProtocol",
            domain_type="model",
            requires=frozenset(["UserProtocol"]),
        ))

        waves = graph.execution_waves()
        # Protocol should be in earlier wave
        protocol_wave = next(i for i, w in enumerate(waves) if "UserProtocol" in w)
        model_wave = next(i for i, w in enumerate(waves) if "UserModel" in w)
        assert protocol_wave < model_wave


# =============================================================================
# Invariant 5: Depth and Complexity Metrics
# =============================================================================


class TestDepthMetricsInvariants:
    """Depth calculations must be consistent."""

    def test_leaf_has_depth_zero(self):
        """Leaves (no dependencies) have depth 0."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))

        assert graph.depth("A") == 0

    def test_depth_increases_with_dependencies(self):
        """Depth is max dependency chain length."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))

        assert graph.depth("A") == 0
        assert graph.depth("B") == 1
        assert graph.depth("C") == 2

    def test_max_depth_is_longest_chain(self):
        """max_depth() returns the longest dependency chain."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        graph.add(ArtifactSpec(id="B", description="B", contract="B", requires=frozenset(["A"])))
        graph.add(ArtifactSpec(id="C", description="C", contract="C", requires=frozenset(["B"])))
        graph.add(ArtifactSpec(id="X", description="X", contract="X"))  # Independent

        assert graph.max_depth() == 2


# =============================================================================
# Integration: ArtifactPlanner Must Produce Valid Graphs
# =============================================================================


class TestArtifactPlannerProducesValidGraphs:
    """ArtifactPlanner must always produce graphs satisfying all invariants."""

    @pytest.mark.asyncio
    async def test_planner_produces_non_empty_graph(self):
        """Planner must produce at least one artifact for any goal."""
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        model = mock_model_with_artifacts([
            {"id": "Main", "description": "Main artifact", "contract": "Must exist", "requires": []}
        ])
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        assert len(graph) >= 1

    @pytest.mark.asyncio
    async def test_planner_produces_acyclic_graph(self):
        """Planner must never produce cycles."""
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        model = mock_model_with_artifacts([
            {"id": "A", "description": "A", "contract": "A", "requires": []},
            {"id": "B", "description": "B", "contract": "B", "requires": ["A"]},
        ])
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        assert graph.detect_cycle() is None

    @pytest.mark.asyncio
    async def test_planner_produces_graph_with_leaves(self):
        """Planner must produce graphs with at least one leaf (starting point)."""
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        model = mock_model_with_artifacts([
            {"id": "Protocol", "description": "Protocol", "contract": "Interface", "requires": []},
            {"id": "Impl", "description": "Implementation", "contract": "Implements Protocol", "requires": ["Protocol"]},
        ])
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        assert len(graph.leaves()) >= 1

    @pytest.mark.asyncio
    async def test_planner_produces_graph_with_roots(self):
        """Planner must produce graphs with at least one root (ending point)."""
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        model = mock_model_with_artifacts([
            {"id": "A", "description": "A", "contract": "A", "requires": []},
            {"id": "B", "description": "B", "contract": "B", "requires": ["A"]},
        ])
        planner = ArtifactPlanner(model=model)

        graph = await planner.discover_graph("Build something")

        assert len(graph.roots()) >= 1

    @pytest.mark.asyncio
    async def test_trivial_goal_produces_single_artifact(self):
        """Trivial goals should produce minimal graphs."""
        from sunwell.naaru.planners.artifact import ArtifactPlanner

        model = MockModel()  # Empty response - triggers trivial path
        planner = ArtifactPlanner(model=model)

        graph = planner._trivial_artifact("Create hello.py that prints Hello")

        assert len(graph) == 1
        assert graph.detect_cycle() is None
        assert len(graph.leaves()) == 1
        assert len(graph.roots()) == 1
