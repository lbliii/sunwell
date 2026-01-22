# RFC: Universal Project Readiness & Preview

**Status**: Draft  
**Created**: 2026-01-22  
**Author**: AI Assistant  
**Related**: RFC-079 (Project Intent Analyzer), RFC-066 (Intelligent Run Button), rfc-backlog-driven-execution

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

## Design

### The Simple Model

```
┌──────────────────────────────────────────────────────────────────┐
│                     Preview Flow                                  │
│                                                                   │
│   User clicks "Try It"                                           │
│          │                                                        │
│          ▼                                                        │
│   ┌─────────────────┐                                            │
│   │ 1. DETECT       │  "What kind of project is this?"           │
│   │    (AI + rules) │  → Flask app, Screenplay, Novel, etc.      │
│   └────────┬────────┘                                            │
│            │                                                      │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ 2. CHECK        │  "What do I need to run it?"               │
│   │    (prereqs)    │  → Python 3.11, Flask, npm, etc.           │
│   └────────┬────────┘                                            │
│            │                                                      │
│            ▼ (satisfied?)                                         │
│   ┌─────────────────┐                                            │
│   │ 3. RUN          │  "How do I start it?"                      │
│   │    (command)    │  → flask run, npm run dev, etc.            │
│   └────────┬────────┘                                            │
│            │                                                      │
│            ▼                                                      │
│   ┌─────────────────┐                                            │
│   │ 4. PREVIEW      │  "Where do I see it?"                      │
│   │    (view type)  │  → WebView, ProseReader, Terminal, etc.    │
│   └─────────────────┘                                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### Component 1: Universal Preview Analysis

**The type we return for ANY project:**

```python
# src/sunwell/project/preview_analysis.py

from dataclasses import dataclass
from enum import Enum


class PreviewType(Enum):
    """How to preview this project."""
    
    WEB_VIEW = "web_view"      # Embedded browser (web apps)
    TERMINAL = "terminal"      # Pre-filled terminal (CLI tools)
    PROSE = "prose"            # Formatted reader (novels, articles)
    SCREENPLAY = "screenplay"  # Fountain renderer (scripts)
    DIALOGUE = "dialogue"      # Interactive tree (game dialogue)
    NOTEBOOK = "notebook"      # Jupyter-style (data science)
    STATIC = "static"          # Just open the file (images, PDFs)
    NONE = "none"              # No preview (libraries, configs)


@dataclass(frozen=True, slots=True)
class Prerequisite:
    """Something that must be installed/available to preview."""
    
    name: str
    """Human-readable name (e.g., 'Python 3.11+')."""
    
    check_command: str | None
    """Command to check if installed (e.g., 'python3 --version')."""
    
    install_hint: str
    """How to install if missing."""
    
    satisfied: bool = False
    """Whether this prerequisite is currently met."""
    
    required: bool = True
    """If False, preview can work without this (degraded)."""


@dataclass(frozen=True, slots=True)
class PreviewAnalysis:
    """Everything needed to preview ANY project."""
    
    # What is it?
    project_type: str
    """Human-readable type (e.g., 'Flask web app', 'Fountain screenplay')."""
    
    framework: str | None
    """Detected framework if any (e.g., 'Flask', 'React', 'Fountain')."""
    
    # What do I need?
    prerequisites: tuple[Prerequisite, ...]
    """What must be installed to preview."""
    
    # How do I run it?
    run_command: str | None
    """Command to start it (e.g., 'flask run', 'npm run dev')."""
    
    run_cwd: str | None
    """Working directory for run command (relative to project root)."""
    
    # Where do I see it?
    preview_type: PreviewType
    """Type of preview view to use."""
    
    preview_url: str | None
    """URL to open (for web views)."""
    
    preview_file: str | None
    """File to render (for prose/screenplay)."""
    
    # Metadata
    confidence: float
    """How confident we are (0.0-1.0)."""
    
    reasoning: str
    """Why we classified this way."""


# Examples of what this returns:

