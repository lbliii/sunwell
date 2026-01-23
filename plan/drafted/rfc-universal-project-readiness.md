# RFC: Universal Project Readiness & Preview

**Status**: Phase 1 Complete  
**Created**: 2026-01-22  
**Author**: AI Assistant  
**Confidence**: 85% 🟢  
**Extends**: RFC-079 (Project Intent Analyzer)  
**Related**: RFC-066 (Intelligent Run Button), rfc-backlog-driven-execution

> **Implementation Note**: Phase 1 (Type Extensions) completed 2026-01-22.
> - Added `PreviewType` enum to `intent_types.py`
> - Extended `ProjectAnalysis` with `preview_type`, `preview_url`, `preview_file`
> - Extended `Prerequisite` with `satisfied`, `required` fields
> - Added `_detect_preview_type()` to `intent_analyzer.py`
> - Created `prereq_check.py` with `can_preview()`, `check_prerequisites()`, etc.
> - 34 tests passing

---

## Executive Summary

Extend RFC-079's `ProjectAnalysis` to support **universal preview** for any project type — not just code with dev servers. Add `PreviewType` as an orthogonal dimension to `ProjectType`, enabling "Try It" to work for screenplays, novels, dialogue trees, and any creative project.

**Key changes**:
1. Add `PreviewType` enum to `intent_types.py`
2. Extend `ProjectAnalysis` with `preview_type`, `preview_url`, `preview_file`
3. Implement built-in renderers for prose, screenplay, dialogue
4. Use existing signals (`has_prose`, `has_fountain`) — no new detection needed

**Not** creating a separate `PreviewAnalysis` type — this extends the existing system.

**Estimated effort**: 3 weeks (type extensions → renderers → studio integration)

---

## Problem Statement

### The Core Question

**"What does it take to preview this project?"**

Every project, regardless of type, has a "Try It" moment:

| Project Type | What "Preview" Means |
|---|---|
| Flask app | Start server, open `localhost:5000` |
| React app | `npm run dev`, open `localhost:5173` |
| Screenplay | Render Fountain → formatted PDF/HTML |
| Novel chapter | Render Markdown → formatted prose |
| Web serial | Render with chapter navigation |
| Jupyter notebook | Start Jupyter server, open in browser |
| CLI tool | Pre-filled terminal command |
| Game dialogue | Interactive dialogue tree player |

### Current State: Code-Only Detection

The "Try It" experience only works for recognized code projects:

```python
# src/sunwell/project/intent_analyzer.py:95-98
dev_command = None
if project_type == ProjectType.CODE:  # ← Only code!
    dev_command = _detect_dev_command(signals)
```

We just hit this bug: a Flask app in `src/app.py` was misclassified as Svelte, tried `npm start`, got a white page.

### What's Missing

For ANY project, we need to answer:

1. **Detect**: What kind of thing is this?
2. **Requirements**: What do I need installed to run/preview it?
3. **Run**: What command(s) start it?
4. **Preview**: Where do I see the result?

---

## Goals

1. **Universal preview detection** — Every project type gets a preview mode
2. **AI-powered detection** — Recognize any project type, not just hardcoded patterns
3. **Requirements checking** — Know what needs to be installed before running
4. **Simple mental model** — Detect → Check → Run → Preview

---

## Non-Goals

- Deep quality gates (covered separately in quality gates RFC)
- Replacing specialized tools
- Supporting every possible project type out of the box (AI handles unknowns)

---

## Design Options

### Option A: Extend Existing `ProjectAnalysis` (Recommended)

Add preview-specific fields to the existing `ProjectAnalysis` type from RFC-079.

```python
# Extend src/sunwell/project/intent_types.py

class PreviewType(Enum):
    """How to preview this project (orthogonal to ProjectType)."""
    WEB_VIEW = "web_view"
    TERMINAL = "terminal"
    PROSE = "prose"
    SCREENPLAY = "screenplay"
    DIALOGUE = "dialogue"
    NOTEBOOK = "notebook"
    STATIC = "static"
    NONE = "none"

@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    # ... existing fields from RFC-079 ...
    
    # NEW: Preview-specific fields
    preview_type: PreviewType = PreviewType.NONE
    preview_url: str | None = None
    preview_file: str | None = None
```

