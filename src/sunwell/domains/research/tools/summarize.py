"""Content summarization tool for research domain."""

from sunwell.tools.core.types import ToolTrust
from sunwell.tools.registry import BaseTool, tool_metadata


@tool_metadata(
    name="summarize",
    simple_description="Summarize content into key points",
    trust_level=ToolTrust.READ_ONLY,
    essential=False,
    usage_guidance=(
        "Use summarize when you need to condense long content into key points. "
        "Provide the content directly or a file path to summarize."
    ),
)
class SummarizeTool(BaseTool):
    """Summarize content into key points.

    Works with both direct content and file paths.
    Uses extractive summarization (no LLM required).
    """

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Content to summarize (text or file path)",
            },
            "max_points": {
                "type": "integer",
                "description": "Maximum number of key points to extract (default: 5)",
                "default": 5,
            },
            "style": {
                "type": "string",
                "description": "Summary style: 'bullet' (default), 'paragraph', or 'headline'",
                "default": "bullet",
                "enum": ["bullet", "paragraph", "headline"],
            },
        },
        "required": ["content"],
    }

    async def execute(self, arguments: dict) -> str:
        """Summarize content.

        Args:
            arguments: Must contain 'content', optionally 'max_points' and 'style'

        Returns:
            Summary in requested format
        """
        content = arguments["content"]
        max_points = arguments.get("max_points", 5)
        style = arguments.get("style", "bullet")

        # Check if content is a file path
        path = self.resolve_path(content)
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")

        if not content.strip():
            return "No content to summarize."

        # Extract key sentences using simple heuristics
        key_points = self._extract_key_points(content, max_points)

        if not key_points:
            return "Could not extract key points from content."

        # Format based on style
        if style == "bullet":
            return "**Key Points:**\n" + "\n".join(f"• {point}" for point in key_points)
        elif style == "paragraph":
            return " ".join(key_points)
        else:  # headline
            return key_points[0] if key_points else "No headline extracted."

    def _extract_key_points(self, content: str, max_points: int) -> list[str]:
        """Extract key sentences from content.

        Uses simple heuristics:
        - Sentences at start of paragraphs (topic sentences)
        - Sentences with key phrases (important, key, main, etc.)
        - Sentences with numbers/data
        """
        import re

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not sentences:
            return []

        # Score sentences
        scored = []
        key_phrases = {
            "important",
            "key",
            "main",
            "significant",
            "crucial",
            "essential",
            "note that",
            "in summary",
            "in conclusion",
            "therefore",
            "thus",
            "result",
            "finding",
        }

        for i, sentence in enumerate(sentences):
            score = 0
            lower = sentence.lower()

            # Position bonus (first sentences of paragraphs)
            if i == 0:
                score += 3
            elif i < 3:
                score += 1

            # Key phrase bonus
            for phrase in key_phrases:
                if phrase in lower:
                    score += 2

            # Numbers/data bonus
            if re.search(r"\d+", sentence):
                score += 1

            # Length penalty for very short/long
            if len(sentence) < 40:
                score -= 1
            elif len(sentence) > 200:
                score -= 1

            scored.append((score, sentence))

        # Sort by score and return top N
        scored.sort(reverse=True, key=lambda x: x[0])
        return [s for _, s in scored[:max_points]]