# Flask app in src/app.py:
PreviewAnalysis(
    project_type="Flask web application",
    framework="Flask",
    prerequisites=(
        Prerequisite("Python 3.8+", "python3 --version", "Install from python.org"),
        Prerequisite("Flask", "python -c 'import flask'", "pip install flask"),
    ),
    run_command="FLASK_APP=src/app.py python -m flask run",
    run_cwd=None,
    preview_type=PreviewType.WEB_VIEW,
    preview_url="http://localhost:5000",
    preview_file=None,
    confidence=0.95,
    reasoning="Found Flask import in src/app.py",
)

# Fountain screenplay:
PreviewAnalysis(
    project_type="Fountain screenplay",
    framework="Fountain",
    prerequisites=(),  # Sunwell has built-in Fountain rendering
    run_command=None,  # No server needed
    run_cwd=None,
    preview_type=PreviewType.SCREENPLAY,
    preview_url=None,
    preview_file="screenplay.fountain",
    confidence=0.90,
    reasoning="Found .fountain file with standard screenplay structure",
)

# Novel/manuscript:
PreviewAnalysis(
    project_type="Novel manuscript",
    framework=None,
    prerequisites=(),  # Sunwell has built-in Markdown rendering
    run_command=None,
    run_cwd=None,
    preview_type=PreviewType.PROSE,
    preview_url=None,
    preview_file="chapters/chapter-01.md",
    confidence=0.85,
    reasoning="Found chapters/ directory with Markdown files",
)

# CLI tool:
PreviewAnalysis(
    project_type="Python CLI tool",
    framework="Click",
    prerequisites=(
        Prerequisite("Python 3.8+", "python3 --version", "Install from python.org"),
    ),
    run_command="python -m myapp --help",
    run_cwd=None,
    preview_type=PreviewType.TERMINAL,
    preview_url=None,
    preview_file=None,
    confidence=0.80,
    reasoning="Found click import and __main__.py",
)
```

---

### Component 2: AI-Powered Detection

**Problem**: Heuristics can't recognize every project type.

**Solution**: Use LLM when heuristics fail or have low confidence.

```python
# src/sunwell/project/preview_analyzer.py

PREVIEW_ANALYSIS_PROMPT = '''Analyze this project and tell me how to preview it.

## Project Info
- Name: {name}
- Files: {file_tree}
- Key file contents: {key_files}

## Question
What does it take to preview this project?

Answer in JSON:
```json
{{
  "project_type": "Flask web app | React app | Fountain screenplay | Novel | CLI tool | ...",
  "framework": "Flask | React | Fountain | null",
  "prerequisites": [
    {{"name": "Python 3.8+", "check_command": "python3 --version", "install_hint": "..."}}
  ],
  "run_command": "flask run | npm run dev | null",
  "run_cwd": "src | null",
  "preview_type": "web_view | terminal | prose | screenplay | dialogue | notebook | static | none",
  "preview_url": "http://localhost:5000 | null",
  "preview_file": "manuscript.md | screenplay.fountain | null",
  "confidence": 0.0-1.0,
  "reasoning": "Why I think this"
}}
```

Be practical. Focus on: What do I run? What do I look at?
'''


async def analyze_for_preview(
    path: Path,
    model: ModelProtocol,
) -> PreviewAnalysis:
    """Analyze any project and figure out how to preview it.
    
    Strategy:
    1. Try heuristic detection first (fast, free)
    2. If low confidence or unknown, use LLM
    3. Return unified PreviewAnalysis
    """
    # Step 1: Try heuristics
    heuristic_result = heuristic_preview_detect(path)
    
    if heuristic_result and heuristic_result.confidence >= 0.8:
        return heuristic_result
    
    # Step 2: Use AI for unknown/low-confidence cases
    context = gather_preview_context(path)
    
    prompt = PREVIEW_ANALYSIS_PROMPT.format(
        name=path.name,
        file_tree=context["file_tree"],
        key_files=context["key_files"],
    )
    
    response = await model.generate(prompt, max_tokens=500)
    data = _extract_json(response.content)
    
    # Step 3: Build PreviewAnalysis from AI response
    prerequisites = tuple(
        Prerequisite(
            name=p["name"],
            check_command=p.get("check_command"),
            install_hint=p.get("install_hint", ""),
        )
        for p in data.get("prerequisites", [])
    )
    
    return PreviewAnalysis(
        project_type=data["project_type"],
        framework=data.get("framework"),
        prerequisites=prerequisites,
        run_command=data.get("run_command"),
        run_cwd=data.get("run_cwd"),
        preview_type=PreviewType(data["preview_type"]),
        preview_url=data.get("preview_url"),
        preview_file=data.get("preview_file"),
        confidence=data.get("confidence", 0.7),
        reasoning=data.get("reasoning", "AI analysis"),
    )
