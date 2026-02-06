"""MCP Server instructions for Sunwell.

Provides system prompt/instructions for AI agents using Sunwell via MCP.
"""

SUNWELL_INSTRUCTIONS = """Sunwell is a domain intelligence system that provides expertise, memory, knowledge, planning, and execution capabilities through MCP.

## Quick Start

1. **Read the briefing first** — `sunwell://briefing` or `sunwell_briefing()` gives you instant project context
2. **Check learnings** — `sunwell_recall("topic")` to leverage past insights and avoid dead ends
3. **Get expertise** — `sunwell_lens("coder")` to inject professional perspective
4. **Search codebase** — `sunwell_search("query")` for semantic search
5. **Report completion** — `sunwell_complete(goal, files_modified)` to update memory

## Tool Categories

### Lens System — Professional Expertise
- `sunwell_lens(name)` — Get lens as injectable expertise (heuristics, anti-patterns, frameworks)
- `sunwell_list(format)` — List available lenses (minimal/compact/full)
- `sunwell_route(command)` — Route shortcuts like `::code` to lenses with confidence scoring
- `sunwell_shortcuts()` — List all available shortcuts

### Knowledge — Codebase Intelligence
- `sunwell_search(query, scope)` — Semantic search across indexed codebase (code/docs/all)
- `sunwell_ask(question)` — Synthesized answer with source references (RFC-135)
- `sunwell_codebase(aspect)` — Structural intelligence (structure/hotpaths/errors/patterns)
- `sunwell_workspace()` — List known projects

### Memory — Persistent Context
- `sunwell_briefing()` — Rolling briefing: mission, status, hazards, hot files, next action
- `sunwell_recall(query, scope)` — Query learnings, dead ends, constraints, decisions
- `sunwell_lineage(file_path)` — Artifact provenance: who created, why, dependencies
- `sunwell_session()` — Session history and metrics

### Planning — Intelligence Routing
- `sunwell_plan(goal)` — Generate execution plan with task graph and estimates
- `sunwell_classify(input)` — Classify intent, complexity, recommended lens/tools
- `sunwell_reason(question, options)` — Reasoned decision with confidence scoring

### Backlog — Autonomous Goals
- `sunwell_goals(status)` — List goals from DAG (all/active/blocked/completed)
- `sunwell_goal(goal_id)` — Goal details with dependencies and hierarchy
- `sunwell_suggest_goal(signal)` — Generate goals from free-text observation

### Multi-Agent Coordination — Self-Driving
- `sunwell_get_goals(state)` — Browse available goals for claiming (pending/claimed/all)
- `sunwell_claim_goal(goal_id)` — Claim a goal for exclusive work
- `sunwell_submit_handoff(...)` — Submit results with findings, concerns, suggestions
- `sunwell_release_goal(goal_id)` — Release a claim if you cannot complete it
- `sunwell_status()` — System health, active workers, error budget

### Mirror — Self-Introspection
- `sunwell_mirror(aspect)` — Learnings, patterns, dead ends, error analysis
- `sunwell_team(query, scope)` — Team knowledge: decisions, failures, ownership, patterns

### Execution — Agent Pipeline
- `sunwell_execute(goal)` — Run full ORIENT->PLAN->EXECUTE->VALIDATE->LEARN pipeline
- `sunwell_validate(file_path, validators)` — Run validators (syntax, lint, type, test)
- `sunwell_complete(goal, files_modified)` — Report completion to update memory

### Delegation — Model Routing
- `sunwell_delegate(task)` — Smart model recommendation (fast vs. smart)

## Resources (Read-Only Context)

Pull in context as needed — resources are cheap to read:

| Resource | Description |
|----------|-------------|
| `sunwell://map` | Capabilities overview (this guide) |
| `sunwell://briefing` | Current rolling briefing |
| `sunwell://learnings` | Accumulated insights from past sessions |
| `sunwell://deadends` | Known dead ends — avoid repeating mistakes |
| `sunwell://constraints` | Active constraints and guardrails |
| `sunwell://goals` | Current active goals |
| `sunwell://goals/blocked` | Blocked goals with reasons |
| `sunwell://lenses` | Available lenses |
| `sunwell://shortcuts` | Shortcut map |
| `sunwell://projects` | Known projects |
| `sunwell://config` | Configuration summary |
| `sunwell://status` | System health |
| `sunwell://reference/domains` | Domain capabilities |
| `sunwell://reference/tools` | Tool catalog with trust levels |
| `sunwell://reference/validators` | Validator catalog |
| `sunwell://reference/models` | Model strengths and aliases |

## Multi-Agent Workflow (Self-Driving)

External agents can participate as workers in Sunwell's autonomous system:

1. `sunwell_get_goals("pending")` — See what needs doing
2. `sunwell_claim_goal("goal-id")` — Claim exclusive access
3. Execute the goal within the provided scope limits
4. `sunwell_submit_handoff(goal_id, success, summary, findings, concerns)` — Report back

Handoffs carry more than success/failure — include findings (discoveries),
concerns (risks), and suggestions (follow-up ideas). This enables Sunwell's
planner to dynamically replan based on what workers learn during execution.

## Completion Tracking

After finishing a task, call `sunwell_complete()` to let Sunwell update its memory:

```
sunwell_complete(
    goal="Added authentication middleware",
    files_modified="src/auth.py,src/middleware.py",
    files_reviewed="src/routes.py",
    learnings="JWT refresh tokens need to be rotated on each use",
    success=True
)
```

This enables Sunwell to accumulate intelligence across sessions.

## Shortcuts

Lenses may define shortcuts (e.g., `::code`, `::review`).
Use `sunwell_route()` to resolve shortcuts to lenses with confidence scoring:
- 1.0: Exact shortcut match
- 0.95: Lens name match
- 0.7: Domain/tag match
- 0.5: Description match
"""