| Pros | Cons |
|------|------|
| ✅ Single source of truth | ⚠️ Grows `ProjectAnalysis` size |
| ✅ No type conversion needed | ⚠️ Couples preview to full analysis |
| ✅ Reuses existing `DevCommand` and `Prerequisite` | |
| ✅ Cache coherency | |

### Option B: Separate `PreviewSpec` Derived from Analysis

Create a focused preview type that's computed from `ProjectAnalysis`.

```python
# src/sunwell/project/preview.py

@dataclass(frozen=True, slots=True)
class PreviewSpec:
    """Lightweight preview specification derived from ProjectAnalysis."""
    preview_type: PreviewType
    preview_url: str | None
    preview_file: str | None
    ready: bool  # All prerequisites satisfied
    
def derive_preview_spec(analysis: ProjectAnalysis) -> PreviewSpec:
    """Derive preview spec from full analysis."""
    ...
```

| Pros | Cons |
|------|------|
| ✅ Separation of concerns | ⚠️ Two types to maintain |
| ✅ Lightweight for UI | ⚠️ Requires conversion |
| ✅ Can cache separately | ⚠️ Potential staleness |

### Option C: Standalone `PreviewAnalysis` (Not Recommended)

Create an independent preview system that doesn't integrate with RFC-079.

| Pros | Cons |
|------|------|
| ✅ Complete independence | ❌ Duplicates detection logic |
| | ❌ Two caches, two codepaths |
| | ❌ Inconsistent project understanding |

### Recommendation: Option A

**Rationale**: RFC-079's `ProjectAnalysis` already has the infrastructure we need:
- `DevCommand` with prerequisites (`intent_types.py:84-107`)
- `ProjectType.CREATIVE` for non-code projects (`intent_types.py:21`)
- Signal detection for prose/fountain (`signals.py:65-66`)
- Confidence scoring and caching

Adding `PreviewType` as an orthogonal dimension keeps the system unified:
- `ProjectType` answers: "What IS this?" (code, creative, data, etc.)
- `PreviewType` answers: "HOW do I view it?" (web, prose reader, terminal, etc.)

---

## Architecture Impact

### Affected Components

| Component | Change | Risk |
|-----------|--------|------|
| `intent_types.py` | Add `PreviewType` enum, extend `ProjectAnalysis` | Low — additive |
| `intent_analyzer.py` | Add `_detect_preview_type()` function | Low — new code path |
| `signals.py` | No change — already has `has_prose`, `has_fountain` | None |
| `studio/src-tauri/src/preview.rs` | Extend `ViewType` enum to match `PreviewType` | Medium — Rust/Python sync |
| UI components | New preview renderers (prose, screenplay, dialogue) | Medium — new features |

### Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                     RFC-079 + This RFC                          │
│                                                                 │
│   analyze_project()                                             │
│         │                                                       │
│         ├─→ _classify_project() → ProjectType                   │
│         ├─→ _detect_dev_command() → DevCommand (existing)       │
│         └─→ _detect_preview_type() → PreviewType (NEW)          │
│                     │                                           │
│                     ▼                                           │
│              ProjectAnalysis                                    │
│              ├─ project_type: ProjectType.CREATIVE              │
│              ├─ dev_command: DevCommand | None                  │
│              └─ preview_type: PreviewType.PROSE  (NEW)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **AI model unavailable** | Medium | Medium | Heuristics always work; AI is fallback only |
| **Detection accuracy issues** | Medium | Low | User can override; cached successful runs |
| **Rust/Python type sync drift** | Medium | Medium | Generate Rust types from Python schema |
| **Prerequisite check hangs** | Low | Medium | 5s timeout on all subprocess calls |
| **Cost overruns** | Low | Low | ~$0.0006/analysis; 80% handled by heuristics |
| **Fountain/dialogue render quality** | Medium | Low | "Good enough" for MVP; iterate with user feedback |

### Fallback Behavior

```python
# If AI unavailable:
if ai_error:
    # Use heuristic best-guess with lower confidence
    return PreviewAnalysis(
        preview_type=_heuristic_preview_type(signals),
        confidence=0.6,  # Lower confidence without AI
        reasoning="Heuristic detection (AI unavailable)",
    )
```

