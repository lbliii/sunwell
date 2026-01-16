"""Summarization service for conversation history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from sunwell.simulacrum.turn import Turn
    from sunwell.models.protocol import ModelProtocol


@dataclass
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
        
        prompt = f"""Create a high-level executive summary (3-4 sentences) of this extended conversation.
Focus on: main accomplishments, key decisions, and important context.

Segment summaries:
{summaries_text}

Executive summary:"""
        
        result = await self.model.generate(prompt)
        return result.text.strip()
