"""Pattern synthesizer for cross-repo analysis.

Compares patterns across multiple repository analyses to find commonalities.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.research.classifier import FunctionCategory, FunctionClassifier
from sunwell.research.types import ClassifiedPatterns, CodeFragment, RepoAnalysis, SynthesizedPatterns

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PatternSynthesizer:
    """Synthesize patterns across multiple repository analyses.

    Identifies commonalities in:
    - Directory structure
    - Component names
    - Dependencies (imports)
    - Architectural patterns
    """

    def __init__(self, min_occurrence: int = 2) -> None:
        """Initialize synthesizer.

        Args:
            min_occurrence: Minimum repos a pattern must appear in to be included.
        """
        self._min_occurrence = min_occurrence

    def synthesize(self, analyses: list[RepoAnalysis]) -> SynthesizedPatterns:
        """Synthesize patterns across multiple analyses.

        Args:
            analyses: List of repository analyses.

        Returns:
            Synthesized patterns with commonalities identified.
        """
        if not analyses:
            return SynthesizedPatterns(
                common_structure={},
                common_components=(),
                common_dependencies=(),
                architecture_summary="No repositories analyzed.",
                recommendations=(),
                classified_patterns=None,
            )

        # Analyze directory structures
        common_structure = self._find_common_structure(analyses)

        # Find common component names
        common_components = self._find_common_components(analyses)

        # Find common dependencies
        common_dependencies = self._find_common_dependencies(analyses)

        # Find semantic patterns (function classification)
        classified_patterns = self._find_semantic_patterns(analyses)

        # Generate architecture summary
        architecture_summary = self._generate_summary(
            analyses, common_structure, common_components
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            analyses, common_structure, common_components, common_dependencies
        )

        return SynthesizedPatterns(
            common_structure=common_structure,
            common_components=tuple(common_components),
            common_dependencies=tuple(common_dependencies),
            architecture_summary=architecture_summary,
            recommendations=tuple(recommendations),
            classified_patterns=classified_patterns,
        )

    def _find_common_structure(
        self, analyses: list[RepoAnalysis]
    ) -> dict[str, int]:
        """Find common directory structure patterns.

        Returns a dict of path patterns to occurrence counts.
        """
        # Collect relative directory paths
        dir_counter: Counter[str] = Counter()

        for analysis in analyses:
            # Get unique parent directories relative to repo root
            seen_dirs: set[str] = set()
            for file_path in analysis.repo.files:
                rel_path = file_path.relative_to(analysis.repo.local_path)
                # Normalize path pattern (e.g., "src/lib/stores" -> "src/lib/stores")
                dir_path = str(rel_path.parent)
                if dir_path and dir_path != ".":
                    # Also track intermediate directories
                    parts = Path(dir_path).parts
                    for i in range(1, len(parts) + 1):
                        partial = "/".join(parts[:i])
                        seen_dirs.add(partial)

            for dir_path in seen_dirs:
                dir_counter[dir_path] += 1

        # Filter to common patterns (appear in min_occurrence repos)
        common = {
            path: count
            for path, count in dir_counter.items()
            if count >= self._min_occurrence
        }

        # Sort by count descending
        return dict(sorted(common.items(), key=lambda x: -x[1]))

    def _find_common_components(self, analyses: list[RepoAnalysis]) -> list[str]:
        """Find component names that appear in multiple repos."""
        name_counter: Counter[str] = Counter()

        for analysis in analyses:
            # Collect unique class/function names per repo
            seen_names: set[str] = set()
            for fragment in analysis.structure:
                if fragment.name:
                    seen_names.add(fragment.name)

            for name in seen_names:
                name_counter[name] += 1

        # Return names appearing in multiple repos
        return [
            name
            for name, count in name_counter.most_common(20)
            if count >= self._min_occurrence
        ]

    def _find_common_dependencies(self, analyses: list[RepoAnalysis]) -> list[str]:
        """Find imports/dependencies common across repos."""
        import_counter: Counter[str] = Counter()

        for analysis in analyses:
            # Collect unique imports per repo
            seen_imports: set[str] = set()

            for node_id, node in analysis.graph.nodes.items():
                if ":external" in node_id and node_id.startswith("module:"):
                    # Extract module name
                    module_name = node.name
                    if module_name and not module_name.startswith("_"):
                        seen_imports.add(module_name)

            for module_name in seen_imports:
                import_counter[module_name] += 1

        # Return imports appearing in multiple repos
        return [
            name
            for name, count in import_counter.most_common(30)
            if count >= self._min_occurrence
        ]

    def _find_semantic_patterns(
        self, analyses: list[RepoAnalysis]
    ) -> ClassifiedPatterns:
        """Classify functions semantically and find cross-repo patterns.

        Groups functions by purpose (CRUD, handlers, predicates, etc.) and
        identifies which patterns appear across multiple repositories.
        """
        classifier = FunctionClassifier()

        # Track functions by category and repo
        # category -> repo_name -> list of function names
        category_by_repo: dict[FunctionCategory, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Track all fragments by category for examples
        category_fragments: dict[FunctionCategory, list[tuple[str, CodeFragment]]] = (
            defaultdict(list)
        )

        for analysis in analyses:
            repo_name = analysis.repo.repo.full_name
            classified = classifier.classify_fragments(analysis.structure)

            for category, fragments in classified.items():
                for frag in fragments:
                    if frag.name:
                        category_by_repo[category][repo_name].append(frag.name)
                        category_fragments[category].append((repo_name, frag))

        # Build by_category dict: category name -> [(repo, func_name), ...]
        by_category: dict[str, list[tuple[str, str]]] = {}
        for category in FunctionCategory:
            if category == FunctionCategory.OTHER:
                continue  # Skip uncategorized

            repos_with_category = category_by_repo[category]
            if not repos_with_category:
                continue

            # Collect all (repo, func_name) pairs
            pairs: list[tuple[str, str]] = []
            for repo_name, func_names in repos_with_category.items():
                for func_name in func_names:
                    pairs.append((repo_name, func_name))

            if pairs:
                by_category[category.name] = pairs

        # Generate cross-repo insights
        cross_repo_patterns: list[str] = []
        total_repos = len(analyses)

        for category in FunctionCategory:
            if category == FunctionCategory.OTHER:
                continue

            repos_with_category = category_by_repo[category]
            repo_count = len(repos_with_category)

            if repo_count >= self._min_occurrence:
                # Get example function names from this category
                example_names: list[str] = []
                for repo_name, func_names in repos_with_category.items():
                    example_names.extend(func_names[:2])  # Max 2 per repo
                example_names = list(dict.fromkeys(example_names))[:5]  # Dedupe, limit 5

                category_label = category.name.replace("_", " ").title()
                if example_names:
                    cross_repo_patterns.append(
                        f"{repo_count}/{total_repos} repos have {category_label} "
                        f"functions: `{', '.join(example_names)}`"
                    )
                else:
                    cross_repo_patterns.append(
                        f"{repo_count}/{total_repos} repos have {category_label} functions"
                    )

        # Select key examples (best representatives from common categories)
        key_examples: list[CodeFragment] = []
        seen_names: set[str] = set()

        # Prioritize categories that appear in multiple repos
        for category in [
            FunctionCategory.CRUD,
            FunctionCategory.PREDICATE,
            FunctionCategory.HANDLER,
            FunctionCategory.GETTER,
            FunctionCategory.TRANSFORM,
            FunctionCategory.LIFECYCLE,
            FunctionCategory.RENDER,
        ]:
            repos_with_category = category_by_repo[category]
            if len(repos_with_category) < self._min_occurrence:
                continue

            # Get examples from this category
            for repo_name, frag in category_fragments[category]:
                if frag.name and frag.name not in seen_names and frag.signature:
                    key_examples.append(frag)
                    seen_names.add(frag.name)
                    if len(key_examples) >= 5:
                        break

            if len(key_examples) >= 5:
                break

        return ClassifiedPatterns(
            by_category=by_category,
            cross_repo_patterns=tuple(cross_repo_patterns),
            key_examples=tuple(key_examples),
        )

    def _generate_summary(
        self,
        analyses: list[RepoAnalysis],
        common_structure: dict[str, int],
        common_components: list[str],
    ) -> str:
        """Generate a human-readable architecture summary."""
        lines: list[str] = []

        lines.append(f"Analyzed {len(analyses)} repositories.\n")

        # Summarize structure patterns
        if common_structure:
            lines.append("## Common Directory Structure\n")
            top_dirs = list(common_structure.items())[:10]
            for dir_path, count in top_dirs:
                lines.append(f"- `{dir_path}/` ({count}/{len(analyses)} repos)")
            lines.append("")

        # Summarize detected patterns
        pattern_counts: Counter[str] = Counter()
        for analysis in analyses:
            for pattern in analysis.patterns:
                pattern_counts[pattern] += 1

        if pattern_counts:
            lines.append("## Detected Patterns\n")
            for pattern, count in pattern_counts.most_common(10):
                if count >= self._min_occurrence:
                    lines.append(f"- `{pattern}` ({count}/{len(analyses)} repos)")
            lines.append("")

        # Summarize common components
        if common_components:
            lines.append("## Common Components\n")
            lines.append(f"Found {len(common_components)} component names across multiple repos:")
            lines.append(f"  {', '.join(common_components[:10])}")
            lines.append("")

        return "\n".join(lines)

    def _generate_recommendations(
        self,
        analyses: list[RepoAnalysis],
        common_structure: dict[str, int],
        common_components: list[str],
        common_dependencies: list[str],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations: list[str] = []

        # Recommend structure
        if common_structure:
            top_dirs = [d for d, c in common_structure.items() if c == len(analyses)][:5]
            if top_dirs:
                recommendations.append(
                    f"Use standard directory structure: {', '.join(top_dirs)}"
                )

        # Recommend dependencies
        if common_dependencies:
            core_deps = common_dependencies[:5]
            recommendations.append(
                f"Consider common dependencies: {', '.join(core_deps)}"
            )

        # Recommend patterns based on what's found
        pattern_counts: Counter[str] = Counter()
        for analysis in analyses:
            for pattern in analysis.patterns:
                pattern_counts[pattern] += 1

        for pattern, count in pattern_counts.most_common(5):
            if count >= self._min_occurrence:
                category, desc = pattern.split(":", 1) if ":" in pattern else (pattern, "")
                if category == "state-management":
                    recommendations.append("Implement centralized state management with stores")
                elif category == "ui":
                    recommendations.append("Use component-based architecture for UI")
                elif category == "routing":
                    recommendations.append("Use file-based routing pattern")
                elif category == "quality":
                    recommendations.append("Include comprehensive test coverage")

        return recommendations
