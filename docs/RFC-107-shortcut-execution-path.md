# RFC-107: Shortcut Execution Path — Make `::a-2 this doc` Work

**Status**: ✅ Implemented  
**Created**: 2026-01-23  
**Authors**: Sunwell Team  
**Priority**: P0 — Critical Use Case  
**Confidence**: 95% 🟢  
**Depends on**: RFC-070 (DORI Lens Migration, Implemented), RFC-011 (Agent Skills)

---

## Summary

Wire the existing shortcut system (`::a`, `::a-2`, etc.) to actual skill execution. All components exist but aren't connected. This RFC closes the gap and delivers a **delightful, discoverable** shortcut experience across CLI and Studio.

**Target state**: User types `sunwell do ::a-2 docs/api.md` → Deep audit runs → Results stream inline with findings highlighted in the document.

**One-liner**: Connect shortcut parsing to skill execution, with discovery UX that helps users learn and love shortcuts.

**S-tier differentiators**:
- Command palette UX in Studio (not just dropdown)
- Inline result annotations (findings appear in document)
- Keyboard shortcuts (Cmd+Shift+A for audit)
- Execution history with re-run
- Smart context injection (related files, git diff)

---

## Motivation

### The DORI Pattern

In Cursor + DORI prompt library:

```
::a-2 this doc
        ↓
Cursor loads validation/docs-audit-enhanced/RULE.mdc
        ↓
Agent runs with full tool access (read_file, grep, codebase_search)
        ↓
Audit report with confidence scoring
```

This is the **core critical use case** for Sunwell right now. Everything else is secondary.

### What Sunwell Has (Designed, Not Connected)

| Component | Status | Location |
|-----------|--------|----------|
| Skill triggers `::a`, `::a-2` | ✅ Defined | `skills/docs-validation-skills.yaml:13,51` |
| Shortcut → skill mapping | ✅ Designed | `Router.shortcuts` in `core/lens.py:140-144` |
| Shortcut parsing | ✅ Implemented | `UnifiedRouter._check_shortcut()` |
| Skill executor | ✅ Implemented | `skills/executor.py` |
| Chat `::command` parsing | ✅ Implemented | `runtime/commands.py` |

### What's Missing

```
User: sunwell ::a-2 docs/api.md
                    ↓
           [GAP - Nothing connects here]
                    ↓
SkillExecutor.execute()
```

The router returns a `RoutingDecision` with `suggested_skills`, but:
1. No CLI command invokes shortcuts directly
2. Chat commands don't route to skills from triggers
3. No lens bundled with validation skills and shortcuts

---

## Goals

### P0: Core Functionality
1. **`sunwell do ::a-2 docs/api.md`** — Direct CLI invocation works
2. **Chat mode** — `::a-2` in `sunwell chat` triggers skill execution
3. **Natural language fallback** — "audit this doc deeply" suggests `::a-2`
4. **Zero new concepts** — Use existing infrastructure only

### P1: Power User Features
5. **Shell completions** — Tab-complete file paths and shortcuts
6. **Studio command palette** — Cursor-style `Cmd+K` interface with shortcuts + files
7. **Keyboard shortcuts** — `Cmd+Shift+A` triggers audit on focused file

### S-tier: Delight
8. **Discovery UX** — Ambient hints help new users learn shortcuts
9. **Inline results** — Audit findings appear as annotations in document
10. **Execution history** — Re-run previous shortcuts, view history
11. **Progress streaming** — Real-time feedback for long-running skills
12. **Smart context** — Auto-inject related files, git diff, workspace info

## Non-Goals

1. New skill system — Use existing `SkillExecutor`
2. New routing system — Use existing `UnifiedRouter`
3. New shortcuts — Use existing DORI-compatible shortcuts
4. New Rust command infrastructure — Reuse existing `writer.rs` handlers

---

## Detailed Design

### Design Principle: Single-Source Shortcut Registry

**Problem**: The naive approach has 3 copies of shortcut definitions:
1. Python CLI completion function
2. Rust `get_shortcut_suggestions`
3. YAML skill triggers

**Solution**: All shortcuts are defined **once** in the lens, loaded at runtime.

```yaml
# lenses/docs-assistant.lens — THE source of truth
router:
  shortcuts:
    "::a": "audit-documentation"
    "::a-2": "audit-documentation-deep"
    # ... etc
```

All consumers load from lens:

```python
# Python CLI completion
def complete_shortcut(ctx, param, incomplete):
    lens = _get_default_lens()  # Load docs-assistant.lens
    shortcuts = list(lens.router.shortcuts.keys()) if lens.router else []
    return [s for s in shortcuts if s.startswith(incomplete)]
```

```rust
// Rust/Tauri
#[tauri::command]
pub async fn get_shortcut_suggestions(query: String) -> Vec<Suggestion> {
    // Call Python to get lens shortcuts (or cache at startup)
    let lens = get_current_lens().await?;
    lens.router.shortcuts
        .iter()
        .filter(|(name, _)| name.contains(&query))
        .map(|(name, skill)| Suggestion { ... })
        .collect()
}
```

**Benefits**:
- Add a shortcut once → available everywhere
- No drift between CLI/Studio
- Custom per-workspace shortcuts work automatically

---

### Part 1: CLI Entry Point

Add a `do` command that accepts shortcuts:

```python
# src/sunwell/cli/do_cmd.py

@click.command("do")
@click.argument("shortcut")  # e.g., "::a-2"
@click.argument("target", required=False)  # e.g., "docs/api.md"
@click.option("--lens", "-l", default="tech-writer", help="Lens to use")
@click.option("--provider", "-p", default=None, help="Model provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def do_cmd(shortcut: str, target: str | None, lens: str, provider: str | None, 
           model: str | None, verbose: bool) -> None:
    """Execute a shortcut command.
    
    Shortcuts are DORI-compatible command aliases that trigger skills.
    
    Examples:
        sunwell do ::a-2 docs/api.md        # Deep audit
        sunwell do ::health                  # Health check
        sunwell do ::p docs/overview.md     # Polish document
    """
    asyncio.run(_do_shortcut(shortcut, target, lens, provider, model, verbose))
```

Implementation:

```python
async def _do_shortcut(
    shortcut: str,
    target: str | None,
    lens_name: str,
    provider: str | None,
    model: str | None,
    verbose: bool,
) -> None:
    """Execute shortcut → skill pipeline."""
    from sunwell.cli.helpers import resolve_model
    from sunwell.fount.resolver import LensResolver
    from sunwell.schema.loader import LensLoader
    from sunwell.skills.executor import SkillExecutor
    from sunwell.workspace.detector import WorkspaceDetector
    
    # 1. Load lens
    loader = LensLoader()
    resolver = LensResolver(loader=loader)
    
    # Try built-in lens first, then local file
    lens = await _resolve_lens(resolver, lens_name)
    if not lens:
        console.print(f"[red]Lens not found:[/red] {lens_name}")
        return
    
    # 2. Resolve shortcut → skill
    if not lens.router or not lens.router.shortcuts:
        console.print(f"[red]Lens has no shortcuts defined[/red]")
        return
    
    skill_name = lens.router.shortcuts.get(shortcut)
    if not skill_name:
        # Try without :: prefix
        skill_name = lens.router.shortcuts.get(f"::{shortcut.lstrip(':')}")
    
    if not skill_name:
        console.print(f"[red]Unknown shortcut:[/red] {shortcut}")
        console.print(f"[dim]Available: {', '.join(lens.router.shortcuts.keys())}[/dim]")
        return
    
    # 3. Find skill in lens
    skill = lens.get_skill(skill_name)
    if not skill:
        console.print(f"[red]Skill not found in lens:[/red] {skill_name}")
        return
    
    if verbose:
        console.print(f"[dim]Shortcut {shortcut} → skill {skill_name}[/dim]")
    
    # 4. Build rich context (S-tier: smart context injection)
    context = await _build_skill_context(target, workspace_root)
    
    # 5. Detect workspace
    workspace_root = None
    try:
        detector = WorkspaceDetector()
        workspace = detector.detect()
        workspace_root = workspace.root
        context["workspace_root"] = str(workspace_root)
    except Exception:
        pass


async def _build_skill_context(target: str | None, workspace_root: Path | None) -> dict:
    """Build rich context for skill execution (S-tier feature).
    
    Goes beyond just file content to provide:
    - Related files (tests, implementations, schemas)
    - Git context (uncommitted changes, recent commits)
    - Diataxis type detection
    - Recent edit locations
    """
    context = {}
    
    if not target:
        return context
    
    target_path = Path(target).expanduser()
    if not target_path.exists():
        context["target"] = target
        return context
    
    # Basic file info
    context["target_file"] = str(target_path)
    context["file_content"] = target_path.read_text()
    context["file_type"] = target_path.suffix.lstrip(".")
    
    # S-tier: Find related files
    if workspace_root:
        related = _find_related_files(target_path, workspace_root)
        if related:
            context["related_files"] = related
    
    # S-tier: Git context for drift detection
    git_diff = _get_git_diff(target_path)
    if git_diff:
        context["uncommitted_changes"] = git_diff
    
    # S-tier: Diataxis type detection for docs
    if target_path.suffix in (".md", ".rst"):
        diataxis_type = _detect_diataxis_type(target_path)
        if diataxis_type:
            context["diataxis_type"] = diataxis_type
    
    return context


def _find_related_files(target: Path, workspace: Path) -> list[dict]:
    """Find files related to target (tests, implementations, schemas)."""
    related = []
    stem = target.stem
    
    # Look for test files
    for pattern in [f"test_{stem}.py", f"{stem}_test.py", f"test_{stem}.ts"]:
        for match in workspace.rglob(pattern):
            related.append({"path": str(match), "relation": "test"})
    
    # Look for implementation if this is a doc
    if target.suffix in (".md", ".rst"):
        # Extract module references from content
        content = target.read_text()
        # Simple heuristic: look for backticked paths
        import re
        for match in re.findall(r'`([a-z_/]+\.py)`', content):
            impl_path = workspace / match
            if impl_path.exists():
                related.append({"path": str(impl_path), "relation": "implementation"})
    
    return related[:5]  # Limit to avoid context bloat


def _get_git_diff(target: Path) -> str | None:
    """Get uncommitted changes for target file."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--", str(target)],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout if result.stdout else None
    except Exception:
        return None


def _detect_diataxis_type(target: Path) -> str | None:
    """Detect Diataxis document type from content."""
    content = target.read_text().lower()
    
    # Simple heuristics
    if any(word in content for word in ["step 1", "step 2", "in this tutorial", "you will learn"]):
        return "TUTORIAL"
    if any(word in content for word in ["how to", "guide", "troubleshooting"]):
        return "HOW-TO"
    if any(word in content for word in ["api reference", "parameters:", "returns:", "arguments:"]):
        return "REFERENCE"
    if any(word in content for word in ["architecture", "how it works", "design", "concepts"]):
        return "EXPLANATION"
    
    return None
    
    # 6. Create model
    synthesis_model = resolve_model(provider, model)
    
    # 7. Execute skill
    executor = SkillExecutor(
        skill=skill,
        lens=lens,
        model=synthesis_model,
        workspace_root=workspace_root,
    )
    
    with console.status(f"[bold green]Running {skill_name}..."):
        result = await executor.execute(
            context=context,
            validate=True,
            dry_run=False,
        )
    
    # 8. Display result
    if verbose:
        console.print(f"\n[cyan]Execution:[/cyan]")
        console.print(f"  Time: {result.execution_time_ms}ms")
        console.print(f"  Validation: {'✅' if result.validation_passed else '⚠️'} ({result.confidence:.0%})")
    
    console.print(f"\n{result.content}")
```

### Part 2: Chat Integration

Extend `runtime/commands.py` to route shortcuts to skills:

```python
# src/sunwell/runtime/commands.py (add to existing)

@commands.register("a", "Quick audit (alias for audit-documentation skill)")
async def cmd_audit(args: str, session: ChatSession) -> str:
    """Execute audit-documentation skill."""
    return await _execute_skill_shortcut("::a", args, session)


@commands.register("a-2", "Deep audit with triangulation")
async def cmd_audit_deep(args: str, session: ChatSession) -> str:
    """Execute audit-documentation-deep skill."""
    return await _execute_skill_shortcut("::a-2", args, session)


@commands.register("p", "Polish documentation")
async def cmd_polish(args: str, session: ChatSession) -> str:
    """Execute polish-documentation skill."""
    return await _execute_skill_shortcut("::p", args, session)


@commands.register("health", "Documentation health check")
async def cmd_health(args: str, session: ChatSession) -> str:
    """Execute check-health skill."""
    return await _execute_skill_shortcut("::health", args, session)


async def _execute_skill_shortcut(shortcut: str, args: str, session: ChatSession) -> str:
    """Execute a skill via shortcut."""
    if not session.lens:
        return "No lens loaded. Use --lens when starting chat."
    
    if not session.lens.router or not session.lens.router.shortcuts:
        return "Current lens has no shortcuts defined."
    
    skill_name = session.lens.router.shortcuts.get(shortcut)
    if not skill_name:
        return f"Shortcut {shortcut} not defined in current lens."
    
    skill = session.lens.get_skill(skill_name)
    if not skill:
        return f"Skill {skill_name} not found in lens."
    
    # Build context from args
    context = {"task": args} if args else {}
    
    # If args looks like a file path, read it
    if args and Path(args).exists():
        context["target_file"] = args
        context["file_content"] = Path(args).read_text()
    
    # Execute (model should be available from chat session)
    # This would need the model from chat context - simplified here
    return f"Would execute skill: {skill_name}\nContext: {context}\n\n[Note: Full execution requires model integration]"
```

### Part 3: Default Lens with Shortcuts

Create `lenses/docs-assistant.lens` that bundles validation skills:

```yaml
# lenses/docs-assistant.lens
lens:
  metadata:
    name: "Docs Assistant"
    domain: "documentation"
    version: "1.0.0"
    description: "DORI-compatible documentation assistant with shortcuts"
  
  # Include validation skills
  skills:
    - include: ../skills/docs-validation-skills.yaml
  
  # DORI-compatible shortcuts
  router:
    shortcuts:
      "::a": "audit-documentation"
      "::a-2": "audit-documentation-deep"
      "::p": "polish-documentation"
      "::health": "check-health"
      "::score": "score-confidence"
      "::drift": "detect-drift"
      "::lint": "lint-structure"
      "::vdr": "assess-vdr"
      "::examples": "audit-code-examples"
      "::readability": "check-readability"
```

### Part 4: Main CLI Integration

Add `do` command to main CLI:

```python
# src/sunwell/cli/main.py (add to existing)

from sunwell.cli import do_cmd
main.add_command(do_cmd.do_cmd, name="do")
```

