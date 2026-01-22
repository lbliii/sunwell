"""Project Intent Analyzer (RFC-079).

Universal project analysis to understand what any project IS and what should happen next.
Replaces the narrow "Run Project = start dev server" model with comprehensive project understanding.
"""

import json
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

from sunwell.models.protocol import ModelProtocol
from sunwell.project.cache import (
    load_cached_analysis,
    save_analysis_cache,
)
from sunwell.project.inference import (
    classify_with_llm,
    infer_goals_from_context,
)
from sunwell.project.intent_types import (
    WORKSPACE_PRIMARIES,
    DevCommand,
    InferredGoal,
    PipelineStep,
    Prerequisite,
    ProjectAnalysis,
    ProjectType,
    SuggestedAction,
)
from sunwell.project.monorepo import SubProject, detect_sub_projects, is_monorepo
from sunwell.project.signals import ProjectSignals, gather_project_signals


async def analyze_project(
    path: Path,
    model: ModelProtocol,
    *,
    force_refresh: bool = False,
) -> ProjectAnalysis:
    """Analyze any project to understand its intent and state.

    This is the main entry point for RFC-079. It:
    1. Gathers filesystem signals
    2. Classifies project type (heuristic or LLM)
    3. Loads/infers goals
    4. Builds pipeline
    5. Suggests next action
    6. Selects appropriate workspace

    Args:
        path: Project root path.
        model: LLM model for semantic analysis.
        force_refresh: Skip cache and force re-analysis.

    Returns:
        ProjectAnalysis with full project understanding.
    """
    # Check cache first (unless forced)
    if not force_refresh:
        cached = load_cached_analysis(path)
        if cached:
            return cached

    # 1. Gather signals
    signals = gather_project_signals(path)

    # 2. Classify project type
    (
        project_type,
        subtype,
        classification_source,
        classification_confidence,
    ) = await _classify_project(signals, model)

    # 3. Load or infer goals
    goals = await _load_or_infer_goals(signals, project_type, model, subtype)

    # 4. Build pipeline from goals
    pipeline = _build_pipeline(goals, project_type)

    # 5. Determine current state
    current_step = _detect_current_step(pipeline)
    completion = _calculate_completion(pipeline)

    # 6. Generate suggested action
    suggested = _suggest_next_action(pipeline, current_step, project_type, signals)

    # 7. Select appropriate workspace primary
    workspace_primary = _select_workspace_primary(project_type, subtype, bool(pipeline))

    # 8. Detect dev command (code projects only)
    dev_command = None
    if project_type == ProjectType.CODE:
        dev_command = _detect_dev_command(signals)

    # 9. Calculate confidence
    confidence = _calculate_confidence(signals, classification_source, classification_confidence)
    confidence_level = (
        "high" if confidence >= 0.85 else "medium" if confidence >= 0.65 else "low"
    )

    analysis = ProjectAnalysis(
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
        classification_source=classification_source,
    )

    # Cache the result
    save_analysis_cache(analysis)

    return analysis


async def load_or_analyze(
    path: Path,
    model: ModelProtocol,
) -> ProjectAnalysis:
    """Load cached analysis or perform fresh analysis.

    Convenience function that always returns an analysis,
    using cache when valid.

    Args:
        path: Project root path.
        model: LLM model for analysis.

    Returns:
        ProjectAnalysis (cached or fresh).
    """
    return await analyze_project(path, model, force_refresh=False)


# =============================================================================
# Project Classification
# =============================================================================