---

## Design

### The Unified Model

This RFC extends RFC-079's `analyze_project()` to include preview information:

```
┌────────────────────────────────────────────────────────────────────┐
│                   analyze_project() [RFC-079 + this RFC]           │
│                                                                    │
│   1. gather_signals()           → ProjectSignals (existing)        │
│          │                                                         │
│          ▼                                                         │
│   2. _classify_project()        → ProjectType (existing)           │
│          │                                                         │
│          ▼                                                         │
│   3. _detect_dev_command()      → DevCommand | None (existing)     │
│          │                                                         │
│          ▼                                                         │
│   4. _detect_preview_type()     → PreviewType (NEW)                │
│          │                                                         │
│          ▼                                                         │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │ ProjectAnalysis                                             │  │
│   │   project_type: ProjectType.CREATIVE                        │  │
│   │   dev_command: DevCommand | None                            │  │
│   │   preview_type: PreviewType.PROSE      ← NEW                │  │
│   │   preview_url: str | None              ← NEW                │  │
│   │   preview_file: "chapters/ch-01.md"    ← NEW                │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                   "Try It" Flow (Studio)                           │
│                                                                    │
│   User clicks "Try It"                                             │
│          │                                                         │
│          ▼                                                         │
│   load_or_analyze(project_path)  → ProjectAnalysis                 │
│          │                                                         │
│          ├── preview_type == WEB_VIEW?                             │
│          │       └── check_prerequisites()                         │
│          │       └── start dev_command                             │
│          │       └── open WebView at preview_url                   │
│          │                                                         │
│          ├── preview_type == PROSE | SCREENPLAY | DIALOGUE?        │
│          │       └── open built-in renderer with preview_file      │
│          │                                                         │
│          └── preview_type == TERMINAL?                             │
│                  └── open terminal with dev_command                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

### Component 1: Extending ProjectAnalysis with Preview

Per **Option A**, we extend the existing `ProjectAnalysis` type from RFC-079 rather than creating a separate type.

**New types to add to `src/sunwell/project/intent_types.py`:**

```python
# src/sunwell/project/intent_types.py (EXTEND existing file)

class PreviewType(Enum):
    """How to preview this project (orthogonal to ProjectType).
    
    ProjectType answers: "What IS this?" (code, creative, data)
    PreviewType answers: "HOW do I view it?" (web, prose reader, terminal)
    """
    
    WEB_VIEW = "web_view"      # Embedded browser (web apps)
    TERMINAL = "terminal"      # Pre-filled terminal (CLI tools)
    PROSE = "prose"            # Formatted reader (novels, articles)
    SCREENPLAY = "screenplay"  # Fountain renderer (scripts)
    DIALOGUE = "dialogue"      # Interactive tree (game dialogue)
    NOTEBOOK = "notebook"      # Jupyter-style (data science)
    STATIC = "static"          # Just open the file (images, PDFs)
    NONE = "none"              # No preview (libraries, configs)


# Extend existing Prerequisite (intent_types.py:84-107)
@dataclass(frozen=True, slots=True)
class Prerequisite:
    """Something that must be installed/available."""
    
    command: str
    """Command to run (e.g., 'pip install flask')."""
    
    description: str
    """Human-readable description."""
    
    check_command: str | None = None
    """Command to check if already satisfied."""
    
    # NEW fields for preview checking:
    satisfied: bool = False
    """Whether this prerequisite is currently met (runtime state)."""
    
    required: bool = True
    """If False, preview can work without this (degraded mode)."""


# Extend existing ProjectAnalysis (intent_types.py:118-163)
@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    """Full project understanding including preview capability."""
    
    # ... existing RFC-079 fields ...
    name: str
    path: Path
    project_type: ProjectType
    project_subtype: str | None
    goals: tuple[InferredGoal, ...]
    pipeline: tuple[PipelineStep, ...]
    current_step: str | None
    completion_percent: float
    suggested_action: SuggestedAction | None
    suggested_workspace_primary: str
    dev_command: DevCommand | None
    confidence: float
    confidence_level: str
    detection_signals: tuple[str, ...]
    classification_source: str
    
    # NEW: Preview-specific fields
    preview_type: PreviewType = PreviewType.NONE
    """How to preview this project."""
    
    preview_url: str | None = None
    """URL for web-based previews."""
    
    preview_file: str | None = None
    """Primary file for content previews (prose, screenplay)."""
