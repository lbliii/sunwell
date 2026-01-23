# RFC-109: CLI Simplification — The Agentic Floor

**Status**: ✅ Implemented  
**Author**: AI Assistant  
**Created**: 2026-01-23  
**Depends on**: RFC-107 (Shortcut Execution) — soft dependency, can implement independently  
**Last Updated**: 2026-01-23

---

## Summary

Sunwell's CLI has grown to **43 top-level commands**, creating cognitive overload. Many commands are variations of "talk to the agent" (`chat`, `ask`, `do`, `agent`, `interface`, `apply`). This RFC proposes collapsing to a minimal surface while maintaining Studio compatibility.

**The thesis**: If everything is agentic, users just talk to the agent. The CLI should reflect this.

---

## Motivation

### Current State: 43 Commands

```
agent, apply, ask, backlog, benchmark, bind, bootstrap, briefing, chat,
config, dag, demo, do, env, eval, external, guardrails, import, index,
intel, interface, lens, naaru, open, plan, project, reason, runtime,
scan, security, self, session, setup, skill, surface, team, verify,
weakness, workers, workflow, workspace
```

**Problems:**
1. **Cognitive overload**: New users face 43 commands, most irrelevant
2. **Overlapping entry points**: Multiple ways to "talk to the agent":
   - `chat` — interactive REPL mode
   - `ask` — single-shot question (deprecated)
   - `do` — skill shortcut execution
   - `agent run` — programmatic execution
   - `interface process` — Studio integration
   - Default `sunwell "goal"` — natural language execution
3. **Internal leakage**: `naaru`, `workers`, `runtime` are implementation details
4. **No clear entry point**: What do I type first?

### Target State: 5 Primary Commands

```bash
sunwell "goal"                    # Talk to the agent (default)
sunwell -s SHORTCUT [TARGET]      # Run skill shortcut
sunwell config                    # Configuration
sunwell project                   # Project operations
sunwell session                   # Session management
```

Everything else is either:
- **Deprecated** (aliased to new commands)
- **Hidden** (developer/debug only)
- **Internal** (only called by Studio, not users)

---

## Goals and Non-Goals

### Goals
1. Reduce `--help` output to ≤10 user-facing items
2. Establish `sunwell "goal"` and `sunwell -s SHORTCUT` as the two primary patterns
3. Preserve all Studio CLI calls without modification
4. Provide clear deprecation warnings with migration hints
5. Maintain shell completion for shortcuts and file paths

### Non-Goals
1. **NOT changing Studio ↔ Python IPC** — Studio continues using subprocess calls; native IPC is a separate future RFC
2. **NOT removing `chat`** — interactive mode remains available, just deprioritized in `--help`
3. **NOT implementing RFC-107 chain syntax** — `-s "p -> a-2"` chaining is optional; single shortcuts work without it
4. **NOT breaking existing scripts** — all current CLI invocations continue working through v0.3.0

### RFC-107 Dependency

This RFC **soft-depends** on RFC-107 (Shortcut Execution):
- **Without RFC-107**: `-s` flag works for single shortcuts only
- **With RFC-107**: `-s` flag supports chaining (`p -> a-2`) and parallel execution (`p, a-2`)

Implementation can proceed independently. Chain syntax is additive.

---

## Detailed Design

### Tier 1: Primary Interface (shown in `--help`)