### Part 5: Shell Completions

Enable tab-completion for file paths and shortcuts. Click has built-in completion support:

```python
# src/sunwell/cli/do_cmd.py (add to existing)

def complete_shortcut(ctx, param, incomplete):
    """Complete shortcut commands."""
    shortcuts = [
        "::a", "::a-2", "::p", "::health", "::score",
        "::drift", "::lint", "::vdr", "::examples", "::readability"
    ]
    return [s for s in shortcuts if s.startswith(incomplete)]


def complete_target(ctx, param, incomplete):
    """Complete file paths for target argument."""
    from pathlib import Path
    
    # Start from current directory or incomplete path
    base = Path(incomplete).parent if incomplete else Path(".")
    prefix = Path(incomplete).name if incomplete else ""
    
    completions = []
    try:
        for path in base.iterdir():
            if path.name.startswith(prefix):
                if path.is_dir():
                    completions.append(f"{path}/")
                elif path.suffix in (".md", ".rst", ".txt", ".py", ".yaml", ".json"):
                    completions.append(str(path))
    except OSError:
        pass
    
    return sorted(completions)[:20]  # Limit for performance


@click.command("do")
@click.argument("shortcut", shell_complete=complete_shortcut)
@click.argument("target", required=False, shell_complete=complete_target)
# ... rest of options
def do_cmd(...):
    ...
```

**Installation** (one-time setup):

```bash
# Bash
sunwell --install-completion bash >> ~/.bashrc

# Zsh
sunwell --install-completion zsh >> ~/.zshrc

# Fish
sunwell --install-completion fish > ~/.config/fish/completions/sunwell.fish
```

**Usage after setup**:

```bash
$ sunwell do ::<TAB>
::a         ::a-2       ::drift     ::examples  ::health    
::lint      ::p         ::readability ::score   ::vdr

$ sunwell do ::a-2 docs/<TAB>
docs/api.md           docs/config.md        docs/overview.md
docs/reference/       docs/tutorials/

$ sunwell do ::a-2 docs/api<TAB>
docs/api.md           docs/api-reference.md
```

### Part 6: Studio Command Palette (S-tier UX)

The desktop app (Sunwell Studio) provides a **command palette** experience inspired by VS Code/Cursor. This goes beyond dropdown autocomplete to provide a discoverable, keyboard-first interface.

#### 6.1 Command Palette vs. Inline Dropdown

| Approach | Pros | Cons |
|----------|------|------|
| Inline dropdown | Familiar, quick | Limited space, no context |
| **Command palette** | Shows context, history, keyboard-first | Extra keystroke to open |

**Decision**: Command palette for `Cmd+K`, inline hints for `::` typing.

#### 6.2 Mention Types

| Prefix | Type | Example | Result |
|--------|------|---------|--------|
| `@` | File | `@docs/api.md` | File content added to context |
| `@` | Directory | `@src/` | Directory listing added |
| `::` | Shortcut | `::a-2` | Skill execution triggered |
| `#` | Lens | `#tech-writer` | Switch active lens |
| `::!!` | Re-run | `::!!` | Re-run last shortcut |

#### 6.2 Frontend Component (Svelte)

```svelte
<!-- studio/src/components/MentionInput.svelte -->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { invoke } from '@tauri-apps/api/tauri';
  
  export let value = '';
  export let placeholder = '::a-2 @docs/api.md';
  
  const dispatch = createEventDispatcher();
  
  let suggestions: Suggestion[] = [];
  let showDropdown = false;
  let selectedIndex = 0;
  let mentionStart = -1;
  let mentionType: 'file' | 'shortcut' | 'lens' | null = null;
  
  interface Suggestion {
    type: 'file' | 'directory' | 'skill' | 'lens';
    value: string;
    display: string;
    icon: string;
    preview?: string;
    description?: string;
  }
  
  // Trigger characters
  const TRIGGERS = {
    '@': 'file',
    '::': 'shortcut', 
    '#': 'lens'
  } as const;
  
  async function handleInput(e: InputEvent) {
    const input = e.target as HTMLInputElement;
    const pos = input.selectionStart || 0;
    const text = input.value;
    
    // Check for trigger patterns
    for (const [trigger, type] of Object.entries(TRIGGERS)) {
      const triggerPos = text.lastIndexOf(trigger, pos);
      if (triggerPos !== -1 && triggerPos >= pos - 50) {
        // Extract query after trigger
        const query = text.slice(triggerPos + trigger.length, pos);
        
        // Don't trigger on spaces (completed mention)
        if (query.includes(' ')) continue;
        
        mentionStart = triggerPos;
        mentionType = type as typeof mentionType;
        
        // Fetch suggestions from backend
        suggestions = await invoke('get_mention_suggestions', { 
          query, 
          mention_type: type 
        });
        
        showDropdown = suggestions.length > 0;
        selectedIndex = 0;
        return;
      }
    }
    
    // No trigger found
    showDropdown = false;
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (!showDropdown) return;
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        break;
      case 'Tab':
      case 'Enter':
        if (suggestions[selectedIndex]) {
          e.preventDefault();
          selectSuggestion(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        showDropdown = false;
        break;
    }
  }
  
  function selectSuggestion(suggestion: Suggestion) {
    const trigger = mentionType === 'shortcut' ? '::' : 
                    mentionType === 'lens' ? '#' : '@';
    
    // Replace trigger+query with completed mention
    const before = value.slice(0, mentionStart);
    const afterPos = value.indexOf(' ', mentionStart);
    const after = afterPos === -1 ? '' : value.slice(afterPos);
    
    value = `${before}${trigger}${suggestion.value} ${after}`.trim();
    showDropdown = false;
    
    // Dispatch event for parent to handle
    dispatch('mention', { type: suggestion.type, value: suggestion.value });
  }
</script>

<div class="mention-input-container">
  <input
    type="text"
    bind:value
    on:input={handleInput}
    on:keydown={handleKeydown}
    on:blur={() => setTimeout(() => showDropdown = false, 200)}
    {placeholder}
    class="mention-input"
  />
  
  {#if showDropdown}
    <div class="suggestions-dropdown" role="listbox">
      {#each suggestions as suggestion, i}
        <button
          class="suggestion"
          class:selected={i === selectedIndex}
          on:click={() => selectSuggestion(suggestion)}
          on:mouseenter={() => selectedIndex = i}
          role="option"
          aria-selected={i === selectedIndex}
        >
          <span class="icon">{suggestion.icon}</span>
          <div class="content">
            <span class="display">{suggestion.display}</span>
            {#if suggestion.description}
              <span class="description">{suggestion.description}</span>
            {/if}
          </div>
          {#if suggestion.preview}
            <span class="preview">{suggestion.preview}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .mention-input-container {
    position: relative;
    width: 100%;
  }
  
  .mention-input {
    width: 100%;
    padding: 12px 16px;
    font-size: 14px;
    font-family: 'JetBrains Mono', monospace;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
  }
  
  .mention-input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 3px var(--accent-color-alpha);
  }
  
  .suggestions-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    max-height: 300px;
    overflow-y: auto;
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    z-index: 100;
  }
  
  .suggestion {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    cursor: pointer;
    text-align: left;
    color: var(--text-primary);
  }
  
  .suggestion:hover,
  .suggestion.selected {
    background: var(--bg-hover);
  }
  
  .icon {
    font-size: 16px;
    width: 24px;
    text-align: center;
  }
  
  .content {
    flex: 1;
    min-width: 0;
  }
  
  .display {
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
  }
  
  .description {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 2px;
  }
  
  .preview {
    font-size: 11px;
    color: var(--text-tertiary);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
```

