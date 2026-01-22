# RFC-079: Project Intent Analyzer — Universal Project Understanding

**Status**: Draft  
**Created**: 2026-01-21  
**Last Updated**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 85% 🟢  
**Supersedes**: RFC-066 (Intelligent Run Button) — extends scope beyond dev servers  
**Depends on**:
- RFC-046 (Autonomous Backlog) — Goal tracking
- RFC-056 (Live DAG Integration) — Pipeline visualization
- RFC-072 (Surface Primitives) — Workspace rendering (**owns WorkspaceSpec**)
- RFC-075 (Generative Interface) — Intent routing (**this RFC hands off to 075**)

---

## Summary

Replace the narrow "Run Project = start dev server" model with a **universal project analyzer** that understands what any project IS and what should happen next. Instead of asking "how do I run this code?", ask "what is this project trying to accomplish and what's the next step?"

**The insight**: Not every project is code. Not every code project has a dev server. Not every interaction with a project means "start the server." The question should be: *"What kind of work is this, and how can I help you make progress?"*

**Core shift**:
| RFC-066 (Current) | RFC-079 (Proposed) |
|-------------------|-------------------|
| Detect dev server command | Understand project intent |
| Code projects only | Any project type |
| Output: shell command | Output: pipeline + next action + workspace |
| "npm start" | "Here's your goal pipeline. What would you like to work on?" |

---

## Goals

1. **Universal project understanding** — Analyze any project type (code, docs, data, planning, creative)
2. **Pipeline surfacing** — Show the project's goal pipeline, not just a run command
3. **Context-aware suggestions** — Suggest next actions based on project state
4. **Workspace composition** — Auto-generate appropriate UI for the project type
5. **Backwards compatibility** — Dev server detection still works for code projects that need it

## Non-Goals

1. **Replace backlog system** — Uses RFC-046 backlog, doesn't duplicate it
2. **Autonomous execution** — Suggests actions, doesn't auto-execute
3. **External project imports** — Focus on Sunwell-managed projects first
4. **Multi-project orchestration** — Single project analysis scope

---

## Motivation

### The Narrow View of RFC-066

RFC-066 solved a real problem: "I generated a project with Sunwell, how do I run it?"

But it assumed:
1. Every project is code
2. Every code project has a dev server
3. "Running" means "start the server"
4. JavaScript/Node.js is the default

These assumptions break for:
- **Documentation projects** — "Run" means build/preview, not npm start
- **Data analysis** — "Run" means execute notebook, not start server
- **Planning/research** — "Run" means work on next goal, no server involved
- **Python projects** — No `package.json`, different tooling
- **Rust projects** — `cargo run`, not npm
- **Creative projects** — No "run" concept at all

### The Real Question

When a user opens a project, they're not asking "start my dev server." They're asking:

> "I want to make progress on this. What should I do next?"

The answer might be:
- Start the dev server (for active code development)
- Continue drafting chapter 3 (for a writing project)
- Review the analysis results (for a data project)
- Pick a goal from the backlog (for a planning project)
- Nothing — show me what's here (for exploration)

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Project type detection** | Multi-signal heuristics + LLM | Files alone aren't enough; need semantic understanding |
| **Pipeline source** | Backlog + inferred | Use existing goals; infer if empty |
| **Workspace generation** | Delegate to RFC-072/075 | Leverage existing generative surface |
| **Dev server detection** | Optional component | Code projects may need it; others don't |
| **State persistence** | `.sunwell/project.json` | Cache analysis results for fast re-open |

---

## Integration with RFC-075 (Generative Interface)

RFC-079 and RFC-075 form a **two-layer intent system**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TWO-LAYER INTENT SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 1: Project Analysis (RFC-079)                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Trigger: User opens project                                            │ │
│  │ Input: Filesystem (files, dirs, README, backlog, git)                 │ │
│  │ Output: ProjectAnalysis {                                              │ │
│  │   project_type: "code",                                                │ │
│  │   suggested_action: SuggestedAction { ... },                          │ │
│  │   suggested_workspace: "CodeEditor" (reference to RFC-072),           │ │
│  │   pipeline: [...],                                                     │ │
│  │   confidence: 0.85                                                     │ │
│  │ }                                                                      │ │
│  └─────────────────────────────────┬──────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼ HAND-OFF                                │
│                                                                              │
│  LAYER 2: Interaction Routing (RFC-075)                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Trigger: User message/action within project                           │ │
│  │ Input: User text + ProjectAnalysis context                            │ │
│  │ Output: IntentAnalysis {                                               │ │
│  │   interaction_type: "workspace" | "view" | "action" | "conversation", │ │
│  │   workspace: WorkspaceSpec (from RFC-072),                            │ │
│  │   ...                                                                  │ │
│  │ }                                                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Hand-off Protocol

