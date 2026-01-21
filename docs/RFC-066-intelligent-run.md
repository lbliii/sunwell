# RFC-066: Intelligent Run Button

**Status:** Evaluated  
**Author:** AI Assistant  
**Created:** 2026-01-20  
**Confidence:** 91%

## Summary

Add an AI-powered "Run" button to Sunwell Studio that analyzes projects and intelligently determines the best way to launch them in development mode. The user always sees and confirms the command before execution.

## Problem

Currently, users have three quick actions for a project:
- **Finder** — Open project directory
- **Terminal** — Open a terminal at the project root
- **Editor** — Open in VS Code/Cursor

The existing `launch_preview` system in `preview.rs` has basic framework detection (Flask, FastAPI, Django, Express), but it's limited:
1. Only detects a handful of frameworks (`preview.rs:48-55`)
2. Doesn't understand modern project structures (monorepos, workspaces)
3. Can't identify prerequisites (missing `npm install`, `pip install`, etc.)
4. No feedback to user about what's happening

Users who create projects with Sunwell often don't know how to run them, especially if they're new to the tech stack.

## Goals

1. **One-click run** — Users can run AI-generated projects with minimal friction
2. **Intelligent detection** — Automatically identify project type, framework, and appropriate run commands
3. **Prerequisite awareness** — Surface missing dependencies before execution fails
4. **User confirmation** — Always show the command and let users edit before execution
5. **Transparency** — Users understand what will be executed and why

## Non-Goals

1. **Replace preview system** — This supplements `preview.rs`, which handles content viewing (prose, fountain, dialogue). Run button is for dev servers; preview is for content display. They coexist.
2. **100% coverage** — 80% of common project types is acceptable
3. **Auto-install without consent** — Always require user confirmation for installs
4. **Production deployment** — Focus is development mode only
5. **Remote execution** — Commands run locally only

## Recommended Approach

**Option B+C Hybrid: AI analysis with user confirmation**

Use AI to analyze project structure and suggest commands, but always show the user what will be executed before running. This combines the intelligence of AI detection with the safety of user control.

Key principles:
- AI suggests, user confirms
- Commands are editable before execution
- Low-confidence results require more user verification
- Cache successful commands for instant re-run

## Design

### UI Flow

```
[Idle State]
┌──────────────────────────────────────────────┐
│ my-project                                    │
│ ~/Sunwell/projects/my-project                │
│                                              │
│ ┌─────┐ ┌─────────┐ ┌──────┐ ┌─────────┐    │
│ │ ▤   │ │ ⊳       │ │ ⊡    │ │ ▶ Run   │    │ ← New button
│ │Finder│ │Terminal │ │Editor│ │         │    │
│ └─────┘ └─────────┘ └──────┘ └─────────┘    │
└──────────────────────────────────────────────┘
```

### Run Analysis Modal

When "Run" is clicked, show analysis results:

```
┌─────────────────────────────────────────────────┐
│ ▶ Run Project                            [×]    │
├─────────────────────────────────────────────────┤
│                                                 │
│ Detected: React + Vite application              │
│ Framework: Vite 5.x with React 18               │
│ Confidence: ●●●○ High                           │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ $ npm run dev                          [✎]  │ │  ← Editable
│ │   Starts development server on port 5173    │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ⚠️ Prerequisites:                               │
│ • Run `npm install` (node_modules not found)    │
│                                                 │
│ ┌─────────────────────────────┐                │
│ │ [Install & Run]  [Run Only] │                │
│ └─────────────────────────────┘                │
└─────────────────────────────────────────────────┘
```

### Low Confidence Warning

When AI confidence is low, show additional warning:

```
┌─────────────────────────────────────────────────┐
│ ▶ Run Project                            [×]    │
├─────────────────────────────────────────────────┤
│                                                 │
│ ⚠️ Low confidence detection                     │
│                                                 │
│ Detected: Python application (uncertain)        │
│ Confidence: ●○○○ Low                            │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ $ python main.py                       [✎]  │ │
│ │   Best guess - please verify                │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Run] [Open Terminal Instead]                   │
└─────────────────────────────────────────────────┘
```

### Fallback/Timeout State

When AI analysis times out or fails, show heuristic result:

```
┌─────────────────────────────────────────────────┐
│ ▶ Run Project                            [×]    │
├─────────────────────────────────────────────────┤
│                                                 │
│ ℹ️ Using quick detection (AI unavailable)       │
│                                                 │
│ Detected: Node.js project                       │
│ Source: package.json scripts                    │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ $ npm run dev                          [✎]  │ │
│ │   From package.json "scripts.dev"           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Run] [Retry AI Analysis]                       │
└─────────────────────────────────────────────────┘
```

### Data Model

```typescript
// New types in lib/types.ts

export interface RunAnalysis {
  // What we detected
  projectType: string;          // "React + Vite application"
  framework: string | null;     // "Vite 5.x"
  language: string;             // "TypeScript"
  
  // Primary run command
  command: string;              // "npm run dev"
  commandDescription: string;   // "Starts development server"
  workingDir?: string;          // For monorepos
  
  // Alternative commands
  alternatives?: RunCommand[];
  
  // Prerequisites
  prerequisites: Prerequisite[];
  
  // Ports/URLs
  expectedPort?: number;        // 5173
  expectedUrl?: string;         // "http://localhost:5173"
  
  // Confidence
  confidence: 'high' | 'medium' | 'low';
  
  // Detection metadata
  source: 'ai' | 'heuristic' | 'cache' | 'user';  // How was this determined?
  fromCache?: boolean;                             // Loaded from cache?
  userSaved?: boolean;                             // User saved this command?
}

export interface RunCommand {
  command: string;
  description: string;
  when?: string;  // "for production build"
}

export interface Prerequisite {
  description: string;
  command: string;
  satisfied: boolean;
  required: boolean;  // vs recommended
}

export interface RunSession {
  id: string;
  projectPath: string;
  command: string;
  pid: number;
  port?: number;
  startedAt: number;
}
```

### Backend Commands

Add to `src-tauri/src/commands.rs`:

```rust
/// Analyze project to determine how to run it.
/// Returns cached result if available and project unchanged.
/// 
/// Timeout: 10 seconds. Falls back to heuristic detection if AI unavailable.
#[tauri::command]
pub async fn analyze_project_for_run(
    path: String,
    force_refresh: bool,  // Skip cache
) -> Result<RunAnalysis, String> {
    // 1. Check cache (if not force_refresh)
    // 2. Gather project metadata (files, package.json, etc.)
    // 3. Try AI analysis with 10s timeout
    //    - On timeout/error: fall back to heuristic detection
    // 4. Cache result with project hash
    // 5. Return structured analysis (with source: 'ai' | 'heuristic' | 'cache')
}

/// Execute the run command for a project.
/// Re-validates edited commands against the allowlist before execution.
#[tauri::command]
pub async fn run_project(
    path: String,
    command: String,
    install_first: bool,
    save_command: bool,  // Save as user's preferred command
) -> Result<RunSession, String> {
    // 1. Re-validate command against allowlist (even if user edited it)
    // 2. Optionally run install command
    // 3. Execute the run command via Command::new() (no shell)
    // 4. If save_command, write to {project}/.sunwell/run.json
    // 5. Return session info (pid, port, started_at)
}

/// Stop a running project.
#[tauri::command]
pub async fn stop_project_run(
    session_id: String,
) -> Result<(), String> {
    // Kill the process
}

/// Save user's preferred command for a project.
#[tauri::command]
pub async fn save_run_command(
    path: String,
    command: String,
) -> Result<(), String> {
    // Save to project config
}
```

### Python Agent Integration

Add to `src/sunwell/tools/run_analyzer.py`:

```python
@dataclass(frozen=True, slots=True)
class RunAnalysis:
    project_type: str
    framework: str | None
    language: str
    command: str
    command_description: str
    working_dir: str | None
    alternatives: tuple[RunCommand, ...]
    prerequisites: tuple[Prerequisite, ...]
    expected_port: int | None
    expected_url: str | None
    confidence: Literal['high', 'medium', 'low']

async def analyze_project_for_run(path: Path, model: ModelProtocol) -> RunAnalysis:
    """Use AI to analyze how to run a project."""
    
    # Gather context
    context = gather_project_context(path)
    
    # Ask the model
    prompt = build_run_analysis_prompt(context)
    response = await model.complete(prompt)
    
    # Parse and validate
    analysis = parse_run_analysis(response)
    
    # Validate command safety
    validate_command_safety(analysis.command)
    
    return analysis

def gather_project_context(path: Path) -> dict:
    """Collect relevant files for analysis."""
    context = {
        'files': list_top_level_files(path),
        'has_node_modules': (path / 'node_modules').exists(),
        'has_venv': (path / 'venv').exists() or (path / '.venv').exists(),
    }
    
    # Include key files if they exist
    key_files = [
        'package.json', 'Cargo.toml', 'pyproject.toml', 
        'requirements.txt', 'Makefile', 'docker-compose.yml',
        'README.md', 'main.py', 'app.py', 'index.js', 'index.ts'
    ]
    
    for f in key_files:
        file_path = path / f
        if file_path.exists():
            context[f] = file_path.read_text()[:5000]  # Limit size
    
    return context

# Command safety allowlist
SAFE_COMMAND_PREFIXES = frozenset({
    'npm', 'npx', 'yarn', 'pnpm', 'bun',
    'python', 'python3', 'pip', 'uv',
    'cargo', 'rustc',
    'go', 'make',
    'docker', 'docker-compose',
})

def validate_command_safety(command: str) -> None:
    """Validate command against allowlist. Raises if unsafe."""
    parts = command.split()
    if not parts:
        raise ValueError("Empty command")
    
    binary = parts[0]
    if binary not in SAFE_COMMAND_PREFIXES:
        raise ValueError(f"Command '{binary}' not in allowlist")
    
    # Block dangerous patterns
    dangerous = ['rm ', 'sudo', '&&', '||', ';', '|', '>', '<', '`', '$(',]
    for pattern in dangerous:
        if pattern in command:
            raise ValueError(f"Command contains dangerous pattern: {pattern}")
```

### Analysis Prompt

```
You are analyzing a software project to determine how to run it in development mode.

PROJECT CONTEXT:
{context}

Analyze this project and determine:

1. PROJECT TYPE: What kind of application is this? (e.g., "React web app", "Python CLI", "Rust web service")

2. FRAMEWORK: What framework/tooling does it use? (e.g., "Vite + React", "FastAPI", "actix-web")

3. RUN COMMAND: What's the primary command to start it in development mode?
   - For Node.js: Check package.json scripts (dev, start, serve)
   - For Python: Check for main.py, app.py, or framework entry points
   - For Rust: Check Cargo.toml for binary targets

4. PREREQUISITES: What needs to be set up first?
   - Dependencies installed? (node_modules, venv, target)
   - Environment variables? (.env file)
   - Database/services running?

5. EXPECTED URL: If it's a web app, what URL will it be available at?

6. CONFIDENCE: How confident are you?
   - high: Clear signals (package.json scripts, standard framework)
   - medium: Some ambiguity but reasonable guess
   - low: Uncertain, user should verify

IMPORTANT: Only suggest commands from this allowlist:
- npm, npx, yarn, pnpm, bun (Node.js)
- python, python3, pip, uv (Python)
- cargo, rustc (Rust)
- go (Go)
- make (Makefiles)
- docker, docker-compose (Containers)

Output JSON:
{
  "project_type": "...",
  "framework": "..." or null,
  "language": "...",
  "command": "...",
  "command_description": "...",
  "working_dir": "..." or null,
  "alternatives": [{"command": "...", "description": "...", "when": "..."}],
  "prerequisites": [{"description": "...", "command": "...", "satisfied": true/false, "required": true/false}],
  "expected_port": ... or null,
  "expected_url": "..." or null,
  "confidence": "high" | "medium" | "low"
}
```

## UI Components

### New Component: `RunButton.svelte`

```svelte
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { RunAnalysis } from '$lib/types';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import Spinner from './ui/Spinner.svelte';
  
  interface Props {
    projectPath: string;
  }
  
  let { projectPath }: Props = $props();
  
  let isAnalyzing = $state(false);
  let analysis = $state<RunAnalysis | null>(null);
  let showModal = $state(false);
  let isRunning = $state(false);
  let error = $state<string | null>(null);
  let editedCommand = $state<string | null>(null);
  
  async function handleClick() {
    isAnalyzing = true;
    error = null;
    showModal = true;
    
    try {
      analysis = await invoke<RunAnalysis>('analyze_project_for_run', { 
        path: projectPath,
        forceRefresh: false,
      });
      editedCommand = analysis.command;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      isAnalyzing = false;
    }
  }
  
  async function handleRun(installFirst: boolean, remember: boolean) {
    if (!analysis || !editedCommand) return;
    isRunning = true;
    
    try {
      // Re-validate edited command before execution
      await invoke('run_project', {
        path: projectPath,
        command: editedCommand,
        installFirst,
        saveCommand: remember,
      });
      showModal = false;
      // TODO: Show running indicator, open preview
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      isRunning = false;
    }
  }
</script>

<button class="action-btn run-btn" onclick={handleClick} aria-label="Run project">
  <span class="action-icon" aria-hidden="true">▶</span>
  <span>Run</span>
</button>

{#if showModal}
  <Modal title="Run Project" onclose={() => showModal = false}>
    {#if isAnalyzing}
      <div class="analyzing">
        <Spinner size="sm" />
        <p>Analyzing project...</p>
      </div>
    {:else if error}
      <div class="error">
        <p>{error}</p>
        <Button onclick={handleClick}>Retry</Button>
      </div>
    {:else if analysis}
      <RunAnalysisView 
        {analysis} 
        {isRunning} 
        bind:editedCommand
        onrun={handleRun} 
      />
    {/if}
  </Modal>
{/if}
```

### New Component: `RunAnalysisView.svelte`

```svelte
<script lang="ts">
  import type { RunAnalysis } from '$lib/types';
  import Button from './Button.svelte';
  
  interface Props {
    analysis: RunAnalysis;
    isRunning: boolean;
    editedCommand: string;
    onrun: (installFirst: boolean, remember: boolean) => void;
  }
  
  let { analysis, isRunning, editedCommand = $bindable(), onrun }: Props = $props();
  
  let rememberCommand = $state(false);
  
  const hasUnmetPrereqs = $derived(
    analysis.prerequisites.some(p => p.required && !p.satisfied)
  );
  
  const confidenceDisplay = $derived({
    high: { dots: '●●●○', label: 'High', class: 'high' },
    medium: { dots: '●●○○', label: 'Medium', class: 'medium' },
    low: { dots: '●○○○', label: 'Low', class: 'low' },
  }[analysis.confidence]);
</script>

<div class="analysis">
  {#if analysis.confidence === 'low'}
    <div class="warning-banner">
      ⚠️ Low confidence detection — please verify the command
    </div>
  {/if}
  
  <div class="detected">
    <span class="label">Detected:</span>
    <span class="value">{analysis.projectType}</span>
  </div>
  
  {#if analysis.framework}
    <div class="framework">
      <span class="label">Framework:</span>
      <span class="value">{analysis.framework}</span>
    </div>
  {/if}
  
  <div class="confidence {confidenceDisplay.class}">
    <span class="dots">{confidenceDisplay.dots}</span>
    <span class="label">{confidenceDisplay.label} confidence</span>
  </div>
  
  {#if analysis.userSaved}
    <div class="cache-notice saved">Using your saved command</div>
  {:else if analysis.source === 'heuristic'}
    <div class="cache-notice heuristic">Detected from project files</div>
  {:else if analysis.fromCache}
    <div class="cache-notice">Using cached analysis</div>
  {/if}
  
  <div class="command-box">
    <label for="run-command">Command:</label>
    <input 
      id="run-command"
      type="text" 
      bind:value={editedCommand}
      class="command-input"
    />
    <p class="description">{analysis.commandDescription}</p>
  </div>
  
  {#if analysis.prerequisites.length > 0}
    <div class="prerequisites">
      <h4>Prerequisites</h4>
      <ul>
        {#each analysis.prerequisites as prereq}
          <li class:satisfied={prereq.satisfied} class:required={prereq.required}>
            {prereq.satisfied ? '✓' : '⚠️'} {prereq.description}
            {#if !prereq.satisfied}
              <code>{prereq.command}</code>
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
  
  <div class="remember-option">
    <label>
      <input type="checkbox" bind:checked={rememberCommand} />
      Remember this command for this project
    </label>
  </div>
  
  <div class="actions">
    {#if hasUnmetPrereqs}
      <Button variant="primary" onclick={() => onrun(true, rememberCommand)} loading={isRunning}>
        Install & Run
      </Button>
      <Button variant="secondary" onclick={() => onrun(false, rememberCommand)} loading={isRunning}>
        Run Only
      </Button>
    {:else}
      <Button variant="primary" onclick={() => onrun(false, rememberCommand)} loading={isRunning}>
        Run
      </Button>
    {/if}
  </div>
  
  {#if analysis.expectedUrl}
    <p class="expected-url">
      Will be available at: <a href={analysis.expectedUrl}>{analysis.expectedUrl}</a>
    </p>
  {/if}
</div>
```

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **AI suggests malicious command** | HIGH | LOW | Command allowlist + user confirmation required |
| **Command injection via edited input** | HIGH | LOW | Validate edited commands against same allowlist |
| **Analysis takes too long** | MEDIUM | MEDIUM | 10s timeout, show progress, cache results |
| **Incorrect command detected** | MEDIUM | MEDIUM | Show confidence level, allow editing, learn from corrections |
| **API costs accumulate** | LOW | HIGH | Cache per project (hash-based), rate limit to 10/min |
| **Process doesn't terminate** | MEDIUM | LOW | Track PIDs, force kill on stop, cleanup on app exit |
| **Port already in use** | LOW | MEDIUM | Detect port conflicts, suggest alternatives |

### Security Model

1. **Command Allowlist**: Only commands starting with known-safe binaries are allowed
2. **Pattern Blocklist**: Dangerous shell patterns (`;`, `&&`, `|`, `>`, etc.) are rejected
3. **User Confirmation**: Command is always shown before execution
4. **Edit Validation**: User edits are re-validated against the allowlist before execution
5. **No Shell Expansion**: Commands run directly via `Command::new()`, not through shell interpreter

### Error Handling & Fallbacks

| Scenario | Behavior |
|----------|----------|
| **Python agent unreachable** | Fall back to heuristic detection (package.json scripts, Makefile targets) |
| **AI timeout (>10s)** | Cancel AI request, use heuristic, show "Analysis took too long" notice |
| **No detection possible** | Show empty command input with "Unable to detect" message; user enters manually |
| **Invalid JSON from AI** | Retry once, then fall back to heuristic |
| **Command fails on run** | Show stderr in modal, offer "Edit & Retry" button |
| **Port conflict** | Detect during `run_project`, suggest alternative port in error message |
| **Docker not running** | For Docker commands, check daemon first; show "Docker is not running" with install link |

**Heuristic Detection Fallback** (no AI required):
```rust
fn heuristic_detect(path: &Path) -> Option<RunAnalysis> {
    // Check package.json scripts: dev > start > serve
    if let Ok(pkg) = read_package_json(path) {
        if pkg.scripts.contains_key("dev") {
            return Some(RunAnalysis { command: "npm run dev", source: "heuristic", ... });
        }
    }
    // Check Makefile targets: run, dev, start
    // Check pyproject.toml scripts
    // Check Cargo.toml for binary
    None
}
```

## Implementation Plan

### Phase 1: Basic Run Analysis (MVP)
1. Add `RunAnalysis` types to `lib/types.ts`
2. Create `run_analyzer.py` in Python agent with safety validation
3. Add `analyze_project_for_run` Tauri command (calls Python, 10s timeout)
4. Implement heuristic fallback detection in Rust
5. Create `RunButton.svelte` and `RunAnalysisView.svelte`
6. Add Run button to `IdleState.svelte`
7. Add keyboard shortcut (⌘R / Ctrl+R)

**Tests (Phase 1)**:
- `test_run_analyzer.py`: Unit tests for `validate_command_safety()`, `gather_project_context()`
- `tests/commands/test_analyze_project.rs`: Integration test for Tauri command
- Manual: Test with React, Python, Rust sample projects

### Phase 2: Execution & Safety
1. Add `run_project` Tauri command with edit re-validation
2. Add `stop_project_run` command
3. Track running processes in `AppState` (pid, port, started_at)
4. Show running indicator in UI (pulse animation on Run button)
5. Auto-open preview when server starts (detect port ready)
6. Add "Remember this command" checkbox → saves to project config

**Tests (Phase 2)**:
- `tests/commands/test_run_project.rs`: Test process spawning, stopping
- `tests/commands/test_command_validation.rs`: Test allowlist enforcement on edited commands
- Integration: Run → Stop cycle for sample project

### Phase 3: Caching & Polish
1. Implement project-hash-based caching (store in `~/.sunwell/cache/run/`)
2. Add cache invalidation on file changes
3. Show "Using saved command" badge when `userSaved: true`
4. Docker daemon detection before Docker commands
5. Add "Refresh" button to force re-analysis

**Tests (Phase 3)**:
- `tests/cache/test_run_cache.rs`: Test hash computation, invalidation
- Integration: Modify project → verify cache invalidation

## Decisions

### Caching Strategy

**Decision**: Cache analysis results per project, invalidated by content hash.

- Cache key: `sha256(sorted file list + key file contents)`
- Cache location: `~/.sunwell/cache/run/{project-id}.json` (consistent with other caches)
- TTL: None (hash-based invalidation)
- User override: "Refresh" button forces re-analysis
- User saved commands: Stored in `.sunwell/run.json` in project directory

### Long-Running Process Handling

**Decision**: Background process with output panel (Option C).

- Processes run in background, managed by Tauri
- Output streams to a collapsible panel in Studio
- "Stop" button kills the process
- Multiple projects can run simultaneously
- Process list shown in status bar

### Docker Support

**Decision**: Detect but don't auto-run Docker.

- If `docker-compose.yml` detected, suggest `docker-compose up -d`
- Require Docker daemon check before execution:
  ```rust
  fn is_docker_running() -> bool {
      Command::new("docker").args(["info"]).output().map(|o| o.status.success()).unwrap_or(false)
  }
  ```
- Show warning if Docker not running: "Docker daemon is not running. Start Docker Desktop to continue."
- Phase 3+ feature (not MVP)

## Alternatives Considered

### A. Enhance existing `launch_preview`
- **Pros**: Less new code
- **Cons**: Preview system is designed for viewing output, not running dev servers; different UX pattern
- **Verdict**: Rejected — wrong abstraction layer

### B. Pure heuristic-based (no AI)
- **Pros**: Faster, no API call, deterministic
- **Cons**: Can't handle diverse project structures, monorepos, custom setups
- **Verdict**: Partial adoption — use heuristics for common cases, AI for complex

### C. Always ask user
- **Pros**: Simple, user is in control, no AI cost
- **Cons**: Bad UX for users who don't know how to run their project
- **Verdict**: Rejected as primary approach — but adopted as fallback for low confidence

## Testing Strategy

### Unit Tests (Python)
| File | Tests |
|------|-------|
| `tests/tools/test_run_analyzer.py` | `validate_command_safety()` allowlist/blocklist |
| | `gather_project_context()` file reading |
| | `parse_run_analysis()` JSON parsing |

### Unit Tests (Rust)
| File | Tests |
|------|-------|
| `tests/commands/test_run_commands.rs` | `analyze_project_for_run` timeout handling |
| | `run_project` allowlist re-validation |
| | `heuristic_detect()` fallback logic |

### Integration Tests
| Scenario | Coverage |
|----------|----------|
| React + Vite project | AI detection → npm run dev |
| Python Flask project | AI detection → python -m flask run |
| Unknown project | Fallback to heuristic → user input |
| AI timeout | 10s timeout → heuristic fallback |
| User edit validation | Edit to unsafe command → rejection |
| Remember command | Save → reload → use saved |

### Sample Projects for Testing
Located in `tests/fixtures/run_analyzer/`:
- `react-vite/` — Standard Vite React app
- `python-flask/` — Flask with requirements.txt
- `rust-actix/` — Actix-web with Cargo.toml
- `monorepo/` — pnpm workspace with multiple apps
- `unknown/` — No recognizable patterns

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Run success rate | 80%+ | Projects run without command edits |
| Analysis latency | <3s (p95) | Time from click to modal populated |
| Command accuracy | 90%+ | AI-suggested commands work first try |
| Cache hit rate | 70%+ | Subsequent runs use cached analysis |
| User satisfaction | 4+/5 | Post-run feedback (optional) |

## Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `⌘R` / `Ctrl+R` | Open Run modal | When project is open |
| `Enter` | Run with current settings | When Run modal is open |
| `Escape` | Close modal | When Run modal is open |

Shortcuts are registered in Phase 1 to provide power-user access from day one.

## Architecture Integration

### Layer Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SVELTE (Frontend)                               │
│  ┌──────────────┐    invoke()     ┌───────────────┐                         │
│  │ RunButton    │ ──────────────► │ Tauri IPC     │                         │
│  │ .svelte      │ ◄────────────── │ (JSON)        │                         │
│  └──────────────┘    Result<T>    └───────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │ ▲
                                         │ │ serde_json
                                         ▼ │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RUST (Tauri Backend)                            │
│  ┌──────────────┐                 ┌───────────────┐    ┌─────────────────┐  │
│  │ commands.rs  │ ───────────────►│ agent_bridge  │───►│ heuristic_      │  │
│  │              │ ◄───────────────│ .rs           │    │ detect.rs       │  │
│  └──────────────┘  RunAnalysis    └───────────────┘    └─────────────────┘  │
│                                         │ ▲                                  │
│                                         │ │ subprocess + JSON stdout         │
│                                         ▼ │                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │ ▲
                                         │ │ JSON (stdout)
                                         ▼ │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PYTHON (Agent)                                  │
│  ┌──────────────┐                 ┌───────────────┐    ┌─────────────────┐  │
│  │ run_analyzer │ ───────────────►│ Model         │───►│ JSON response   │  │
│  │ .py          │ ◄───────────────│ Protocol      │    │ to stdout       │  │
│  └──────────────┘                 └───────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rust ↔ Python Bridge

Rust calls Python via subprocess (same pattern as existing agent invocations):

```rust
// src-tauri/src/agent_bridge.rs

use std::process::Command;
use tokio::time::{timeout, Duration};

/// Call Python agent for run analysis.
/// Returns None on timeout or error (fallback to heuristic).
pub async fn call_run_analyzer(path: &str) -> Option<RunAnalysis> {
    let result = timeout(Duration::from_secs(10), async {
        let output = Command::new("python")
            .args(["-m", "sunwell.tools.run_analyzer", "--path", path])
            .output()
            .ok()?;
        
        if !output.status.success() {
            return None;
        }
        
        serde_json::from_slice(&output.stdout).ok()
    }).await;
    
    result.ok().flatten()
}
```

Python entry point for subprocess invocation:

```python
# src/sunwell/tools/run_analyzer.py

if __name__ == "__main__":
    import sys
    import json
    import asyncio
    
    path = sys.argv[sys.argv.index("--path") + 1]
    
    async def main():
        from sunwell.models.ollama import OllamaModel
        model = OllamaModel()  # Or get from config
        result = await analyze_project_for_run(Path(path), model)
        print(json.dumps(result.to_dict()))
    
    asyncio.run(main())
```

### Type Schema Synchronization

**Single source of truth**: JSON Schema in `schemas/run-analysis.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RunAnalysis",
  "type": "object",
  "required": ["projectType", "language", "command", "commandDescription", "prerequisites", "confidence", "source"],
  "properties": {
    "projectType": { "type": "string" },
    "framework": { "type": ["string", "null"] },
    "language": { "type": "string" },
    "command": { "type": "string" },
    "commandDescription": { "type": "string" },
    "workingDir": { "type": ["string", "null"] },
    "alternatives": {
      "type": "array",
      "items": { "$ref": "#/definitions/RunCommand" }
    },
    "prerequisites": {
      "type": "array",
      "items": { "$ref": "#/definitions/Prerequisite" }
    },
    "expectedPort": { "type": ["integer", "null"] },
    "expectedUrl": { "type": ["string", "null"] },
    "confidence": { "enum": ["high", "medium", "low"] },
    "source": { "enum": ["ai", "heuristic", "cache", "user"] },
    "fromCache": { "type": "boolean" },
    "userSaved": { "type": "boolean" }
  }
}
```

**Code generation** (add to `Makefile`):

```makefile
generate-run-types:
	# TypeScript (studio/src/lib/types/)
	npx json-schema-to-typescript schemas/run-analysis.schema.json > studio/src/lib/run-analysis.d.ts
	
	# Python (already uses dataclass, validate against schema in tests)
	
	# Rust (use serde with matching field names)
```

### Rust Type Definition

```rust
// src-tauri/src/run_analysis.rs

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunAnalysis {
    pub project_type: String,
    pub framework: Option<String>,
    pub language: String,
    pub command: String,
    pub command_description: String,
    pub working_dir: Option<String>,
    #[serde(default)]
    pub alternatives: Vec<RunCommand>,
    pub prerequisites: Vec<Prerequisite>,
    pub expected_port: Option<u16>,
    pub expected_url: Option<String>,
    pub confidence: Confidence,
    pub source: Source,
    #[serde(default)]
    pub from_cache: bool,
    #[serde(default)]
    pub user_saved: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Confidence {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Source {
    Ai,
    Heuristic,
    Cache,
    User,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunCommand {
    pub command: String,
    pub description: String,
    pub when: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Prerequisite {
    pub description: String,
    pub command: String,
    pub satisfied: bool,
    pub required: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunSession {
    pub id: String,
    pub project_path: String,
    pub command: String,
    pub pid: u32,
    pub port: Option<u16>,
    pub started_at: u64,
}
```

### State Propagation: Running Sessions → UI

Use Tauri events to push session state changes to frontend:

```rust
// Rust: Emit events when session state changes
app_handle.emit_all("run-session-started", &session)?;
app_handle.emit_all("run-session-stopped", &session_id)?;
app_handle.emit_all("run-session-output", RunOutput { session_id, line })?;
```

```svelte
<!-- Svelte: Listen for session events -->
<script lang="ts">
  import { listen } from '@tauri-apps/api/event';
  import { onMount } from 'svelte';
  
  let sessions = $state<RunSession[]>([]);
  
  onMount(() => {
    const unlisten1 = listen<RunSession>('run-session-started', (e) => {
      sessions = [...sessions, e.payload];
    });
    
    const unlisten2 = listen<string>('run-session-stopped', (e) => {
      sessions = sessions.filter(s => s.id !== e.payload);
    });
    
    return () => { unlisten1.then(f => f()); unlisten2.then(f => f()); };
  });
</script>
```

### Cross-Layer Touchpoint Summary

| Touchpoint | Svelte | Rust | Python |
|------------|--------|------|--------|
| **Types** | `lib/types.ts` | `run_analysis.rs` | `run_analyzer.py` |
| **Schema** | Generated | Serde + JSON Schema | Dataclass + validation |
| **API** | `invoke()` calls | `#[tauri::command]` | `__main__` subprocess |
| **Events** | `listen()` | `emit_all()` | N/A |
| **Errors** | Catch + display | `Result<T, String>` | `raise ValueError` |
| **Caching** | N/A | `~/.sunwell/cache/run/` | N/A |
| **User prefs** | N/A | `.sunwell/run.json` | N/A |

### Files to Create/Modify

| Layer | File | Action |
|-------|------|--------|
| **Schema** | `schemas/run-analysis.schema.json` | CREATE |
| **Svelte** | `studio/src/lib/types.ts` | MODIFY (add RunAnalysis) |
| **Svelte** | `studio/src/components/RunButton.svelte` | CREATE |
| **Svelte** | `studio/src/components/RunAnalysisView.svelte` | CREATE |
| **Svelte** | `studio/src/components/project/IdleState.svelte` | MODIFY (add button) |
| **Rust** | `studio/src-tauri/src/run_analysis.rs` | CREATE |
| **Rust** | `studio/src-tauri/src/agent_bridge.rs` | CREATE or MODIFY |
| **Rust** | `studio/src-tauri/src/commands.rs` | MODIFY (add commands) |
| **Rust** | `studio/src-tauri/src/heuristic_detect.rs` | CREATE |
| **Python** | `src/sunwell/tools/run_analyzer.py` | CREATE |
| **Makefile** | `Makefile` | MODIFY (add generate-run-types) |

## Related

- `preview.rs` — Existing preview/launch system (complements, not replaces)
- `IdleState.svelte` — Where the Run button will live
- `agent_bridge.rs` — Existing Rust↔Python communication (if exists)
- RFC-043 Sunwell Studio — Original Studio design