#### 6.3 Backend (Rust/Tauri) — Reuse Existing Infrastructure

**Key insight**: `writer.rs` already has `get_lens_skills` and `execute_skill`. We extend it rather than creating parallel infrastructure.

```rust
// studio/src-tauri/src/writer.rs (EXTEND existing file)

use std::path::PathBuf;
use glob::glob;
use serde::{Deserialize, Serialize};

// Add to existing file — suggestion types for command palette
#[derive(Debug, Serialize, Deserialize)]
pub struct PaletteSuggestion {
    #[serde(rename = "type")]
    pub suggestion_type: String,  // "skill" | "file" | "lens"
    pub value: String,
    pub display: String,
    pub icon: String,
    pub preview: Option<String>,
    pub description: Option<String>,
    pub last_run: Option<LastRunInfo>,  // S-tier: show when last used
    pub related_files: Option<Vec<RelatedFile>>,  // S-tier: show related
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LastRunInfo {
    pub timestamp: String,
    pub duration_ms: u64,
    pub status: String,
    pub summary: Option<String>,  // e.g., "38 verified, 4 issues"
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RelatedFile {
    pub path: String,
    pub relation: String,  // "test" | "implementation" | "schema"
}

// New command — combines suggestions for command palette
#[tauri::command]
pub async fn get_palette_suggestions(
    query: String,
    current_file: Option<String>,
) -> Result<Vec<PaletteSuggestion>, String> {
    let mut suggestions = Vec::new();
    
    // 1. Shortcuts (from current lens)
    suggestions.extend(get_shortcut_suggestions(&query, current_file.as_deref()).await?);
    
    // 2. Files (with related file detection)
    suggestions.extend(get_file_suggestions(&query, current_file.as_deref()).await?);
    
    // 3. Lenses (for #lens switching)
    suggestions.extend(get_lens_suggestions_internal(&query).await?);
    
    Ok(suggestions)
}

async fn get_shortcut_suggestions(
    query: &str,
    current_file: Option<&str>,
) -> Result<Vec<PaletteSuggestion>, String> {
    // Use existing get_lens_skills to get shortcuts
    let skills = get_lens_skills_internal().await?;
    
    // Load history for last-run info
    let history = load_shortcut_history();
    
    skills
        .iter()
        .filter(|s| s.triggers.iter().any(|t| t.contains(query)))
        .map(|skill| {
            let shortcut = skill.triggers.iter()
                .find(|t| t.starts_with("::"))
                .unwrap_or(&skill.name);
            
            let last_run = history.get(shortcut).cloned();
            
            PaletteSuggestion {
                suggestion_type: "skill".into(),
                value: shortcut.clone(),
                display: shortcut.clone(),
                icon: "⚡".into(),
                preview: Some(skill.name.clone()),
                description: Some(skill.description.clone()),
                last_run,
                related_files: None,
            }
        })
        .collect()
}

async fn get_file_suggestions(query: &str) -> Result<Vec<Suggestion>, String> {
    let mut suggestions = Vec::new();
    
    // Glob pattern based on query
    let pattern = if query.is_empty() {
        "**/*".to_string()
    } else if query.contains('/') {
        format!("{}*", query)
    } else {
        format!("**/*{}*", query)
    };
    
    if let Ok(paths) = glob(&pattern) {
        for entry in paths.flatten().take(15) {
            let is_dir = entry.is_dir();
            let display = entry.display().to_string();
            
            // Get file preview (first line for files)
            let preview = if !is_dir {
                std::fs::read_to_string(&entry)
                    .ok()
                    .and_then(|s| s.lines().next().map(|l| l.chars().take(50).collect()))
            } else {
                // Directory: show file count
                std::fs::read_dir(&entry)
                    .ok()
                    .map(|d| format!("{} items", d.count()))
            };
            
            suggestions.push(Suggestion {
                suggestion_type: if is_dir { "directory" } else { "file" }.into(),
                value: display.clone(),
                display: display.clone(),
                icon: get_file_icon(&entry),
                preview,
                description: None,
            });
        }
    }
    
    Ok(suggestions)
}

fn get_shortcut_suggestions(query: &str) -> Result<Vec<Suggestion>, String> {
    let shortcuts = vec![
        ("a", "audit-documentation", "Quick validation against source"),
        ("a-2", "audit-documentation-deep", "Deep audit with triangulation"),
        ("p", "polish-documentation", "Quick polish pass"),
        ("health", "check-health", "System-wide health check"),
        ("score", "score-confidence", "Calculate confidence scores"),
        ("drift", "detect-drift", "Find stale documentation"),
        ("lint", "lint-structure", "Validate structure vs. Diataxis"),
        ("vdr", "assess-vdr", "VDR/VPR checklist assessment"),
        ("examples", "audit-code-examples", "Verify code examples work"),
        ("readability", "check-readability", "Assess readability scores"),
    ];
    
    let query_lower = query.to_lowercase();
    let suggestions: Vec<Suggestion> = shortcuts
        .into_iter()
        .filter(|(name, skill, desc)| {
            name.contains(&query_lower) || 
            skill.contains(&query_lower) ||
            desc.to_lowercase().contains(&query_lower)
        })
        .map(|(name, skill, desc)| Suggestion {
            suggestion_type: "skill".into(),
            value: name.into(),
            display: format!("::{}", name),
            icon: "⚡".into(),
            preview: Some(skill.into()),
            description: Some(desc.into()),
        })
        .collect();
    
    Ok(suggestions)
}

async fn get_lens_suggestions(query: &str) -> Result<Vec<Suggestion>, String> {
    // Load available lenses from workspace and ~/.sunwell/lenses
    let mut suggestions = Vec::new();
    
    let lens_dirs = vec![
        PathBuf::from("lenses"),
        dirs::home_dir()
            .map(|h| h.join(".sunwell/lenses"))
            .unwrap_or_default(),
    ];
    
    for dir in lens_dirs {
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().map_or(false, |e| e == "lens") {
                    let name = path.file_stem()
                        .and_then(|s| s.to_str())
                        .unwrap_or("")
                        .to_string();
                    
                    if name.contains(query) || query.is_empty() {
                        suggestions.push(Suggestion {
                            suggestion_type: "lens".into(),
                            value: name.clone(),
                            display: format!("#{}", name),
                            icon: "🔮".into(),
                            preview: None,
                            description: Some(format!("Switch to {} lens", name)),
                        });
                    }
                }
            }
        }
    }
    
    Ok(suggestions)
}

fn get_file_icon(path: &PathBuf) -> String {
    if path.is_dir() {
        return "📁".into();
    }
    
    match path.extension().and_then(|e| e.to_str()) {
        Some("md") => "📝",
        Some("py") => "🐍",
        Some("rs") => "🦀",
        Some("ts" | "tsx") => "💠",
        Some("js" | "jsx") => "📜",
        Some("yaml" | "yml") => "⚙️",
        Some("json") => "📋",
        Some("toml") => "⚙️",
        Some("html") => "🌐",
        Some("css" | "scss") => "🎨",
        Some("svg" | "png" | "jpg") => "🖼️",
        _ => "📄",
    }.into()
}
```

#### 6.4 Register Tauri Command