| Event | Owner | Action |
|-------|-------|--------|
| Project opened | RFC-079 | Analyze filesystem → `ProjectAnalysis` |
| Show project overview | RFC-079 | Render pipeline, suggested action |
| User clicks "Work on this" | RFC-079 → RFC-075 | Pass `suggested_action` as RFC-075 input |
| User types in workspace | RFC-075 | Route intent with project context |
| User asks "what should I do next?" | RFC-075 | Use RFC-079's pipeline for context |

### Shared Types

**WorkspaceSpec is owned by RFC-072**. Both RFC-079 and RFC-075 reference it:

```python
# RFC-072 owns the type
from sunwell.surface.types import WorkspaceSpec

# RFC-079 references it for suggested_workspace
@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    suggested_workspace: str  # Primary primitive name, resolved by RFC-072
    # NOT: suggested_workspace: WorkspaceSpec (that's RFC-072's job)

# RFC-075 gets full WorkspaceSpec from RFC-072
```

### Context Propagation

RFC-075's `IntentAnalyzer` receives project context:

```python
# In RFC-075's analyze() method
async def analyze(self, goal: str, project_context: ProjectAnalysis | None = None) -> IntentAnalysis:
    """Analyze intent with optional project context from RFC-079."""
    
    context = await self._gather_context()
    
    # Augment with project context if available
    if project_context:
        context["project_type"] = project_context.project_type.value
        context["current_pipeline_step"] = project_context.current_step
        context["project_confidence"] = project_context.confidence
```

---

## Design

### Project Analysis Model

```python
@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    """Universal project understanding."""
    
    # Identity
    name: str
    path: Path
    
    # What kind of project is this?
    project_type: ProjectType
    project_subtype: str | None  # "svelte-app", "sphinx-docs", "jupyter-notebook"
    
    # What's the current state?
    goals: tuple[Goal, ...]              # From backlog or inferred
    pipeline: tuple[PipelineStep, ...]   # Execution order
    current_step: str | None             # Where we are now
    completion_percent: float            # 0.0 - 1.0
    
    # What should happen next?
    suggested_action: SuggestedAction | None
    suggested_workspace_primary: str     # Primary primitive name (e.g., "CodeEditor")
                                         # RFC-072 resolves this to full WorkspaceSpec
    
    # Code-specific (optional)
    dev_command: DevCommand | None       # Only for code projects with servers
    
    # Confidence (0.0 - 1.0, propagates to RFC-075)
    confidence: float
    confidence_level: Literal["high", "medium", "low"]  # Derived from confidence
    detection_signals: tuple[str, ...]   # What we based this on


class ProjectType(Enum):
    """Primary project classification."""
    CODE = "code"                 # Software development
    DOCUMENTATION = "documentation"  # Docs, guides, specs
    DATA = "data"                 # Analysis, notebooks, datasets
    PLANNING = "planning"         # Goals, roadmaps, research
    CREATIVE = "creative"         # Writing, design, media
    MIXED = "mixed"               # Multiple types


@dataclass(frozen=True, slots=True)
class SuggestedAction:
    """What the user might want to do next."""
    
    action_type: Literal["execute_goal", "continue_work", "start_server", "review", "add_goal"]
    description: str              # "Continue drafting chapter 3"
    goal_id: str | None           # Reference to backlog goal
    command: str | None           # Shell command if applicable
    confidence: float             # How sure we are this is helpful


@dataclass(frozen=True, slots=True)  
class DevCommand:
    """Dev server command (code projects only)."""
    
    command: str                  # "npm run dev"
    description: str              # "Start Vite development server"
    prerequisites: tuple[Prerequisite, ...]
    expected_url: str | None      # "http://localhost:5173"
```

### Detection Logic