```

**Why AI matters**: Heuristics can recognize Flask, React, Django. But what about:
- A Ren'Py visual novel
- A Twine interactive fiction project
- A Hugo static site
- A LaTeX academic paper
- A Godot game project

The LLM can figure these out because it understands context, not just file patterns.

---

### Component 3: Universal Gate Registry

**Problem**: Gates only validate code.

**Solution**: YAML-based gate registry for all project types.

```yaml
# gates/registry.yaml

# =============================================================================
# Code Gates (existing, referenced for completeness)
# =============================================================================

syntax:
  id: syntax
  category: static
  description: "Can the code parse?"
  applies_to: [web_app, cli_tool, library, api_service]
  check:
    method: command
    value: "python -m py_compile {file}"
  auto_fix: false

lint:
  id: lint
  category: static
  description: "Does it pass linting?"
  applies_to: [web_app, cli_tool, library, api_service]
  check:
    method: command
    value: "ruff check {file}"
  auto_fix: true
  fix_command: "ruff check --fix {file}"

type_check:
  id: type_check
  category: static
  description: "Does it pass type checking?"
  applies_to: [web_app, cli_tool, library, api_service]
  check:
    method: command
    value: "ty check {file}"
  auto_fix: false

import_check:
  id: import_check
  category: runtime
  description: "Can we import it?"
  applies_to: [web_app, cli_tool, library, api_service]
  check:
    method: python
    value: "import {module}"
  auto_fix: false

# =============================================================================
# Creative Writing Gates
# =============================================================================

word_count:
  id: word_count
  category: progress
  description: "Does the content meet word count targets?"
  applies_to: [novel, short_story, web_serial]
  check:
    method: script
    value: "scripts/gates/word_count.py"
  parameters:
    novel_chapter_min: 2000
    novel_chapter_max: 8000
    novel_total_min: 50000
    novel_total_max: 120000
    short_story_min: 1000
    short_story_max: 7500
    web_serial_chapter_min: 1500
    web_serial_chapter_max: 5000
  auto_fix: false
  message_template: "Chapter has {actual} words (target: {min}-{max})"

readability:
  id: readability
  category: quality
  description: "Is the prose readable?"
  applies_to: [novel, short_story, web_serial, technical_docs]
  check:
    method: script
    value: "scripts/gates/readability.py"
  parameters:
    # Flesch-Kincaid Grade Level targets by genre
    novel_target: 6-10
    technical_target: 10-14
    children_target: 3-6
  auto_fix: false
  llm_assist: true  # Can suggest rewrites for difficult passages

grammar:
  id: grammar
  category: quality
  description: "Are there grammar issues?"
  applies_to: [novel, short_story, web_serial, screenplay, technical_docs]
  check:
    method: script
    value: "scripts/gates/grammar.py"
  auto_fix: true  # Can auto-fix simple issues
  llm_assist: true  # Complex issues get LLM suggestions

pov_consistency:
  id: pov_consistency
  category: consistency
  description: "Is the point of view consistent?"
  applies_to: [novel, short_story, web_serial]
  check:
    method: llm
    prompt: |
      Analyze this chapter for POV consistency.
      
      Expected POV: {expected_pov}
      Content: {content}
      
      Check for:
      1. POV head-hopping (switching whose thoughts we see)
      2. Tense consistency
      3. Pronoun consistency
      
      Report any violations.
  auto_fix: false
  llm_required: true

character_voice:
  id: character_voice
  category: consistency
  description: "Are character voices distinct and consistent?"
  applies_to: [novel, short_story, web_serial, screenplay, game_dialogue]
  check:
    method: llm
    prompt: |
      Analyze dialogue for character voice consistency.
      
      Characters: {character_profiles}
      Content: {content}
      
      Check:
      1. Does each character sound distinct?
      2. Are speech patterns consistent with their profile?
      3. Does dialogue match their education/background?
      
      Report inconsistencies.
  auto_fix: false
  llm_required: true

