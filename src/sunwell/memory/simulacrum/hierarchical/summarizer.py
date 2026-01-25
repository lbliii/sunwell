"""Summarization service for conversation history.

RFC-084: Includes HeuristicSummarizer for LLM-free summarization.
"""


import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol
    from sunwell.simulacrum.core.turn import Turn


# Pre-compiled regex patterns for sentence splitting (avoid per-call compilation)
_RE_DOT_IN_WORD = re.compile(r"(\w)\.(\w)")
_RE_ABBREVIATIONS = re.compile(r"(Mr|Mrs|Dr|Prof|etc|vs|i\.e|e\.g)\.")
_RE_SENTENCE_SPLIT = re.compile(r"[.!?]+")


@runtime_checkable
class SummarizerProtocol(Protocol):
    """Protocol for summarizers - enables dependency injection."""

    async def summarize_turns(self, turns: Sequence[Turn]) -> str:
        """Generate a summary for a sequence of turns."""
        ...

    async def extract_facts(self, turns: Sequence[Turn]) -> list[str]:
        """Extract concrete facts from turns."""
        ...

    async def extract_themes(self, summaries: Sequence[str]) -> list[str]:
        """Identify themes across summaries."""
        ...

    async def generate_executive_summary(self, summaries: Sequence[str]) -> str:
        """Create high-level summary from multiple chunk summaries."""
        ...


@dataclass(slots=True)
class HeuristicSummarizer:
    """Extract summaries using TF-IDF-like scoring (no LLM required).

    RFC-084: Default summarizer for cost-effective summarization.
    Uses sentence scoring and pattern matching instead of LLM calls.
    """

    max_summary_sentences: int = 3
    """Maximum sentences in generated summary."""

    min_sentence_length: int = 20
    """Minimum characters for a sentence to be considered."""

    # Common stopwords to filter out
    _stopwords: set[str] = field(default_factory=lambda: {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "and", "but", "if", "or",
        "because", "until", "while", "this", "that", "these", "those", "i",
        "you", "he", "she", "it", "we", "they", "what", "which", "who", "whom",
    })

    async def summarize_turns(self, turns: Sequence[Turn]) -> str:
        """Extract most informative sentences using TF-IDF scoring."""
        if not turns:
            return ""

        text = " ".join(t.content for t in turns)
        sentences = self._split_sentences(text)

        if not sentences:
            return ""

        # Score sentences by term frequency-inverse document frequency
        word_freq = Counter(
            w.lower()
            for s in sentences
            for w in s.split()
            if w.lower() not in self._stopwords and len(w) > 2
        )
        total_words = sum(word_freq.values()) or 1

        scored: list[tuple[float, str]] = []
        for s in sentences:
            if len(s) < self.min_sentence_length:
                continue
            words = [w.lower() for w in s.split() if w.lower() not in self._stopwords]
            if not words:
                continue
            # TF-IDF-like score: sum of term frequencies normalized by sentence length
            score = sum(word_freq[w] / total_words for w in words) / len(words)
            scored.append((score, s))

        scored.sort(reverse=True)
        top = [s for _, s in scored[: self.max_summary_sentences]]

        return ". ".join(top) + "." if top else ""

    async def extract_facts(self, turns: Sequence[Turn]) -> list[str]:
        """Extract factual statements using pattern matching."""
        text = " ".join(t.content for t in turns)

        patterns = [
            r"(?:my name is|I am|I'm) ([\w\s]+)",
            r"(?:we use|using|we're using|I use) ([\w\s]+)",
            r"(?:the \w+ is|the \w+ are) ([\w\s]+)",
            r"(?:it has|there are|there is) ([\w\s]+)",
            r"(\w+ (?:equals?|is|are|was|were) [\w\s]+)",
            r"(?:prefer|always|never) ([\w\s]+)",
            r"(?:running on|deployed to|hosted on) ([\w\s]+)",
        ]

        facts: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                fact = match.group(0).strip()
                # Filter to reasonable length facts
                if 10 < len(fact) < 100:
                    facts.append(fact)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_facts: list[str] = []
        for fact in facts:
            fact_lower = fact.lower()
            if fact_lower not in seen:
                seen.add(fact_lower)
                unique_facts.append(fact)

        return unique_facts[:10]  # Cap at 10 facts

    async def extract_themes(self, summaries: Sequence[str]) -> list[str]:
        """Extract themes from summaries using keyword extraction."""
        if not summaries:
            return []

        combined = " ".join(summaries)
        words = [
            w.lower()
            for w in combined.split()
            if w.lower() not in self._stopwords and len(w) > 3
        ]

        if not words:
            return []

        # Find most common meaningful words as themes
        word_counts = Counter(words)
        themes = [word for word, _ in word_counts.most_common(5)]
        return themes

    async def generate_executive_summary(self, summaries: Sequence[str]) -> str:
        """Combine mini-chunk summaries into macro summary."""
        if not summaries:
            return ""

        combined = " ".join(summaries)
        sentences = self._split_sentences(combined)

        # Take first sentence from each summary + most unique content
        result: list[str] = []
        seen_words: set[str] = set()

        for s in sentences[: len(summaries)]:
            words = set(s.lower().split())
            new_words = words - seen_words
            # Include if >30% new information
            if len(new_words) > len(words) * 0.3:
                result.append(s)
                seen_words.update(words)

        return ". ".join(result[:5]) + "." if result else ""

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Handle common abbreviations to avoid false splits (use pre-compiled patterns)
        text = _RE_DOT_IN_WORD.sub(r"\1<DOT>\2", text)  # e.g., "file.py"
        text = _RE_ABBREVIATIONS.sub(r"\1<DOT>", text)

        sentences = _RE_SENTENCE_SPLIT.split(text)
        return [s.replace("<DOT>", ".").strip() for s in sentences if s.strip()]