async def _classify_project(
    signals: ProjectSignals,
    model: ModelProtocol,
) -> tuple[ProjectType, str | None, str, float]:
    """Classify project type from signals.

    Uses heuristics first, falls back to LLM for ambiguous cases.

    Returns:
        (project_type, subtype, classification_source, confidence)
    """
    scores: dict[ProjectType, int] = {
        ProjectType.CODE: 0,
        ProjectType.DOCUMENTATION: 0,
        ProjectType.DATA: 0,
        ProjectType.PLANNING: 0,
        ProjectType.CREATIVE: 0,
    }

    # Code signals (weight rationale: manifest files are explicit declarations)
    if signals.has_package_json:
        scores[ProjectType.CODE] += 3
    if signals.has_pyproject or signals.has_cargo or signals.has_go_mod:
        scores[ProjectType.CODE] += 3
    if signals.has_src_dir:
        scores[ProjectType.CODE] += 2

    # Documentation signals
    if signals.has_docs_dir and signals.markdown_count > 5:
        scores[ProjectType.DOCUMENTATION] += 3
    if signals.has_sphinx_conf or signals.has_mkdocs:
        scores[ProjectType.DOCUMENTATION] += 4

    # Data signals
    if signals.has_notebooks:
        scores[ProjectType.DATA] += 4
    if signals.has_data_dir and signals.has_csv_files:
        scores[ProjectType.DATA] += 2

    # Planning signals
    if signals.has_backlog:
        scores[ProjectType.PLANNING] += 2
    if signals.has_rfc_dir:
        scores[ProjectType.PLANNING] += 2

    # Creative signals
    if signals.has_prose or signals.has_fountain:
        scores[ProjectType.CREATIVE] += 4

    # If unclear or mixed, try LLM for semantic analysis
    max_score = max(scores.values())
    if max_score < 3 or list(scores.values()).count(max_score) > 1:
        try:
            project_type, subtype, confidence = await classify_with_llm(signals, model)
            return project_type, subtype, "llm", confidence
        except Exception:
            # LLM failed (model unavailable, etc.) - fall back to best heuristic guess
            pass

    # Use heuristic classification
    primary_type = max(scores, key=lambda k: scores[k])
    subtype = _detect_subtype(primary_type, signals)

    # Calculate heuristic confidence based on score
    confidence = min(0.95, 0.6 + (max_score * 0.1))

    return primary_type, subtype, "heuristic", confidence


def _detect_subtype(project_type: ProjectType, signals: ProjectSignals) -> str | None:
    """Detect specific framework/tooling within project type."""
    if project_type == ProjectType.CODE:
        if signals.has_package_json:
            pkg = _read_package_json(signals.path)
            if pkg:
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "svelte" in deps:
                    return "svelte-app"
                if "@sveltejs/kit" in deps:
                    return "sveltekit-app"
                if "react" in deps:
                    return "react-app"
                if "vue" in deps:
                    return "vue-app"
                if "next" in deps:
                    return "next-app"
                if "@tauri-apps/api" in deps:
                    return "tauri-app"
                if "express" in deps:
                    return "express-api"
                if "fastify" in deps:
                    return "fastify-api"

        if signals.has_pyproject:
            pyproject = _read_pyproject(signals.path)
            if pyproject:
                deps = pyproject.get("project", {}).get("dependencies", [])
                deps_str = " ".join(str(d) for d in deps)

                if "fastapi" in deps_str:
                    return "fastapi-api"
                if "django" in deps_str:
                    return "django-app"
                if "flask" in deps_str:
                    return "flask-app"
                if "streamlit" in deps_str:
                    return "streamlit-app"

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


