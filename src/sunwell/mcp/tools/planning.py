"""MCP planning tools for Sunwell.

Provides tools for intent classification, execution planning,
and reasoned decision-making.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import (
    DEFAULT_FORMAT,
    mcp_json,
    omit_empty,
    resolve_format,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime


def register_planning_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register planning-related tools.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and async bridging
    """

    @mcp.tool()
    def sunwell_plan(
        goal: str,
        project: str | None = None,
        domain: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Generate an execution plan for a goal without executing it.

        Creates a task graph with estimated duration, recommended lens/tools,
        and validation gates.

        Formats:
        - "summary": task count + estimated seconds only (~50 tokens)
        - "compact": task list with titles and deps (default)
        - "full": full task graph with metrics and signals

        Args:
            goal: The goal to plan for (natural language)
            project: Optional project path
            domain: Optional domain hint (code, research, writing, data)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with task graph, metrics, estimated duration, and recommendations
        """
        fmt = resolve_format(format)

        try:
            from sunwell.agent.core.agent import Agent
            from sunwell.memory.facade import PersistentMemory
            from sunwell.models.registry.registry import resolve_model

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            model = resolve_model("default")
            if not model:
                return mcp_json({"error": "No model available for planning"}, fmt)

            memory = runtime.memory if runtime else PersistentMemory.load(ws)

            agent = Agent(model=model)
            result = runtime.run(agent.plan_only(goal, memory=memory)) if runtime else None

            if result is None:
                return mcp_json({"error": "Runtime not available for async planning"}, fmt)

            # Extract task count
            task_count = 0
            if result.task_graph and hasattr(result.task_graph, "tasks"):
                task_count = len(result.task_graph.tasks)

            if fmt == "summary":
                return mcp_json(omit_empty({
                    "goal": goal,
                    "task_count": task_count,
                    "estimated_seconds": result.estimated_seconds,
                }), fmt)

            # Extract task graph info
            tasks = []
            if result.task_graph and hasattr(result.task_graph, "tasks"):
                for task in result.task_graph.tasks:
                    entry = omit_empty({
                        "id": getattr(task, "id", None),
                        "title": getattr(task, "title", getattr(task, "description", str(task))),
                        "depends_on": list(getattr(task, "depends_on", ())),
                    })
                    if fmt == "full":
                        entry["estimated_seconds"] = getattr(task, "estimated_seconds", None)
                    tasks.append(entry)

            data: dict = {
                "goal": goal,
                "tasks": tasks,
                "task_count": task_count,
                "estimated_seconds": result.estimated_seconds,
            }

            if fmt == "full":
                # Extract metrics
                metrics = {}
                if result.metrics:
                    for field in ("depth", "width", "parallelism_factor", "total_tasks", "critical_path_length"):
                        val = getattr(result.metrics, field, None)
                        if val is not None:
                            metrics[field] = val
                data["metrics"] = metrics
                data["signals"] = omit_empty({
                    "intent": getattr(result.signals, "intent", None) if result.signals else None,
                    "complexity": getattr(result.signals, "complexity", None) if result.signals else None,
                })

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "goal": goal}, fmt)

    @mcp.tool()
    def sunwell_classify(
        input: str,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Classify intent and complexity of an input.

        Uses Sunwell's UnifiedRouter to determine intent, complexity,
        recommended lens/tools, mood, expertise, and execution tier.

        Formats:
        - "summary": intent + complexity + confidence only (~50 tokens)
        - "compact": core routing fields (default)
        - "full": everything including reasoning, exemplars, breakdowns

        Args:
            input: The user input or goal to classify
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with intent, complexity, lens, tools, mood, expertise, and confidence
        """
        fmt = resolve_format(format)

        try:
            from sunwell.planning.routing.unified import create_unified_router

            router = create_unified_router()

            if not runtime:
                return mcp_json({"error": "Runtime not available for async classification"}, fmt)

            decision = runtime.run(router.route(input))

            intent = str(decision.intent.value) if hasattr(decision.intent, "value") else str(decision.intent)
            complexity = str(decision.complexity.value) if hasattr(decision.complexity, "value") else str(decision.complexity)
            confidence = round(decision.confidence, 3)

            if fmt == "summary":
                return mcp_json({
                    "intent": intent,
                    "complexity": complexity,
                    "confidence": confidence,
                }, fmt)

            data = omit_empty({
                "input": input,
                "intent": intent,
                "complexity": complexity,
                "tier": str(decision.tier.value) if hasattr(decision.tier, "value") else str(decision.tier),
                "lens": decision.lens,
                "tools": list(decision.tools),
                "mood": str(decision.mood.value) if hasattr(decision.mood, "value") else str(decision.mood),
                "expertise": str(decision.expertise.value) if hasattr(decision.expertise, "value") else str(decision.expertise),
                "confidence": confidence,
                "focus": list(decision.focus),
                "suggested_skills": list(decision.suggested_skills),
            })

            if fmt == "full":
                data["reasoning"] = decision.reasoning
                data["skill_confidence"] = round(decision.skill_confidence, 3) if decision.skill_confidence else None
                data["confidence_breakdown"] = decision.confidence_breakdown
                data["matched_exemplar"] = decision.matched_exemplar

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "input": input}, fmt)

    @mcp.tool()
    def sunwell_reason(
        question: str,
        options: list[str] | None = None,
        context: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Get a reasoned decision on an open question.

        Uses Sunwell's Reasoner (LLM-driven judgment) to make a decision
        with explicit reasoning, confidence scoring, and rationale.

        Formats:
        - "summary": outcome + confidence only (~50 tokens)
        - "compact": outcome + confidence + rationale (default)
        - "full": everything including similar decisions and context used

        Args:
            question: The question or decision to reason about
            options: Optional list of options to choose between
            context: Optional context to consider
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with decision outcome, confidence, rationale, and reasoning
        """
        fmt = resolve_format(format)

        try:
            from sunwell.planning.reasoning.decisions import DecisionType
            from sunwell.planning.reasoning.reasoner import Reasoner
            from sunwell.models.registry.registry import resolve_model

            model = resolve_model("default")
            if not model:
                return mcp_json({"error": "No model available for reasoning"}, fmt)

            reasoner = Reasoner(model=model)

            decision_context: dict = {"question": question}
            if options:
                decision_context["options"] = options
            if context:
                decision_context["additional_context"] = context

            if not runtime:
                return mcp_json({"error": "Runtime not available for async reasoning"}, fmt)

            result = runtime.run(
                reasoner.decide(
                    decision_type=DecisionType.SEVERITY_ASSESSMENT,
                    context=decision_context,
                    force_reasoning=True,
                )
            )

            outcome = str(result.outcome)
            confidence = round(result.confidence, 3)

            if fmt == "summary":
                return mcp_json({
                    "outcome": outcome,
                    "confidence": confidence,
                    "is_confident": result.is_confident,
                }, fmt)

            data: dict = {
                "question": question,
                "outcome": outcome,
                "confidence": confidence,
                "confidence_level": result.confidence_level,
                "is_confident": result.is_confident,
                "rationale": result.rationale,
            }

            if fmt == "full":
                data["similar_decisions"] = list(result.similar_decisions)
                data["context_used"] = list(result.context_used)

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "question": question}, fmt)