```

**Key insight**: `ProjectType` and `PreviewType` are orthogonal:

| ProjectType | PreviewType | Example |
|-------------|-------------|---------|
| CODE | WEB_VIEW | React app |
| CODE | TERMINAL | CLI tool |
| CREATIVE | PROSE | Novel manuscript |
| CREATIVE | SCREENPLAY | Fountain screenplay |
| CREATIVE | DIALOGUE | Yarn/ink game dialogue |
| DATA | NOTEBOOK | Jupyter analysis |

**Examples of what the extended `ProjectAnalysis` returns:

# Flask app — ProjectType.CODE + PreviewType.WEB_VIEW
ProjectAnalysis(
    name="my-flask-app",
    project_type=ProjectType.CODE,
    project_subtype="flask-app",
    dev_command=DevCommand(
        command="FLASK_APP=src/app.py python -m flask run",
    prerequisites=(
            Prerequisite("pip install flask", "Install Flask", "python -c 'import flask'"),
    ),
        expected_url="http://localhost:5000",
    ),
    # NEW preview fields:
    preview_type=PreviewType.WEB_VIEW,
    preview_url="http://localhost:5000",
    preview_file=None,
    confidence=0.95,
)

# Fountain screenplay — ProjectType.CREATIVE + PreviewType.SCREENPLAY
ProjectAnalysis(
    name="my-screenplay",
    project_type=ProjectType.CREATIVE,
    project_subtype="fountain-screenplay",
    dev_command=None,  # No server needed
    # NEW preview fields:
    preview_type=PreviewType.SCREENPLAY,
    preview_url=None,
    preview_file="screenplay.fountain",
    confidence=0.90,
)

# Novel — ProjectType.CREATIVE + PreviewType.PROSE
ProjectAnalysis(
    name="my-novel",
    project_type=ProjectType.CREATIVE,
    project_subtype="novel-manuscript",
    dev_command=None,
    # NEW preview fields:
    preview_type=PreviewType.PROSE,
    preview_url=None,
    preview_file="chapters/chapter-01.md",
    confidence=0.85,
)

# CLI tool — ProjectType.CODE + PreviewType.TERMINAL
ProjectAnalysis(
    name="my-cli",
    project_type=ProjectType.CODE,
    project_subtype="python-cli",
    dev_command=DevCommand(
        command="python -m myapp --help",
    prerequisites=(
            Prerequisite("pip install click", "Install Click"),
    ),
    ),
    # NEW preview fields:
    preview_type=PreviewType.TERMINAL,
    preview_url=None,
    preview_file=None,
    confidence=0.80,
)
```

---

### Component 2: AI-Powered Preview Detection (Small Model)

**Problem**: Heuristics can't recognize every project type.

**Solution**: Use LLM when heuristics fail or have low confidence.

**Key insight**: This is a perfect task for the **cheapest/fastest model**:
- Structured JSON output (not creative)
- Pattern recognition (not reasoning)
- Low stakes (user can override)
- Needs to be instant (<2s)

| Model | Cost | Speed | Sufficient? |
|---|---|---|---|
| Claude Haiku | $0.25/1M | ~0.5s | ✅ Yes |
| GPT-3.5-turbo | $0.50/1M | ~0.5s | ✅ Yes |
| Gemini Flash | $0.075/1M | ~0.3s | ✅ Yes |
| Local (Llama 3 8B) | Free | ~1s | ✅ Yes |
| Claude Opus | $15/1M | ~3s | ❌ Overkill |

**Use `model_tier: "fast"` for preview detection.**

