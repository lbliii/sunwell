"""Research reporter for formatting analysis results.

Generates markdown and JSON reports from synthesized patterns.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sunwell.research.types import RepoAnalysis, RepoResult, SynthesizedPatterns

if TYPE_CHECKING:
    pass


class ResearchReporter:
    """Format research results for consumption."""

    def format_markdown(
        self,
        query: str,
        repos: list[RepoResult],
        analyses: list[RepoAnalysis],
        patterns: SynthesizedPatterns,
    ) -> str:
        """Generate a markdown research report.

        Args:
            query: Original research query.
            repos: List of searched repositories.
            analyses: Individual repo analyses.
            patterns: Synthesized patterns.

        Returns:
            Formatted markdown report.
        """
        lines: list[str] = []

        # Header
        lines.append(f"# Research: {query}\n")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        # Analyzed repositories
        lines.append("## Analyzed Repositories\n")
        for i, repo in enumerate(repos, 1):
            stars = f"{repo.stars:,}" if repo.stars else "0"
            lang = repo.language or "Unknown"
            desc = repo.description[:80] + "..." if repo.description and len(repo.description) > 80 else (repo.description or "No description")
            lines.append(f"{i}. **{repo.full_name}** ({stars} ⭐, {lang})")
            lines.append(f"   - {desc}")
        lines.append("")

        # Architecture summary
        if patterns.architecture_summary:
            lines.append(patterns.architecture_summary)

        # Common structure
        if patterns.common_structure:
            lines.append("## Recommended Directory Structure\n")
            lines.append("Based on analyzed repositories, consider this structure:\n")
            lines.append("```")
            self._format_tree(patterns.common_structure, len(repos), lines)
            lines.append("```\n")

        # Common dependencies
        if patterns.common_dependencies:
            lines.append("## Common Dependencies\n")
            lines.append("Packages used across multiple repositories:\n")
            for dep in patterns.common_dependencies[:10]:
                lines.append(f"- `{dep}`")
            lines.append("")

        # Key patterns per repo
        if analyses:
            lines.append("## Key Patterns by Repository\n")
            for analysis in analyses:
                lines.append(f"### {analysis.repo.repo.full_name}\n")

                # Key files
                if analysis.key_files:
                    lines.append("**Entry Points:**")
                    for kf in analysis.key_files[:5]:
                        rel_path = kf.relative_to(analysis.repo.local_path)
                        lines.append(f"- `{rel_path}`")
                    lines.append("")

                # Graph stats (Python AST)
                stats = analysis.graph.stats()
                
                # Also count extracted fragments (includes JS/TS/Svelte)
                fragment_counts: dict[str, int] = {}
                for frag in analysis.structure:
                    frag_type = frag.fragment_type
                    fragment_counts[frag_type] = fragment_counts.get(frag_type, 0) + 1
                
                # Build structure summary
                py_summary = f"{stats['modules']} py modules, {stats['classes']} classes, {stats['functions']} functions"
                
                # Add JS/TS fragment counts if any
                js_parts: list[str] = []
                if fragment_counts.get("arrow_function", 0):
                    js_parts.append(f"{fragment_counts['arrow_function']} arrow fns")
                if fragment_counts.get("function", 0):
                    js_parts.append(f"{fragment_counts['function']} functions")
                if fragment_counts.get("class", 0):
                    js_parts.append(f"{fragment_counts['class']} classes")
                
                if js_parts:
                    lines.append(f"**Python:** {py_summary}")
                    lines.append(f"**JS/TS/Svelte:** {', '.join(js_parts)}\n")
                else:
                    lines.append(f"**Structure:** {py_summary}\n")

                # Detected patterns
                if analysis.patterns:
                    lines.append("**Patterns:** " + ", ".join(f"`{p}`" for p in analysis.patterns))
                lines.append("")

        # Semantic patterns section
        if patterns.classified_patterns:
            cp = patterns.classified_patterns

            # Show categories with function names
            if cp.by_category:
                lines.append("## Semantic Patterns\n")
                lines.append("Functions grouped by purpose:\n")

                for category_name, functions in cp.by_category.items():
                    if functions:
                        # Get unique function names (limit to 5)
                        unique_names = list(dict.fromkeys(f[1] for f in functions))[:5]
                        category_label = category_name.replace("_", " ").title()
                        lines.append(f"- **{category_label}:** `{', '.join(unique_names)}`")

                lines.append("")

            # Cross-repo insights
            if cp.cross_repo_patterns:
                lines.append("### Cross-Repository Insights\n")
                for insight in cp.cross_repo_patterns:
                    lines.append(f"- {insight}")
                lines.append("")

            # Code examples
            if cp.key_examples:
                lines.append("### Example Code\n")
                for ex in cp.key_examples[:3]:
                    frag_type = ex.fragment_type.replace("_", " ")
                    lines.append(f"**{ex.name}** ({frag_type}):")
                    # Determine language for syntax highlighting
                    if ex.file_path:
                        suffix = ex.file_path.suffix.lower()
                        lang = {
                            ".py": "python",
                            ".js": "javascript",
                            ".ts": "typescript",
                            ".svelte": "javascript",
                            ".jsx": "javascript",
                            ".tsx": "typescript",
                        }.get(suffix, "")
                    else:
                        lang = ""
                    lines.append(f"```{lang}")
                    # Show signature (truncate if too long)
                    sig = ex.signature or ex.content
                    if len(sig) > 200:
                        sig = sig[:200] + "..."
                    lines.append(sig)
                    lines.append("```\n")

        # Recommendations
        if patterns.recommendations:
            lines.append("## Recommendations\n")
            for i, rec in enumerate(patterns.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)

    def format_json(
        self,
        query: str,
        repos: list[RepoResult],
        analyses: list[RepoAnalysis],
        patterns: SynthesizedPatterns,
    ) -> dict[str, Any]:
        """Generate a JSON research report.

        Args:
            query: Original research query.
            repos: List of searched repositories.
            analyses: Individual repo analyses.
            patterns: Synthesized patterns.

        Returns:
            Structured JSON-serializable dict.
        """
        return {
            "query": query,
            "generated_at": datetime.now().isoformat(),
            "repositories": [
                {
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "stars": repo.stars,
                    "language": repo.language,
                    "topics": list(repo.topics),
                    "updated_at": repo.updated_at.isoformat(),
                }
                for repo in repos
            ],
            "analyses": [
                {
                    "repo": analysis.repo.repo.full_name,
                    "graph_stats": analysis.graph.stats(),
                    "key_files": [
                        str(f.relative_to(analysis.repo.local_path))
                        for f in analysis.key_files
                    ],
                    "patterns": list(analysis.patterns),
                    "structure_count": len(analysis.structure),
                }
                for analysis in analyses
            ],
            "synthesis": {
                "common_structure": patterns.common_structure,
                "common_components": list(patterns.common_components),
                "common_dependencies": list(patterns.common_dependencies),
                "recommendations": list(patterns.recommendations),
            },
        }

    def format_json_string(
        self,
        query: str,
        repos: list[RepoResult],
        analyses: list[RepoAnalysis],
        patterns: SynthesizedPatterns,
    ) -> str:
        """Generate a JSON string report."""
        data = self.format_json(query, repos, analyses, patterns)
        return json.dumps(data, indent=2)

    def _format_tree(
        self,
        structure: dict[str, int],
        total_repos: int,
        lines: list[str],
        prefix: str = "",
    ) -> None:
        """Format directory structure as a tree."""
        # Group by top-level directory
        grouped: dict[str, list[str]] = {}
        for path in structure:
            parts = path.split("/")
            top = parts[0]
            if top not in grouped:
                grouped[top] = []
            if len(parts) > 1:
                grouped[top].append("/".join(parts[1:]))

        for top in sorted(grouped.keys()):
            count = structure.get(top, 0)
            marker = "✓" if count == total_repos else f"{count}/{total_repos}"
            lines.append(f"{prefix}{top}/ [{marker}]")

            # Show subdirectories
            subdirs = grouped[top]
            for subdir in sorted(set(subdirs))[:5]:  # Limit depth
                sub_path = f"{top}/{subdir}"
                sub_count = structure.get(sub_path, 0)
                if sub_count >= 2:
                    lines.append(f"{prefix}  {subdir}/")


def format_for_tool(
    query: str,
    repos: list[RepoResult],
    analyses: list[RepoAnalysis],
    patterns: SynthesizedPatterns,
) -> str:
    """Format research results for agent tool consumption.

    Provides a concise summary suitable for LLM context.
    """
    lines: list[str] = []

    lines.append(f"## Research Results: {query}\n")

    # Quick stats
    lines.append(f"Analyzed {len(repos)} repositories:\n")
    for repo in repos:
        lines.append(f"- {repo.full_name} ({repo.stars:,}⭐)")
    lines.append("")

    # Semantic patterns (most valuable for LLM)
    if patterns.classified_patterns:
        cp = patterns.classified_patterns
        if cp.cross_repo_patterns:
            lines.append("### Function Patterns")
            for insight in cp.cross_repo_patterns[:5]:
                lines.append(f"- {insight}")
            lines.append("")

        if cp.key_examples:
            lines.append("### Key Examples")
            for ex in cp.key_examples[:3]:
                lines.append(f"- `{ex.name}`: `{ex.signature[:60]}...`" if ex.signature and len(ex.signature) > 60 else f"- `{ex.name}`: `{ex.signature}`")
            lines.append("")

    # Key findings
    if patterns.common_structure:
        lines.append("### Common Structure")
        top_dirs = [d for d, c in patterns.common_structure.items() if c >= 2][:8]
        lines.append(f"Directories present in most repos: {', '.join(top_dirs)}")
        lines.append("")

    if patterns.common_dependencies:
        lines.append("### Shared Dependencies")
        lines.append(", ".join(patterns.common_dependencies[:8]))
        lines.append("")

    if patterns.recommendations:
        lines.append("### Recommendations")
        for rec in patterns.recommendations[:5]:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)