timeline_integrity:
  id: timeline_integrity
  category: consistency
  description: "Do events happen in a consistent timeline?"
  applies_to: [novel, short_story, web_serial, screenplay]
  check:
    method: llm
    prompt: |
      Check timeline consistency.
      
      Previous events: {timeline_context}
      Current content: {content}
      
      Look for:
      1. Anachronisms
      2. Impossible timing (character in two places)
      3. Forgotten injuries/conditions
      4. Season/weather inconsistencies
      
      Report any timeline issues.
  auto_fix: false
  llm_required: true

# =============================================================================
# Screenplay Gates
# =============================================================================

fountain_format:
  id: fountain_format
  category: format
  description: "Is the screenplay in valid Fountain format?"
  applies_to: [screenplay]
  check:
    method: script
    value: "scripts/gates/fountain_validate.py"
  auto_fix: true  # Can fix common formatting issues

page_count:
  id: page_count
  category: progress
  description: "Is the screenplay within industry page limits?"
  applies_to: [screenplay]
  check:
    method: script
    value: "scripts/gates/screenplay_pages.py"
  parameters:
    feature_min: 90
    feature_max: 120
    short_max: 40
    pilot_target: 30-60
  auto_fix: false
  message_template: "Screenplay is {actual} pages (target: {min}-{max})"

scene_numbering:
  id: scene_numbering
  category: format
  description: "Are scenes properly numbered (for production drafts)?"
  applies_to: [screenplay]
  check:
    method: script
    value: "scripts/gates/scene_numbers.py"
  auto_fix: true
  context: "Only required for production drafts, not spec scripts"

dialogue_balance:
  id: dialogue_balance
  category: quality
  description: "Is dialogue reasonably balanced between characters?"
  applies_to: [screenplay, stage_play]
  check:
    method: script
    value: "scripts/gates/dialogue_balance.py"
  parameters:
    max_monologue_lines: 10  # Flag monologues over 10 lines
    protagonist_dialogue_max_percent: 40  # Protagonist shouldn't dominate
  auto_fix: false
  message_template: "{character} has {percent}% of dialogue"

# =============================================================================
# Web Serial Gates
# =============================================================================

chapter_hook:
  id: chapter_hook
  category: quality
  description: "Does the chapter have a compelling hook?"
  applies_to: [web_serial]
  check:
    method: llm
    prompt: |
      Evaluate the opening hook of this chapter.
      
      First 500 words: {opening}
      
      Rate 1-10 on:
      1. Immediate engagement (does it grab attention?)
      2. Promise of conflict/mystery
      3. Character voice establishment
      
      Web serial readers decide quickly. Is this hook strong enough?
  auto_fix: false
  llm_required: true

cliffhanger:
  id: cliffhanger
  category: quality
  description: "Does the chapter end with forward momentum?"
  applies_to: [web_serial]
  check:
    method: llm
    prompt: |
      Evaluate the chapter ending.
      
      Last 500 words: {ending}
      
      Check for:
      1. Unresolved tension
      2. Promise of what's next
      3. Emotional resonance
      
      Web serials need readers to click "next chapter". Is this ending compelling?
  auto_fix: false
  llm_required: true

posting_schedule:
  id: posting_schedule
  category: progress
  description: "Are you on track for your posting schedule?"
  applies_to: [web_serial]
  check:
    method: script
    value: "scripts/gates/posting_schedule.py"
  parameters:
    schedule: "config.posting_schedule"  # User-defined
  auto_fix: false
  message_template: "Next post due in {days} days, {chapters_ready} chapters ready"

# =============================================================================
# Game Writing Gates
# =============================================================================

branching_coverage:
  id: branching_coverage
  category: quality
  description: "Do all dialogue branches lead somewhere?"
  applies_to: [game_dialogue, interactive_fiction]
  check:
    method: script
    value: "scripts/gates/branching_coverage.py"
  auto_fix: false
  message_template: "{orphan_count} orphan nodes, {dead_end_count} dead ends"