```
USAGE:
    sunwell [OPTIONS] [GOAL]
    sunwell -s <SHORTCUT> [TARGET]
    sunwell <COMMAND>

ARGUMENTS:
    [GOAL]    Natural language goal (default action)

OPTIONS:
    -s, --skill <SHORTCUT>    Run skill shortcut (a-2, p, health, etc.) [TAB-COMPLETE]
    -t, --target <FILE>       Target file/directory [TAB-COMPLETE]
    -c, --chain <CHAIN>       Chain shortcuts: "p -> a-2 -> r"
    -l, --lens <NAME>         Use specific lens
    -m, --model <NAME>        Override model
    -p, --provider <NAME>     Override provider (openai, anthropic, ollama)
    --plan                    Show plan without executing
    --json                    Output as JSON (for programmatic use)
    -v, --verbose             Verbose output
    -h, --help                Print help
    -V, --version             Print version

POSITIONAL (after options):
    [TARGET]                  Target file/directory (alternative to -t) [TAB-COMPLETE]
    [CONTEXT...]              Additional instructions for the skill

COMMANDS:
    config      View or modify configuration
    project     Project analysis and management
    session     Session management (list, resume, delete)
    lens        Lens management (list, show, create)
    setup       First-time setup wizard

SHORTCUTS:
    a, a-2      Audit (quick, deep)
    p           Polish
    health      Health check
    swarm       All personas
    pipeline    Full docs pipeline

EXAMPLES:
    sunwell "audit the CLI docs"
    sunwell -s a-2 docs/cli.md
    sunwell -s a-2 docs/cli.md "focus on the migration section"
    sunwell -s "p -> a-2" docs/cli.md
    sunwell -s swarm docs/cli.md "check for beginner confusion"
    sunwell config model
    sunwell project ~/myapp

SHELL COMPLETION (preserved from do_cmd):
    sunwell -s a<TAB>         → a, a-2, architecture
    sunwell -s a-2 doc<TAB>   → docs/, docker-compose.yml
    sunwell -s a-2 docs/<TAB> → docs/cli.md, docs/api.md, ...
```

### Tier 2: Power User Commands (shown in `--help`)

| Command | Purpose | Notes |
|---------|---------|-------|
| `config` | View/set configuration | Absorbs `bind`, `env`, `bootstrap` |
| `project` | Project operations | Absorbs `workspace`, `scan`, `surface`, `import` |
| `session` | Session management | Absorbs `team` |
| `lens` | Lens management | Already exists, keep as-is |
| `setup` | First-time wizard | Already exists, keep as-is |

### Tier 3: Hidden Commands (not in `--help`, still work)

For developers and debugging. Access via `sunwell --all-commands` to see full list.

| Command | Purpose | Who uses it |
|---------|---------|-------------|
| `benchmark` | Run benchmarks | Developers |
| `demo` | Prism Principle demonstrations | Studio, Developers |
| `eval` | Evaluation suite | Developers, CI, Studio |
| `index` | Codebase indexing | Studio, Developers |
| `runtime` | Runtime management | Developers |
| `chat` | Interactive REPL mode | Power users (retained for discoverability) |

### Tier 4: Internal Commands (Studio contract only)

These are ONLY called by Studio via subprocess. Users never see or type them.
**These MUST remain stable for backward compatibility.**

| Command | Subcommands | Purpose |
|---------|-------------|---------|
| `backlog` | `refresh`, `run` | Autonomous backlog management |
| `dag` | `plan`, `cache stats/clear`, `impact` | DAG execution and caching |
| `interface` | `demo` | Interface demonstrations |
| `lens` | `list`, `show`, `library`, `fork`, `save`, `delete`, `versions`, `rollback`, `set-default`, `export`, `record-usage`, `skills`, `skill-graph`, `skill-plan` | Full lens lifecycle |
| `naaru` | `process`, `convergence` | Naaru coordination |
| `scan` | (project path) | State DAG scanning |
| `security` | `analyze`, `approve`, `audit`, `scan` | Security-first execution |
| `self` | `source read/find/list/search`, `analysis patterns/failures`, `proposals list/show/test/approve/apply/rollback`, `summary` | Self-knowledge introspection |
| `skill` | `cache-stats`, `cache-clear` | Skill cache management |
| `surface` | `registry` | Surface composition registry |
| `weakness` | `scan`, `preview`, `extract-contract` | Weakness cascade detection |
| `workers` | `ui-state`, `pause`, `resume`, `start` | Multi-instance coordination |
| `workflow` | `auto`, `run`, `stop`, `resume`, `skip`, `chains`, `list` | Workflow execution control |
| `workspace` | `detect`, `show`, `link`, `unlink`, `list` | Workspace link management |

**Note**: `demo` and `eval` are also called by Studio but are Tier 3 (developer-accessible).

### Deprecated Commands (aliased, show warning)