```rust
// studio/src-tauri/src/main.rs (add to existing invoke_handler)
// NO new module needed — just add to writer section

.invoke_handler(tauri::generate_handler![
    // ... existing writer handlers ...
    writer::detect_diataxis,
    writer::validate_document,
    writer::get_lens_skills,
    writer::execute_skill,
    writer::fix_all_issues,
    // NEW — command palette support
    writer::get_palette_suggestions,
    writer::get_shortcut_history,
    writer::record_shortcut_run,
])
```

**Note**: We're extending `writer.rs` not creating `mentions.rs`. This:
- Reuses existing lens/skill infrastructure
- Keeps related functionality together
- Reduces code duplication

#### 6.5 Studio Features Beyond Cursor

| Feature | Cursor | Sunwell Studio |
|---------|--------|----------------|
| `@file` mention | ✅ | ✅ |
| `@directory` mention | ✅ | ✅ |
| `::shortcut` completion | ❌ | ✅ **With descriptions** |
| File preview in dropdown | ❌ | ✅ **First line shown** |
| Drag & drop files | ✅ | ✅ |
| Recent files | ✅ | ✅ **Persist across sessions** |
| Skill suggestions | ❌ | ✅ **"audit" suggests ::a-2** |
| Lens switching | ❌ | ✅ **#lens-name** |
| Fuzzy matching | ✅ | ✅ |
| Keyboard navigation | ✅ | ✅ |

#### 6.6 Studio Command Palette Mockup (S-tier)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Sunwell Studio                                              ─ □ ✕     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                    ╭─────────────────────────────────────────╮          │
│                    │ > ::a-2 @docs/api█                      │          │
│                    ├─────────────────────────────────────────┤          │
│                    │ ⚡ ::a-2  Deep Audit with Triangulation │          │
│                    │    Last run: 2 hours ago on this file   │          │
│                    │    Found 4 issues, 38 verified          │          │
│                    │    [TAB to run] [↵ for options]         │          │
│                    ├─────────────────────────────────────────┤          │
│                    │ 📝 @docs/api.md                         │          │
│                    │    # API Reference Documentation        │          │
│                    │    Modified: Jan 22 • 245 lines         │          │
│                    ├─────────────────────────────────────────┤          │
│                    │ Related files:                          │          │
│                    │   🧪 @tests/test_api.py (test)          │          │
│                    │   🐍 @src/api/handler.py (impl)         │          │
│                    ╰─────────────────────────────────────────╯          │
│                                                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│                                                                         │
│  With execution history (::!!):                                         │
│                                                                         │
│                    ╭─────────────────────────────────────────╮          │
│                    │ > ::!!█                                 │          │
│                    ├─────────────────────────────────────────┤          │
│                    │ ↻ Recent Shortcuts                      │          │
│                    │   ::a-2 @docs/api.md       2h ago  ✅   │          │
│                    │   ::p @docs/overview.md    5h ago  ✅   │          │
│                    │   ::health                 1d ago  ⚠️   │          │
│                    │   ::a-2 @docs/config.md    2d ago  ✅   │          │
│                    ╰─────────────────────────────────────────╯          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key UX improvements over simple dropdown**:
- Shows **last run context** (when, what it found)
- Shows **related files** proactively
- **History with re-run** via `::!!`
- **Keyboard-first** (Tab to run, Enter for options)

**Interaction flow**:

1. User types `::a-2 @do`
2. Command palette appears with matching files + context
3. User presses `↓` to highlight `docs/api.md`
4. User presses `Tab` to accept
5. Input becomes: `::a-2 @docs/api.md `
6. User presses `Enter` to execute
7. Audit runs and results stream **inline with document annotations**

---

### Part 7: Discovery UX (S-tier)

New users shouldn't have to read documentation to discover shortcuts. The system teaches them contextually.

#### 7.1 Ambient Suggestions

```svelte
<!-- components/AmbientSuggestion.svelte (enhance existing) -->
<script lang="ts">
  import { writerState } from '../stores';
  import { hasUsedShortcut, markShortcutUsed } from '../stores/suggestions.svelte';
  
  const currentFile = $derived(writerState.filePath);
  const isMarkdown = $derived(currentFile?.endsWith('.md') || currentFile?.endsWith('.rst'));
  const showAuditHint = $derived(isMarkdown && !hasUsedShortcut('::a-2'));
</script>

{#if showAuditHint}
  <div class="ambient-hint" transition:slide>
    <span class="hint-icon">💡</span>
    <span class="hint-text">
      Try <code>::a-2</code> to audit this document against source code
    </span>
    <button class="hint-try" onclick={() => insertShortcut('::a-2')}>
      Try it
    </button>
    <button class="hint-dismiss" onclick={() => markShortcutUsed('::a-2')}>
      ✕
    </button>
  </div>
{/if}
```

#### 7.2 First-Run Onboarding

When Studio opens for the first time, show a brief tooltip tour:

```
┌─────────────────────────────────────────────┐
│  Welcome to Shortcuts! 🚀                   │
│                                             │
│  Type :: to see available commands:         │
│                                             │
│  ::a-2  Deep audit with triangulation       │
│  ::p    Polish documentation                │
│  ::health  Check doc health                 │
│                                             │
│  Or press Cmd+K for the command palette     │
│                                             │
│  [Got it]                                   │
└─────────────────────────────────────────────┘
```

#### 7.3 Contextual Help

`::?` or `::help` shows shortcuts relevant to the current context:

```markdown
## Available Shortcuts

**For this markdown file:**
- `::a-2` — Deep audit against source code
- `::p` — Polish for clarity and style
- `::readability` — Check readability score

**General:**
- `::health` — System-wide doc health
- `::drift` — Find stale documentation
- `::!!` — Re-run last shortcut

Tip: Press Cmd+Shift+A to audit the focused file
```

---

### Part 8: Inline Result Annotations (S-tier)

Instead of results only appearing in a separate panel, audit findings appear **inline in the document**.

#### 8.1 Annotation Component

```svelte
<!-- components/writer/AuditAnnotation.svelte -->
<script lang="ts">
  import { slide } from 'svelte/transition';
  
  interface Props {
    line: number;
    severity: 'error' | 'warning' | 'info';
    claim: string;
    issue: string;
    expected?: string;
    actual?: string;
    evidence?: string;
    onfix?: () => void;
    ondismiss?: () => void;
  }
  
  let { line, severity, claim, issue, expected, actual, evidence, onfix, ondismiss }: Props = $props();
</script>

<div 
  class="audit-annotation" 
  class:error={severity === 'error'}
  class:warning={severity === 'warning'}
  data-line={line}
  transition:slide
>
  <div class="annotation-header">
    <span class="severity-icon">
      {severity === 'error' ? '❌' : severity === 'warning' ? '⚠️' : 'ℹ️'}
    </span>
    <span class="claim">{claim}</span>
  </div>
  
  <div class="annotation-body">
    <p class="issue">{issue}</p>
    
    {#if expected && actual}
      <div class="diff">
        <div class="expected">
          <span class="label">Doc says:</span>
          <code>{expected}</code>
        </div>
        <div class="actual">
          <span class="label">Actual:</span>
          <code>{actual}</code>
        </div>
      </div>
    {/if}
    
    {#if evidence}
      <div class="evidence">
        <span class="label">Evidence:</span>
        <code>{evidence}</code>
      </div>
    {/if}
  </div>
  
  <div class="annotation-actions">
    {#if onfix}
      <button class="fix-btn" onclick={onfix}>Fix</button>
    {/if}
    <button class="dismiss-btn" onclick={ondismiss}>Dismiss</button>
  </div>
</div>

<style>
  .audit-annotation {
    margin: var(--space-2) 0;
    padding: var(--space-3);
    border-radius: var(--radius-md);
    border-left: 3px solid var(--border-subtle);
    background: var(--bg-secondary);
  }
  
  .audit-annotation.error {
    border-left-color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }
  
  .audit-annotation.warning {
    border-left-color: var(--warning);
    background: rgba(245, 158, 11, 0.1);
  }
  
  .diff {
    display: grid;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .expected code { color: var(--error); }
  .actual code { color: var(--success); }
  
  .fix-btn {
    background: var(--gold);
    color: var(--bg-primary);
  }
</style>
```

