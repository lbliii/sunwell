"""Shared event rendering for CLI interfaces.

Provides consistent Holy Light styling for agent events across
both chat and goal interfaces.

Uses RenderContext for hierarchical display:
- Tasks grouped with their gates
- Proper indentation and tree connectors
- Deferred/batched learnings
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sunwell.interface.cli.core.render_context import (
    RenderContext,
    RenderPhase,
    TREE,
    get_render_context,
    TimelineEvent,
)
from sunwell.interface.cli.core.theme import (
    CHARS_CHECKS,
    CHARS_CIRCLES,
    CHARS_DIAMONDS,
    CHARS_MISC,
    CHARS_PROGRESS,
    CHARS_STARS,
    console,
    render_alert,
    render_collapsible,
    render_confidence,
    render_decision,
    render_diff,
    render_error,
    render_streaming,
    render_timeline,
    Sparkle,
)

if TYPE_CHECKING:
    from rich.console import Console
    from sunwell.agent.events import AgentEvent


# =============================================================================
# HIERARCHICAL RENDERING HELPERS
# =============================================================================


def _render_phase_header_minimal(con: Console, phase: str, ctx: RenderContext) -> None:
    """Render a minimal phase header (no box, just icon + text)."""
    headers = {
        "understanding": f"[holy.radiant]{CHARS_STARS['radiant']}[/] Understanding",
        "illuminating": f"[holy.radiant]{CHARS_STARS['radiant']}[/] Planning",
        "crafting": f"[holy.radiant]{CHARS_STARS['radiant']}[/] Crafting",
        "verifying": f"[holy.radiant]{CHARS_STARS['radiant']}[/] Verifying",
        "complete": f"[holy.success]{CHARS_STARS['complete']}[/] Complete",
    }
    header = headers.get(phase, f"[holy.radiant]{CHARS_STARS['radiant']}[/] {phase.title()}")
    con.print(f"\n{header}")


def _render_task_header(con: Console, ctx: RenderContext) -> None:
    """Render task header with tree connector."""
    task = ctx.current_task
    if not task:
        return

    # Determine connector based on position
    is_last = ctx.is_last_task()
    connector = TREE["last"] if is_last else TREE["branch"]

    # Task description (truncate if needed)
    desc = task.description[:55] + "..." if len(task.description) > 55 else task.description

    con.print(
        f"  {connector} [holy.gold]Task {task.task_number}/{task.total_tasks}:[/] {desc}"
    )


def _render_task_result(con: Console, ctx: RenderContext, duration_ms: int) -> None:
    """Render task completion inline under the task."""
    task = ctx.current_task
    if not task:
        return

    # Continuation line based on whether this is the last task
    is_last_task = ctx.is_last_task()
    pipe = TREE["space"] if is_last_task else TREE["pipe"]

    # Format duration
    if duration_ms >= 1000:
        time_str = f"{duration_ms / 1000:.1f}s"
    else:
        time_str = f"{duration_ms}ms"

    con.print(
        f"  {pipe}  [holy.gold]{TREE['branch']}[/] write      "
        f"[holy.success]{CHARS_STARS['progress']}[/] [neutral.dim]{time_str}[/]"
    )


def _render_gate_inline(
    con: Console,
    ctx: RenderContext,
    gate_name: str,
    passed: bool,
    is_last_gate: bool = False,
) -> None:
    """Render a gate result inline under the current task."""
    task = ctx.current_task
    if not task:
        # Fallback: render at top level
        icon = CHARS_STARS["progress"] if passed else CHARS_CHECKS["fail"]
        style = "holy.success" if passed else "void.purple"
        con.print(f"  [{style}]{icon}[/] gate: {gate_name}")
        return

    # Continuation based on task position
    is_last_task = ctx.is_last_task()
    pipe = TREE["space"] if is_last_task else TREE["pipe"]

    # Gate connector
    gate_connector = TREE["last"] if is_last_gate else TREE["branch"]

    # Status
    icon = CHARS_STARS["progress"] if passed else CHARS_CHECKS["fail"]
    style = "holy.success" if passed else "void.purple"

    # Shorten gate name for display
    short_name = gate_name.replace("gate_", "").replace("post_tool_", "")

    con.print(
        f"  {pipe}  [holy.gold]{gate_connector}[/] gate       "
        f"[{style}]{icon}[/] [neutral.dim]{short_name}[/]"
    )


def _render_plan_skeleton(con: Console, task_summaries: list[dict]) -> None:
    """Render a preview skeleton of upcoming tasks."""
    if not task_summaries:
        return

    con.print()
    con.print(f"  [neutral.dim]Upcoming tasks:[/]")

    for i, task in enumerate(task_summaries[:8], 1):  # Limit to 8
        desc = task.get("description", "Task")[:50]
        category = task.get("category", "")
        is_last = i == len(task_summaries[:8])
        connector = TREE["last"] if is_last else TREE["branch"]

        category_str = f" [neutral.dim]({category})[/]" if category else ""
        con.print(f"  {connector} [neutral.dim]{i}. {desc}{category_str}[/]")

    if len(task_summaries) > 8:
        con.print(f"  [neutral.dim]    +{len(task_summaries) - 8} more tasks[/]")


def _render_tool_start(con: Console, ctx: RenderContext, tool_name: str) -> None:
    """Render tool call start (nested under task if active)."""
    if ctx.current_task:
        is_last_task = ctx.is_last_task()
        pipe = TREE["space"] if is_last_task else TREE["pipe"]
        con.print(f"  {pipe}  [neutral.dim]{CHARS_MISC['gear']} {tool_name}...[/]")
    else:
        con.print(f"  [neutral.dim]{CHARS_MISC['gear']} {tool_name}...[/]")


def _render_tool_complete(
    con: Console,
    ctx: RenderContext,
    tool_name: str,
    duration_ms: int,
) -> None:
    """Render tool call completion."""
    time_str = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.1f}s"
    if ctx.current_task:
        is_last_task = ctx.is_last_task()
        pipe = TREE["space"] if is_last_task else TREE["pipe"]
        con.print(
            f"  {pipe}  [holy.success]{CHARS_CHECKS['pass']}[/] "
            f"{tool_name} [neutral.dim]{time_str}[/]"
        )
    else:
        con.print(
            f"  [holy.success]{CHARS_CHECKS['pass']}[/] "
            f"{tool_name} [neutral.dim]{time_str}[/]"
        )


def _render_tool_error(
    con: Console,
    ctx: RenderContext,
    tool_name: str,
    error: str,
) -> None:
    """Render tool call error."""
    if ctx.current_task:
        is_last_task = ctx.is_last_task()
        pipe = TREE["space"] if is_last_task else TREE["pipe"]
        con.print(f"  {pipe}  [void.purple]{CHARS_CHECKS['fail']}[/] {tool_name}")
        con.print(f"  {pipe}     [void.purple]{error[:60]}[/]")
    else:
        con.print(f"  [void.purple]{CHARS_CHECKS['fail']}[/] {tool_name}: {error[:60]}")


def _render_batched_learnings(con: Console, ctx: RenderContext) -> None:
    """Render accumulated learnings in a compact format."""
    learnings = ctx.get_batched_learnings()
    if not learnings:
        return

    total = sum(count for _, count in learnings)
    unique = len(learnings)

    if unique == 1 and total > 1:
        # Single repeated learning
        fact, count = learnings[0]
        con.print(f"  [holy.gold.dim]{CHARS_MISC['learning']}[/] Learned: {fact} [neutral.dim](×{count})[/]")
    elif unique <= 3:
        # Show all
        for fact, count in learnings:
            count_str = f" (×{count})" if count > 1 else ""
            con.print(f"  [holy.gold.dim]{CHARS_MISC['learning']}[/] Learned: {fact}[neutral.dim]{count_str}[/]")
    else:
        # Collapse
        fact, count = learnings[0]
        count_str = f" (×{count})" if count > 1 else ""
        con.print(f"  [holy.gold.dim]{CHARS_MISC['learning']}[/] Learned: {fact}[neutral.dim]{count_str}[/]")
        con.print(f"  [neutral.dim]    +{unique - 1} more learnings[/]")

    ctx.clear_learnings()


def _render_complete_summary(
    con: Console,
    ctx: RenderContext,
    tasks_done: int,
    duration: float,
    files_created: list[str],
    files_modified: list[str],
    verbose: bool = False,
) -> None:
    """Render completion summary with proper hierarchy."""
    # Phase header
    _render_phase_header_minimal(con, "complete", ctx)

    # Summary line
    con.print(f"  [holy.radiant]{CHARS_STARS['radiant']} {tasks_done} tasks completed in {duration:.1f}s[/]")

    # Batched learnings
    _render_batched_learnings(con, ctx)

    # Files summary (compact)
    all_files = files_created + files_modified
    if all_files:
        con.print()
        if files_created:
            con.print(f"  [neutral.text]Files created: {len(files_created)}[/]")
            for f in files_created[:5]:
                con.print(f"    [green]+[/] {f}")
            if len(files_created) > 5:
                con.print(f"    [neutral.dim]+{len(files_created) - 5} more[/]")

        if files_modified:
            con.print(f"  [neutral.text]Files modified: {len(files_modified)}[/]")
            for f in files_modified[:5]:
                con.print(f"    [holy.gold]~[/] {f}")
            if len(files_modified) > 5:
                con.print(f"    [neutral.dim]+{len(files_modified) - 5} more[/]")

    # Token/cost metrics (if tracked)
    if ctx.total_tokens > 0:
        con.print()
        metrics_parts = [f"{ctx.total_tokens:,} tokens"]
        if ctx.total_cost > 0:
            metrics_parts.append(f"${ctx.total_cost:.4f}")
        con.print(f"  [neutral.dim]{CHARS_CIRCLES['double']} {' · '.join(metrics_parts)}[/]")

    # Timeline in verbose mode
    if verbose and ctx.timeline:
        con.print()
        con.print(f"  [neutral.text]Timeline:[/]")
        timeline_data = ctx.get_timeline_for_render()
        # Show last 10 events max
        for time_str, desc, completed in timeline_data[-10:]:
            icon = CHARS_STARS["complete"] if completed else CHARS_STARS["progress"]
            style = "holy.success" if completed else "holy.gold"
            con.print(f"    [{style}]{icon}[/] [neutral.dim]{time_str}[/] {desc}")

    con.print()
    con.print(f"  [holy.radiant]{CHARS_STARS['radiant']}{CHARS_STARS['progress']}{CHARS_STARS['radiant']}[/] Goal achieved")
    con.print()


# =============================================================================
# MAIN EVENT RENDERER
# =============================================================================


def render_agent_event(
    event: AgentEvent,
    console: Console | None = None,
    verbose: bool = False,
) -> None:
    """Render an AgentEvent with Holy Light styling and hierarchical context.

    Uses RenderContext to track state for proper visual grouping:
    - Tasks grouped with their verification gates
    - Tree connectors showing parent-child relationships
    - Batched learnings at phase boundaries

    Args:
        event: The agent event to render
        console: Rich console (uses module default if not provided)
        verbose: Show additional details
    """
    from sunwell.agent.events import EventType
    from sunwell.interface.cli.core.theme import console as default_console

    con = console or default_console
    ctx = get_render_context()

    match event.type:
        # ═══════════════════════════════════════════════════════════════
        # SIGNAL & UNDERSTANDING
        # ═══════════════════════════════════════════════════════════════
        case EventType.SIGNAL:
            status = event.data.get("status", "")
            if status == "extracting":
                if ctx.transition_phase(RenderPhase.UNDERSTANDING):
                    _render_phase_header_minimal(con, "understanding", ctx)
            elif status == "extracted":
                con.print(f"  [holy.gold]{CHARS_STARS['progress']}[/] Signal extracted")

        # ═══════════════════════════════════════════════════════════════
        # PLANNING
        # ═══════════════════════════════════════════════════════════════
        case EventType.PLAN_START:
            if ctx.transition_phase(RenderPhase.PLANNING):
                technique = event.data.get("technique", "planning")
                con.print(f"\n  [neutral.dim]Planning: {technique}[/]")

        case EventType.SIGNAL_ROUTE:
            planning = event.data.get("planning", "")
            confidence = event.data.get("confidence", 0)
            render_confidence(con, confidence, label=f"Route → {planning}")

        case EventType.PLAN_WINNER:
            tasks = event.data.get("tasks", 0)
            gates = event.data.get("gates", 0)
            technique = event.data.get("technique", "")
            rationale = event.data.get("rationale", "")
            task_summaries = event.data.get("task_summaries", [])
            ctx.total_tasks = tasks
            # Add to timeline
            ctx.add_timeline_event(f"Plan: {tasks} tasks, {gates} gates", phase="planning", completed=True)
            con.print()
            render_decision(
                con,
                f"Plan selected: {tasks} tasks, {gates} gates",
                rationale=rationale or technique,
            )
            # Show task skeleton preview if available
            if task_summaries and verbose:
                _render_plan_skeleton(con, task_summaries)

        case EventType.PLAN_CANDIDATE_GENERATED:
            prog = event.data.get("progress", 1)
            total = event.data.get("total_candidates", 5)
            style = event.data.get("variance_config", {}).get("prompt_style", "?")
            artifacts = event.data.get("artifact_count", 0)
            # Compact inline progress
            con.print(f"  [neutral.dim]Candidate {prog}/{total}: {style} ({artifacts} artifacts)[/]")

        # ═══════════════════════════════════════════════════════════════
        # TASK EXECUTION (CRAFTING)
        # ═══════════════════════════════════════════════════════════════
        case EventType.TASK_START:
            task_desc = event.data.get("description", "Working...")
            task_id = event.data.get("task_id", "")
            task_num = event.data.get("task_number", 0)
            total_tasks = event.data.get("total_tasks", 0) or ctx.total_tasks

            # Phase transition on first task
            if task_num == 1 or task_id == "1" or event.data.get("first_task"):
                if ctx.transition_phase(RenderPhase.CRAFTING):
                    _render_phase_header_minimal(con, "crafting", ctx)
                    ctx.add_timeline_event("Started crafting", phase="crafting")

            # Start task group
            ctx.start_task(task_id, task_desc, task_num, total_tasks)
            # Add to timeline (short desc)
            short_desc = task_desc[:40] + "..." if len(task_desc) > 40 else task_desc
            ctx.add_timeline_event(f"Task {task_num}: {short_desc}", phase="crafting")
            _render_task_header(con, ctx)

        case EventType.TASK_COMPLETE:
            duration_ms = event.data.get("duration_ms", 0)
            _render_task_result(con, ctx, duration_ms)
            ctx.complete_task(duration_ms)

        # ═══════════════════════════════════════════════════════════════
        # VALIDATION GATES (inline with tasks)
        # ═══════════════════════════════════════════════════════════════
        case EventType.GATE_START:
            # Don't render phase header - gates are inline
            ctx.transition_phase(RenderPhase.VERIFYING)
            # Gate header is rendered when we get the pass/fail result

        case EventType.GATE_PASS:
            gate_name = event.data.get("gate_name", "Validation")
            gate_id = event.data.get("gate_id", gate_name)
            ctx.add_gate(gate_id, passed=True)
            # Render inline - assume it might be the last gate (will be overwritten if not)
            _render_gate_inline(con, ctx, gate_id, passed=True, is_last_gate=True)

        case EventType.GATE_FAIL:
            gate_name = event.data.get("gate_name", "Validation")
            gate_id = event.data.get("gate_id", gate_name)
            error = event.data.get("error_message", "Failed")
            error_trace = event.data.get("error_trace", [])
            ctx.add_gate(gate_id, passed=False, details=error)
            _render_gate_inline(con, ctx, gate_id, passed=False, is_last_gate=True)

            # Show error details if available
            if error:
                is_last_task = ctx.is_last_task()
                pipe = TREE["space"] if is_last_task else TREE["pipe"]
                con.print(f"  {pipe}       [void.purple]{error[:60]}[/]")

            if error_trace:
                render_collapsible(
                    con,
                    "Error trace",
                    error_trace,
                    expanded=False,
                    item_count=len(error_trace),
                )

        # ═══════════════════════════════════════════════════════════════
        # MODEL INFERENCE
        # ═══════════════════════════════════════════════════════════════
        case EventType.MODEL_START:
            # Start streaming mode for verbose output
            if verbose:
                ctx.start_streaming()
                model = event.data.get("model", "")
                render_streaming(con, f"Thinking... ({model})" if model else "Thinking...", complete=False)

        case EventType.MODEL_THINKING:
            # Show thinking indicator with streaming support
            content = event.data.get("content", "")
            if ctx.is_streaming:
                # Append to streaming buffer and render
                full_text = ctx.append_streaming(content)
                # Truncate for display
                display_text = full_text[-60:] if len(full_text) > 60 else full_text
                render_streaming(con, f"Thinking: {display_text}", complete=False)
            elif verbose:
                con.print(f"  [neutral.dim]◜ {content[:60]}...[/]" if len(content) > 60 else f"  [neutral.dim]◜ {content}[/]")

        case EventType.MODEL_COMPLETE:
            # End streaming if active
            if ctx.is_streaming:
                ctx.end_streaming()
                render_streaming(con, "Thinking complete", complete=True)
            # Track tokens
            total = event.data.get("total_tokens", 0)
            cost = event.data.get("cost", 0.0)
            ctx.add_tokens(total, cost)
            # Only show metrics in verbose mode
            if verbose:
                duration = event.data.get("duration_s", 0)
                tps = event.data.get("tokens_per_second", 0)
                if tps > 0:
                    con.print(f"  [neutral.dim]{total:,} tokens, {tps:.0f} tok/s[/]")

        # ═══════════════════════════════════════════════════════════════
        # COMPLETION
        # ═══════════════════════════════════════════════════════════════
        case EventType.COMPLETE:
            tasks_done = event.data.get("tasks_completed", 0) or ctx.task_count
            duration = event.data.get("duration_s", 0) or ctx.get_elapsed_seconds()
            # Prefer context-tracked files (more complete), fall back to event data
            files_created = ctx.files_created or event.data.get("files_created", [])
            files_modified = ctx.files_modified or event.data.get("files_modified", [])

            # Add completion to timeline
            ctx.add_timeline_event("Goal achieved", phase="complete", completed=True)

            ctx.transition_phase(RenderPhase.COMPLETE)
            _render_complete_summary(con, ctx, tasks_done, duration, files_created, files_modified, verbose)

            # Sparkle burst for celebration (respects accessibility)
            if not ctx.reduced_motion:
                asyncio.create_task(Sparkle.burst("Goal achieved", duration=0.3))

        # ═══════════════════════════════════════════════════════════════
        # FILE OPERATIONS (tracked in context, shown in summary)
        # ═══════════════════════════════════════════════════════════════
        case EventType.FILE_CREATED:
            path = event.data.get("path", "")
            ctx.add_file_created(path)
            # Show in verbose mode or when not in task execution
            if verbose or not ctx.current_task:
                con.print(f"  [green]+[/] {path}")

        case EventType.FILE_MODIFIED:
            path = event.data.get("path", "")
            ctx.add_file_modified(path)
            if verbose or not ctx.current_task:
                old_content = event.data.get("old_content", [])
                new_content = event.data.get("new_content", [])
                con.print(f"  [holy.gold]~[/] {path}")
                if old_content and new_content:
                    render_diff(con, old_content, new_content, context_lines=2)

        case EventType.FILE_DELETED:
            path = event.data.get("path", "")
            con.print(f"  [void.purple]-[/] {path}")

        case EventType.FILE_READ:
            if verbose:
                path = event.data.get("path", "")
                con.print(f"  [neutral.dim]◦[/] {path}")

        # ═══════════════════════════════════════════════════════════════
        # LEARNINGS (deferred/batched)
        # ═══════════════════════════════════════════════════════════════
        case EventType.LEARNING_EXTRACTED | EventType.MEMORY_LEARNING:
            fact = event.data.get("fact", "")
            ctx.add_learning(fact)
            # Don't render immediately - batched at phase boundaries

        # ═══════════════════════════════════════════════════════════════
        # CODE & DECISIONS
        # ═══════════════════════════════════════════════════════════════
        case EventType.CODE_GENERATED:
            code = event.data.get("code", "")
            language = event.data.get("language", "python")
            context = event.data.get("context", "")
            from sunwell.interface.cli.core.theme import render_code
            if code and verbose:
                render_code(con, code, language=language, context=context)

        case EventType.DECISION_MADE:
            decision = event.data.get("decision", "")
            rationale = event.data.get("rationale", "")
            render_decision(con, decision, rationale=rationale)

        # ═══════════════════════════════════════════════════════════════
        # INTENT CLASSIFICATION (DAG)
        # ═══════════════════════════════════════════════════════════════
        case EventType.INTENT_CLASSIFIED:
            from sunwell.interface.cli.progress.dag_path import format_dag_path

            path_parts = event.data.get("path", [])
            confidence = event.data.get("confidence", 0)
            requires_approval = event.data.get("requires_approval", False)
            tool_scope = event.data.get("tool_scope")

            path_text = format_dag_path(path_parts) if path_parts else event.data.get("path_formatted", "")

            con.print()
            con.print(f"  [holy.gold]{CHARS_PROGRESS['arrow']}[/] Intent: {path_text}")

            if verbose or requires_approval:
                render_confidence(con, confidence, label="confidence")
                if tool_scope:
                    con.print(f"     [neutral.dim]scope: {tool_scope}[/]")
                if requires_approval:
                    con.print(f"     [void.indigo]{CHARS_MISC['approval']} requires approval[/]")

        case EventType.NODE_TRANSITION:
            from_node = event.data.get("from_node", "?")
            to_node = event.data.get("to_node", "?")
            reason = event.data.get("reason", "")
            con.print(
                f"  [neutral.dim]{CHARS_DIAMONDS['hollow']} {from_node} → [/][holy.gold]{to_node}[/]"
                + (f" [neutral.dim]({reason})[/]" if reason else "")
            )

        # ═══════════════════════════════════════════════════════════════
        # FIXING
        # ═══════════════════════════════════════════════════════════════
        case EventType.FIX_START:
            con.print(f"\n  [void.indigo]{CHARS_MISC['gear']}[/] Auto-fixing...")

        case EventType.FIX_PROGRESS:
            stage = event.data.get("stage", "?")
            detail = event.data.get("detail", "")
            con.print(f"     [holy.gold]{TREE['branch']}[/] {stage}: {detail}")

        case EventType.FIX_COMPLETE:
            con.print(f"     [holy.success]{CHARS_CHECKS['pass']}[/] Fix applied")

        # ═══════════════════════════════════════════════════════════════
        # ESCALATION & ERRORS
        # ═══════════════════════════════════════════════════════════════
        case EventType.ESCALATE:
            reason = event.data.get("reason", "unknown")
            message = event.data.get("message", "")
            render_alert(
                con,
                f"Reason: {reason}\n{message}" if message else f"Reason: {reason}",
                severity="warning",
                title="Escalating to user",
            )

        # Errors
        case EventType.ERROR:
            message = event.data.get("message", "Unknown error")
            details = event.data.get("details")
            render_error(con, message, details=details)

        # ═══════════════════════════════════════════════════════════════
        # TOOL CALLS (nested under tasks)
        # ═══════════════════════════════════════════════════════════════
        case EventType.TOOL_START:
            tool_name = event.data.get("tool_name", "tool")
            ctx.start_tool(tool_name)
            # Only show in verbose or if no active task
            if verbose or not ctx.current_task:
                _render_tool_start(con, ctx, tool_name)

        case EventType.TOOL_COMPLETE:
            ctx.complete_tool(success=True)
            if verbose or not ctx.current_task:
                tool_name = event.data.get("tool_name", "tool")
                duration = event.data.get("duration_ms", 0)
                _render_tool_complete(con, ctx, tool_name, duration)

        case EventType.TOOL_ERROR:
            error = event.data.get("error", "Unknown error")
            ctx.complete_tool(success=False, error=error)
            tool_name = event.data.get("tool_name", "tool")
            _render_tool_error(con, ctx, tool_name, error)

        # ═══════════════════════════════════════════════════════════════
        # CONVERGENCE (fix loops)
        # ═══════════════════════════════════════════════════════════════
        case EventType.CONVERGENCE_START:
            max_iter = event.data.get("max_iterations", 5)
            ctx.start_convergence(max_iter)
            con.print(f"\n  [holy.gold]{CHARS_MISC['gear']}[/] Starting convergence loop (max {max_iter} iterations)")

        case EventType.CONVERGENCE_ITERATION_START:
            iteration = ctx.next_convergence_iteration()
            con.print(f"  [neutral.dim]{'─' * 40}[/]")
            con.print(f"  [holy.gold]↻[/] Iteration {iteration}/{ctx.convergence_max}")

        case EventType.CONVERGENCE_ITERATION_COMPLETE:
            gates_passed = event.data.get("gates_passed", 0)
            gates_total = event.data.get("gates_total", 0)
            con.print(f"     [neutral.dim]Gates: {gates_passed}/{gates_total} passed[/]")

        case EventType.CONVERGENCE_FIXING:
            ctx.start_fixing()
            errors = event.data.get("errors", [])
            con.print(f"  [void.indigo]{CHARS_MISC['gear']}[/] Fixing {len(errors)} issue(s)...")
            for err in errors[:3]:
                con.print(f"     [neutral.dim]• {err[:60]}[/]")
            if len(errors) > 3:
                con.print(f"     [neutral.dim]  +{len(errors) - 3} more[/]")

        case EventType.CONVERGENCE_STABLE:
            ctx.end_fixing()
            con.print(f"\n  [holy.success]{CHARS_STARS['complete']}[/] Convergence achieved - all gates pass")

        case EventType.CONVERGENCE_STUCK | EventType.CONVERGENCE_MAX_ITERATIONS:
            ctx.end_fixing()
            con.print(f"\n  [void.purple]{CHARS_CHECKS['fail']}[/] Convergence failed after {ctx.convergence_iteration} iterations")

        case EventType.CONVERGENCE_TIMEOUT:
            ctx.end_fixing()
            con.print(f"\n  [void.indigo]{CHARS_CIRCLES['quarter']}[/] Convergence timed out")

        case EventType.CONVERGENCE_BUDGET_EXCEEDED:
            ctx.end_fixing()
            con.print(f"\n  [void.purple]{CHARS_MISC['budget']}[/] Token budget exhausted during convergence")

        # ═══════════════════════════════════════════════════════════════
        # BUDGET & METRICS
        # ═══════════════════════════════════════════════════════════════
        case EventType.MODEL_TOKENS:
            tokens = event.data.get("tokens", 0)
            cost = event.data.get("cost", 0.0)
            ctx.add_tokens(tokens, cost)

        case EventType.BUDGET_WARNING:
            used = event.data.get("used", 0)
            total = event.data.get("total", 0)
            pct = (used / total * 100) if total > 0 else 0
            con.print(f"  [void.indigo]{CHARS_MISC['budget']}[/] Budget warning: {pct:.0f}% used ({used:,}/{total:,} tokens)")

        case EventType.BUDGET_EXHAUSTED:
            render_alert(con, "Token budget exhausted", severity="error", title="Budget Exhausted")

        # ═══════════════════════════════════════════════════════════════
        # SECURITY
        # ═══════════════════════════════════════════════════════════════
        case EventType.SECURITY_APPROVAL_REQUESTED:
            permissions = event.data.get("permissions", [])
            risk = event.data.get("risk_level", "unknown")
            render_alert(
                con,
                f"Permissions: {', '.join(permissions)}\nRisk level: {risk}",
                severity="warning",
                title="Approval Required",
            )

        case EventType.SECURITY_VIOLATION:
            violation = event.data.get("violation", "Unknown violation")
            render_alert(con, violation, severity="error", title="Security Violation")

        case EventType.SECURITY_APPROVAL_RECEIVED:
            approved = event.data.get("approved", False)
            if approved:
                con.print(f"  [holy.success]{CHARS_CHECKS['pass']}[/] Approved")
            else:
                con.print(f"  [void.purple]{CHARS_CHECKS['fail']}[/] Rejected")

        # ═══════════════════════════════════════════════════════════════
        # RELIABILITY
        # ═══════════════════════════════════════════════════════════════
        case EventType.RELIABILITY_WARNING:
            message = event.data.get("message", "Reliability concern detected")
            con.print(f"  [void.indigo]{CHARS_MISC['warning']}[/] {message}")

        case EventType.RELIABILITY_HALLUCINATION:
            details = event.data.get("details", "Model may have hallucinated completion")
            render_alert(con, details, severity="error", title="Hallucination Detected")

        # ═══════════════════════════════════════════════════════════════
        # SKILL EXECUTION
        # ═══════════════════════════════════════════════════════════════
        case EventType.SKILL_GRAPH_RESOLVED:
            skill_count = event.data.get("skill_count", 0)
            wave_count = event.data.get("wave_count", 0)
            con.print(f"  [holy.gold]{CHARS_DIAMONDS['solid']}[/] Skill graph: {skill_count} skills in {wave_count} waves")

        case EventType.SKILL_WAVE_START:
            wave = event.data.get("wave", 0)
            skills = event.data.get("skill_count", 0)
            con.print(f"  [neutral.dim]Wave {wave}: {skills} skills[/]")

        case EventType.SKILL_WAVE_COMPLETE:
            succeeded = event.data.get("succeeded", 0)
            failed = event.data.get("failed", 0)
            if failed > 0:
                con.print(f"     [holy.success]{CHARS_CHECKS['pass']} {succeeded}[/] [void.purple]{CHARS_CHECKS['fail']} {failed}[/]")
            else:
                con.print(f"     [holy.success]{CHARS_CHECKS['pass']} {succeeded}[/]")

        case EventType.SKILL_CACHE_HIT:
            skill_name = event.data.get("skill_name", "skill")
            con.print(f"  [holy.gold]{CHARS_STARS['cache']}[/] {skill_name} [neutral.dim](cached)[/]")

        case EventType.SKILL_EXECUTE_START:
            if verbose:
                skill_name = event.data.get("skill_name", "skill")
                con.print(f"  [neutral.dim]{CHARS_STARS['progress']} {skill_name}...[/]")

        case EventType.SKILL_EXECUTE_COMPLETE:
            if verbose:
                skill_name = event.data.get("skill_name", "skill")
                success = event.data.get("success", True)
                icon = CHARS_CHECKS["pass"] if success else CHARS_CHECKS["fail"]
                style = "holy.success" if success else "void.purple"
                con.print(f"  [{style}]{icon}[/] {skill_name}")

        # ═══════════════════════════════════════════════════════════════
        # SESSION RESUME
        # ═══════════════════════════════════════════════════════════════
        case EventType.RECOVERY_LOADED:
            tasks_done = event.data.get("tasks_completed", 0)
            tasks_remaining = event.data.get("tasks_remaining", 0)
            con.print(f"\n  [holy.gold]{CHARS_PROGRESS['step_done']}[/] Resuming session")
            con.print(f"     [neutral.dim]Completed: {tasks_done} tasks[/]")
            con.print(f"     [holy.gold]Remaining: {tasks_remaining} tasks[/]")

        case EventType.CHECKPOINT_FOUND:
            phase = event.data.get("phase", "unknown")
            con.print(f"  [holy.gold]{CHARS_MISC['save']}[/] Found checkpoint at: {phase}")

        case EventType.CHECKPOINT_SAVED:
            phase = event.data.get("phase", "")
            con.print(f"  [holy.success]{CHARS_MISC['save']}[/] Checkpoint saved{f': {phase}' if phase else ''}")