```python
# src/sunwell/project/intent_analyzer.py (EXTEND existing file)

PREVIEW_DETECTION_PROMPT = '''What's the best way to preview this project?

## Project Info
- Name: {name}
- Files: {file_tree}
- Key file contents: {key_files}

Answer in JSON:
```json
{{
  "preview_type": "web_view | terminal | prose | screenplay | dialogue | notebook | static | none",
  "preview_url": "http://localhost:5000 | null",
  "preview_file": "manuscript.md | screenplay.fountain | null",
  "confidence": 0.0-1.0,
  "reasoning": "Why I think this"
}}
```

Focus on: What do I look at? Where do I see the result?
'''


def _detect_preview_type(
    signals: ProjectSignals,
    project_type: ProjectType,
    dev_command: DevCommand | None,
) -> tuple[PreviewType, str | None, str | None]:
    """Detect preview type from signals and existing analysis.
    
    Returns:
        (preview_type, preview_url, preview_file)
    """
    # Web apps with dev commands → WEB_VIEW
    if dev_command and dev_command.expected_url:
        return PreviewType.WEB_VIEW, dev_command.expected_url, None
    
    # CLI tools → TERMINAL
    if dev_command and not dev_command.expected_url:
        return PreviewType.TERMINAL, None, None
    
    # Creative projects based on signals
    if signals.has_fountain:
        fountain_file = _find_primary_fountain(signals.path)
        return PreviewType.SCREENPLAY, None, fountain_file
    
    if signals.has_prose:
        prose_file = _find_primary_prose(signals.path)
        return PreviewType.PROSE, None, prose_file
    
    # Data projects with notebooks
    if signals.has_notebooks:
        return PreviewType.NOTEBOOK, "http://localhost:8888", None
    
    # Default: no preview
    return PreviewType.NONE, None, None


async def _detect_preview_type_with_ai(
    signals: ProjectSignals,
    model_provider: ModelProvider,
) -> tuple[PreviewType, str | None, str | None, float]:
    """Use AI when heuristics fail or have low confidence.
    
    Returns:
        (preview_type, preview_url, preview_file, confidence)
    """
    model = model_provider.get_model(tier="fast")
    context = gather_preview_context(signals.path)
    
    prompt = PREVIEW_DETECTION_PROMPT.format(
        name=signals.path.name,
        file_tree=context["file_tree"],
        key_files=context["key_files"],
    )
    
    response = await model.generate(
        prompt,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    data = _extract_json(response.content)
    
    return (
        PreviewType(data["preview_type"]),
        data.get("preview_url"),
        data.get("preview_file"),
        data.get("confidence", 0.7),
    )
```

**Why this works with small models**:
- Structured JSON output (not open-ended)
- Finite set of `preview_type` values to choose from
- Clear examples in the prompt
- Pattern matching, not reasoning

**Why AI matters**: Heuristics can recognize Flask, React, Django. But what about:
- A Ren'Py visual novel
- A Twine interactive fiction project
- A Hugo static site
- A LaTeX academic paper
- A Godot game project

The LLM can figure these out because it understands context, not just file patterns.

---

### Component 3: Heuristic Preview Detection

Preview detection integrates into the existing `_classify_project()` flow in `intent_analyzer.py`. The heuristics use signals already gathered by RFC-079.

```python
# src/sunwell/project/intent_analyzer.py (EXTEND existing functions)

def _detect_preview_type(
    signals: ProjectSignals,
    project_type: ProjectType,
    subtype: str | None,
    dev_command: DevCommand | None,
) -> tuple[PreviewType, str | None, str | None]:
    """Detect preview type from existing analysis.
    
    This runs AFTER _classify_project() and _detect_dev_command(),
    so we can leverage their results.
    
    Returns:
        (preview_type, preview_url, preview_file)
    """
    
    # === CODE PROJECTS: Use dev_command info ===
    if project_type == ProjectType.CODE:
        if dev_command:
            if dev_command.expected_url:
                # Web app with dev server
                return PreviewType.WEB_VIEW, dev_command.expected_url, None
            else:
                # CLI tool
                return PreviewType.TERMINAL, None, None
        return PreviewType.NONE, None, None  # Library, no preview
    
    # === CREATIVE PROJECTS: Content-based preview ===
    if project_type == ProjectType.CREATIVE:
        # Screenplay
        if signals.has_fountain:
            fountain_file = _find_primary_file(signals.path, "**/*.fountain")
            return PreviewType.SCREENPLAY, None, fountain_file
        
        # Prose (novel, manuscript)
        if signals.has_prose:
            prose_file = _find_primary_prose(signals.path)
            return PreviewType.PROSE, None, prose_file
        
        # Dialogue (Yarn, ink)
        if yarn_file := _find_primary_file(signals.path, "**/*.yarn"):
            return PreviewType.DIALOGUE, None, yarn_file
        if ink_file := _find_primary_file(signals.path, "**/*.ink"):
            return PreviewType.DIALOGUE, None, ink_file
    
    # === DATA PROJECTS: Notebooks ===
    if project_type == ProjectType.DATA:
        if signals.has_notebooks:
            return PreviewType.NOTEBOOK, "http://localhost:8888", None
    
    # === DEFAULT: No preview ===
    return PreviewType.NONE, None, None


def _find_primary_file(path: Path, pattern: str) -> str | None:
    """Find the primary file matching a pattern."""
    files = list(path.glob(pattern))
    if not files:
        return None
    # Prefer files in root, then alphabetically
    files.sort(key=lambda f: (len(f.parts), f.name))
    return str(files[0].relative_to(path))


def _find_primary_prose(path: Path) -> str | None:
    """Find the primary prose file (first chapter or main manuscript)."""
    for dir_name in ["chapters", "manuscript"]:
        chapter_dir = path / dir_name
        if chapter_dir.is_dir():
            chapters = sorted(chapter_dir.glob("*.md"))
            if chapters:
                return str(chapters[0].relative_to(path))
    return None
```

