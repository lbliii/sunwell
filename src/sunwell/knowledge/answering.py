"""Question answering using SmartContext (RFC-135).

Provides shared functionality for answering questions about the codebase.
Used by both the goal command and chat loop for CONVERSATION intents.

This module combines:
- SmartContext: Semantic code search for relevant context
- LLM: Answer generation from context

Example:
    >>> answer = await answer_question("where is auth used?", workspace, model)
    >>> print(answer)
    "Authentication is handled in src/auth/oauth.py:..."
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """Result of question answering.

    Contains the answer text, source context, and metadata.
    """

    answer: str
    """The generated answer."""

    sources: tuple[str, ...]
    """Source file references used to generate the answer."""

    confidence: float
    """Confidence in the answer (based on context relevance)."""

    context_used: str
    """The code context passed to the model (for debugging)."""


async def answer_question(
    question: str,
    workspace: Path,
    model: ModelProtocol,
    *,
    max_sources: int = 5,
    max_content_per_source: int = 500,
) -> AnswerResult | None:
    """Answer a question about the codebase using SmartContext.

    Uses semantic code search to find relevant context, then generates
    a response using the provided model. This is the fast path for
    CONVERSATION intents in RFC-135 unified routing.

    Args:
        question: The user's question
        workspace: Workspace path for code search
        model: Model for answer generation
        max_sources: Maximum number of source files to include
        max_content_per_source: Maximum characters per source snippet

    Returns:
        AnswerResult with answer and metadata, or None if no relevant context found.

    Example:
        >>> result = await answer_question("where is flask used?", workspace, model)
        >>> if result:
        ...     print(result.answer)
        ...     for source in result.sources:
        ...         print(f"  - {source}")
    """
    from sunwell.knowledge.indexing import create_smart_context
    from sunwell.models import Message

    try:
        # Use SmartContext for semantic code search
        smart_ctx = await create_smart_context(workspace, model)

        # Search for relevant context
        results = await smart_ctx.search(question, limit=max_sources * 2)

        if not results:
            return None  # No results, caller should fallback to planning

        # Build context from search results
        context_parts: list[str] = []
        sources: list[str] = []

        for result in results[:max_sources]:
            source_ref = f"{result.file_path}:{result.start_line}-{result.end_line}"
            sources.append(source_ref)
            context_parts.append(f"**{source_ref}**")
            context_parts.append(f"```\n{result.content[:max_content_per_source]}\n```\n")

        context = "\n".join(context_parts)

        # Generate answer using the model
        messages = (
            Message(
                role="system",
                content=(
                    "You are a code assistant. Answer the user's question based on "
                    "the code context provided. Be concise and reference specific "
                    "files/lines when relevant. If the context doesn't contain "
                    "enough information to answer the question, say so."
                ),
            ),
            Message(
                role="user",
                content=f"Question: {question}\n\nRelevant code:\n{context}",
            ),
        )

        response = await model.generate(messages)

        # Calculate confidence based on number of relevant results
        confidence = min(len(results) / max_sources, 1.0)

        return AnswerResult(
            answer=response.text,
            sources=tuple(sources),
            confidence=confidence,
            context_used=context,
        )

    except Exception:
        # On any failure, return None to trigger fallback
        return None


async def answer_question_simple(
    question: str,
    workspace: Path,
    model: ModelProtocol,
) -> str | None:
    """Simple wrapper that returns just the answer text.

    Convenience function for callers that don't need metadata.

    Args:
        question: The user's question
        workspace: Workspace path for code search
        model: Model for answer generation

    Returns:
        The answer text, or None if no relevant context found.
    """
    result = await answer_question(question, workspace, model)
    return result.answer if result else None


# =============================================================================
# Goal-Aware Context Enrichment (Phase 1b)
# =============================================================================


async def enrich_context_for_goal(
    goal: str,
    workspace: Path,
    model: ModelProtocol,
    base_context: str,
    *,
    max_chunks: int = 5,
    max_content_per_chunk: int = 500,
) -> str:
    """Enrich workspace context with goal-relevant code snippets.

    Uses SmartContext to find existing code related to the goal,
    so artifact planning can generate consistent artifacts that match
    the existing codebase patterns.

    This is critical for tasks on existing projects - without this,
    the planner might generate Flask artifacts when the project uses
    FastAPI, or create duplicate functionality.

    Args:
        goal: The user's goal/task
        workspace: Workspace path for code search
        model: Model for semantic search
        base_context: Base workspace context from SessionContext
        max_chunks: Maximum number of code chunks to include
        max_content_per_chunk: Maximum characters per chunk

    Returns:
        Enriched context with relevant existing code snippets.
        Falls back to base_context if search fails.

    Example:
        >>> base = session.to_planning_prompt()  # "Project: my-api, Type: Python"
        >>> enriched = await enrich_context_for_goal(
        ...     "add user authentication", workspace, model, base
        ... )
        >>> # Now enriched includes:
        >>> # "## Relevant Existing Code
        >>> #  **src/auth/oauth.py:1-25**
        >>> #  from fastapi.security import OAuth2PasswordBearer..."
    """
    from sunwell.knowledge.indexing import create_smart_context

    try:
        # Use SmartContext for semantic code search
        smart_ctx = await create_smart_context(workspace, model)

        # Search for code relevant to the goal
        results = await smart_ctx.search(goal, limit=max_chunks * 2)

        if not results:
            return base_context  # No relevant code found

        # Build enriched context
        lines: list[str] = [base_context, "", "## Relevant Existing Code", ""]

        for chunk in results[:max_chunks]:
            source_ref = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            lines.append(f"**{source_ref}**")
            # Truncate content if needed
            content = chunk.content
            if len(content) > max_content_per_chunk:
                content = content[:max_content_per_chunk] + "\n... (truncated)"
            lines.append(f"```\n{content}\n```")
            lines.append("")

        return "\n".join(lines)

    except Exception:
        # On any failure, return base context unchanged
        return base_context
