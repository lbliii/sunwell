"""Self-directed expertise retrieval tools (RFC-027).

Provides tool handlers for on-demand expertise retrieval during generation:
- get_expertise: Retrieve relevant heuristics for a topic
- verify_against_expertise: Check code against retrieved heuristics
- list_expertise_areas: List available heuristic categories

These tools enable a ReAct pattern where the model can request and verify
guidance during generation, rather than relying only on system-injected context.
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.heuristic import Heuristic
    from sunwell.foundation.core.lens import Lens
    from sunwell.agent.runtime.retriever import ExpertiseRetriever


@dataclass(slots=True)
class ExpertiseToolHandler:
    """Handler for expertise retrieval tools.

    Wraps ExpertiseRetriever to provide tool-based access to heuristics
    during model generation. This enables self-directed expertise retrieval
    where the model can request guidance on-demand.

    Args:
        retriever: The expertise retriever with embedded lens
        lens: The lens containing all heuristics (for listing/verification)
    """

    retriever: ExpertiseRetriever
    lens: Lens

    # Cache for verification (heuristics retrieved this session)
    _retrieved_cache: dict[str, list[Heuristic]] = field(
        default_factory=dict, init=False
    )
    _call_count: int = field(default=0, init=False)

    async def handle(self, tool_name: str, arguments: dict) -> str:
        """Route tool call to appropriate handler.

        Args:
            tool_name: One of 'get_expertise', 'verify_against_expertise',
                      'list_expertise_areas'
            arguments: Tool arguments from the model

        Returns:
            Tool output as a formatted string
        """
        self._call_count += 1

        if tool_name == "get_expertise":
            return await self._get_expertise(arguments)
        elif tool_name == "verify_against_expertise":
            return await self._verify_against_expertise(arguments)
        elif tool_name == "list_expertise_areas":
            return await self._list_expertise_areas(arguments)
        else:
            return f"Unknown expertise tool: {tool_name}"

    async def _get_expertise(self, arguments: dict) -> str:
        """Retrieve relevant heuristics for a topic.

        Args:
            arguments: {'topic': str, 'top_k': int (optional)}

        Returns:
            Formatted heuristics with always/never patterns
        """
        topic = arguments.get("topic", "")
        if not topic:
            return "Error: 'topic' argument is required"

        top_k = min(arguments.get("top_k", 5), 10)  # Cap at 10

        # Retrieve relevant heuristics
        result = await self.retriever.retrieve(topic, top_k=top_k)

        if not result.heuristics:
            return f"No expertise found for topic: '{topic}'. Try a more general query or use list_expertise_areas() to see available topics."

        # Cache for verification
        cache_key = topic.lower().strip()
        self._retrieved_cache[cache_key] = list(result.heuristics)

        # Format output
        output_parts = [f"## Expertise Retrieved for: {topic}\n"]
        output_parts.append(f"Found {len(result.heuristics)} relevant heuristics:\n")

        for h in result.heuristics:
            output_parts.append(self._format_heuristic(h))

        # Add usage hint
        output_parts.append("\n---")
        output_parts.append(
            "💡 Use `verify_against_expertise(code)` to check your solution "
            "against these heuristics before finalizing."
        )

        return "\n".join(output_parts)

    async def _verify_against_expertise(self, arguments: dict) -> str:
        """Verify code against retrieved heuristics.

        Args:
            arguments: {'code': str, 'focus_areas': list[str] (optional)}

        Returns:
            Verification results with violations and suggestions
        """
        code = arguments.get("code", "")
        if not code:
            return "Error: 'code' argument is required"

        focus_areas = arguments.get("focus_areas", [])

        # Get heuristics to check against
        heuristics_to_check: list[Heuristic] = []

        if focus_areas:
            # Filter by focus areas (match against heuristic name and rule)
            for h in self.lens.heuristics:
                h_text = f"{h.name} {h.rule}".lower()
                if any(fa.lower() in h_text for fa in focus_areas):
                    heuristics_to_check.append(h)
        else:
            # Use cached retrieved heuristics or fall back to recent retrievals
            for cached in self._retrieved_cache.values():
                heuristics_to_check.extend(cached)

            # Remove duplicates while preserving order
            seen = set()
            unique_heuristics = []
            for h in heuristics_to_check:
                if h.name not in seen:
                    seen.add(h.name)
                    unique_heuristics.append(h)
            heuristics_to_check = unique_heuristics

        if not heuristics_to_check:
            return (
                "No heuristics available for verification. "
                "Call get_expertise(topic) first to retrieve relevant heuristics."
            )

        # Check for violations
        violations = []
        good_practices = []

        for h in heuristics_to_check:
            # Check "never" patterns (violations)
            for pattern in h.never:
                pattern_lower = pattern.lower()
                # Simple keyword matching for common anti-patterns
                if self._check_pattern_violation(code, pattern_lower):
                    violations.append({
                        "heuristic": h.name,
                        "pattern": pattern,
                        "type": "never",
                        "severity": "warning",
                    })

            # Check "always" patterns (to confirm good practices)
            for pattern in h.always:
                pattern_lower = pattern.lower()
                if self._check_pattern_present(code, pattern_lower):
                    good_practices.append({
                        "heuristic": h.name,
                        "pattern": pattern,
                        "type": "always",
                    })

        # Format output
        output_parts = ["## Verification Results\n"]
        output_parts.append(f"Checked against {len(heuristics_to_check)} heuristics.\n")

        if violations:
            output_parts.append(f"### ⚠️ Potential Issues ({len(violations)})\n")
            for v in violations:
                output_parts.append(
                    f"- **{v['heuristic']}**: Avoid '{v['pattern']}'"
                )
            output_parts.append("")
        else:
            output_parts.append("### ✅ No Violations Found\n")

        if good_practices:
            output_parts.append(f"### ✅ Good Practices Detected ({len(good_practices)})\n")
            for gp in good_practices[:5]:  # Limit to top 5
                output_parts.append(
                    f"- **{gp['heuristic']}**: Following '{gp['pattern']}'"
                )
            if len(good_practices) > 5:
                output_parts.append(f"- ...and {len(good_practices) - 5} more")

        # Summary
        output_parts.append("\n---")
        if violations:
            output_parts.append(
                "💡 Consider addressing the issues above before finalizing your response."
            )
        else:
            output_parts.append("✅ Code looks good! Ready to proceed.")

        return "\n".join(output_parts)

    async def _list_expertise_areas(self, arguments: dict) -> str:
        """List available heuristic categories in the lens.

        Args:
            arguments: {} (no arguments needed)

        Returns:
            Formatted list of expertise areas with descriptions
        """
        if not self.lens.heuristics:
            return "No heuristics available in the current lens."

        # Get lens name
        lens_name = getattr(self.lens.metadata, 'name', 'Lens') if hasattr(self.lens, 'metadata') else 'Lens'

        output_parts = [f"## Available Expertise ({lens_name})\n"]
        output_parts.append(f"Total heuristics: {len(self.lens.heuristics)}\n")

        output_parts.append("### Available Heuristics\n")

        # List all heuristics with brief descriptions
        for h in self.lens.heuristics[:20]:  # Limit to 20
            rule_preview = h.rule[:60] + "..." if len(h.rule) > 60 else h.rule
            output_parts.append(f"- **{h.name}**: {rule_preview}")

            # Show count of always/never patterns
            patterns = []
            if h.always:
                patterns.append(f"{len(h.always)} always")
            if h.never:
                patterns.append(f"{len(h.never)} never")
            if patterns:
                output_parts.append(f"  - Patterns: {', '.join(patterns)}")

        if len(self.lens.heuristics) > 20:
            output_parts.append(f"\n...and {len(self.lens.heuristics) - 20} more heuristics")

        # Extract keywords from heuristic names for topic hints
        keywords = set()
        for h in self.lens.heuristics:
            words = h.name.lower().replace("-", " ").replace("_", " ").split()
            keywords.update(w for w in words if len(w) > 3)

        if keywords:
            output_parts.append("\n### Topic Keywords\n")
            output_parts.append(f"Try: {', '.join(sorted(keywords)[:10])}")

        output_parts.append("\n---")
        output_parts.append(
            "💡 Use `get_expertise(topic)` with a topic or keyword "
            "to retrieve specific guidance."
        )

        return "\n".join(output_parts)

    def _format_heuristic(self, h: Heuristic) -> str:
        """Format a single heuristic for display."""
        parts = [f"\n### {h.name}\n"]

        # Use rule as the description
        if h.rule:
            parts.append(f"**Rule**: {h.rule}\n")

        if h.always:
            parts.append("**Always:**")
            for pattern in h.always:
                parts.append(f"- ✅ {pattern}")
            parts.append("")

        if h.never:
            parts.append("**Never:**")
            for pattern in h.never:
                parts.append(f"- ❌ {pattern}")
            parts.append("")

        return "\n".join(parts)

    def _check_pattern_violation(self, code: str, pattern: str) -> bool:
        """Check if code contains a 'never' pattern violation.

        This is a heuristic check based on common anti-patterns.
        More sophisticated analysis could use AST parsing.
        """
        code_lower = code.lower()

        # Common anti-pattern keywords to check
        keywords = self._extract_keywords(pattern)

        # If multiple keywords present, likely a violation
        matches = sum(1 for kw in keywords if kw in code_lower)
        return matches >= len(keywords) * 0.5 if keywords else False

    def _check_pattern_present(self, code: str, pattern: str) -> bool:
        """Check if code contains an 'always' pattern.

        This is a heuristic check based on common good practices.
        """
        code_lower = code.lower()
        keywords = self._extract_keywords(pattern)

        # If most keywords present, pattern is likely followed
        matches = sum(1 for kw in keywords if kw in code_lower)
        return matches >= len(keywords) * 0.6 if keywords else False

    def _extract_keywords(self, pattern: str) -> list[str]:
        """Extract meaningful keywords from a pattern description."""
        # Filter out common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "use", "using", "used", "make", "makes", "made",
            "all", "any", "both", "each", "every", "some", "no", "not",
        }

        words = pattern.lower().split()
        keywords = [
            w.strip(".,;:!?\"'()[]{}")
            for w in words
            if len(w) > 2 and w.lower() not in stop_words
        ]

        return keywords[:5]  # Limit to 5 most significant keywords

    def get_stats(self) -> dict:
        """Get handler statistics."""
        return {
            "call_count": self._call_count,
            "cached_topics": len(self._retrieved_cache),
            "total_cached_heuristics": sum(
                len(v) for v in self._retrieved_cache.values()
            ),
        }

    def clear_cache(self) -> None:
        """Clear the retrieved heuristics cache."""
        self._retrieved_cache.clear()


# =============================================================================
# System Prompt for Self-Directed Expertise (RFC-027)
# =============================================================================

SELF_DIRECTED_SYSTEM_PROMPT = """## Self-Directed Expertise

You have access to expertise tools. Use them proactively:

1. **Before starting complex tasks**: Call `list_expertise_areas()` to see what guidance is available
2. **When uncertain**: Call `get_expertise(topic)` to retrieve specific best practices
3. **Before finalizing**: Call `verify_against_expertise(your_code)` to check your solution

### ReAct Pattern

For complex tasks, think step-by-step:

THINK: What expertise do I need?
ACT: get_expertise("topic")
OBSERVE: [expertise returned]
THINK: Draft response, then verify
ACT: verify_against_expertise(draft)
OBSERVE: [verification results]
THINK: Revise if needed, respond
"""


def get_self_directed_prompt() -> str:
    """Get the system prompt hint for self-directed expertise."""
    return SELF_DIRECTED_SYSTEM_PROMPT