```python
DEPRECATED_ALIASES = {
    # "Talk to agent" variants → main entry point
    "agent": "sunwell",           # `agent run "goal"` → `sunwell "goal"`
    "ask": "sunwell",             # `ask "question"` → `sunwell "question"`
    "apply": "sunwell -s",        # `apply lens` → `sunwell -s` with lens
    
    # Shortcut execution absorbed into -s flag
    "do": "sunwell -s",           # `do ::a-2 file` → `sunwell -s a-2 file`
    
    # Absorbed into other commands
    "bind": "sunwell config binding",
    "env": "sunwell config env",
    "bootstrap": "sunwell setup",
    "plan": "sunwell --plan",
    "scan": "sunwell project --scan",
    "workspace": "sunwell project",
    "import": "sunwell project --import",
    "open": "sunwell",            # `open .` → `sunwell .`
    "verify": "sunwell -s verify",
    "guardrails": "sunwell config safety",
    "team": "sunwell session",    # Team context → session management
    
    # Internal leakage (should never have been top-level)
    "briefing": None,  # Remove - agent continuity is internal
    "intel": None,     # Remove - absorbed into project analysis
    "reason": None,    # Remove - internal LLM routing
    "external": None,  # Remove - internal integration
}

# NOT deprecated (retained as hidden):
# - chat: Interactive REPL mode, useful for power users
# - demo: Used by Studio for Prism Principle demos
# - eval: Used by Studio and CI for quality measurement
```

**Migration examples**:
```bash
# Old                          # New
sunwell do ::a-2 docs/api.md   sunwell -s a-2 docs/api.md
sunwell agent run "build X"    sunwell "build X"
sunwell ask "what is X?"       sunwell "what is X?"
sunwell open ~/project         sunwell ~/project
sunwell workspace show         sunwell project show
```

---

## Shortcut System (from RFC-107)

### Syntax

```bash
# Single shortcut
sunwell -s a-2 docs/cli.md

# Chain (sequential)
sunwell -s "p -> a-2 -> r" docs/cli.md

# Parallel (merge results)
sunwell -s "p, r, a-2" docs/cli.md

# Named pipelines
sunwell -s pipeline docs/cli.md      # research → draft → verify
sunwell -s swarm docs/cli.md         # all personas
```

### Built-in Shortcuts

| Shortcut | Skill | Description |
|----------|-------|-------------|
| `a` | audit-documentation | Quick audit |
| `a-2` | audit-documentation-deep | Deep audit with triangulation |
| `p` | polish-documentation | Polish and improve |
| `r` | research-verify | Research and verify claims |
| `health` | check-health | Health check |
| `drift` | detect-drift | Drift detection |
| `lint` | lint-structure | Structure linting |
| `swarm` | [all personas] | Run all personas |
| `pipeline` | [research→draft→verify] | Full docs pipeline |

### Custom Shortcuts via Lens

```yaml
# In lens file
router:
  shortcuts:
    "::review": "code-review"
    "::test": "generate-tests"
```

---

## Migration Plan

### Phase 1: Soft Deprecation (v0.2.0)

1. Add `-s` / `--skill` flag to main command
2. Add deprecation warnings to old commands
3. Hide internal commands from `--help`
4. Update documentation

**No breaking changes.** All old commands still work.

### Phase 2: Hard Deprecation (v0.3.0)

1. Old commands show error with migration hint
2. Remove from `--help` entirely
3. Update Studio to use new patterns where possible

### Phase 3: Removal (v1.0.0)

1. Remove deprecated command modules
2. Clean up CLI codebase
3. Final documentation update

---

## Studio Compatibility

### Contract: Internal Commands

The following commands are called by Studio via subprocess. **These MUST remain stable.**

Verified from `studio/src-tauri/src/`:

| Source File | Command | Subcommands |
|-------------|---------|-------------|
| `dag.rs` | `backlog` | `refresh`, `run` |
| `dag.rs` | `dag` | `plan --json`, `cache stats --json`, `cache clear`, `impact --json` |
| `coordinator.rs` | `workers` | `ui-state`, `pause`, `resume`, `start` |
| `coordinator.rs` | `scan` | `<path> --json` |
| `lens.rs` | `lens` | `list --json`, `show --json`, `library --json`, `fork`, `save`, `delete`, `versions --json`, `rollback`, `set-default`, `export`, `record-usage` |
| `writer.rs` | `lens` | `skills --json`, `skill-graph --json`, `skill-plan --json` |
| `writer.rs` | `skill` | `cache-stats --json`, `cache-clear` |
| `self_knowledge.rs` | `self` | `source read/find/list/search --json`, `analysis patterns/failures --json`, `proposals list/show/test/approve/apply/rollback --json`, `summary --json` |
| `workflow.rs` | `workflow` | `auto --json`, `run --json`, `stop`, `resume --json`, `skip`, `chains --json`, `list --json` |
| `weakness.rs` | `weakness` | `scan --json`, `preview --json`, `extract-contract --json` |
| `security.rs` | `security` | `analyze --json`, `approve --json`, `audit --json`, `scan --json` |
| `surface.rs` | `surface` | `registry --json` |
| `naaru.rs` | `naaru` | `process --stream --json`, `convergence --json` |
| `indexing.rs` | `index` | `build --json --progress`, `query --json`, `metrics --json` |
| `workspace.rs` | `workspace` | `detect --json`, `show --json`, `link`, `unlink`, `list --json` |
| `eval.rs` | `eval` | `--list-tasks --json`, `--stats --json`, (run with streaming) |
| `demo.rs` | `demo` | (run with streaming) |
| `interface.rs` | `interface` | `demo` |

**Total**: ~60 distinct CLI call patterns across 14 source files.

**Strategy**: Keep these commands working internally but hide from user-facing `--help`.

### Future: Native IPC

In a future RFC, consider replacing subprocess calls with:
- Unix domain sockets
- gRPC
- Tauri's native Rust-Python bridge

This would eliminate the CLI contract entirely for Studio.

### Testing Strategy

To ensure Studio compatibility:

1. **Contract test file**: Create `tests/test_studio_contract.py` that exercises all CLI patterns from the table above
2. **Snapshot testing**: Capture `--help` output for each command; fail if signature changes
3. **Integration test**: Run Studio e2e tests before any CLI release
4. **Grep audit script**: `grep -r "Command::new.*sunwell" studio/src-tauri/src/` must match documented patterns

```python
# tests/test_studio_contract.py
STUDIO_CLI_PATTERNS = [
    ["backlog", "refresh"],
    ["dag", "plan", "--json"],
    ["dag", "cache", "stats", "--json"],
    ["lens", "list", "--json"],
    ["lens", "show", "test-lens", "--json"],
    ["naaru", "process", "--stream", "--json", "test"],
    # ... all 60 patterns
]

@pytest.mark.parametrize("args", STUDIO_CLI_PATTERNS)
def test_studio_cli_pattern(args):
    """Ensure all Studio CLI patterns work."""
    result = subprocess.run(["sunwell", *args], capture_output=True)
    assert result.returncode == 0 or "--help" in result.stderr.decode()
```

---

## Implementation

### Shell Completion (preserved)

The current `do_cmd.py` has shell completion for shortcuts and file paths. This MUST be preserved:

```python
# From do_cmd.py - migrate to main.py

def complete_shortcut(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[str]:
    """Complete shortcut commands from lens."""
    shortcuts = list(_get_default_lens_shortcuts().keys())
    return [s for s in shortcuts if s.startswith(incomplete)]

def complete_target(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[str]:
    """Complete file paths for target argument."""
    base = Path(incomplete).parent if incomplete else Path(".")
    prefix = Path(incomplete).name if incomplete else ""
    
    completions = []
    for path in base.iterdir():
        if path.name.startswith("."):
            continue
        if path.name.startswith(prefix):
            if path.is_dir():
                completions.append(f"{path}/")
            elif path.suffix in (".md", ".rst", ".txt", ".py", ".yaml", ".yml", ".json", ".toml"):
                completions.append(str(path))
    return sorted(completions)[:20]
```

Usage in main:
```python
@click.option("-s", "--skill", shell_complete=complete_shortcut, help="Run skill shortcut")
@click.argument("target", required=False, shell_complete=complete_target)
```

### Changes to `main.py`

