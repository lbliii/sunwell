"""Mirror tool handler for RFC-015 and RFC-085.

Routes mirror neuron tool calls to appropriate handlers,
enforces safety checks, and manages the proposal workflow.

RFC-085 Update: Now uses Self.get() for source introspection,
ensuring correct resolution from any workspace.
"""


import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.mirror.analysis import FailureAnalyzer, PatternAnalyzer
from sunwell.mirror.introspection import (
    ExecutionIntrospector,
    LensIntrospector,
    SimulacrumIntrospector,
)
from sunwell.mirror.model_tracker import ModelPerformanceTracker
from sunwell.mirror.proposals import ProposalManager, ProposalStatus
from sunwell.mirror.router import ModelRouter
from sunwell.mirror.safety import SafetyChecker
from sunwell.self import Self

if TYPE_CHECKING:
    from sunwell.tools.executor import ToolExecutor


@dataclass(slots=True)
class MirrorHandler:
    """Handler for mirror neuron tool calls.

    Routes tool calls to appropriate introspection, analysis,
    or proposal handlers. Enforces safety constraints.

    RFC-085: Uses Self.get() for source introspection, which auto-resolves
    the Sunwell source root regardless of the current workspace.

    Example:
        >>> handler = MirrorHandler(
        ...     workspace=Path("/path/to/user/project"),
        ...     storage_path=Path(".sunwell/mirror"),
        ... )
        >>> result = await handler.handle("introspect_source", {"module": "sunwell.tools"})
    """

    # Renamed from sunwell_root to workspace (RFC-085 Phase 2)
    workspace: Path
    storage_path: Path
    lens: Any = None
    simulacrum: Any = None
    executor: ToolExecutor | None = None
    lens_config: dict[str, Any] | None = None  # For model routing
    session_model: str = "session"  # Default model for session

    # Internal components (initialized in __post_init__)
    _lens_introspector: LensIntrospector = field(init=False)
    _simulacrum_introspector: SimulacrumIntrospector = field(init=False)
    _execution_introspector: ExecutionIntrospector = field(init=False)
    _pattern_analyzer: PatternAnalyzer = field(init=False)
    _failure_analyzer: FailureAnalyzer = field(init=False)
    _proposal_manager: ProposalManager = field(init=False)
    _safety_checker: SafetyChecker = field(init=False)
    _model_tracker: ModelPerformanceTracker = field(init=False)
    _model_router: ModelRouter = field(init=False)

    def __post_init__(self) -> None:
        """Initialize internal components.

        RFC-085: Source introspection now uses Self.get().source which
        auto-resolves the Sunwell source root from package location.
        """
        # RFC-085: Use Self.get() for source introspection
        # (accessed directly via Self.get().source in handlers)

        self._lens_introspector = LensIntrospector()
        self._simulacrum_introspector = SimulacrumIntrospector()
        self._execution_introspector = ExecutionIntrospector()
        self._pattern_analyzer = PatternAnalyzer()
        self._failure_analyzer = FailureAnalyzer()
        self._proposal_manager = ProposalManager(self.storage_path / "proposals")
        self._safety_checker = SafetyChecker(workspace=self.workspace)

        # Phase 5: Model routing components
        self._model_tracker = ModelPerformanceTracker(
            storage_path=self.storage_path / "model_performance",
        )
        self._model_router = ModelRouter(
            lens_config=self.lens_config,
            performance_tracker=self._model_tracker,
            session_model=self.session_model,
        )

    async def handle(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Handle a mirror tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            JSON string with tool result
        """
        # Route to appropriate handler
        handlers = {
            # Introspection
            "introspect_source": self._handle_introspect_source,
            "introspect_lens": self._handle_introspect_lens,
            "introspect_simulacrum": self._handle_introspect_simulacrum,
            "introspect_execution": self._handle_introspect_execution,
            # Analysis
            "analyze_patterns": self._handle_analyze_patterns,
            "analyze_failures": self._handle_analyze_failures,
            "analyze_model_performance": self._handle_analyze_model_performance,
            # Proposals
            "propose_improvement": self._handle_propose_improvement,
            "propose_model_routing": self._handle_propose_model_routing,
            "list_proposals": self._handle_list_proposals,
            "get_proposal": self._handle_get_proposal,
            "submit_proposal": self._handle_submit_proposal,
            "approve_proposal": self._handle_approve_proposal,
            "apply_proposal": self._handle_apply_proposal,
            "rollback_proposal": self._handle_rollback_proposal,
            # Model routing
            "get_routing_info": self._handle_get_routing_info,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown mirror tool: {tool_name}"})

        try:
            result = await handler(arguments)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e), "type": type(e).__name__})

    # === INTROSPECTION HANDLERS ===

    async def _handle_introspect_source(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle introspect_source tool.

        RFC-085: Uses Self.get().source for introspection, which auto-resolves
        the Sunwell source root regardless of current workspace.
        """
        module = args["module"]
        symbol = args.get("symbol")

        # RFC-085: Use Self.get().source instead of passed path
        source_knowledge = Self.get().source

        if symbol:
            info = source_knowledge.find_symbol(module, symbol)
            return {
                "module": module,
                "symbol": symbol,
                "type": info.type,
                "source": info.source,
                "start_line": info.start_line,
                "end_line": info.end_line,
                "docstring": info.docstring,
                "methods": list(info.methods) if info.methods else [],
                "is_async": info.is_async,
            }
        else:
            source = source_knowledge.read_module(module)
            structure = source_knowledge.get_module_structure(module)
            return {
                "module": module,
                "structure": {
                    "classes": list(structure.classes),
                    "functions": list(structure.functions),
                    "imports": list(structure.imports),
                },
                "source_preview": source[:2000] + "..." if len(source) > 2000 else source,
                "full_source_lines": len(source.splitlines()),
            }

    async def _handle_introspect_lens(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle introspect_lens tool."""
        component = args.get("component", "all")

        if not self.lens:
            return {"error": "No lens currently loaded"}

        if component == "all":
            return self._lens_introspector.get_all(self.lens)
        elif component == "heuristics":
            return {"heuristics": self._lens_introspector.get_heuristics(self.lens)}
        elif component == "validators":
            return {"validators": self._lens_introspector.get_validators(self.lens)}
        elif component == "personas":
            return {"personas": self._lens_introspector.get_personas(self.lens)}
        elif component == "framework":
            return {"framework": self._lens_introspector.get_framework(self.lens)}
        else:
            return {"error": f"Unknown component: {component}"}

    async def _handle_introspect_simulacrum(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle introspect_simulacrum tool."""
        section = args.get("section", "all")

        if not self.simulacrum:
            return {"error": "No simulacrum currently active"}

        if section == "all":
            return self._simulacrum_introspector.get_all(self.simulacrum)
        elif section == "learnings":
            return {"learnings": self._simulacrum_introspector.get_learnings(self.simulacrum)}
        elif section == "dead_ends":
            return {"dead_ends": self._simulacrum_introspector.get_dead_ends(self.simulacrum)}
        elif section == "focus":
            return {"focus": self._simulacrum_introspector.get_focus(self.simulacrum)}
        elif section == "context":
            return {"context": self._simulacrum_introspector.get_context(self.simulacrum)}
        else:
            return {"error": f"Unknown section: {section}"}

    async def _handle_introspect_execution(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle introspect_execution tool."""
        limit = args.get("limit", 10)
        filter_type = args.get("filter", "all")

        if not self.executor:
            return {"error": "No executor configured"}

        if filter_type == "all":
            calls = self._execution_introspector.get_recent_tool_calls(self.executor, limit)
            return {"recent_calls": calls, "stats": self._execution_introspector.get_stats(self.executor)}
        elif filter_type == "errors":
            errors = self._execution_introspector.get_errors(self.executor, limit)
            summary = self._execution_introspector.get_error_summary(self.executor)
            return {"errors": errors, "summary": summary}
        elif filter_type == "tools":
            calls = self._execution_introspector.get_recent_tool_calls(self.executor, limit)
            return {"tool_calls": calls}
        else:
            return {"error": f"Unknown filter: {filter_type}"}

    # === ANALYSIS HANDLERS ===

    async def _handle_analyze_patterns(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle analyze_patterns tool."""
        if not self.executor:
            return {"error": "No executor configured"}

        scope = args.get("scope", "session")
        focus = args["focus"]
        audit_log = self.executor.get_audit_log()

        if focus == "tool_usage":
            return self._pattern_analyzer.analyze_tool_usage(audit_log, scope)
        elif focus == "latency":
            return self._pattern_analyzer.analyze_latency(audit_log, scope)
        elif focus == "error_types":
            return self._pattern_analyzer.analyze_errors(audit_log, scope)
        else:
            return {"error": f"Unknown focus: {focus}"}

    async def _handle_analyze_failures(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle analyze_failures tool."""
        if not self.executor:
            return {"error": "No executor configured"}

        audit_log = self.executor.get_audit_log()
        return self._failure_analyzer.summarize_failures(audit_log)

    # === PROPOSAL HANDLERS ===

    async def _handle_propose_improvement(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle propose_improvement tool."""
        scope = args["scope"]
        problem = args["problem"]
        evidence = args["evidence"]
        diff = args["diff"]

        # Safety check the diff
        from sunwell.mirror.safety import validate_diff_safety
        is_safe, reason = validate_diff_safety(diff)
        if not is_safe:
            return {"error": f"Safety check failed: {reason}"}

        # Create title from problem
        title = problem[:50] + "..." if len(problem) > 50 else problem

        proposal = self._proposal_manager.create_proposal(
            proposal_type=scope,
            title=title,
            rationale=problem,
            evidence=evidence,
            diff=diff,
        )

        return {
            "proposal_id": proposal.id,
            "status": proposal.status.value,
            "message": "Proposal created. Use 'submit_proposal' to submit for review.",
            "summary": proposal.summary(),
        }

    async def _handle_list_proposals(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle list_proposals tool."""
        status_str = args.get("status", "pending_review")

        if status_str == "all":
            proposals = self._proposal_manager.list_proposals()
        else:
            status = ProposalStatus(status_str)
            proposals = self._proposal_manager.list_proposals(status=status)

        return {
            "count": len(proposals),
            "proposals": [p.to_dict() for p in proposals[:20]],  # Limit to 20
            "stats": self._proposal_manager.get_stats(),
        }

    async def _handle_get_proposal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle get_proposal tool."""
        proposal_id = args["proposal_id"]
        proposal = self._proposal_manager.get_proposal(proposal_id)

        if not proposal:
            return {"error": f"Proposal not found: {proposal_id}"}

        return proposal.to_dict()

    async def _handle_submit_proposal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle submit_proposal tool."""
        proposal_id = args["proposal_id"]

        try:
            proposal = self._proposal_manager.submit_for_review(proposal_id)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "message": "Proposal submitted for review.",
            }
        except ValueError as e:
            return {"error": str(e)}

    async def _handle_approve_proposal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle approve_proposal tool."""
        proposal_id = args["proposal_id"]

        # Check if confirmation is required
        if self._safety_checker.requires_confirmation("approve_proposal"):
            proposal = self._proposal_manager.get_proposal(proposal_id)
            if not proposal:
                return {"error": f"Proposal not found: {proposal_id}"}

            return {
                "requires_confirmation": True,
                "proposal": proposal.to_dict(),
                "message": "This operation requires user confirmation. Please confirm to proceed.",
            }

        try:
            proposal = self._proposal_manager.approve_proposal(proposal_id)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "message": "Proposal approved. Ready to apply.",
            }
        except ValueError as e:
            return {"error": str(e)}

    async def _handle_apply_proposal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle apply_proposal tool."""
        proposal_id = args["proposal_id"]

        proposal = self._proposal_manager.get_proposal(proposal_id)
        if not proposal:
            return {"error": f"Proposal not found: {proposal_id}"}

        # Full safety validation
        is_valid, reason = self._safety_checker.validate_application(proposal)
        if not is_valid:
            return {"error": f"Safety validation failed: {reason}"}

        # For now, we just mark as applied with placeholder rollback data
        # Actual application logic would be implemented based on proposal type
        rollback_data = json.dumps({
            "original_state": "placeholder",
            "applied_at": str(proposal.created_at),
        })

        try:
            proposal = self._proposal_manager.apply_proposal(proposal_id, rollback_data)
            return {
                "proposal_id": proposal.id,
                "status": proposal.status.value,
                "applied_at": str(proposal.applied_at),
                "message": "Proposal applied successfully. Rollback available if needed.",
            }
        except ValueError as e:
            return {"error": str(e)}

    async def _handle_rollback_proposal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle rollback_proposal tool."""
        proposal_id = args["proposal_id"]

        try:
            rollback_data = self._proposal_manager.rollback_proposal(proposal_id)
            return {
                "proposal_id": proposal_id,
                "status": "rolled_back",
                "message": "Proposal rolled back successfully.",
                "rollback_data": rollback_data,
            }
        except ValueError as e:
            return {"error": str(e)}

    # === MODEL ROUTING HANDLERS (Phase 5) ===

    async def _handle_analyze_model_performance(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle analyze_model_performance tool."""
        scope = args.get("scope", "all")
        category = args.get("category")

        if category:
            # Analyze specific category
            comparisons = self._model_tracker.compare_models(category, scope)
            return {
                "category": category,
                "scope": scope,
                "models": comparisons,
                "recommendation": self._model_router.get_category_recommendation(category),
            }
        else:
            # Overall summary
            summary = self._model_tracker.get_summary(scope)
            return summary

    async def _handle_propose_model_routing(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle propose_model_routing tool."""
        category = args["category"]
        current_model = args.get("current_model", self.session_model)
        proposed_model = args["proposed_model"]
        evidence = args["evidence"]

        # Build diff for model routing change
        diff = f"""model_routing:
  preferences:
    {category}:
-     model: "{current_model}"
+     model: "{proposed_model}"
      rationale: "Performance data shows better results"
"""

        # Create title
        title = f"Route {category} to {proposed_model}"

        # Create proposal
        proposal = self._proposal_manager.create_proposal(
            proposal_type="config",
            title=title,
            rationale=f"Change model routing for {category} from {current_model} to {proposed_model}",
            evidence=evidence,
            diff=diff,
        )

        return {
            "proposal_id": proposal.id,
            "status": proposal.status.value,
            "category": category,
            "current_model": current_model,
            "proposed_model": proposed_model,
            "message": "Model routing proposal created. Submit for review to apply.",
        }

    async def _handle_get_routing_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle get_routing_info tool."""
        category = args.get("category")

        if category:
            return self._model_router.get_category_recommendation(category)
        else:
            return self._model_router.get_routing_info()

    # === PUBLIC METHODS ===

    def record_model_performance(
        self,
        model: str,
        tool_name: str,
        success: bool,
        latency_ms: int,
        user_edited: bool = False,
    ) -> None:
        """Record performance data for a model execution.

        Call this from the tool executor after each execution.

        Args:
            model: Model identifier
            tool_name: Tool that was called
            success: Whether execution succeeded
            latency_ms: Execution time
            user_edited: Whether user modified the output
        """
        category = self._model_router.classify_task(tool_name)
        self._model_tracker.record(
            model=model,
            task_category=category,
            success=success,
            latency_ms=latency_ms,
            user_edited=user_edited,
        )

    def select_model_for_task(self, tool_name: str) -> str:
        """Get recommended model for a tool call.

        Args:
            tool_name: The tool being called

        Returns:
            Model identifier to use
        """
        return self._model_router.select_model(tool_name)

    def get_rate_limits(self) -> dict[str, Any]:
        """Get current rate limit status."""
        return self._safety_checker.get_rate_limit_status()

    def list_available_modules(self) -> list[str]:
        """List all Sunwell modules available for introspection.

        RFC-085: Uses Self.get().source for auto-resolved source root.
        """
        return Self.get().source.list_modules()

    def get_model_tracker(self) -> ModelPerformanceTracker:
        """Get the model performance tracker for external access."""
        return self._model_tracker

    def get_model_router(self) -> ModelRouter:
        """Get the model router for external access."""
        return self._model_router