variable_consistency:
  id: variable_consistency
  category: consistency
  description: "Are dialogue variables used consistently?"
  applies_to: [game_dialogue, interactive_fiction]
  check:
    method: script
    value: "scripts/gates/yarn_variables.py"
  auto_fix: false

localization_ready:
  id: localization_ready
  category: quality
  description: "Is dialogue ready for localization?"
  applies_to: [game_dialogue]
  check:
    method: llm
    prompt: |
      Check dialogue for localization issues.
      
      Content: {content}
      
      Flag:
      1. Idioms that don't translate
      2. Culture-specific references
      3. Puns or wordplay
      4. Hardcoded text lengths
      
      These need localization notes.
  auto_fix: false
  llm_required: true
```

---

### Component 4: Readiness Check Flow

```python
# src/sunwell/project/readiness.py

from dataclasses import dataclass
from pathlib import Path

from sunwell.project.anticipation import anticipate_project_needs, AnticipatedNeeds
from sunwell.project.prerequisites import load_prerequisites, check_prerequisite
from sunwell.project.gates import load_gates


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Result of checking project readiness."""
    
    genre: str
    """Detected/anticipated genre."""
    
    ready: bool
    """Whether all required prerequisites are met."""
    
    prerequisites_met: tuple[str, ...]
    """IDs of met prerequisites."""
    
    prerequisites_missing: tuple[str, ...]
    """IDs of missing prerequisites."""
    
    prerequisites_optional: tuple[str, ...]
    """IDs of optional prerequisites that could help."""
    
    suggested_tools: tuple[str, ...]
    """Tool suggestions based on genre."""
    
    available_gates: tuple[str, ...]
    """Gate types that will be available for this project."""
    
    setup_commands: tuple[str, ...]
    """Commands to run to satisfy missing prerequisites."""


async def check_project_readiness(
    path: Path,
    model: ModelProtocol,
    user_description: str | None = None,
) -> ReadinessResult:
    """Check if a project has everything it needs to succeed.
    
    This is the main entry point for project readiness.
    
    1. Uses AI to anticipate what the project will need
    2. Checks each prerequisite
    3. Reports what's ready and what's missing
    4. Suggests setup steps
    
    Args:
        path: Project root path.
        model: LLM for anticipation.
        user_description: Optional user description of what they're making.
    
    Returns:
        ReadinessResult with detailed readiness status.
    """
    # Step 1: Anticipate needs
    needs = await anticipate_project_needs(path, model, user_description)
    
    # Step 2: Load prerequisite definitions
    all_prerequisites = load_prerequisites()
    
    # Step 3: Check each relevant prerequisite
    met: list[str] = []
    missing: list[str] = []
    optional: list[str] = []
    setup_commands: list[str] = []
    
    for prereq_id in needs.prerequisites:
        prereq = all_prerequisites.get(prereq_id)
        if not prereq:
            continue
        
        result = await check_prerequisite(prereq, path)
        
        if result.satisfied:
            met.append(prereq_id)
        elif prereq.required:
            missing.append(prereq_id)
            if prereq.install.method == "command":
                setup_commands.append(prereq.install.value)
        else:
            optional.append(prereq_id)
    
    # Step 4: Determine available gates
    all_gates = load_gates()
    available_gates = [
        gate_id
        for gate_id, gate in all_gates.items()
        if needs.genre.value in gate.applies_to
    ]
    
    return ReadinessResult(
        genre=needs.genre.value,
        ready=len(missing) == 0,
        prerequisites_met=tuple(met),
        prerequisites_missing=tuple(missing),
        prerequisites_optional=tuple(optional),
        suggested_tools=needs.suggested_tools,
        available_gates=tuple(available_gates),
        setup_commands=tuple(setup_commands),
    )
```

---

### Component 5: Gate Execution for All Types

```python
# src/sunwell/project/universal_gates.py

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateCategory(Enum):
    """Categories of gates."""
    
    STATIC = "static"       # No execution needed (linting, format checking)
    RUNTIME = "runtime"     # Requires execution (imports, tests)
    PROGRESS = "progress"   # Milestone checking (word count, page count)
    QUALITY = "quality"     # Quality metrics (readability, grammar)
    CONSISTENCY = "consistency"  # Internal consistency (POV, timeline)
    FORMAT = "format"       # Format validation (Fountain, Markdown)


@dataclass(frozen=True, slots=True)
class UniversalGateResult:
    """Result of running a universal gate."""
    
    gate_id: str
    """Gate that was run."""
    
    passed: bool
    """Whether the gate passed."""
    
    score: float | None
    """Optional score (0.0-1.0) for quality gates."""
    
    message: str
    """Human-readable result message."""
    
    details: dict[str, Any]
    """Detailed results (varies by gate type)."""
    
    auto_fixed: bool
    """Whether issues were auto-fixed."""
    
    suggestions: tuple[str, ...]
    """Suggestions for improvement."""


class UniversalGateRunner:
    """Runs gates for any project type."""
    
    def __init__(
        self,
        project_path: Path,
        model: ModelProtocol | None = None,
    ):
        self.project_path = project_path
        self.model = model
        self.gate_registry = load_gates()
    
    async def run_gate(
        self,
        gate_id: str,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> UniversalGateResult:
        """Run a single gate.
        
        Args:
            gate_id: ID of gate from registry.
            content: Content to check.
            context: Additional context (character profiles, timeline, etc.)
        
        Returns:
            UniversalGateResult with pass/fail and details.
        """
        gate = self.gate_registry.get(gate_id)
        if not gate:
            raise ValueError(f"Unknown gate: {gate_id}")
        
        match gate.check.method:
            case "command":
                return await self._run_command_gate(gate, content)
            case "script":
                return await self._run_script_gate(gate, content, context)
            case "llm":
                return await self._run_llm_gate(gate, content, context)
            case "python":
                return await self._run_python_gate(gate, content)
            case _:
                raise ValueError(f"Unknown check method: {gate.check.method}")
    
    async def run_gates_for_artifact(
        self,
        artifact_type: str,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> list[UniversalGateResult]:
        """Run all appropriate gates for an artifact.
        
        Automatically selects gates based on artifact type.
        
        Args:
            artifact_type: Type of artifact (chapter, screenplay, module, etc.)
            content: Content to check.
            context: Additional context.
        
        Returns:
            List of gate results.
        """
        # Map artifact types to gate sets
        gate_sets = {
            "chapter": ["word_count", "readability", "grammar", "pov_consistency"],
            "screenplay": ["fountain_format", "page_count", "dialogue_balance"],
            "dialogue": ["branching_coverage", "variable_consistency", "character_voice"],
            "module": ["syntax", "lint", "type_check", "import_check"],
        }
        
        gates_to_run = gate_sets.get(artifact_type, [])
        results = []
        
        for gate_id in gates_to_run:
            try:
                result = await self.run_gate(gate_id, content, context)
                results.append(result)
            except Exception as e:
                results.append(UniversalGateResult(
                    gate_id=gate_id,
                    passed=False,
                    score=None,
                    message=f"Gate error: {e}",
                    details={},
                    auto_fixed=False,
                    suggestions=(),
                ))
        
        return results
```

---

### Component 6: Integration with DAG Execution

Update the backlog-driven execution to use universal gates:

```python
# In ExecutionManager (from rfc-backlog-driven-execution)

async def _execute_goal(self, goal: BacklogGoal) -> GoalResult:
    """Execute a goal with universal gate checking."""
    
    # Plan the goal
    plan = await self._planner.plan(goal, self._context)
    
    # Execute artifacts with gates
    results: list[ArtifactResult] = []
    
    for artifact in plan.artifacts:
        # Create the artifact
        content = await self._create_artifact(artifact)
        
        # Run universal gates for this artifact type
        gate_results = await self._gate_runner.run_gates_for_artifact(
            artifact_type=artifact.type,  # "chapter", "module", "screenplay", etc.
            content=content,
            context=self._get_gate_context(artifact),
        )
        
        # Check if gates passed
        all_passed = all(g.passed for g in gate_results)
        
        if not all_passed:
            # Attempt fix if available
            fixed = await self._attempt_fix(artifact, content, gate_results)
            if not fixed:
                # Emit gate failure event
                await self._emit(EventType.GATE_FAIL, {
                    "artifact_id": artifact.id,
                    "failed_gates": [g.gate_id for g in gate_results if not g.passed],
                })
        
        results.append(ArtifactResult(
            artifact_id=artifact.id,
            content=content,
            gate_results=gate_results,
            passed=all_passed,
        ))
    
    return GoalResult(
        goal_id=goal.id,
        artifacts=results,
        success=all(r.passed for r in results),
    )
```

---

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. Create `AnticipatedNeeds` and anticipation prompt
2. Create YAML schema for prerequisites and gates
3. Implement `load_prerequisites()` and `load_gates()`
4. Implement `check_project_readiness()`

### Phase 2: Creative Writing Gates (Week 2)
1. Implement word count gate script
2. Implement readability gate script
3. Implement grammar gate (integrate with LanguageTool or LLM)
4. Implement LLM-based consistency gates

### Phase 3: Screenplay & Game Writing (Week 3)
1. Implement Fountain validation script
2. Implement dialogue balance script
3. Implement branching coverage script
4. Integrate Yarn/ink format support

### Phase 4: Integration (Week 4)
1. Update `ExecutionManager` to use universal gates
2. Add readiness check to project open flow
3. Add gate results to DAG UI
4. Add prerequisite installation wizard to Studio

---

## UI Integration

### Readiness Panel (on project open)

```
┌────────────────────────────────────────────────────────────┐
│ 📋 Project Readiness: Web Serial                           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ ✅ Ready to create!                                        │
│                                                            │
│ Prerequisites:                                             │
│ ✅ Word processor available                                │
│ ✅ Grammar tool available                                  │
│ ⚠️ Platform account (optional)                            │
│    → Create Royal Road account for publishing              │
│ ⚠️ Cover art (optional)                                   │
│    → Commission or create cover for better visibility      │
│                                                            │
│ Quality Gates Available:                                   │
│ • Word count targets (1,500-5,000/chapter)                │
│ • Readability scoring                                     │
│ • Grammar checking                                         │
│ • Chapter hook analysis                                   │
│ • Cliffhanger evaluation                                  │
│                                                            │
│ [Start Creating] [Configure Gates] [Skip]                  │
└────────────────────────────────────────────────────────────┘
```

### Gate Results in DAG

```
┌─────────────────────────────────────────────────────────────┐
│ Chapter 3: The Awakening                                    │
├─────────────────────────────────────────────────────────────┤
│ Status: ✅ Complete                                         │
│                                                             │
│ Gate Results:                                               │
│ ✅ Word count: 3,247 words (target: 1,500-5,000)           │
│ ✅ Readability: Grade 7.2 (target: 6-10)                   │
│ ⚠️ Grammar: 3 issues found                                 │
│    → Line 45: "Their" should be "There"                    │
│    → Line 89: Run-on sentence                              │
│    → Line 156: Passive voice (consider rewriting)          │
│ ✅ POV consistency: First person maintained                │
│ ✅ Chapter hook: 8/10 - Strong opening                     │
│ ⚠️ Cliffhanger: 6/10 - Could be stronger                  │
│    → Consider ending on the revelation, not after          │
│                                                             │
│ [Fix Grammar] [View Details] [Mark Complete]                │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Criteria

1. **Any project type gets readiness check** — Novelist gets software suggestions, screenwriter gets format validation
2. **Gates run at DAG milestones** — Chapter complete? Run word count + readability + grammar
3. **AI anticipates needs** — "You're writing LitRPG? You'll need stat blocks and a progression system"
4. **Easy to extend** — Adding new project type = YAML entry, not code changes
5. **Never blocks** — All gates are advisory, user can always bypass

---

## Open Questions

1. **Gate ordering**: Should gates run in a specific order? (Fast static checks first, slow LLM checks last?)
2. **Cross-chapter gates**: Some consistency checks need to span multiple chapters (timeline, character arcs). How to handle?
3. **User customization**: How much should users be able to customize gate thresholds? (Some authors write 10k chapters)
4. **Cost management**: LLM gates cost tokens. Run on every save? Only on "check" command? Only before publishing?

---

## References

- RFC-079: Project Intent Analyzer
- RFC-042: Validation Gates (original code gates)
- RFC-066: Intelligent Run Button
- rfc-backlog-driven-execution: DAG execution flow
- TECHNICAL-VISION.md: Workflow quality gates section
