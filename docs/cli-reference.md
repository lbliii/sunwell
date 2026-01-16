# Sunwell CLI Reference

## Getting Started

### `sunwell setup`
One-time setup to create default bindings.

```bash
sunwell setup [OPTIONS]
```

**Options**:
- `--provider, -p <name>`: Default provider (default: openai)
- `--model, -m <name>`: Default model (auto-selected if not specified)
- `--lenses-dir <path>`: Directory containing lens files
- `--force, -f`: Overwrite existing bindings

**Creates these bindings:**
| Binding | Lens | Tier | Description |
|---------|------|------|-------------|
| `writer` ⭐ | tech-writer.lens | 1 (Standard) | Technical documentation |
| `reviewer` | code-reviewer.lens | 2 (Deep) | Code review |
| `helper` | helper.lens | 0 (Fast) | Quick questions |

**Examples**:
```bash
sunwell setup                           # Use OpenAI defaults
sunwell setup --provider anthropic      # Use Claude
sunwell setup --force                   # Reset to defaults
```

After setup:
```bash
sunwell ask "Write docs for my API"              # Uses writer (default)
sunwell ask reviewer "Review this PR"            # Uses reviewer
sunwell ask helper "What does this error mean?"  # Uses helper (fast)
```

---

## Core Commands

### `sunwell apply`
Apply a lens to a single prompt.

```bash
sunwell apply <lens> <prompt> [OPTIONS]
```

**Options**:
- `--model, -m <name>`: Model name (default: auto based on provider)
- `--provider, -p <name>`: Provider (openai, anthropic, mock)
- `--tier <0|1|2>`: Execution tier (0=fast, 1=standard, 2=deep)
- `--headspace, -H <name>`: Use/create persistent headspace
- `--context, -c <pattern>`: File patterns to include
- `--output, -o <path>`: Write output to file
- `--verbose, -v`: Verbose output

**Examples**:
```bash
sunwell apply tech-writer.lens "Document auth.py"
sunwell apply code-reviewer.lens "Review this PR" --tier 2 --headspace my-project
```

---

### `sunwell ask` ⭐
The simplest way to use Sunwell! Uses bindings for zero-flag invocation.

```bash
sunwell ask <binding> <prompt>
sunwell ask <prompt>  # Uses default binding
```

**Options**:
- `--provider, -p`: Override provider
- `--model, -m`: Override model
- `--tier`: Override tier
- `--output, -o`: Write output to file

**Examples**:
```bash
sunwell ask my-project "Write API docs"      # Uses binding settings
sunwell ask "Review this code"               # Uses default binding
sunwell ask my-project "Complex task" --tier 2
```

---

## Binding Commands

Bindings are your "soul stones" — attune once, use forever without flags.

### `sunwell bind create`
Create a new binding.

```bash
sunwell bind create <name> --lens <path> [OPTIONS]
```

**Options**:
- `--lens, -l <path>`: Path to lens file (required)
- `--provider, -p`: LLM provider (default: openai)
- `--model, -m`: Model name
- `--tier <0|1|2>`: Default tier
- `--set-default`: Set as default binding

**Example**:
```bash
sunwell bind create my-docs --lens tech-writer.lens --provider anthropic --set-default
```

### `sunwell bind list`
List all bindings.

```bash
sunwell bind list
```

### `sunwell bind show`
Show binding details.

```bash
sunwell bind show <name>
```

### `sunwell bind default`
Get or set default binding.

```bash
sunwell bind default           # Show current
sunwell bind default <name>    # Set default
```

### `sunwell bind delete`
Delete a binding.

```bash
sunwell bind delete <name> [--force]
```

---

## Chat & Sessions

### `sunwell chat`
Start interactive chat with persistent headspace.

```bash
sunwell chat <lens> [OPTIONS]
```

**Options**:
- `--session, -s <name>`: Session name (creates/resumes)
- `--model, -m`: Model name
- `--provider, -p`: Provider

**In-chat commands**:
- `/switch <provider:model>`: Switch models mid-conversation
- `/branch <name>`: Create exploration branch
- `/dead-end`: Mark current path as dead end
- `/learn <fact>`: Add learning manually
- `/learnings`: Show all learnings
- `/quit`: Save and exit

**Example**:
```bash
sunwell chat code-reviewer.lens --session auth-debugging
```

### `sunwell sessions list`
List saved sessions.

### `sunwell sessions stats`
Show storage statistics.

### `sunwell sessions archive`
Archive old sessions to cold storage.

---

## Lens Management

### `sunwell validate`
Validate a lens file.

```bash
sunwell validate <lens>
```

### `sunwell list`
List available lenses.

```bash
sunwell list [--path <dir>]
```

### `sunwell inspect`
Show lens details.

```bash
sunwell inspect <lens>
```

---

## Skill Execution

### `sunwell exec`
Execute a skill from a lens.

```bash
sunwell exec <lens> <skill-name> <task> [OPTIONS]
```

**Options**:
- `--model, -m`: Model name
- `--provider, -p`: Provider
- `--output, -o`: Output file
- `--dry-run`: Don't write files

**Example**:
```bash
sunwell exec tech-writer.lens create-api-docs "Document auth.py" -o docs/auth.md
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |

You can also use a `.env` file in your project root.

---

## Workflow Examples

### Daily workflow with bindings
```bash
# Setup (once)
sunwell bind create work --lens tech-writer.lens --set-default

# Daily use (no flags!)
sunwell ask "Document the auth module"
sunwell ask "What learnings do we have?"
sunwell ask "Try a different approach" --tier 2
```

### Problem-solving session
```bash
sunwell chat code-reviewer.lens --session fix-auth-bug

# In chat:
> The tests are failing on line 42
> /branch try-mocking
> That didn't work
> /dead-end
> /checkout main
> /switch anthropic:claude-sonnet-4-20250514
> Fresh perspective - what do you see?
```

### Multi-model handoff
```bash
# Start with fast model
sunwell ask my-project "Quick check on this pattern" --tier 0

# Switch to deep analysis
sunwell ask my-project "Deep review of security" --tier 2 -m claude-sonnet-4-20250514

# All learnings persist in the same headspace!
```
