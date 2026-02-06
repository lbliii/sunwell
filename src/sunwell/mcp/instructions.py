"""MCP Server instructions for Sunwell.

Provides system prompt/instructions for AI agents using Sunwell via MCP.
"""

SUNWELL_INSTRUCTIONS = """Sunwell is a domain intelligence system that provides expertise, memory, knowledge, planning, and execution capabilities through MCP.

## Quick Start

1. **Read the briefing first** — `sunwell://briefing/summary` for quick status, or `sunwell_briefing()` for full context
2. **Check learnings** — `sunwell_recall("topic")` to leverage past insights and avoid dead ends
3. **Get expertise** — `sunwell_lens("coder")` to inject professional perspective
4. **Search codebase** — `sunwell_search("query")` for semantic search
5. **Report completion** — `sunwell_complete(goal, files_modified)` to update memory

## Format Tiers (Token Optimization)

Most tools accept a `format` parameter with three tiers:

| Tier | Tokens | Use When |
|------|--------|----------|
| **summary** | ~50-200 | Scanning. "Do I need to look deeper?" |
| **compact** | ~200-1k | Default. Regular work and decision-making. |
| **full** | ~1-15k | You need the complete payload (e.g., injectable context). |

Default is `compact`. Use `summary` to minimize token spend when scanning multiple tools.

Examples:
```
sunwell_briefing(format="summary")     # ~200 tokens vs ~2-5k
sunwell_mirror(format="summary")       # ~100 tokens vs ~5-10k
sunwell_goals(format="summary")        # ~150 tokens vs ~2k
sunwell_classify(input, format="summary")  # ~50 tokens vs ~500
```

## Thin Mode (Large Content)

Tools returning injectable content support `include_context=False`:

```
sunwell_lens("coder", include_context=False)    # ~200 tokens metadata vs 5-15k
sunwell_route("::code", include_context=False)  # Routing only, no context blob
```

Use thin mode first to identify the right lens, then fetch with `include_context=True`.

## Summary Resources (Low-Token Alternatives)

Resources have summary variants for quick lookups:

| Full Resource | Summary Resource | Savings |
|---------------|------------------|---------|
| `sunwell://briefing` (~2-5k) | `sunwell://briefing/summary` (~200) | 90%+ |
| `sunwell://learnings` (~2-4k) | `sunwell://learnings/summary` (~150) | 90%+ |
| `sunwell://goals` (~1-3k) | `sunwell://goals/summary` (~100) | 90%+ |
| `sunwell://lenses` (~1-2k) | `sunwell://lenses/minimal` (~200) | 80%+ |

## Tool Categories

### Lens System — Professional Expertise
- `sunwell_lens(name, include_context, format)` — Get lens as injectable expertise
- `sunwell_list(format)` — List available lenses (minimal/compact/full)
- `sunwell_route(command, include_context)` — Route shortcuts to lenses with confidence scoring
- `sunwell_shortcuts()` — List all available shortcuts

### Knowledge — Codebase Intelligence
- `sunwell_search(query, scope, format)` — Semantic search (summary=paths only, compact=truncated, full=extended)
- `sunwell_ask(question, format)` — Synthesized answer with source references
- `sunwell_codebase(aspect, format)` — Structural intelligence (summary=counts, compact=top-20, full=top-50)
- `sunwell_workspace()` — List known projects

### Memory — Persistent Context
- `sunwell_briefing(format)` — Rolling briefing (summary=status only, compact=no prompt, full=with prompt)
- `sunwell_recall(query, scope, format)` — Query learnings/dead ends/constraints (summary=counts only)
- `sunwell_lineage(file_path, format)` — Artifact provenance
- `sunwell_session(format)` — Session history (summary=ID+counts, compact=metrics, full=with goals)

### Planning — Intelligence Routing
- `sunwell_plan(goal, format)` — Execution plan (summary=count+estimate, compact=task list, full=with metrics)
- `sunwell_classify(input, format)` — Intent classification (summary=intent+complexity+confidence)
- `sunwell_reason(question, options, format)` — Reasoned decision (summary=outcome+confidence)

### Backlog — Autonomous Goals
- `sunwell_goals(status, format)` — List goals (summary=counts by status only)
- `sunwell_goal(goal_id, format)` — Goal details with dependencies
- `sunwell_suggest_goal(signal)` — Generate goal suggestions from observation

### Multi-Agent Coordination — Self-Driving
- `sunwell_claim_goal(goal_id)` — Claim a goal for exclusive work
- `sunwell_submit_handoff(...)` — Submit results with findings, concerns, suggestions
- `sunwell_release_goal(goal_id)` — Release a claim if you cannot complete it
- `sunwell_get_goal_context(goal_id)` — Get rich execution context for a claimed goal
- `sunwell_status()` — System health, active workers, error budget
- `sunwell_events()` — Recent event stream

### Mirror — Self-Introspection
- `sunwell_mirror(aspect, format)` — Learnings, patterns, dead ends (summary=counts only)
- `sunwell_team(query, scope, format)` — Team knowledge (summary=warnings only, compact=truncated)

### Execution — Agent Pipeline
- `sunwell_execute(goal, format)` — Run full agent pipeline
- `sunwell_validate(file_path, format)` — Run validators (summary=pass/fail only)
- `sunwell_complete(goal, files_modified)` — Report completion to update memory

### Delegation — Model Routing
- `sunwell_delegate(task)` — Smart model recommendation

## Resources (Read-Only Context)

| Resource | Description |
|----------|-------------|
| `sunwell://map` | Capabilities overview (this guide) |
| `sunwell://briefing` | Rolling briefing (full prompt) |
| `sunwell://briefing/summary` | Mission + status + hazards (low token) |
| `sunwell://learnings` | Accumulated insights |
| `sunwell://learnings/summary` | Count + top-5 most-used (low token) |
| `sunwell://deadends` | Known dead ends |
| `sunwell://constraints` | Active constraints |
| `sunwell://goals` | Active goals |
| `sunwell://goals/summary` | Counts by status (low token) |
| `sunwell://goals/blocked` | Blocked goals with reasons |
| `sunwell://lenses` | Available lenses |
| `sunwell://lenses/minimal` | Names and domains only (low token) |
| `sunwell://lenses/registry` | Full registry with shortcuts/overrides |
| `sunwell://shortcuts` | Shortcut map |
| `sunwell://projects` | Known projects |
| `sunwell://config` | Configuration summary |
| `sunwell://status` | System health |
| `sunwell://reference/domains` | Domain capabilities |
| `sunwell://reference/tools` | Tool catalog |
| `sunwell://reference/validators` | Validator catalog |
| `sunwell://reference/models` | Model strengths and aliases |

## Token Budget Guidance

- **Scanning phase**: Use `format="summary"` and summary resources. ~50-200 tokens per call.
- **Working phase**: Use default `format="compact"`. ~200-1k tokens per call.
- **Deep dive**: Use `format="full"` only when you need the complete content. ~1-15k tokens per call.
- **Lens injection**: Use `include_context=False` first to find the right lens (~200 tokens), then `include_context=True` for the one you need (~5-15k tokens).

## Multi-Agent Workflow (Self-Driving)

External agents can participate as workers in Sunwell's autonomous system:

1. `sunwell_goals("pending")` — See what needs doing
2. `sunwell_goal("goal-id")` — Inspect details and dependencies
3. `sunwell_claim_goal("goal-id")` — Claim exclusive access
4. `sunwell_get_goal_context("goal-id")` — Get execution context
5. Execute within scope limits
6. `sunwell_submit_handoff(goal_id, success, summary, findings, concerns)` — Report back

Handoffs carry findings (discoveries), concerns (risks), and suggestions (follow-up ideas), enabling the planner to dynamically replan.

## Completion Tracking

After finishing a task, call `sunwell_complete()` to update memory:

```
sunwell_complete(
    goal="Added authentication middleware",
    files_modified="src/auth.py,src/middleware.py",
    files_reviewed="src/routes.py",
    learnings="JWT refresh tokens need to be rotated on each use",
    success=True
)
```

## Shortcuts

Lenses define shortcuts (e.g., `::code`, `::review`). Use `sunwell_route()` to resolve them:
- 1.0: Exact shortcut match
- 0.95: Lens name match
- 0.7: Domain/tag match
- 0.5: Description match
"""