```python
@click.group(cls=GoalFirstGroup, invoke_without_command=True)
@click.option("-s", "--skill", shell_complete=complete_shortcut, help="Run skill shortcut")
@click.option("-c", "--chain", help="Chain shortcuts: 'p -> a-2'")
@click.option("-l", "--lens", default="tech-writer", help="Lens to use")
@click.option("-m", "--model", help="Override model")
@click.option("-p", "--provider", help="Override provider")
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("--all-commands", is_flag=True, hidden=True, help="Show all commands")
@click.argument("target", required=False, shell_complete=complete_target)
@click.argument("context", nargs=-1)  # Captures remaining args as context
@click.pass_context
def main(ctx, skill, chain, lens, model, provider, plan, json_output, verbose, all_commands, target, context):
    """Sunwell - Your AI development partner.
    
    Talk naturally or use shortcuts:
    
        sunwell "audit the CLI docs"
        sunwell -s a-2 docs/cli.md
        sunwell -s a-2 docs/cli.md "focus on the migration section"
    """
    if all_commands:
        _show_all_commands()
        return
    
    # Join context args into a single string
    context_str = " ".join(context) if context else None
    
    if skill or chain:
        # Route to shortcut execution
        return _run_shortcut(
            skill or chain, target, context_str, 
            lens, model, provider, plan, json_output, verbose
        )
    
    if target and not target.startswith("-"):
        # Target without -s is treated as a goal
        goal = target
        if context_str:
            goal = f"{target} {context_str}"
        return _run_agent(goal, lens, model, provider, plan, json_output, verbose)
    
    # No args - show help
    click.echo(ctx.get_help())


# Visible commands (Tier 1 & 2)
main.add_command(config_cmd.config)
main.add_command(project_cmd.project)
main.add_command(session_cmd.session)
main.add_command(lens_cmd.lens)
main.add_command(setup_cmd.setup)

# Hidden commands (Tier 3) - accessible but not in --help
main.add_command(benchmark_cmd.benchmark, hidden=True)
main.add_command(eval_cmd.eval_cmd, hidden=True)
main.add_command(index_cmd.index, hidden=True)
main.add_command(dag_cmd.dag, hidden=True)
main.add_command(runtime_cmd.runtime, hidden=True)

# Internal commands (Tier 4) - for Studio only
main.add_command(interface_cmd.interface, hidden=True)
main.add_command(backlog_cmd.backlog, hidden=True)
main.add_command(naaru_cmd.naaru, hidden=True)
# ... etc

# Deprecated aliases with warnings
for old, new in DEPRECATED_ALIASES.items():
    main.add_command(_make_deprecated_command(old, new), hidden=True)
```

### New File Structure

```
cli/
├── main.py              # Entry point with -s flag
├── shortcuts.py         # Shortcut execution logic (from do_cmd.py)
├── agent.py             # Agent execution (absorbed from agent_cmd.py)
├── config_cmd.py        # Unified config (absorbs bind, env, bootstrap)
├── project_cmd.py       # Unified project (absorbs workspace, scan, etc.)
├── session_cmd.py       # Session management (absorbs team)
├── lens_cmd.py          # Lens management (keep as-is)
├── setup_cmd.py         # Setup wizard (keep as-is)
├── internal/            # Studio-only commands
│   ├── interface.py
│   ├── dag.py
│   ├── backlog.py
│   └── ...
└── deprecated/          # Deprecated command stubs
    └── aliases.py
```

---

## Success Criteria

1. **Reduced cognitive load**: `sunwell --help` shows ≤10 items
2. **Clear entry point**: `sunwell "goal"` or `sunwell -s shortcut`
3. **Zero breaking changes**: All Studio calls continue working
4. **Deprecation path**: Old commands warn but work through v0.3.0

---

## Risks

| Risk | Mitigation |
|------|------------|
| Studio breaks | Keep internal commands stable; add integration tests that exercise all ~60 Studio CLI patterns |
| User confusion during transition | Clear deprecation warnings with migration hints; provide `sunwell migrate` command to check scripts |
| Lost functionality | Ensure all features accessible via new patterns; `--all-commands` escape hatch |
| Documentation debt | Update all docs as part of implementation; generate migration guide from DEPRECATED_ALIASES |
| Shell completion regression | Port `do_cmd.py` completion functions to `main.py` before deprecating `do` |
| RFC-107 expectation mismatch | Clearly document that chain syntax is optional; single shortcuts work immediately |

---

## Alternatives Considered

### 1. Keep current CLI
**Rejected**: 43 commands is unmaintainable and confusing.

### 2. Radical reduction to just `sunwell`
**Rejected**: Power users need shortcuts, Studio needs internal commands.

