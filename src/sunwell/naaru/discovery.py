"""Opportunity discovery for RFC-016 Autonomous Mode."""


import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.naaru.types import (
    Opportunity,
    OpportunityCategory,
    RiskLevel,
)

if TYPE_CHECKING:
    from sunwell.mirror import MirrorHandler


@dataclass
class OpportunityDiscoverer:
    """Discover improvement opportunities based on goals.

    Analyzes the codebase to find things Sunwell could improve
    about itself, then prioritizes them by goal alignment.
    """

    mirror: MirrorHandler
    workspace: Path

    async def discover(self, goals: list[str]) -> list[Opportunity]:
        """Discover opportunities matching the given goals.

        Args:
            goals: List of improvement goals

        Returns:
            List of opportunities sorted by priority
        """
        opportunities = []

        for goal in goals:
            goal_lower = goal.lower()

            if "error" in goal_lower:
                opps = await self._find_error_handling_opportunities()
                opportunities.extend(opps)

            if "test" in goal_lower:
                opps = await self._find_testing_opportunities()
                opportunities.extend(opps)

            if "performance" in goal_lower or "optim" in goal_lower:
                opps = await self._find_performance_opportunities()
                opportunities.extend(opps)

            if "doc" in goal_lower:
                opps = await self._find_documentation_opportunities()
                opportunities.extend(opps)

            if "quality" in goal_lower or "refactor" in goal_lower:
                opps = await self._find_code_quality_opportunities()
                opportunities.extend(opps)

        # Dedupe and sort by priority
        seen_ids = set()
        unique = []
        for opp in opportunities:
            if opp.id not in seen_ids:
                seen_ids.add(opp.id)
                unique.append(opp)

        return sorted(unique, key=lambda o: -o.priority)

    async def _find_error_handling_opportunities(self) -> list[Opportunity]:
        """Find opportunities to improve error handling."""
        opportunities = []

        # Check what error patterns the FailureAnalyzer already knows
        from sunwell.mirror.analysis import FailureAnalyzer
        analyzer = FailureAnalyzer()
        known_patterns = set(analyzer.known_patterns.keys())

        # Common error types that might be missing
        potential_patterns = [
            ("OutOfMemory", "Memory exhaustion errors"),
            ("SSL", "SSL/TLS certificate errors"),
            ("JSON", "JSON parsing errors"),
            ("Encoding", "Character encoding errors"),
            ("Deadlock", "Thread deadlock errors"),
            ("Overflow", "Buffer/integer overflow errors"),
            ("Auth", "Authentication/authorization errors"),
            ("Disk", "Disk space errors"),
        ]

        for pattern, desc in potential_patterns:
            # Check if already covered
            already_covered = any(
                pattern.lower() in known.lower()
                for known in known_patterns
            )

            if not already_covered:
                opportunities.append(Opportunity(
                    id=f"err_{pattern.lower()}_{uuid.uuid4().hex[:6]}",
                    category=OpportunityCategory.ERROR_HANDLING,
                    description=f"Add {pattern} error pattern recognition",
                    target_module="sunwell.mirror.analysis",
                    priority=0.85,
                    estimated_effort="small",
                    risk_level=RiskLevel.LOW,
                    details={"pattern": pattern, "description": desc},
                ))

        return opportunities

    async def _find_testing_opportunities(self) -> list[Opportunity]:
        """Find opportunities to improve test coverage."""
        opportunities = []

        # List all modules
        modules = self.mirror.list_available_modules()

        # Check which have corresponding test files
        test_dir = self.workspace / "tests"

        for module in modules:
            # Skip test modules themselves
            if "test" in module:
                continue

            # Expected test file
            module_name = module.split(".")[-1]
            test_file = test_dir / f"test_{module_name}.py"

            if not test_file.exists():
                opportunities.append(Opportunity(
                    id=f"test_{module_name}_{uuid.uuid4().hex[:6]}",
                    category=OpportunityCategory.TESTING,
                    description=f"Add tests for {module}",
                    target_module=module,
                    priority=0.7,
                    estimated_effort="medium",
                    risk_level=RiskLevel.LOW,
                    details={"missing_test_file": str(test_file)},
                ))

        return opportunities[:10]  # Limit to top 10

    async def _find_performance_opportunities(self) -> list[Opportunity]:
        """Find opportunities to improve performance."""
        opportunities = []

        # Look for patterns that suggest performance issues
        patterns_to_check = [
            ("sequential file reads", r"for\s+\w+\s+in\s+.*:\s*\n\s*.*read_file", "parallel"),
            ("unbounded loops", r"while\s+True:", "bounded"),
            ("string concatenation in loop", r"for\s+.*:\s*\n\s*\w+\s*\+=\s*['\"]", "join"),
        ]

        for name, pattern, improvement in patterns_to_check:
            # This is simplified - real implementation would search files
            opportunities.append(Opportunity(
                id=f"perf_{name.replace(' ', '_')}_{uuid.uuid4().hex[:6]}",
                category=OpportunityCategory.PERFORMANCE,
                description=f"Optimize {name} → use {improvement}",
                target_module="sunwell.*",
                priority=0.6,
                estimated_effort="medium",
                risk_level=RiskLevel.MEDIUM,
                details={"pattern": pattern, "improvement": improvement},
            ))

        return opportunities

    async def _find_documentation_opportunities(self) -> list[Opportunity]:
        """Find opportunities to improve documentation."""
        opportunities = []

        # Check for missing docstrings
        modules = self.mirror.list_available_modules()[:20]  # Sample

        for module in modules:
            try:
                from sunwell.mirror.introspection import SourceIntrospector
                introspector = SourceIntrospector(self.workspace)
                structure = introspector.get_module_structure(module)

                # Check classes without docstrings
                for cls in structure.get("classes", []):
                    if not cls.get("docstring"):
                        opportunities.append(Opportunity(
                            id=f"doc_{cls['name']}_{uuid.uuid4().hex[:6]}",
                            category=OpportunityCategory.DOCUMENTATION,
                            description=f"Add docstring to {cls['name']}",
                            target_module=module,
                            priority=0.4,
                            estimated_effort="trivial",
                            risk_level=RiskLevel.TRIVIAL,
                            details={"class_name": cls["name"]},
                        ))

                # Check functions without docstrings
                for func in structure.get("functions", []):
                    if not func.get("docstring") and not func["name"].startswith("_"):
                        opportunities.append(Opportunity(
                            id=f"doc_{func['name']}_{uuid.uuid4().hex[:6]}",
                            category=OpportunityCategory.DOCUMENTATION,
                            description=f"Add docstring to {func['name']}()",
                            target_module=module,
                            priority=0.3,
                            estimated_effort="trivial",
                            risk_level=RiskLevel.TRIVIAL,
                            details={"function_name": func["name"]},
                        ))
            except Exception:
                continue

        return opportunities[:15]  # Limit

    async def _find_code_quality_opportunities(self) -> list[Opportunity]:
        """Find opportunities to improve code quality."""
        opportunities = []

        # Look for TODO/FIXME comments
        src_dir = self.workspace / "src" / "sunwell"

        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                content = py_file.read_text()

                # Find TODOs
                for match in re.finditer(r"#\s*(TODO|FIXME):\s*(.+)", content):
                    tag, message = match.groups()
                    module = str(py_file.relative_to(src_dir)).replace("/", ".").replace(".py", "")

                    opportunities.append(Opportunity(
                        id=f"quality_{tag.lower()}_{uuid.uuid4().hex[:6]}",
                        category=OpportunityCategory.CODE_QUALITY,
                        description=f"Address {tag}: {message[:50]}",
                        target_module=f"sunwell.{module}",
                        priority=0.5 if tag == "FIXME" else 0.4,
                        estimated_effort="small",
                        risk_level=RiskLevel.MEDIUM,
                        details={"tag": tag, "message": message},
                    ))
            except Exception:
                continue

        return opportunities[:10]  # Limit