**Key insight**: Preview detection reuses signals already gathered by RFC-079.

**Expected coverage** (to be validated during implementation):
- Heuristics: ~70-80% of projects (common frameworks with clear signals)
- AI fallback: ~20-30% (uncommon formats, ambiguous signals)

---

### Component 3.5: Self-Validation (Optional, Small Model)

For low-confidence AI detections, a second validation pass catches obvious mismatches:

```python
async def _validate_preview_detection(
    analysis: ProjectAnalysis,
    model_provider: ModelProvider,
) -> bool:
    """Validate preview detection makes sense.
    
    Only runs when:
    - AI was used for detection (not heuristics)
    - Confidence < 0.9
    
    Returns True if valid, False if suspicious.
    """
    if analysis.confidence >= 0.9:
        return True  # High confidence, skip
    
    model = model_provider.get_model(tier="fast")
    
    prompt = f'''Sanity check: Does this preview setup make sense?

Project type: {analysis.project_type.value}
Dev command: {analysis.dev_command.command if analysis.dev_command else "None"}
Preview type: {analysis.preview_type.value}

Reply with JSON: {{"valid": true/false, "issue": "explanation if invalid"}}
'''
    
    response = await model.generate(prompt, max_tokens=100)
    result = _extract_json(response.content)
    
    if not result.get("valid", True):
        logger.warning(f"Preview validation failed: {result.get('issue')}")
        return False
    
    return True
```

**Why self-validation works**:
- Catch mismatches like "Flask app" + "npm run dev"
- Second opinion is cheap (~$0.0001)
- Small models are good at "does this make sense?" checks

---

### Component 4: Prerequisite Checking

Prerequisite checking extends the existing `DevCommand.prerequisites` system from RFC-079.

```python
# src/sunwell/project/prereq_check.py

import subprocess


def check_prerequisites(analysis: ProjectAnalysis) -> list[Prerequisite]:
    """Check which prerequisites are satisfied.
    
    Examines dev_command.prerequisites and returns updated list
    with satisfaction status.
    """
    if not analysis.dev_command or not analysis.dev_command.prerequisites:
        return []
    
    checked = []
    for prereq in analysis.dev_command.prerequisites:
        satisfied = _check_single_prerequisite(prereq)
        checked.append(Prerequisite(
            command=prereq.command,
            description=prereq.description,
            check_command=prereq.check_command,
            satisfied=satisfied,
            required=prereq.required,
        ))
    
    return checked


def _check_single_prerequisite(prereq: Prerequisite) -> bool:
    """Check if a single prerequisite is satisfied."""
    if not prereq.check_command:
        return False  # Can't verify, assume not satisfied
    
            try:
                result = subprocess.run(
                    prereq.check_command,
                    shell=True,
                    capture_output=True,
                    timeout=5,
                )
        return result.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
        return False


def can_preview(analysis: ProjectAnalysis) -> bool:
    """Check if preview is ready (no server needed or prerequisites met)."""
    # Content previews (prose, screenplay, dialogue) have no prerequisites
    if analysis.preview_type in (
        PreviewType.PROSE,
        PreviewType.SCREENPLAY,
        PreviewType.DIALOGUE,
        PreviewType.STATIC,
    ):
        return True
    
    # Web/terminal previews need dev_command prerequisites
    if analysis.dev_command:
        checked = check_prerequisites(analysis)
        return all(p.satisfied or not p.required for p in checked)
    
    return analysis.preview_type != PreviewType.NONE


def missing_prerequisites(analysis: ProjectAnalysis) -> list[Prerequisite]:
    """Get list of missing required prerequisites."""
    checked = check_prerequisites(analysis)
    return [p for p in checked if not p.satisfied and p.required]
```