def _read_package_json(path: Path) -> dict | None:
    """Read package.json safely."""
    try:
        return json.loads((path / "package.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_pyproject(path: Path) -> dict | None:
    """Read pyproject.toml safely."""
    try:
        return tomllib.loads((path / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError:
        return None


# =============================================================================
# Goal Loading/Inference
# =============================================================================


async def _load_or_infer_goals(
    signals: ProjectSignals,
    project_type: ProjectType,
    model: ModelProtocol,
    subtype: str | None,
) -> tuple[InferredGoal, ...]:
    """Load backlog goals or infer from context."""
    # Try to load from backlog
    backlog_goals = _load_backlog_goals(signals.path)
    if backlog_goals:
        return backlog_goals

    # Try to infer goals from context using LLM
    try:
        return await infer_goals_from_context(signals, project_type, model, subtype)
    except Exception:
        # LLM failed - return a single generic goal
        return (
            InferredGoal(
                id="current",
                title="Untitled",
                description="",
                priority="medium",
                status="confirmed",
                confidence=1.0,
            ),
        )


def _load_backlog_goals(path: Path) -> tuple[InferredGoal, ...] | None:
    """Load goals from .sunwell/backlog if exists."""
    backlog_dir = path / ".sunwell" / "backlog"
    if not backlog_dir.exists():
        backlog_dir = path / ".sunwell" / "goals"
        if not backlog_dir.exists():
            return None

    goals: list[InferredGoal] = []

    try:
        for goal_file in backlog_dir.glob("*.json"):
            data = json.loads(goal_file.read_text(encoding="utf-8"))
            goals.append(
                InferredGoal(
                    id=data.get("id", goal_file.stem),
                    title=data.get("title", "Untitled"),
                    description=data.get("description", ""),
                    priority=data.get("priority", "medium"),
                    status="confirmed",  # Backlog goals are user-confirmed
                    confidence=1.0,
                )
            )
    except (json.JSONDecodeError, OSError):
        pass

    return tuple(goals) if goals else None


# =============================================================================
# Pipeline Building
# =============================================================================


def _build_pipeline(
    goals: tuple[InferredGoal, ...],
    project_type: ProjectType,
) -> tuple[PipelineStep, ...]:
    """Build execution pipeline from goals."""
    if not goals:
        return ()

    steps: list[PipelineStep] = []
    for i, goal in enumerate(goals):
        # Simple status mapping: first goal is in_progress, rest are pending
        status = "in_progress" if i == 0 else "pending"

        steps.append(
            PipelineStep(
                id=goal.id,
                title=goal.title,
                status=status,
                description=goal.description,
            )
        )

    return tuple(steps)


def _detect_current_step(pipeline: tuple[PipelineStep, ...]) -> str | None:
    """Detect current step in pipeline."""
    for step in pipeline:
        if step.status == "in_progress":
            return step.id
    return None


def _calculate_completion(pipeline: tuple[PipelineStep, ...]) -> float:
    """Calculate pipeline completion percentage."""
    if not pipeline:
        return 0.0

    completed = sum(1 for s in pipeline if s.status == "completed")
    return completed / len(pipeline)


# =============================================================================
# Suggested Action
# =============================================================================


def _suggest_next_action(
    pipeline: tuple[PipelineStep, ...],
    current_step: str | None,
    project_type: ProjectType,
    signals: ProjectSignals,
) -> SuggestedAction | None:
    """Generate suggested next action."""
    # If there's a current step, suggest continuing it
    if current_step:
        for step in pipeline:
            if step.id == current_step:
                return SuggestedAction(
                    action_type="continue_work",
                    description=f"Continue: {step.title}",
                    goal_id=step.id,
                    confidence=0.85,
                )

    # If no current step but pipeline exists, suggest first pending
    for step in pipeline:
        if step.status == "pending":
            return SuggestedAction(
                action_type="execute_goal",
                description=f"Start: {step.title}",
                goal_id=step.id,
                confidence=0.75,
            )

    # For code projects with dev servers, suggest starting server
    if project_type == ProjectType.CODE:
        dev_cmd = _detect_dev_command(signals)
        if dev_cmd:
            return SuggestedAction(
                action_type="start_server",
                description="Start development server",
                command=dev_cmd.command,
                confidence=0.8,
            )

    # Default: suggest adding a goal
    return SuggestedAction(
        action_type="add_goal",
        description="Add a goal to get started",
        confidence=0.6,
    )


# =============================================================================
# Workspace Selection
# =============================================================================


def _select_workspace_primary(
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


# =============================================================================
# Dev Command Detection
# =============================================================================


def _detect_dev_command(signals: ProjectSignals) -> DevCommand | None:
    """Detect dev server command for code projects."""
    if signals.has_package_json:
        pkg = _read_package_json(signals.path)
        if pkg:
            scripts = pkg.get("scripts", {})

            # Priority: dev > start > serve
            for script in ["dev", "start", "serve"]:
                if script in scripts:
                    return DevCommand(
                        command=f"npm run {script}",
                        description=f"Run '{script}' script",
                        prerequisites=(
                            Prerequisite(
                                command="npm install",
                                description="Install dependencies",
                                check_command="test -d node_modules",
                            ),
                        ),
                        expected_url=_infer_dev_url(pkg, scripts.get(script, "")),
                    )

    if signals.has_pyproject:
        pyproject = _read_pyproject(signals.path)
        if pyproject:
            # Check for common Python dev servers
            deps = pyproject.get("project", {}).get("dependencies", [])
            deps_str = " ".join(str(d) for d in deps)

            if "fastapi" in deps_str or "uvicorn" in deps_str:
                return DevCommand(
                    command="uvicorn main:app --reload",
                    description="Start FastAPI with uvicorn",
                    prerequisites=(
                        Prerequisite(
                            command="pip install -e .",
                            description="Install dependencies",
                        ),
                    ),
                    expected_url="http://localhost:8000",
                )

            if "flask" in deps_str:
                return DevCommand(
                    command="flask run --debug",
                    description="Start Flask development server",
                    prerequisites=(
                        Prerequisite(
                            command="pip install -e .",
                            description="Install dependencies",
                        ),
                    ),
                    expected_url="http://localhost:5000",
                )

            if "streamlit" in deps_str:
                return DevCommand(
                    command="streamlit run app.py",
                    description="Start Streamlit app",
                    prerequisites=(
                        Prerequisite(
                            command="pip install -e .",
                            description="Install dependencies",
                        ),
                    ),
                    expected_url="http://localhost:8501",
                )

    if signals.has_cargo:
        return DevCommand(
            command="cargo run",
            description="Build and run Rust project",
            expected_url=None,
        )

    if signals.has_go_mod:
        return DevCommand(
            command="go run .",
            description="Run Go project",
            expected_url=None,
        )

    return None


def _infer_dev_url(pkg: dict, script_content: str) -> str | None:
    """Infer expected dev server URL from package.json."""
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    # Vite default
    if "vite" in deps:
        return "http://localhost:5173"

    # Next.js default
    if "next" in deps:
        return "http://localhost:3000"

    # Create React App default
    if "react-scripts" in deps:
        return "http://localhost:3000"

    # Vue CLI default
    if "@vue/cli-service" in deps:
        return "http://localhost:8080"

    # Generic fallback
    return "http://localhost:3000"


# =============================================================================
# Confidence Calculation
# =============================================================================


def _calculate_confidence(
    signals: ProjectSignals,
    classification_source: str,
    classification_confidence: float,
) -> float:
    """Calculate overall confidence score.

    Components:
    - Signal strength: How many definitive signals found (40%)
    - Classification method: Heuristic vs LLM (30%)
    - Context richness: README, git history, backlog (30%)
    """
    score = 0.0

    # Signal strength (40%)
    definitive_signals = sum(
        [
            signals.has_package_json,
            signals.has_pyproject,
            signals.has_cargo,
            signals.has_sphinx_conf,
            signals.has_mkdocs,
            signals.has_notebooks,
            signals.has_prose,
        ]
    )
    score += min(definitive_signals * 0.1, 0.4)

    # Classification method (30%)
    if classification_source == "heuristic":
        score += 0.30 * classification_confidence
    elif classification_source == "llm":
        score += 0.20 * classification_confidence
    else:
        score += 0.10

    # Context richness (30%)
    if signals.readme_content:
        score += 0.10
    if signals.git_status and signals.git_status.commit_count > 5:
        score += 0.10
    if signals.has_backlog:
        score += 0.10

    return min(score, 1.0)


# =============================================================================
# Monorepo Support
# =============================================================================


async def analyze_monorepo(
    path: Path,
    model: ModelProtocol,
) -> tuple[ProjectAnalysis, list[SubProject]]:
    """Analyze a monorepo and its sub-projects.

    Args:
        path: Monorepo root path.
        model: LLM model for analysis.

    Returns:
        Tuple of (root analysis, list of sub-projects).
    """
    # Analyze root
    root_analysis = await analyze_project(path, model)

    # Detect sub-projects
    sub_projects = detect_sub_projects(path)

    return root_analysis, sub_projects


__all__ = [
    "analyze_project",
    "analyze_monorepo",
    "load_or_analyze",
    "is_monorepo",
    "detect_sub_projects",
    "SubProject",
]