```python
async def analyze_project(path: Path, model: ModelProtocol) -> ProjectAnalysis:
    """Analyze any project to understand its intent and state."""
    
    # 1. Gather signals
    signals = gather_project_signals(path)
    # - File patterns (package.json, pyproject.toml, docs/, notebooks/)
    # - Directory structure
    # - README content
    # - Existing backlog
    # - Git history
    
    # 2. Classify project type
    project_type, subtype = classify_project(signals, model)
    
    # 3. Load or infer goals (see Goal Inference section below)
    goals = load_backlog_goals(path)
    if not goals:
        goals = await infer_goals_from_context(signals, project_type, model)
    
    # 4. Build pipeline from goals
    pipeline = build_pipeline(goals, project_type)
    
    # 5. Determine current state
    current_step = detect_current_step(pipeline, path)
    completion = calculate_completion(pipeline)
    
    # 6. Generate suggested action
    suggested = suggest_next_action(pipeline, current_step, project_type)
    
    # 7. Select appropriate workspace primary (RFC-072 composes full layout)
    workspace_primary = select_workspace_primary(project_type, subtype, bool(pipeline))
    
    # 8. Detect dev command (code projects only)
    dev_command = None
    if project_type == ProjectType.CODE:
        dev_command = detect_dev_command(path, signals)
    
    # 9. Calculate confidence
    confidence = calculate_confidence(signals)
    confidence_level = (
        "high" if confidence >= 0.85
        else "medium" if confidence >= 0.65
        else "low"
    )
    
    return ProjectAnalysis(
        name=path.name,
        path=path,
        project_type=project_type,
        project_subtype=subtype,
        goals=goals,
        pipeline=pipeline,
        current_step=current_step,
        completion_percent=completion,
        suggested_action=suggested,
        suggested_workspace_primary=workspace_primary,
        dev_command=dev_command,
        confidence=confidence,
        confidence_level=confidence_level,
        detection_signals=signals.summary,
    )
```

### Signal Gathering

```python
def gather_project_signals(path: Path) -> ProjectSignals:
    """Collect signals that indicate project type and state."""
    
    signals = ProjectSignals()
    
    # Code signals
    signals.has_package_json = (path / "package.json").exists()
    signals.has_pyproject = (path / "pyproject.toml").exists()
    signals.has_cargo = (path / "Cargo.toml").exists()
    signals.has_go_mod = (path / "go.mod").exists()
    signals.has_makefile = (path / "Makefile").exists()
    
    # Documentation signals
    signals.has_docs_dir = (path / "docs").is_dir()
    signals.has_sphinx_conf = (path / "docs" / "conf.py").exists()
    signals.has_mkdocs = (path / "mkdocs.yml").exists()
    signals.markdown_count = len(list(path.glob("**/*.md")))
    
    # Data signals
    signals.has_notebooks = len(list(path.glob("**/*.ipynb"))) > 0
    signals.has_data_dir = (path / "data").is_dir()
    signals.has_csv_files = len(list(path.glob("**/*.csv"))) > 0
    
    # Planning signals
    signals.has_backlog = (path / ".sunwell" / "backlog").exists()
    signals.has_roadmap = any(path.glob("**/ROADMAP*"))
    signals.has_rfc_dir = (path / "docs" / "rfcs").is_dir() or (path / "rfcs").is_dir()
    
    # Creative signals  
    signals.has_prose = (path / "manuscript").is_dir() or (path / "chapters").is_dir()
    signals.has_fountain = len(list(path.glob("**/*.fountain"))) > 0
    
    # State signals
    signals.git_status = get_git_status(path)
    signals.readme_content = read_readme(path)
    signals.recent_files = get_recently_modified(path, limit=10)
    
    return signals
```

### Project Type Classification

#### Heuristic Weight Rationale

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Package manifest (`package.json`, `pyproject.toml`, `Cargo.toml`) | 3 | **Strong indicator** — explicit project definition |
| Framework config (`sphinx conf.py`, `mkdocs.yml`) | 4 | **Definitive** — unambiguous project type |
| `src/` directory | 2 | **Moderate** — common but not universal |
| `docs/` + markdown files | 3 | **Strong** — combined signal reduces false positives |
| Notebooks (`.ipynb`) | 4 | **Definitive** — unique to data projects |
| Prose directories (`manuscript/`, `chapters/`) | 4 | **Definitive** — unique to creative projects |
| Backlog/RFC directories | 2 | **Moderate** — often coexists with code |

**Threshold**: Score ≥3 required for classification. Ties or low scores → LLM fallback.