---

### Component 5: Built-in Renderers

**Sunwell provides built-in preview for creative formats:**

| Format | Renderer | Notes |
|---|---|---|
| Markdown prose | Built-in | Formatted reader with typography |
| Fountain screenplay | Built-in | Industry-standard formatting |
| Yarn dialogue | Built-in | Interactive tree player |
| ink narrative | Built-in | Playable story |
| Jupyter notebook | Jupyter (external) | Opens in browser |

**For code projects**, we start the dev server and embed WebView.

**For prose/screenplay**, we render directly in Sunwell (no external dependencies).

```rust
// studio/src-tauri/src/preview.rs (existing, to be extended)

pub enum ViewType {
    WebView,      // Embedded browser (web apps)
    Terminal,     // Pre-filled terminal (CLI tools)
    Prose,        // Formatted reader (novels, articles)  ← Add renderer
    Fountain,     // Screenplay viewer                    ← Add renderer
    Dialogue,     // Interactive dialogue player          ← Add renderer
    Generic,      // Generic file viewer
}
```

---

## Implementation Plan

### Phase 1: Type Extensions (Week 1)

1. **Add `PreviewType` enum** to `intent_types.py`
2. **Extend `ProjectAnalysis`** with `preview_type`, `preview_url`, `preview_file`
3. **Extend `Prerequisite`** with `satisfied`, `required` fields
4. **Add `_detect_preview_type()`** function to `intent_analyzer.py`
5. **Update `analyze_project()`** to populate preview fields

**Deliverable**: `analyze_project()` returns preview info for all project types.

### Phase 2: Built-in Renderers (Week 2)

1. **Prose renderer** — Markdown to formatted view with typography
2. **Fountain renderer** — Screenplay to industry-formatted view
3. **Dialogue renderer** — Yarn/ink to interactive player

**Deliverable**: `PreviewType.PROSE`, `SCREENPLAY`, `DIALOGUE` can render without external tools.

### Phase 3: Studio Integration (Week 3)

1. **Sync Rust types** — Update `ViewType` in `preview.rs` to match `PreviewType`
2. **Update "Try It" flow** — Route to correct preview based on `analysis.preview_type`
3. **Prerequisites UI** — Show missing prerequisites and offer to install

**Deliverable**: End-to-end "Try It" works for any project type.

---

## UI Flow

### "Try It" Button Click