### 3. Separate CLI for users vs Studio
**Considered**: Could have `sunwell` (user) and `sunwell-internal` (Studio). Adds complexity but cleaner separation. May revisit in v1.0.

---

## Timeline

| Phase | Version | Date | Scope |
|-------|---------|------|-------|
| 1 | v0.2.0 | 2026-Q1 | Soft deprecation, add -s flag |
| 2 | v0.3.0 | 2026-Q2 | Hard deprecation, hide old commands |
| 3 | v1.0.0 | 2026-Q3 | Remove deprecated, finalize |

---

## Appendix: Full Command Audit

### Current Commands (43)

| Command | Disposition | Notes |
|---------|-------------|-------|
| `agent` | Deprecated → `sunwell` | Core functionality |
| `apply` | Deprecated → `sunwell -s` | Already deprecated |
| `ask` | Deprecated → `sunwell` | Already deprecated |
| `backlog` | Internal (Studio) | Keep for Studio |
| `benchmark` | Hidden (Tier 3) | Developer tool |
| `bind` | Deprecated → `config binding` | Absorbed |
| `bootstrap` | Deprecated → `setup` | Absorbed |
| `briefing` | Remove | Internal leak |
| `chat` | Hidden (Tier 3) | Interactive mode retained for power users |
| `config` | Keep (Tier 2) | Primary config |
| `dag` | Internal (Studio) | Keep for Studio |
| `demo` | Hidden (Tier 3) | Studio uses for demos; keep accessible |
| `do` | Deprecated → `sunwell -s` | Absorbed |
| `env` | Deprecated → `config env` | Absorbed |
| `eval` | Hidden (Tier 3) | Developer tool |
| `exec` | Deprecated → `skill run` | Legacy command |
| `external` | Remove | Internal leak |
| `guardrails` | Deprecated → `config safety` | Absorbed |
| `import` | Deprecated → `project --import` | Absorbed |
| `index` | Hidden (Tier 3) | Developer/Studio |
| `intel` | Remove | Internal leak |
| `interface` | Internal (Studio) | Keep for Studio |
| `lens` | Keep (Tier 2) | Primary lens mgmt |
| `naaru` | Internal (Studio) | Keep for Studio |
| `open` | Deprecated → `sunwell PATH` | Absorbed |
| `plan` | Deprecated → `--plan` | Absorbed |
| `project` | Keep (Tier 2) | Primary project |
| `reason` | Remove | Internal leak |
| `runtime` | Hidden (Tier 3) | Developer tool |
| `scan` | Internal (Studio) | Keep for Studio; user-facing via `project --scan` |
| `security` | Internal (Studio) | Keep for Studio |
| `self` | Internal (Studio) | Keep for Studio |
| `session` | Keep (Tier 2) | Primary session |
| `setup` | Keep (Tier 2) | Primary setup |
| `skill` | Internal (Studio) | Keep for Studio |
| `surface` | Internal (Studio) | Keep for Studio |
| `team` | Deprecated → `session` | Absorbed |
| `validate` | Deprecated → `skill validate` | Legacy command |
| `verify` | Deprecated → `-s verify` | Absorbed |
| `weakness` | Internal (Studio) | Keep for Studio |
| `workers` | Internal (Studio) | Keep for Studio |
| `workflow` | Internal (Studio) | Keep for Studio |
| `workspace` | Deprecated → `project` | Absorbed |

### Result

| Disposition | Count | Commands |
|-------------|-------|----------|
| **Keep visible (Tier 1-2)** | 5 | `config`, `project`, `session`, `lens`, `setup` |
| **Hidden (Tier 3)** | 6 | `benchmark`, `chat`, `demo`, `eval`, `index`, `runtime` |
| **Internal (Tier 4)** | 14 | `backlog`, `dag`, `interface`, `naaru`, `scan`, `security`, `self`, `skill`, `surface`, `weakness`, `workers`, `workflow`, `workspace` + `lens` extended subcommands |
| **Deprecated** | 14 | `agent`, `apply`, `ask`, `bind`, `bootstrap`, `do`, `env`, `exec`, `guardrails`, `import`, `open`, `plan`, `team`, `validate`, `verify` |
| **Remove** | 5 | `briefing`, `external`, `intel`, `reason` |

**Net visible commands**: 43 → 5 (88% reduction in `--help` noise)
