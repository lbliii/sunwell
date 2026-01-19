# RFC-037: CLI Consolidation — Goal-First Interface

| Field | Value |
|-------|-------|
| **RFC** | 037 |
| **Title** | CLI Consolidation — Goal-First Interface |
| **Status** | Implemented |
| **Created** | 2026-01-19 |
| **Author** | llane |
| **Builds on** | RFC-032 (Agent Mode), RFC-036 (Artifact-First Planning) |

---

## Abstract

Sunwell's CLI has grown organically from a lens-application tool to a full agentic system. The current interface reflects this history: 47 commands/subcommands and ~100 flags that expose implementation details users don't need to care about.

**The key insight**: Once you have an agent, the interface becomes trivial. Users state a goal; the agent figures out the rest. The CLI should reflect this.

```bash
# Current (implementation-leaky)
sunwell naaru run "Build REST API" --strategy artifact_first --trust workspace

# Proposed (goal-first)
sunwell "Build REST API"
```

This RFC proposes collapsing the CLI to its essential form: **goal in, results out**.

---

## Goals and Non-Goals

### Goals

1. **Goal-first interface** — `sunwell "goal"` as the primary command
2. **Zero-config default path** — Agent decides strategy, trust, model, etc.
3. **Progressive disclosure** — Power features exist but don't clutter the main interface
4. **Backward compatibility** — Existing commands continue to work
5. **Clear mental model** — Users understand what Sunwell is in 10 seconds

### Non-Goals

1. **Remove power features** — Advanced users keep full control
2. **Break existing scripts** — All current commands remain functional
3. **Hide interactive mode** — `sunwell chat` stays prominent
4. **Eliminate configuration** — Bindings and setup still exist for those who want them

---

## Motivation

### The Flag Explosion Problem

The current `apply` command has 20 flags:

```bash
sunwell apply <lens> <prompt>
  --model, --provider, --stream, --tier, --context, --no-workspace,
  --output, --save-session, --headspace, --no-auto-headspace, --learn,
  --dead-end, --skill, --dry-run, --tools, --tools-only, --trust,
  --smart, --router-model, --verbose
```

Each flag represents a decision the user must make. But with an agent, most of these decisions should be **automatic**:

| Flag | Should Be | Agent Logic |
|------|-----------|-------------|
| `--tier` | Auto | Assess task complexity |
| `--trust` | Auto | Infer from tool requirements |
| `--tools` | Auto | Enable when goal requires actions |
| `--smart` | Always on | Why would you want dumb routing? |
| `--headspace` | Auto | SimulacrumManager routes this |
| `--model` | Auto | Selected per-task by planner |
| `--strategy` | Auto | `artifact_first` default (RFC-036) |

### The Namespace Problem

Users must currently know internal terminology:

```bash
sunwell naaru run "goal"      # What's a "naaru"?
sunwell naaru illuminate      # What does this even mean?
sunwell apply lens.lens ...   # Why do I need a lens?
```

Compare to git, which uses intuitive verbs:

```bash
git commit    # I know what commit means
git push      # I know what push means
```

Sunwell should be equally intuitive:

```bash
sunwell "Build an API"        # I want to build something
sunwell chat                  # I want to chat
```

### The Discovery Problem

Running `sunwell --help` shows 15 top-level commands. New users must read documentation to know which one to use. But there's really only one question: **"What do you want to accomplish?"**

---

## Current CLI Inventory

### Commands by Category

```yaml
# PRIMARY ENTRY POINTS (3, but only 1 is needed)
apply:     Manual lens application (20 flags)
ask:       Binding-based simplified apply (8 flags)
naaru run: Agent mode (7 flags)

# INTERACTIVE
chat:      Interactive conversation (12 flags)

# AGENT ADVANCED
naaru resume:     Resume from checkpoint
naaru illuminate: Self-improvement mode
naaru status:     Agent state
naaru benchmark:  Agent benchmarks

# CONFIGURATION
setup:     First-time setup
bind:      Manage bindings (5 subcommands)
config:    Global configuration
lens:      Lens management

# MEMORY/STATE
sessions:  Conversation sessions (3 subcommands)

# DEVELOPMENT
benchmark: Quality testing (5 subcommands)
runtime:   Runtime diagnostics
exec:      Execute skills
validate:  Validate skills

# TOTAL: 47 commands/subcommands, ~100 flags
```