```
┌──────────────────────────────────────────────────────────────┐
│  🎬 Try It: Screenplay                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Detected: Fountain screenplay                               │
│  Confidence: 90%                                             │
│                                                              │
│  ✅ Ready to preview!                                        │
│  No external dependencies needed.                            │
│                                                              │
│  [▶ Open Preview]                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────────────────────────────────────┐
│  🌐 Try It: Flask App                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Detected: Flask web application                             │
│  Confidence: 95%                                             │
│                                                              │
│  Prerequisites:                                              │
│  ✅ Python 3.11+ installed                                   │
│  ❌ Flask not found                                          │
│     → pip install flask                                      │
│                                                              │
│  [Install & Run] [Run Anyway] [Cancel]                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Preview Views

**Web App** → Embedded WebView showing localhost:5000

**Screenplay** → Formatted screenplay with:
- Character names centered/caps
- Dialogue indented
- Scene headings bold
- Page breaks (90-120 page target)

**Novel** → Formatted prose reader with:
- Book typography (proper fonts)
- Chapter navigation
- Word count display
- Progress tracking

**Dialogue** → Interactive player with:
- Current node display
- Choice buttons
- Variable state panel
- Branching path visualization

---

## Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| **Coverage** | "Try It" works for ANY project type | Test matrix: Flask, React, Novel, Screenplay, Dialogue, CLI |
| **Detection accuracy** | ≥90% correct preview type | Measure against test corpus of 50 projects |
| **Prerequisites UX** | User knows what to install | Prerequisites shown before failed run |
| **Built-in previews** | No external tools for creative | Prose/screenplay/dialogue render in Sunwell |
| **Performance** | Heuristics <100ms, AI <2s | Instrumented timing in `analyze_project()` |
| **Cost** | <$0.001/analysis with AI | Track token usage in telemetry |

### Validation Plan

**Phase 1 exit criteria**:
- [ ] `analyze_project()` returns valid `preview_type` for all `ProjectType` values
- [ ] Unit tests cover heuristic detection paths
- [ ] AI fallback works when heuristics return low confidence

**Phase 2 exit criteria**:
- [ ] Prose renderer displays Markdown with proper typography
- [ ] Fountain renderer formats screenplay with character/dialogue styling
- [ ] Dialogue renderer plays through basic Yarn/ink scripts

**Phase 3 exit criteria**:
- [ ] "Try It" button routes to correct preview type
- [ ] Prerequisites modal shows missing dependencies
- [ ] End-to-end test: Flask, Novel, Screenplay projects all preview correctly

---

## Cost Analysis

**Per preview analysis (when AI needed):**

| Step | Tokens | Cost (Haiku) | Cost (Flash) |
|---|---|---|---|
| Context gathering | ~500 input | $0.000125 | $0.0000375 |
| Analysis | ~300 output | $0.000375 | $0.0001125 |
| Validation | ~100 round-trip | $0.000075 | $0.0000225 |
| **Total** | | **~$0.0006** | **~$0.0002** |

**At scale (estimated):**
- 1,000 projects/day = $0.60/day (Haiku) or $0.20/day (Flash)
- If heuristics handle ~75% → ~250 AI calls/day = **~$0.15/day**

**Conclusion**: Cost is negligible. No reason to skimp on AI fallback.

---

## Open Questions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Render fidelity**: How accurate should Fountain rendering be? | "Good enough" for MVP | Industry-perfect requires significant investment. Start with readable formatting, iterate based on user feedback. |
| **Dialogue complexity**: Support branching variables? Conditions? | Basic playthrough for MVP | Full variable/condition support is complex. Start with linear playthrough + choice selection, add variables in v2. |
| **Novel navigation**: Chapter list? Table of contents? Search? | Chapter list + word count | Essential for navigation. TOC and search are nice-to-have for v2. |

---

## Future: Quality Gates

This RFC focuses on **preview** — "can I see it working?"

A future RFC should address **quality gates** — "is it good?"

| Gate Type | What It Checks | Applies To |
|---|---|---|
| Word count | Chapter within target range | Prose |
| Readability | Flesch-Kincaid grade level | Prose, Docs |
| Grammar | Spelling, punctuation, style | All text |
| POV consistency | No head-hopping | Fiction |
| Timeline | No anachronisms | Fiction |
| Fountain format | Valid screenplay syntax | Screenplay |
| Page count | 90-120 pages | Screenplay |
| Branch coverage | All paths reachable | Dialogue |

These gates would run in the DAG at artifact completion, similar to how code gates run today.

---

## References

**Extends**:
- RFC-079: Project Intent Analyzer — adds preview capability to `ProjectAnalysis`

**Related**:
- RFC-066: Intelligent Run Button — original "Try It" concept (superseded for scope)
- RFC-042: Validation Gates — code quality gates (future: creative quality gates)
- rfc-backlog-driven-execution: DAG execution flow

**Source files**:
- `src/sunwell/project/intent_analyzer.py` — main analyzer, lines 95-98 show code-only limitation
- `src/sunwell/project/intent_types.py` — `ProjectAnalysis`, `DevCommand`, `Prerequisite` types
- `src/sunwell/project/signals.py` — `has_prose`, `has_fountain` signals (lines 65-66, 178-179)
- `studio/src-tauri/src/preview.rs` — Rust `ViewType` enum to sync