@dataclass(slots=True)
class Summarizer:
    """Generates concise summaries and extracts insights from conversation turns.

    Supports both LLM-based intelligent summarization and fast heuristic fallbacks.
    """

    model: ModelProtocol | None = None

    async def summarize_turns(self, turns: Sequence[Turn]) -> str:
        """Generate a summary for a sequence of turns.

        Args:
            turns: Sequence of turns to summarize

        Returns:
            Concise summary string
        """
        if not turns:
            return ""

        if self.model:
            return await self._llm_summarize(turns)
        else:
            return self._heuristic_summarize(turns)

    async def _llm_summarize(self, turns: Sequence[Turn]) -> str:
        """Use the LLM to generate a high-quality summary."""
        conversation_text = "\n".join(
            f"{t.turn_type.value}: {t.content[:500]}"
            for t in turns
        )

        prompt = f"""Summarize this conversation segment in 2-3 sentences.
Focus on: key topics, decisions made, and information shared.

Conversation:
{conversation_text}

Summary:"""

        result = await self.model.generate(prompt)
        return result.text.strip()

    def _heuristic_summarize(self, turns: Sequence[Turn]) -> str:
        """Fallback to a simple rule-based summary when no LLM is available."""
        user_turns = [t for t in turns if t.turn_type.value == "user"]

        if not user_turns:
            return f"Conversation segment with {len(turns)} turns."

        # Take the first user message as the primary topic/intent
        first_user_msg = user_turns[0].content
        topic = first_user_msg.split('.')[0][:100]

        return f"Discussion starting with: {topic}..."

    async def extract_facts(self, turns: Sequence[Turn]) -> list[str]:
        """Extract concrete facts and insights to be stored as learnings.

        Args:
            turns: Sequence of turns to analyze

        Returns:
            List of extracted fact strings
        """
        if not self.model:
            return [] # Heuristic fact extraction is unreliable

        conversation_text = "\n".join(
            f"{t.turn_type.value}: {t.content[:300]}"
            for t in turns
        )

        prompt = f"""Extract key facts from this conversation that should be remembered.
Only include concrete, reusable information (preferences, technical decisions, constraints).
Return as a list, one fact per line.

Conversation:
{conversation_text}

Facts:"""

        result = await self.model.generate(prompt)

        # Simple line-based parsing
        facts = []
        for line in result.text.strip().split("\n"):
            cleaned = line.strip().lstrip("-*• ").strip()
            if cleaned and len(cleaned) > 5:
                facts.append(cleaned)

        return facts[:10] # Cap at 10 facts per segment

    async def extract_themes(self, summaries: Sequence[str]) -> list[str]:
        """Identify main themes across multiple chunk summaries.

        Args:
            summaries: List of chunk summaries

        Returns:
            List of theme strings
        """
        if not self.model or not summaries:
            return []

        summaries_text = "\n".join(f"- {s}" for s in summaries)

        prompt = f"""Identify 3-5 main themes from these conversation segment summaries.
Return as a list of single words or short phrases.

Summaries:
{summaries_text}

Themes:"""

        result = await self.model.generate(prompt)

        themes = []
        for line in result.text.strip().split("\n"):
            theme = line.strip().lstrip("-*• ").strip().lower()
            if theme and len(theme) < 30:
                themes.append(theme)

        return themes[:5]

    async def generate_executive_summary(self, summaries: Sequence[str]) -> str:
        """Create a high-level executive summary from multiple chunk summaries.

        Args:
            summaries: List of chunk summaries

        Returns:
            Executive summary string
        """
        if not self.model:
            return " | ".join(summaries[:3])

        summaries_text = "\n".join(f"- {s}" for s in summaries)

        prompt = f"""Create a high-level executive summary (3-4 sentences).
Focus on: main accomplishments, key decisions, and important context.

Segment summaries:
{summaries_text}

Executive summary:"""

        result = await self.model.generate(prompt)
        return result.text.strip()