#### 8.2 Integration with Writer Surface

```svelte
<!-- components/writer/WriterSurface.svelte (add to existing) -->
{#if auditResults}
  <div class="audit-overlay">
    {#each auditResults.issues as issue}
      <AuditAnnotation
        line={issue.line}
        severity={issue.severity}
        claim={issue.claim}
        issue={issue.description}
        expected={issue.doc_says}
        actual={issue.actual}
        evidence={issue.evidence}
        onfix={() => applyFix(issue)}
        ondismiss={() => dismissIssue(issue)}
      />
    {/each}
  </div>
{/if}
```

---

### Part 9: Keyboard Shortcuts (S-tier)

Power users expect keyboard-first workflows. Every shortcut should have a key binding.

#### 9.1 Keyboard Mapping

| Shortcut | Action | Scope |
|----------|--------|-------|
| `Cmd+K` | Open command palette | Global |
| `Cmd+Shift+A` | Run `::a-2` on focused file | Writer |
| `Cmd+Shift+P` | Run `::p` on focused file | Writer |
| `Cmd+Shift+H` | Run `::health` | Global |
| `Cmd+;` | Focus shortcut input | Global |
| `Cmd+Shift+R` | Re-run last shortcut (`::!!`) | Global |
| `Escape` | Dismiss annotations/palette | Global |

#### 9.2 Implementation (Svelte)

```svelte
<!-- App.svelte (add keyboard handler) -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { executeShortcut, openCommandPalette } from './stores/shortcuts.svelte';
  import { writerState } from './stores';
  
  function handleKeydown(e: KeyboardEvent) {
    const meta = e.metaKey || e.ctrlKey;
    
    // Cmd+K → Command palette
    if (meta && e.key === 'k') {
      e.preventDefault();
      openCommandPalette();
      return;
    }
    
    // Cmd+Shift+A → Audit
    if (meta && e.shiftKey && e.key === 'A') {
      e.preventDefault();
      if (writerState.filePath) {
        executeShortcut('::a-2', writerState.filePath);
      }
      return;
    }
    
    // Cmd+Shift+P → Polish
    if (meta && e.shiftKey && e.key === 'P') {
      e.preventDefault();
      if (writerState.filePath) {
        executeShortcut('::p', writerState.filePath);
      }
      return;
    }
    
    // Cmd+Shift+R → Re-run last
    if (meta && e.shiftKey && e.key === 'R') {
      e.preventDefault();
      executeShortcut('::!!');
      return;
    }
  }
  
  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  });
</script>
```

#### 9.3 Tauri Global Shortcuts (Optional)

For shortcuts that work even when Studio isn't focused:

```rust
// studio/src-tauri/src/shortcuts.rs
use tauri::{GlobalShortcutManager, Manager};

pub fn register_global_shortcuts(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let handle = app.handle();
    
    // Cmd+Shift+A globally
    app.global_shortcut_manager().register("CmdOrCtrl+Shift+A", move || {
        let _ = handle.emit_all("global-shortcut", "audit");
    })?;
    
    Ok(())
}
```

---

### Part 10: Execution History (S-tier)

Track shortcut executions for re-run, learning, and debugging.

#### 10.1 History Store

```typescript
// stores/shortcut-history.svelte.ts
import { writable } from 'svelte/store';

interface ShortcutRun {
  id: string;
  shortcut: string;
  target?: string;
  timestamp: Date;
  status: 'success' | 'warning' | 'error';
  duration_ms: number;
  summary?: string;  // e.g., "38 verified, 4 issues"
}

const MAX_HISTORY = 50;

export const shortcutHistory = writable<ShortcutRun[]>([]);

export function recordShortcutRun(run: Omit<ShortcutRun, 'id'>) {
  shortcutHistory.update(history => {
    const newRun = { ...run, id: crypto.randomUUID() };
    return [newRun, ...history].slice(0, MAX_HISTORY);
  });
  
  // Persist to localStorage
  localStorage.setItem('shortcut-history', JSON.stringify(get(shortcutHistory)));
}

export function getLastRun(): ShortcutRun | undefined {
  return get(shortcutHistory)[0];
}

export function rerunLast() {
  const last = getLastRun();
  if (last) {
    executeShortcut(last.shortcut, last.target);
  }
}
```

#### 10.2 History Panel Component

```svelte
<!-- components/ShortcutHistory.svelte -->
<script lang="ts">
  import { shortcutHistory, rerunLast } from '../stores/shortcut-history.svelte';
  import { formatRelativeTime } from '$lib/format';
  
  function rerun(run: ShortcutRun) {
    executeShortcut(run.shortcut, run.target);
  }
</script>

<div class="shortcut-history">
  <h3>
    Recent Shortcuts
    <kbd class="hint">Cmd+Shift+R to re-run</kbd>
  </h3>
  
  {#each $shortcutHistory as run}
    <button class="history-item" onclick={() => rerun(run)}>
      <span class="shortcut">{run.shortcut}</span>
      {#if run.target}
        <span class="target">@{run.target.split('/').pop()}</span>
      {/if}
      <span class="time">{formatRelativeTime(run.timestamp)}</span>
      <span class="status">
        {run.status === 'success' ? '✅' : run.status === 'warning' ? '⚠️' : '❌'}
      </span>
      {#if run.summary}
        <span class="summary">{run.summary}</span>
      {/if}
    </button>
  {/each}
  
  {#if $shortcutHistory.length === 0}
    <p class="empty">No shortcuts run yet. Try <code>::a-2</code> on a doc!</p>
  {/if}
</div>
```

---

### Part 11: Progress Streaming (S-tier)

Long-running skills like `::a-2` on large codebases need real-time feedback.

#### 11.1 Progress Events

```typescript
// Skill execution emits progress events
interface SkillProgressEvent {
  skill_name: string;
  phase: 'setup' | 'extracting' | 'verifying' | 'triangulating' | 'complete';
  progress_percent: number;
  current_step?: string;  // e.g., "Verifying claim 23/42"
  claims_verified?: number;
  claims_total?: number;
  issues_found?: number;
}
```

#### 11.2 Progress Component

```svelte
<!-- components/SkillProgress.svelte -->
<script lang="ts">
  import { slide } from 'svelte/transition';
  
  interface Props {
    skillName: string;
    phase: string;
    progress: number;
    currentStep?: string;
    oncancel?: () => void;
  }
  
  let { skillName, phase, progress, currentStep, oncancel }: Props = $props();
</script>

<div class="skill-progress" transition:slide>
  <div class="progress-header">
    <span class="skill-name">⚡ {skillName}</span>
    <span class="phase">{phase}</span>
    {#if oncancel}
      <button class="cancel-btn" onclick={oncancel}>Cancel</button>
    {/if}
  </div>
  
  <div class="progress-bar-container">
    <div class="progress-bar" style="width: {progress}%"></div>
  </div>
  
  {#if currentStep}
    <div class="current-step">{currentStep}</div>
  {/if}
</div>

<style>
  .skill-progress {
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .progress-bar-container {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
  }
  
  .progress-bar {
    height: 100%;
    background: var(--gold);
    transition: width 0.3s ease;
  }
  
  .current-step {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin-top: var(--space-2);
  }
</style>
```