```python
def classify_project(signals: ProjectSignals, model: ModelProtocol) -> tuple[ProjectType, str | None]:
    """Classify project type from signals."""
    
    # Quick heuristic pass
    scores = {
        ProjectType.CODE: 0,
        ProjectType.DOCUMENTATION: 0,
        ProjectType.DATA: 0,
        ProjectType.PLANNING: 0,
        ProjectType.CREATIVE: 0,
    }
    
    # Code signals (weight rationale: manifest files are explicit declarations)
    if signals.has_package_json:
        scores[ProjectType.CODE] += 3  # Strong: explicit project definition
    if signals.has_pyproject or signals.has_cargo or signals.has_go_mod:
        scores[ProjectType.CODE] += 3  # Strong: explicit project definition
    if (signals.path / "src").is_dir():
        scores[ProjectType.CODE] += 2  # Moderate: common but not universal
        
    # Documentation signals
    if signals.has_docs_dir and signals.markdown_count > 5:
        scores[ProjectType.DOCUMENTATION] += 3  # Strong: combined signal
    if signals.has_sphinx_conf or signals.has_mkdocs:
        scores[ProjectType.DOCUMENTATION] += 4  # Definitive: framework config
        
    # Data signals
    if signals.has_notebooks:
        scores[ProjectType.DATA] += 4  # Definitive: unique to data projects
    if signals.has_data_dir and signals.has_csv_files:
        scores[ProjectType.DATA] += 2  # Moderate: could be test data
        
    # Planning signals
    if signals.has_backlog:
        scores[ProjectType.PLANNING] += 2  # Moderate: often coexists with code
    if signals.has_rfc_dir:
        scores[ProjectType.PLANNING] += 2  # Moderate: often coexists with code
        
    # Creative signals
    if signals.has_prose or signals.has_fountain:
        scores[ProjectType.CREATIVE] += 4  # Definitive: unique structure
    
    # If unclear or mixed, use LLM for semantic analysis
    max_score = max(scores.values())
    if max_score < 3 or list(scores.values()).count(max_score) > 1:
        return classify_with_llm(signals, model)
    
    primary_type = max(scores, key=scores.get)
    subtype = detect_subtype(primary_type, signals)
    
    return primary_type, subtype


def detect_subtype(project_type: ProjectType, signals: ProjectSignals) -> str | None:
    """Detect specific framework/tooling within project type."""
    
    if project_type == ProjectType.CODE:
        if signals.has_package_json:
            pkg = json.loads((signals.path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            
            if "svelte" in deps:
                return "svelte-app"
            if "react" in deps:
                return "react-app"
            if "vue" in deps:
                return "vue-app"
            if "@tauri-apps/api" in deps:
                return "tauri-app"
            if "express" in deps:
                return "express-api"
                
        if signals.has_pyproject:
            pyproject = toml.loads((signals.path / "pyproject.toml").read_text())
            deps = pyproject.get("project", {}).get("dependencies", [])
            
            if any("fastapi" in d for d in deps):
                return "fastapi-api"
            if any("django" in d for d in deps):
                return "django-app"
            if any("flask" in d for d in deps):
                return "flask-app"
                
        if signals.has_cargo:
            return "rust-app"
        if signals.has_go_mod:
            return "go-app"
            
    if project_type == ProjectType.DOCUMENTATION:
        if signals.has_sphinx_conf:
            return "sphinx-docs"
        if signals.has_mkdocs:
            return "mkdocs-docs"
        return "markdown-docs"
        
    if project_type == ProjectType.DATA:
        if signals.has_notebooks:
            return "jupyter-analysis"
        return "data-project"
        
    return None
```

### LLM Classification (Fallback)

When heuristics are ambiguous (score < 3 or ties), use LLM for semantic analysis:

```python
PROJECT_CLASSIFICATION_PROMPT = '''Analyze this project and classify its primary type.

## Project Signals
- Path: {path}
- README excerpt: {readme_excerpt}
- Top-level files: {top_level_files}
- Directory structure: {dir_tree}
- Recent git commits: {recent_commits}

## Project Types
- **code**: Software development (apps, libraries, APIs)
- **documentation**: Technical docs, guides, specifications
- **data**: Analysis, notebooks, datasets, ML experiments
- **planning**: Goals, roadmaps, research, RFCs
- **creative**: Writing, design, media (novels, scripts, artwork)
- **mixed**: Multiple types (explain which)

## Instructions
Respond with JSON:
```json
{{
  "project_type": "code|documentation|data|planning|creative|mixed",
  "subtype": "svelte-app|fastapi-api|sphinx-docs|jupyter-analysis|etc" or null,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}
```

Consider:
1. What is the PRIMARY purpose? (A code project with docs/ is still a code project)
2. What would the user most likely want to do when opening this?
3. Look at the README for intent signals.

Analyze:'''


async def classify_with_llm(signals: ProjectSignals, model: ModelProtocol) -> tuple[ProjectType, str | None]:
    """Use LLM for ambiguous project classification."""
    
    prompt = PROJECT_CLASSIFICATION_PROMPT.format(
        path=signals.path.name,
        readme_excerpt=signals.readme_content[:500] if signals.readme_content else "No README",
        top_level_files=", ".join(f.name for f in signals.path.iterdir() if f.is_file())[:200],
        dir_tree=format_dir_tree(signals.path, max_depth=2),
        recent_commits=format_recent_commits(signals.git_status, limit=5),
    )
    
    response = await model.generate(prompt, temperature=0.2, max_tokens=300)
    
    try:
        data = parse_json_response(response)
        project_type = ProjectType(data["project_type"])
        subtype = data.get("subtype")
        return project_type, subtype
    except (ValueError, KeyError):
        # Default to mixed if parsing fails
        return ProjectType.MIXED, None
```

### Goal Inference

When a project has no backlog, infer reasonable goals from context:

```python
GOAL_INFERENCE_PROMPT = '''Analyze this project and suggest 3-5 reasonable goals.

## Project Context
- Name: {project_name}
- Type: {project_type} ({subtype})
- README excerpt: {readme_excerpt}
- Recent files modified: {recent_files}
- Recent git commits: {recent_commits}
- Current state: {state_signals}

## Instructions
Based on this context, what are the likely next goals for this project?

Respond with JSON:
```json
{{
  "goals": [
    {{
      "id": "goal-1",
      "title": "Short descriptive title",
      "description": "What this goal accomplishes",
      "priority": "high|medium|low",
      "confidence": 0.0-1.0
    }}
  ],
  "reasoning": "Why these goals make sense for this project"
}}
```

Guidelines:
1. Infer from README TODOs, roadmap mentions, commit messages
2. For code projects: consider tests, docs, features mentioned
3. For docs projects: consider incomplete sections, TODO markers
4. For data projects: consider analysis steps, visualization needs
5. If unclear, suggest generic appropriate goals (e.g., "Review existing code")

Analyze:'''


async def infer_goals_from_context(
    signals: ProjectSignals,
    project_type: ProjectType,
    model: ModelProtocol,
) -> tuple[Goal, ...]:
    """Infer reasonable goals when no backlog exists."""
    
    prompt = GOAL_INFERENCE_PROMPT.format(
        project_name=signals.path.name,
        project_type=project_type.value,
        subtype=detect_subtype(project_type, signals) or "generic",
        readme_excerpt=signals.readme_content[:800] if signals.readme_content else "No README",
        recent_files=", ".join(f.name for f in signals.recent_files[:5]),
        recent_commits=format_recent_commits(signals.git_status, limit=5),
        state_signals=describe_state(signals),
    )
    
    response = await model.generate(prompt, temperature=0.4, max_tokens=500)
    
    try:
        data = parse_json_response(response)
        goals = []
        for g in data.get("goals", []):
            goals.append(Goal(
                id=g["id"],
                title=g["title"],
                description=g.get("description", ""),
                priority=g.get("priority", "medium"),
                status="inferred",  # Mark as AI-inferred, not user-created
                confidence=g.get("confidence", 0.6),
            ))
        return tuple(goals)
    except (ValueError, KeyError):
        # Return a single generic goal
        return (Goal(
            id="explore",
            title=f"Explore {signals.path.name}",
            description="Review the project structure and understand the codebase",
            priority="medium",
            status="inferred",
            confidence=0.5,
        ),)


def describe_state(signals: ProjectSignals) -> str:
    """Describe current project state for goal inference."""
    
    state_parts = []
    
    if signals.has_backlog:
        state_parts.append("Has existing backlog (empty or incomplete)")
    if signals.git_status and signals.git_status.uncommitted_changes:
        state_parts.append("Has uncommitted changes")
    if signals.has_notebooks:
        state_parts.append("Contains Jupyter notebooks")
    if signals.markdown_count > 10:
        state_parts.append(f"Contains {signals.markdown_count} markdown files")
    
    return "; ".join(state_parts) if state_parts else "Fresh project"
```

### Confidence Calculation

Confidence score (0.0 - 1.0) reflects how certain we are about the analysis:

```python
def calculate_confidence(signals: ProjectSignals, classification_source: str) -> float:
    """Calculate confidence score for project analysis.
    
    Components:
    - Signal strength: How many definitive signals found (40%)
    - Classification method: Heuristic vs LLM (30%)
    - Context richness: README, git history, backlog (30%)
    """
    
    score = 0.0
    
    # Signal strength (40%)
    definitive_signals = sum([
        signals.has_package_json,
        signals.has_pyproject,
        signals.has_cargo,
        signals.has_sphinx_conf,
        signals.has_mkdocs,
        signals.has_notebooks,
        signals.has_prose,
    ])
    score += min(definitive_signals * 0.1, 0.4)  # Cap at 40%
    
    # Classification method (30%)
    if classification_source == "heuristic":
        score += 0.30  # High confidence from clear signals
    elif classification_source == "llm":
        score += 0.20  # Lower confidence from semantic analysis
    else:
        score += 0.10  # Fallback/default
    
    # Context richness (30%)
    if signals.readme_content:
        score += 0.10
    if signals.git_status and signals.git_status.commit_count > 5:
        score += 0.10
    if signals.has_backlog:
        score += 0.10
    
    return min(score, 1.0)
```

**Confidence levels**:
| Range | Level | Behavior |
|-------|-------|----------|
| ≥0.85 | High 🟢 | Auto-show workspace |
| 0.65-0.84 | Medium 🟡 | Show with subtle "Is this right?" option |
| <0.65 | Low 🟠 | Ask user to confirm project type |

### Workspace Selection

RFC-079 selects a **primary primitive** based on project type. RFC-072 (Surface Primitives) handles actual workspace composition.

```python
# Workspace primary primitives by project type
# RFC-072 uses this to compose the full workspace layout
WORKSPACE_PRIMARIES: dict[ProjectType, str] = {
    ProjectType.CODE: "CodeEditor",
    ProjectType.DOCUMENTATION: "ProseEditor",
    ProjectType.DATA: "NotebookEditor",
    ProjectType.PLANNING: "KanbanBoard",
    ProjectType.CREATIVE: "ProseEditor",
    ProjectType.MIXED: "CodeEditor",  # Default for mixed
}


def select_workspace_primary(
    project_type: ProjectType,
    subtype: str | None,
    has_pipeline: bool,
) -> str:
    """Select primary workspace primitive for project type.
    
    Returns the primary primitive name. RFC-072 handles:
    - Secondary primitives (FileTree, Terminal, etc.)
    - Contextual widgets (DAGView if pipeline exists)
    - Layout arrangement
    """
    
    # Subtype-specific overrides
    if subtype == "jupyter-analysis":
        return "NotebookEditor"
    if subtype in ("sphinx-docs", "mkdocs-docs", "markdown-docs"):
        return "ProseEditor"
    
    return WORKSPACE_PRIMARIES.get(project_type, "CodeEditor")


# Example integration with RFC-072:
# 
# analysis = await analyze_project(path, model)
# workspace_spec = surface_composer.compose_for_primitive(
#     primary=analysis.suggested_workspace_primary,
#     context={
#         "project_type": analysis.project_type,
#         "has_pipeline": bool(analysis.pipeline),
#         "has_dev_server": analysis.dev_command is not None,
#     }
# )
```

---

## UI Changes

### Project Open Flow

**Before (RFC-066)**:
```
User opens project
    ↓
Show project card with "Run" button
    ↓
Click "Run" → Analyze for dev server → Show command → Execute
```

**After (RFC-079)**:
```
User opens project
    ↓
Analyze project intent (type, goals, state)
    ↓
Show Project Overview:
  - Project type badge
  - Goal pipeline (if any)
  - Suggested next action
  - Appropriate workspace
    ↓
User can:
  - Work on suggested action
  - Pick different goal from pipeline  
  - Start dev server (if applicable)
  - Add new goals
  - Just explore
```

### Project Overview Component

```
┌─────────────────────────────────────────────────────────────────┐
│ sunwell-studio                                        [⚙️] [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 Code Project (Svelte + Tauri)              85% confident   │
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│  📋 Pipeline                                        3/7 done   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ✅ Setup project structure                              │   │
│  │  ✅ Implement core components                            │   │
│  │  ✅ Add DAG visualization                                │   │
│  │  🔄 Fix run command detection  ← current                 │   │
│  │  ⏳ Add project intent analyzer                          │   │
│  │  ⏳ Integrate with generative interface                  │   │
│  │  ⏳ Write tests                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│  💡 Suggested: Continue "Fix run command detection"            │
│                                                                 │
│  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ ▶ Work on this   │  │ 🖥️ Dev Server   │  │ ➕ Add Goal  │  │
│  └──────────────────┘  └─────────────────┘  └──────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Empty State (No Pipeline Yet)

```
┌─────────────────────────────────────────────────────────────────┐
│ my-new-project                                        [⚙️] [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 Code Project (React)                           90% confident│
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│                    📋 No goals yet                              │
│                                                                 │
│     This looks like a React web app. What would you            │
│     like to accomplish?                                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 💬 Describe your goal...                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Or:                                                            │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ 🖥️ Start Server │  │ 🔍 Explore Code │                      │
│  └─────────────────┘  └─────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Caching Strategy

Project analysis is cached in `.sunwell/project.json` for fast re-open.

### Cache Schema

```json
{
  "version": 1,
  "analyzed_at": "2026-01-21T14:30:00Z",
  "project_type": "code",
  "project_subtype": "svelte-app",
  "confidence": 0.85,
  "detection_signals": ["has_package_json", "has_src_dir", "svelte_dependency"],
  "suggested_workspace_primary": "CodeEditor",
  "goals_inferred": true,
  "goals": [
    {"id": "goal-1", "title": "...", "status": "inferred"}
  ],
  "dev_command": {
    "command": "npm run dev",
    "expected_url": "http://localhost:5173"
  },
  "file_hashes": {
    "package.json": "abc123...",
    "pyproject.toml": null,
    "README.md": "def456..."
  }
}
```

### Invalidation Rules

| Trigger | Action |
|---------|--------|
| Key file changed (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `README.md`) | Full re-analysis |
| TTL expired (default: 1 hour) | Re-analyze in background |
| New top-level directory created | Check if changes classification |
| Git branch changed | Re-analyze (goals may differ) |
| User runs `sunwell analyze --fresh` | Force re-analysis |

```python
async def load_or_analyze(path: Path, model: ModelProtocol) -> ProjectAnalysis:
    """Load cached analysis or perform fresh analysis."""
    
    cache_path = path / ".sunwell" / "project.json"
    
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
        
        # Check invalidation
        if is_cache_valid(cache, path):
            return ProjectAnalysis.from_cache(cache)
    
    # Fresh analysis
    analysis = await analyze_project(path, model)
    
    # Cache result
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(analysis.to_cache_json())
    
    return analysis


def is_cache_valid(cache: dict, path: Path) -> bool:
    """Check if cached analysis is still valid."""
    
    # Check version
    if cache.get("version") != 1:
        return False
    
    # Check TTL (1 hour default)
    analyzed_at = datetime.fromisoformat(cache["analyzed_at"])
    if datetime.now() - analyzed_at > timedelta(hours=1):
        return False
    
    # Check key file hashes
    for filename, expected_hash in cache.get("file_hashes", {}).items():
        file_path = path / filename
        if file_path.exists():
            actual_hash = hash_file(file_path)
            if actual_hash != expected_hash:
                return False
        elif expected_hash is not None:
            # File was deleted
            return False
    
    return True
```

---

## Monorepo Detection

Monorepos contain multiple sub-projects. RFC-079 detects and surfaces them.

### Detection

```python
def detect_sub_projects(path: Path) -> list[SubProject]:
    """Detect sub-projects in a monorepo."""
    
    sub_projects = []
    
    # Check common monorepo patterns
    patterns = [
        "packages/*/package.json",      # npm workspaces
        "apps/*/package.json",          # Turborepo/Nx
        "services/*/pyproject.toml",    # Python services
        "crates/*/Cargo.toml",          # Rust workspace
    ]
    
    for pattern in patterns:
        for manifest in path.glob(pattern):
            sub_projects.append(SubProject(
                name=manifest.parent.name,
                path=manifest.parent,
                manifest=manifest,
            ))
    
    # Also check for workspace definitions
    if (path / "pnpm-workspace.yaml").exists():
        sub_projects.extend(parse_pnpm_workspace(path))
    if (path / "Cargo.toml").exists():
        sub_projects.extend(parse_cargo_workspace(path))
    
    return sub_projects


@dataclass(frozen=True, slots=True)
class SubProject:
    """A sub-project within a monorepo."""
    name: str
    path: Path
    manifest: Path
```

### UI Behavior

When monorepo detected:

```
┌─────────────────────────────────────────────────────────────────┐
│ my-monorepo                                              [⚙️] [×] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 Monorepo (5 sub-projects)                    85% confident │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Which project would you like to work on?                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  📦 packages/web         Svelte app                     │   │
│  │  📦 packages/api         FastAPI backend                │   │
│  │  📦 packages/shared      Shared utilities               │   │
│  │  📄 docs                 Sphinx documentation           │   │
│  │  🔧 infrastructure       Terraform configs              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Or work on the monorepo as a whole:                            │
│  ┌──────────────────┐                                           │
│  │ 📋 View Pipeline │                                           │
│  └──────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

User selects a sub-project → RFC-079 re-analyzes that path → normal flow continues.

---

## Migration Path

### Phase 1: Extend `run_analyzer.py` → `project_analyzer.py`

1. Keep existing dev command detection
2. Add project type classification
3. Add pipeline/goal integration
4. Return `ProjectAnalysis` instead of `RunAnalysis`

### Phase 2: Update Studio UI

1. Replace "Run Project" modal with "Project Overview"
2. Show pipeline when available
3. Show suggested action
4. Keep "Start Dev Server" as secondary action for code projects

### Phase 3: Integration with Generative Interface

1. Project open triggers workspace composition
2. Suggested action integrates with RFC-075 intent routing
3. Goal selection flows into Naaru execution

---

## File Changes

| File | Change |
|------|--------|
| `src/sunwell/project/analyzer.py` | New: Universal project analysis (main module) |
| `src/sunwell/project/types.py` | New: `ProjectAnalysis`, `ProjectType`, `SuggestedAction` |
| `src/sunwell/project/signals.py` | New: `ProjectSignals`, signal gathering |
| `src/sunwell/project/inference.py` | New: Goal inference logic with LLM prompts |
| `src/sunwell/project/cache.py` | New: Cache loading/saving/invalidation |
| `src/sunwell/project/monorepo.py` | New: Monorepo detection and sub-project handling |
| `src/sunwell/interface/analyzer.py` | Update: Accept `ProjectAnalysis` context in `analyze()` |
| `studio/src-tauri/src/commands.rs` | Add `analyze_project` command |
| `studio/src/components/ProjectOverview.svelte` | New: Full project overview UI |
| `studio/src/stores/project.svelte.ts` | New: Project analysis state |
| `studio/src/lib/types.ts` | Add `ProjectAnalysis` types |

---

## Open Questions

1. ~~**How to infer goals for projects without a backlog?**~~ **RESOLVED** — See Goal Inference section. LLM analysis of README + commits with confidence scoring.

2. ~~**Should project analysis run on every open?**~~ **RESOLVED** — See Caching Strategy section. Cache with TTL + file hash invalidation.

3. ~~**What about monorepos with multiple project types?**~~ **RESOLVED** — See Monorepo Detection section. Detect sub-projects, let user choose focus.

4. **How does this interact with lens/binding selection?** Project type could suggest appropriate lens.
   - *Proposal*: `ProjectAnalysis` includes `suggested_lens: str | None` that maps to existing lens definitions.

5. **Should inferred goals persist to backlog?** Currently marked as `status: "inferred"` but not saved.
   - *Proposal*: Prompt user "These goals were inferred. Save to backlog?" on first interaction.

6. **Confidence threshold for auto-showing workspace vs. asking?** Currently always shows suggested workspace.
   - *Proposal*: If confidence < 0.6, show "I think this is a {type} project. Is that right?" confirmation.

---

## Alternatives Considered

### A: Keep RFC-066 as-is, add project type detection separately

**Rejected**: Creates two overlapping systems. Better to unify.

### B: Make project analysis purely LLM-driven (no heuristics)

**Rejected**: Too slow for project open. Heuristics first, LLM for ambiguous cases.

### C: Require explicit project configuration

**Rejected**: Friction. Should work out-of-the-box with smart defaults.

---

## Success Metrics

1. **Accuracy**: >90% correct project type detection on test corpus
2. **Latency**: <500ms for cached analysis, <2s for fresh analysis
3. **Coverage**: Works for code (any language), docs, data, planning, creative projects
4. **User feedback**: "It understood what my project is" sentiment

---

## References

- RFC-046: Autonomous Backlog
- RFC-056: Live DAG Integration
- RFC-066: Intelligent Run Button (superseded)
- RFC-072: Surface Primitives
- RFC-075: Generative Interface
