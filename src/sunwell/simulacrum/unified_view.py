"""Unified Memory View - RFC-026.

Provides a single pane of glass for viewing all memory types:
- Facts/Learnings from DAG
- Observations from Identity Store
- Active topics from Simulacrum

Example:
    >>> view = UnifiedMemoryView.from_session(
    ...     dag=dag,
    ...     identity_store=identity_store,
    ...     session_name="writer",
    ... )
    >>> print(view.render_panel())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.simulacrum.core.dag import ConversationDAG, Learning
    from sunwell.identity.store import IdentityStore


@dataclass
class Fact:
    """A fact extracted from memory."""
    
    content: str
    category: str
    confidence: float
    source: str = "dag"
    quality_score: float | None = None
    issues: list[str] = field(default_factory=list)


@dataclass  
class UnifiedMemoryView:
    """Aggregates all memory sources into single view.
    
    This is the "single pane of glass" for viewing what Sunwell knows
    about the user and the current session.
    """
    
    # From DAG
    facts: list[Fact] = field(default_factory=list)
    turns_count: int = 0
    
    # From Identity Store
    observations: list[dict[str, Any]] = field(default_factory=list)
    identity_prompt: str | None = None
    identity_confidence: float = 0.0
    
    # Metadata
    session_name: str = ""
    global_identity_loaded: bool = False
    
    @classmethod
    def from_session(
        cls,
        dag: "ConversationDAG | None" = None,
        identity_store: "IdentityStore | None" = None,
        session_name: str = "",
    ) -> "UnifiedMemoryView":
        """Load unified view from session components.
        
        Args:
            dag: ConversationDAG with facts/learnings
            identity_store: IdentityStore with observations
            session_name: Name of the current session
            
        Returns:
            UnifiedMemoryView aggregating all sources
        """
        view = cls(session_name=session_name)
        
        # Load facts from DAG
        if dag:
            view.turns_count = len(dag.turns)
            for learning in dag.get_active_learnings():
                fact = Fact(
                    content=learning.fact,
                    category=learning.category,
                    confidence=learning.confidence,
                    source="dag",
                )
                # Quality scoring
                fact.quality_score, fact.issues = score_fact_quality(learning.fact, learning.confidence)
                view.facts.append(fact)
        
        # Load identity
        if identity_store:
            identity = identity_store.identity
            view.observations = [
                {
                    "behavior": obs.behavior,
                    "count": obs.count,
                    "category": obs.category,
                }
                for obs in identity.observations
            ]
            view.identity_prompt = identity.prompt
            view.identity_confidence = identity.confidence
            view.global_identity_loaded = True
        
        return view
    
    def render_panel(self) -> str:
        """Render as text for terminal display.
        
        Returns a Rich-compatible string with the memory summary.
        """
        lines = []
        
        # Header
        lines.append(f"[bold cyan]🧠 MEMORY: {self.session_name or 'default'}[/bold cyan]")
        lines.append("")
        
        # Facts section
        if self.facts:
            lines.append(f"[bold]FACTS ({len(self.facts)})[/bold]")
            for fact in self.facts[:10]:  # Show top 10
                status = "✅" if fact.quality_score and fact.quality_score >= 0.7 else "⚠️"
                conf = f"{int(fact.confidence * 100)}%"
                lines.append(f"  {status} {fact.content[:60]:<60} [{fact.category}] {conf}")
            if len(self.facts) > 10:
                lines.append(f"  [dim]... and {len(self.facts) - 10} more[/dim]")
            lines.append("")
        else:
            lines.append("[dim]No facts learned yet[/dim]")
            lines.append("")
        
        # Identity section
        if self.identity_prompt:
            conf_pct = int(self.identity_confidence * 100)
            lines.append(f"[bold]IDENTITY (confidence: {conf_pct}%)[/bold]")
            # Truncate if too long
            prompt_preview = self.identity_prompt[:200]
            if len(self.identity_prompt) > 200:
                prompt_preview += "..."
            lines.append(f"  [italic]{prompt_preview}[/italic]")
            lines.append("")
        
        # Behaviors section
        if self.observations:
            lines.append(f"[bold]BEHAVIORS ({len(self.observations)} observations)[/bold]")
            for obs in self.observations[:5]:
                lines.append(f"  • {obs['behavior']} ({obs['count']}x)")
            if len(self.observations) > 5:
                lines.append(f"  [dim]... and {len(self.observations) - 5} more[/dim]")
            lines.append("")
        
        # Stats
        lines.append(f"[dim]Turns: {self.turns_count} | Global identity: {'✓' if self.global_identity_loaded else '✗'}[/dim]")
        
        return "\n".join(lines)
    
    def to_json(self) -> dict[str, Any]:
        """Export as JSON-serializable dict."""
        return {
            "session_name": self.session_name,
            "turns_count": self.turns_count,
            "facts": [
                {
                    "content": f.content,
                    "category": f.category,
                    "confidence": f.confidence,
                    "quality_score": f.quality_score,
                    "issues": f.issues,
                }
                for f in self.facts
            ],
            "observations": self.observations,
            "identity": {
                "prompt": self.identity_prompt,
                "confidence": self.identity_confidence,
            },
            "global_identity_loaded": self.global_identity_loaded,
        }


def score_fact_quality(fact: str, confidence: float) -> tuple[float, list[str]]:
    """Score fact quality and return issues.
    
    Heuristics to flag suspicious facts:
    - Too short
    - Looks like category echo (extraction bug)
    - Too generic
    
    Returns:
        Tuple of (quality_score, list_of_issues)
    """
    import re
    
    issues = []
    score = confidence
    
    # Too short
    if len(fact) < 10:
        score -= 0.2
        issues.append("very short")
    
    # Looks like category echo (extraction bug pattern)
    if re.match(r"^[A-Z][a-z]+\s*\(", fact):
        score -= 0.3
        issues.append("looks like category echo")
    
    # Too generic
    generic_patterns = ["user is back", "none", "nothing", "n/a", "unknown"]
    if fact.lower().strip() in generic_patterns:
        score -= 0.4
        issues.append("too generic")
    
    return max(0.0, score), issues