---

## Usage Examples

### Example 1: CLI Deep Audit

```bash
$ sunwell do ::a-2 docs/api-reference.md

Running audit-documentation-deep...

## 🔍 Deep Audit: api-reference.md

**Summary**: 42 claims analyzed, 38 verified (90%)
**Confidence**: 87% 🟡

### Triangulation Results

**HIGH Confidence (3/3 sources agree)**:
- "API returns JSON by default" — `api/handler.py:45`, `tests/test_api.py:23`, `openapi.yaml:12`
- "Rate limit is 1000 req/min" — `config/limits.py:8`, `tests/test_limits.py:56`, `docs/config.md:34`

### ⚠️ Issues Found (4)

1. **Line 78**: Function signature changed
   - Doc says: `get_users(limit=50)`
   - Actual: `get_users(limit=100)` — `api/users.py:67`
   
2. **Line 112**: Config option removed
   - Doc mentions `CACHE_TTL` 
   - Not found in current codebase

### 📋 Action Items
- [ ] Update function signature on line 78
- [ ] Remove reference to CACHE_TTL on line 112
- [ ] Review 2 other medium-confidence claims
```

### Example 2: Chat Mode

```
$ sunwell chat --lens docs-assistant

> ::a-2 docs/overview.md

[Running audit-documentation-deep...]

## 🔍 Deep Audit: overview.md
...

> ::health

[Running check-health...]

## 🏥 Documentation Health
...
```

### Example 3: Natural Language Fallback

```bash
$ sunwell "audit docs/api.md thoroughly"

Router detected intent: VALIDATION
Suggested skill: audit-documentation-deep (::a-2)

Executing...
```

---

## Implementation Plan

### Phase 1: CLI Entry Point (2 hours) — P0

| Task | Description | Size |
|------|-------------|------|
| 1.1 | Create `src/sunwell/cli/do_cmd.py` with rich context | M |
| 1.2 | Add to `main.py` | S |
| 1.3 | Test with existing `docs-validation-skills.yaml` | S |

### Phase 2: Default Lens (1 hour) — P0

| Task | Description | Size |
|------|-------------|------|
| 2.1 | Create `lenses/docs-assistant.lens` | S |
| 2.2 | Verify skill includes work | S |
| 2.3 | Test shortcut resolution | S |

### Phase 3: Chat Integration (2 hours) — P1

| Task | Description | Size |
|------|-------------|------|
| 3.1 | Add shortcut handlers to `runtime/commands.py` | M |
| 3.2 | Wire model from chat session | M |
| 3.3 | Integration test in chat mode | S |

### Phase 4: Shell Completions (1 hour) — P1

| Task | Description | Size |
|------|-------------|------|
| 4.1 | Add `complete_shortcut` function (load from lens) | S |
| 4.2 | Add `complete_target` function | S |
| 4.3 | Wire to Click arguments with `shell_complete` | S |
| 4.4 | Test with bash/zsh/fish | S |

### Phase 5: Studio Command Palette (4 hours) — P1

| Task | Description | Size |
|------|-------------|------|
| 5.1 | Create `CommandPalette.svelte` component | L |
| 5.2 | Wire to existing `writer::get_lens_skills` | S |
| 5.3 | Add file suggestion with previews + related files | M |
| 5.4 | Add shortcut suggestions with last-run context | M |
| 5.5 | Keyboard navigation (arrow keys, Tab, Enter) | S |
| 5.6 | `Cmd+K` global binding | S |

### Phase 6: Discovery UX (2 hours) — S-tier

| Task | Description | Size |
|------|-------------|------|
| 6.1 | Enhance `AmbientSuggestion.svelte` with shortcut hints | M |
| 6.2 | First-run onboarding tooltip | M |
| 6.3 | `::?` / `::help` contextual help | S |

### Phase 7: Inline Results (3 hours) — S-tier

| Task | Description | Size |
|------|-------------|------|
| 7.1 | Create `AuditAnnotation.svelte` | M |
| 7.2 | Integrate with `WriterSurface.svelte` | M |
| 7.3 | Add "Fix" action handler | M |
| 7.4 | Dismiss/persist annotation state | S |

### Phase 8: Keyboard Shortcuts (1 hour) — S-tier

| Task | Description | Size |
|------|-------------|------|
| 8.1 | Add keyboard handler to `App.svelte` | M |
| 8.2 | `Cmd+Shift+A/P/R` bindings | S |
| 8.3 | Keyboard shortcut cheatsheet (`Cmd+/`) | S |

### Phase 9: Execution History (2 hours) — S-tier

| Task | Description | Size |
|------|-------------|------|
| 9.1 | Create `shortcut-history.svelte.ts` store | M |
| 9.2 | Create `ShortcutHistory.svelte` panel | M |
| 9.3 | `::!!` re-run implementation | S |
| 9.4 | LocalStorage persistence | S |

### Phase 10: Progress Streaming (2 hours) — S-tier

| Task | Description | Size |
|------|-------------|------|
| 10.1 | Create `SkillProgress.svelte` component | M |
| 10.2 | Wire to skill execution events | M |
| 10.3 | Cancel button functionality | S |

**Total: ~20 hours**

### Priority Order

```
P0 (Critical):  Phase 1, 2                    → Core CLI works        (3 hours)
P1 (Important): Phase 3, 4, 5                 → Chat + Studio basics  (7 hours)  
S-tier:         Phase 6, 7, 8, 9, 10          → Delight features      (10 hours)
```

### Recommended Approach

1. **Ship P0 first** (3 hours) — CLI works, users can start using shortcuts
2. **Ship P1 quickly** (7 hours) — Chat + Studio, competitive with Cursor
3. **Iterate on S-tier** — Discovery, inline results, history make it *better* than Cursor

---

## File Changes

```
Modified (Python):
  src/sunwell/cli/main.py              # Add do_cmd
  src/sunwell/runtime/commands.py      # Add shortcut handlers

Modified (Svelte):
  studio/src/App.svelte                # Keyboard shortcuts
  studio/src/components/AmbientSuggestion.svelte  # Discovery hints
  studio/src/components/writer/WriterSurface.svelte  # Inline results

Modified (Rust):
  studio/src-tauri/src/writer.rs       # Reuse existing, add progress events
  studio/src-tauri/src/main.rs         # Register new commands

New (Python):
  src/sunwell/cli/do_cmd.py            # ~300 lines (includes smart context)
  lenses/docs-assistant.lens           # ~50 lines

New (Svelte):
  studio/src/components/CommandPalette.svelte     # ~400 lines
  studio/src/components/AuditAnnotation.svelte    # ~150 lines
  studio/src/components/ShortcutHistory.svelte    # ~100 lines
  studio/src/components/SkillProgress.svelte      # ~80 lines
  studio/src/stores/shortcut-history.svelte.ts    # ~60 lines
  studio/src/stores/shortcuts.svelte.ts           # ~40 lines

Total: ~1,180 new lines across 10 new files + modifications
```

---

## Success Criteria

