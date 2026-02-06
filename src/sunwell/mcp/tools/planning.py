"""MCP planning tools for Sunwell.

Provides tools for intent classification, execution planning,
and reasoned decision-making.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_planning_tools(mcp: FastMCP, workspace: str | None = None) -> None:
    """Register planning-related tools.

    Args:
        mcp: FastMCP server instance
        workspace: Optional workspace root path
    """

    def _resolve_workspace(project: str | None = None) -> Path:
        if project:
            p = Path(project).expanduser().resolve()
            if p.exists():
                return p
        if workspace:
            return Path(workspace).expanduser().resolve()
        return Path.cwd()

    @mcp.tool()
    def sunwell_plan(
        goal: str,
        project: str | None = None,
        domain: str | None = None,
    ) -> str:
        """
        Generate an execution plan for a goal without executing it.

        Creates a task graph with estimated duration, recommended lens/tools,
        and validation gates. This is a dry-run of Sunwell's full planning
        pipeline. Useful for understanding how Sunwell would approach a task.

        Args:
            goal: The goal to plan for (natural language)
            project: Optional project path
            domain: Optional domain hint (code, research, writing, data)

        Returns:
            JSON with task graph, metrics, estimated duration, and recommendations
        """
        import asyncio

        try:
            from sunwell.agent.core.agent import Agent
            from sunwell.memory.facade import PersistentMemory
            from sunwell.models.registry.registry import resolve_model

            ws = _resolve_workspace(project)
            model = resolve_model("default")
            if not model:
                return json.dumps(
                    {"error": "No model available for planning", "hint": "Configure a model"},
                    indent=2,
                )

            # Load memory for context-aware planning
            memory = PersistentMemory.load(ws)

            agent = Agent(model=model)
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(agent.plan_only(goal, memory=memory))
            finally:
                loop.close()

            # Extract task graph info
            tasks = []
            if result.task_graph and hasattr(result.task_graph, "tasks"):
                for task in result.task_graph.tasks:
                    tasks.append({
                        "id": getattr(task, "id", None),
                        "title": getattr(task, "title", getattr(task, "description", str(task))),
                        "depends_on": list(getattr(task, "depends_on", ())),
                        "estimated_seconds": getattr(task, "estimated_seconds", None),
                    })

            # Extract metrics
            metrics = {}
            if result.metrics:
                for field in ("depth", "width", "parallelism_factor", "total_tasks", "critical_path_length"):
                    val = getattr(result.metrics, field, None)
                    if val is not None:
                        metrics[field] = val

            return json.dumps(
                {
                    "goal": goal,
                    "tasks": tasks,
                    "task_count": len(tasks),
                    "metrics": metrics,
                    "estimated_seconds": result.estimated_seconds,
                    "signals": {
                        "intent": getattr(result.signals, "intent", None) if result.signals else None,
                        "complexity": getattr(result.signals, "complexity", None) if result.signals else None,
                    },
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "goal": goal}, indent=2)

    @mcp.tool()
    def sunwell_classify(input: str) -> str:
        """
        Classify intent and complexity of an input.

        Uses Sunwell's UnifiedRouter to determine:
        - Intent: CODE, EXPLAIN, DEBUG, CHAT, SEARCH, REVIEW
        - Complexity: TRIVIAL, STANDARD, COMPLEX
        - Recommended lens and tools
        - User mood and expertise detection
        - Execution tier: FAST, LIGHT, FULL

        Args:
            input: The user input or goal to classify

        Returns:
            JSON with intent, complexity, lens, tools, mood, expertise, and confidence
        """
        import asyncio

        try:
            from sunwell.planning.routing.unified import create_unified_router

            router = create_unified_router()

            loop = asyncio.new_event_loop()
            try:
                decision = loop.run_until_complete(router.route(input))
            finally:
                loop.close()

            return json.dumps(
                {
                    "input": input,
                    "intent": str(decision.intent.value) if hasattr(decision.intent, "value") else str(decision.intent),
                    "complexity": str(decision.complexity.value) if hasattr(decision.complexity, "value") else str(decision.complexity),
                    "tier": str(decision.tier.value) if hasattr(decision.tier, "value") else str(decision.tier),
                    "lens": decision.lens,
                    "tools": list(decision.tools),
                    "mood": str(decision.mood.value) if hasattr(decision.mood, "value") else str(decision.mood),
                    "expertise": str(decision.expertise.value) if hasattr(decision.expertise, "value") else str(decision.expertise),
                    "confidence": round(decision.confidence, 3),
                    "reasoning": decision.reasoning,
                    "focus": list(decision.focus),
                    "suggested_skills": list(decision.suggested_skills),
                    "skill_confidence": round(decision.skill_confidence, 3) if decision.skill_confidence else None,
                    "confidence_breakdown": decision.confidence_breakdown,
                    "matched_exemplar": decision.matched_exemplar,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "input": input}, indent=2)

    @mcp.tool()
    def sunwell_reason(
        question: str,
        options: list[str] | None = None,
        context: str | None = None,
    ) -> str:
        """
        Get a reasoned decision on an open question.

        Uses Sunwell's Reasoner (LLM-driven judgment) to make a decision
        with explicit reasoning, confidence scoring, and rationale.

        Good for:
        - "Should I use Redis or Memcached for this cache?"
        - "Is this code change safe to deploy?"
        - "Which approach minimizes risk?"

        Args:
            question: The question or decision to reason about
            options: Optional list of options to choose between
            context: Optional context to consider

        Returns:
            JSON with decision outcome, confidence, rationale, and reasoning
        """
        import asyncio

        try:
            from sunwell.planning.reasoning.decisions import DecisionType
            from sunwell.planning.reasoning.reasoner import Reasoner
            from sunwell.models.registry.registry import resolve_model

            model = resolve_model("default")
            if not model:
                return json.dumps(
                    {"error": "No model available for reasoning"},
                    indent=2,
                )

            reasoner = Reasoner(model=model)

            decision_context: dict = {"question": question}
            if options:
                decision_context["options"] = options
            if context:
                decision_context["additional_context"] = context

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    reasoner.decide(
                        decision_type=DecisionType.SEVERITY_ASSESSMENT,
                        context=decision_context,
                        force_reasoning=True,
                    )
                )
            finally:
                loop.close()

            return json.dumps(
                {
                    "question": question,
                    "outcome": str(result.outcome),
                    "confidence": round(result.confidence, 3),
                    "confidence_level": result.confidence_level,
                    "is_confident": result.is_confident,
                    "rationale": result.rationale,
                    "similar_decisions": list(result.similar_decisions),
                    "context_used": list(result.context_used),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "question": question}, indent=2)