### Redundancy Analysis

| Use Case | Current Commands | Proposed |
|----------|------------------|----------|
| Execute a goal | `apply`, `ask`, `naaru run` | `sunwell "goal"` |
| Interactive session | `chat` | `sunwell chat` |
| Plan without executing | `naaru run --dry-run` | `sunwell "goal" --plan` |
| Use specific model | `apply --model X`, `ask --model X`, `naaru run --model X` | `sunwell "goal" --model X` |

---

## Proposed Design

### The Goal-First Interface

```python
@click.group(invoke_without_command=True)
@click.argument("goal", required=False)
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--model", "-m", help="Override model selection")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--time", "-t", default=300, help="Max execution time (seconds)")
@click.pass_context
def main(ctx, goal: str | None, plan: bool, model: str | None, 
         verbose: bool, time: int, quiet: bool = False) -> None:
    """Sunwell — AI agent for software tasks.
    
    Just tell it what you want:
    
    \b
        sunwell "Build a REST API with auth"
        sunwell "Write docs for the CLI module"
        sunwell "Refactor auth.py to use async"
    
    For interactive mode:
    
        sunwell chat
    
    For planning without execution:
    
        sunwell "Build an app" --plan
    """
    load_dotenv()
    check_free_threading(quiet=quiet)
    
    # If a goal was provided and no subcommand invoked, run agent
    if goal and ctx.invoked_subcommand is None:
        ctx.invoke(
            _run_goal,
            goal=goal,
            dry_run=plan,
            model=model,
            verbose=verbose,
            time=time,
        )
```

### Command Hierarchy

```yaml
# TIER 1: The 90% Path (visible in --help)
sunwell "goal"           # Execute goal (DEFAULT)
sunwell chat [binding]   # Interactive mode
sunwell setup            # First-time setup

# TIER 2: Power User (visible in --help, grouped)
sunwell bind ...         # Manage saved configurations
sunwell config ...       # Global settings

# TIER 3: Advanced (shown with --help-all or in docs)
sunwell agent ...        # Renamed from 'naaru' (clearer)
  sunwell agent run      # Explicit agent mode (same as bare goal)
  sunwell agent resume   # Resume checkpoint
  sunwell agent status   # Show state
  
sunwell apply ...        # Legacy manual mode (deprecated warning)
sunwell ask ...          # Legacy binding mode (deprecated warning)
sunwell benchmark ...    # Quality testing
sunwell sessions ...     # Memory management
```

### Flag Reduction

**Before** (`apply`): 20 flags

**After** (bare command): 5 flags

| Flag | Purpose | Notes |
|------|---------|-------|
| `--plan` | Show plan only | Replaces `--dry-run` |
| `--model` | Override model | For when auto-selection is wrong |
| `--verbose` | Detailed output | Debugging |
| `--time` | Max execution time | Safety limit |
| `--trust` | Override trust level | Security-conscious users |

All other decisions are made by the agent.

### Relationship to Existing Commands

| New Command | Equivalent To | Notes |
|-------------|---------------|-------|
| `sunwell "goal"` | `sunwell naaru run "goal" --strategy artifact_first` | Same backend |
| `sunwell "goal" --plan` | `sunwell naaru run "goal" --dry-run` | Shows plan without `--show-graph` |
| `sunwell "goal" --plan --verbose` | `sunwell naaru run "goal" --dry-run --show-graph` | Full graph view |

The `--plan` flag is a user-friendly alias for `--dry-run`. Both invoke the same planner but skip execution.

### Interactive Mode Behavior

`sunwell chat` remains the entry point for interactive sessions. It does **not** auto-enable tools based on goal complexity because:

1. **Predictability**: Users expect chat to behave consistently
2. **Security**: Tool access should be explicit, not inferred
3. **Existing flag**: `sunwell chat --tools` already provides opt-in

However, the chat session can suggest tool mode when appropriate:

```
You: Build a REST API with auth