### P0: Core Functionality

| Criterion | Test |
|-----------|------|
| CLI works | `sunwell do ::a-2 docs/api.md` produces audit report |
| Chat works | `::a-2` in `sunwell chat --lens docs-assistant` executes skill |
| All shortcuts work | `::a`, `::a-2`, `::p`, `::health`, `::score` resolve correctly |
| Error handling | Unknown shortcuts show available options |
| Verbose mode | `--verbose` shows execution details |
| Rich context | Related files and git diff included in context |

### P1: Shell Completions

| Criterion | Test |
|-----------|------|
| Shortcut completion | `sunwell do ::<TAB>` shows all shortcuts |
| File completion | `sunwell do ::a-2 docs/<TAB>` shows .md files |
| Directory completion | `sunwell do ::a-2 src/<TAB>` shows subdirectories |
| Completion install | `sunwell --install-completion bash` works |

### P1: Studio Command Palette

| Criterion | Test |
|-----------|------|
| `Cmd+K` opens palette | Command palette appears centered |
| `@` triggers file suggestions | Typing `@do` shows files matching "do" |
| `::` triggers shortcut suggestions | Typing `::a` shows audit shortcuts |
| Shows last run context | Shortcut shows "Last run: 2h ago, 4 issues" |
| Related files shown | Selecting file shows test/implementation files |
| Keyboard navigation | Arrow keys, Tab, Enter work correctly |

### S-tier: Discovery

| Criterion | Test |
|-----------|------|
| Ambient hints | Opening .md file shows "try ::a-2" hint |
| First-run onboarding | New user sees shortcut tutorial |
| `::?` help | Shows contextual shortcut list |
| Hints dismiss | After using shortcut, hint doesn't reappear |

### S-tier: Inline Results

| Criterion | Test |
|-----------|------|
| Annotations appear | Audit findings show inline in document |
| Severity styling | Errors red, warnings yellow |
| Fix button works | Clicking "Fix" applies suggested change |
| Dismiss works | Can dismiss individual annotations |

### S-tier: Keyboard Shortcuts

| Criterion | Test |
|-----------|------|
| `Cmd+Shift+A` | Audits focused file |
| `Cmd+Shift+P` | Polishes focused file |
| `Cmd+Shift+R` | Re-runs last shortcut |
| Cheatsheet | `Cmd+/` shows all keyboard shortcuts |

### S-tier: History & Progress

| Criterion | Test |
|-----------|------|
| History recorded | Shortcut runs appear in history panel |
| `::!!` works | Re-runs last shortcut with same target |
| Progress shows | Long-running skill shows progress bar |
| Cancel works | Can cancel mid-execution |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model not configured | Execution fails | Clear error message with setup instructions |
| Skill includes broken | Lens won't load | Validate includes at load time |
| Tool permissions | Skill can't read files | Default to `read-only` preset, document trust levels |
| Scope creep to S-tier | P0 delayed | Ship P0/P1 first, S-tier is additive |
| Keyboard conflicts | Cmd+K collides with other apps | Allow user customization in settings |
| History grows unbounded | Storage bloat | Cap at 50 entries, localStorage only |
| Inline annotations overwhelming | UX noise | Collapse by default, show count badge |
| Long-running skills block UI | Frustration | Progress streaming + cancel button |

---

## Alternatives Considered

### A: Extend `sunwell skill exec`

```bash
sunwell skill exec docs-assistant.lens audit-documentation-deep "Audit docs/api.md"
```

**Rejected**: Too verbose. The whole point is `::a-2 docs/api.md`.

### B: Make shortcuts top-level CLI arguments

```bash
sunwell ::a-2 docs/api.md
```

**Rejected**: Click doesn't handle `::` prefix well. `sunwell do ::a-2` is cleaner.

### C: Only support chat mode

**Rejected**: CLI-first is critical for scripting and CI/CD.

---

## Future Extensions

### Near-term (Post S-tier)

1. **Skill chaining**: `::a-2 | ::p` for audit-then-polish workflow
   - Already have `workflows/docs-chain-executor` pattern
   - Expose via `::chain` or pipe syntax
   - Visual chain builder in Studio

2. **Batch operations**: `sunwell do ::a-2 docs/*.md` or `@docs/` in Studio
   - Parallel execution using `IncrementalSkillExecutor` waves
   - Progress shows per-file status

3. **Custom shortcut mapping**: Per-project `.sunwell/shortcuts.yaml`
   ```yaml
   shortcuts:
     "::lint": "my-custom-linter"
     "::deploy": "deploy-docs"
   ```

### Medium-term

4. **Alias shortcuts at CLI level**: `alias sa2='sunwell do ::a-2'`
5. **Drag & drop files**: Drop files onto Studio input to add as context
6. **Recent files list**: Quick access to recently mentioned files
7. **Inline file preview**: Hover to preview full file content
8. **Shortcut marketplace**: Share custom shortcuts via fount

### Long-term

9. **Voice shortcuts**: "Hey Sunwell, audit this doc"
10. **Watch mode**: `sunwell do ::a-2 --watch docs/` — re-run on file changes
11. **CI integration**: GitHub Action that runs `::a-2` on PR docs

---

## Related RFCs

- **RFC-070**: DORI Lens Migration — Defined shortcuts and skills
- **RFC-011**: Agent Skills — Skill execution foundation
- **RFC-086**: Writer Workspace — Universal writing environment
- **RFC-092**: Skill Permission Defaults — Security presets

---

## Appendix: Complete Shortcut Reference

| Shortcut | Skill | Description |
|----------|-------|-------------|
| `::a` | `audit-documentation` | Quick validation against source |
| `::a-2` | `audit-documentation-deep` | Deep audit with triangulation |
| `::p` | `polish-documentation` | Quick polish pass |
| `::health` | `check-health` | System-wide health check |
| `::score` | `score-confidence` | Calculate confidence scores |
| `::drift` | `detect-drift` | Find stale documentation |
| `::lint` | `lint-structure` | Validate structure vs. Diataxis |
| `::vdr` | `assess-vdr` | VDR/VPR checklist assessment |
| `::examples` | `audit-code-examples` | Verify code examples work |
| `::readability` | `check-readability` | Assess readability scores |
| `::!!` | (special) | Re-run last shortcut |
| `::?` | (special) | Show contextual help |

---

## Summary: What Makes This S-Tier

| Feature | Cursor/DORI | Sunwell After This RFC |
|---------|-------------|------------------------|
| Shortcut execution | ✅ Manual rule loading | ✅ Direct `sunwell do ::a-2` |
| File mentions | ✅ `@file` | ✅ `@file` + related files shown |
| Completion | ❌ None | ✅ Shell + Studio command palette |
| Discovery | ❌ Read docs | ✅ Ambient hints, first-run tour |
| Results | ❌ Console only | ✅ Inline annotations in document |
| History | ❌ None | ✅ Re-run last, view history |
| Keyboard | ❌ None | ✅ Cmd+Shift+A/P/R |
| Progress | ❌ Spinner | ✅ Streaming progress with cancel |
| Context | ❌ File only | ✅ Related files, git diff, Diataxis |

**The gap we're closing**: DORI shortcuts are powerful but require:
1. Knowing they exist
2. Remembering the syntax
3. Reading console output

**After this RFC**: Shortcuts are discoverable, keyboard-accessible, and results appear exactly where you need them—inline in the document you're editing.

**One-liner pitch**: "Cursor's command palette, but for documentation skills, with inline results."