"""Project Intent Analyzer Types (RFC-079).

Universal project understanding types for analyzing what any project IS
and what should happen next.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class ProjectType(Enum):
    """Primary project classification."""

    CODE = "code"  # Software development
    DOCUMENTATION = "documentation"  # Docs, guides, specs
    DATA = "data"  # Analysis, notebooks, datasets
    PLANNING = "planning"  # Goals, roadmaps, research
    CREATIVE = "creative"  # Writing, design, media
    MIXED = "mixed"  # Multiple types


class PreviewType(Enum):
    """How to preview this project (orthogonal to ProjectType).

    ProjectType answers: "What IS this?" (code, creative, data)
    PreviewType answers: "HOW do I view it?" (web, prose reader, terminal)

    RFC: Universal Project Readiness & Preview
    """

    WEB_VIEW = "web_view"  # Embedded browser (web apps)
    TERMINAL = "terminal"  # Pre-filled terminal (CLI tools)
    PROSE = "prose"  # Formatted reader (novels, articles)
    SCREENPLAY = "screenplay"  # Fountain renderer (scripts)
    DIALOGUE = "dialogue"  # Interactive tree (game dialogue)
    NOTEBOOK = "notebook"  # Jupyter-style (data science)
    STATIC = "static"  # Just open the file (images, PDFs)
    NONE = "none"  # No preview (libraries, configs)


@dataclass(frozen=True, slots=True)
class Prerequisite:
    """A prerequisite for running a dev command."""

    command: str
    """Command to run (e.g., 'npm install')."""

    description: str
    """What this prerequisite does."""

    check_command: str | None = None
    """Command to check if prerequisite is already met."""

    satisfied: bool = False
    """Whether this prerequisite is currently met (runtime state)."""

    required: bool = True
    """If False, preview can work without this (degraded mode)."""


@dataclass(frozen=True, slots=True)
class DevCommand:
    """Dev server command (code projects only)."""

    command: str
    """Shell command to run (e.g., 'npm run dev')."""

    description: str
    """Description (e.g., 'Start Vite development server')."""

    prerequisites: tuple[Prerequisite, ...] = ()
    """Prerequisites to run first."""

    expected_url: str | None = None
    """Expected URL (e.g., 'http://localhost:5173')."""


@dataclass(frozen=True, slots=True)
class SuggestedAction:
    """What the user might want to do next."""

    action_type: Literal["execute_goal", "continue_work", "start_server", "review", "add_goal"]
    """Type of suggested action."""

    description: str
    """Description (e.g., 'Continue drafting chapter 3')."""

    goal_id: str | None = None
    """Reference to backlog goal (if applicable)."""

    command: str | None = None
    """Shell command (if applicable)."""

    confidence: float = 0.8
    """How sure we are this is helpful (0.0-1.0)."""


@dataclass(frozen=True, slots=True)
class PipelineStep:
    """A step in the project's goal pipeline."""

    id: str
    """Unique identifier."""

    title: str
    """Step title."""

    status: Literal["completed", "in_progress", "pending"]
    """Current status."""

    description: str = ""
    """Optional description."""


@dataclass(frozen=True, slots=True)
class InferredGoal:
    """A goal inferred from project context.

    Separate from backlog.Goal to avoid coupling.
    Can be converted to backlog.Goal if user confirms.
    """

    id: str
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    status: Literal["inferred", "confirmed", "rejected"] = "inferred"
    confidence: float = 0.6


@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    """Universal project understanding."""

    # Identity
    name: str
    """Project name."""

    path: Path
    """Project root path."""

    # What kind of project is this?
    project_type: ProjectType
    """Primary classification."""

    project_subtype: str | None = None
    """Specific subtype (e.g., 'svelte-app', 'sphinx-docs', 'jupyter-notebook')."""

    # What's the current state?
    goals: tuple[InferredGoal, ...] = ()
    """Goals from backlog or inferred."""

    pipeline: tuple[PipelineStep, ...] = ()
    """Execution order."""

    current_step: str | None = None
    """Current step ID (if any)."""

    completion_percent: float = 0.0
    """Completion 0.0-1.0."""

    # What should happen next?
    suggested_action: SuggestedAction | None = None
    """Suggested next action."""

    suggested_workspace_primary: str = "CodeEditor"
    """Primary primitive name for RFC-072 workspace composition."""

    # Code-specific (optional)
    dev_command: DevCommand | None = None
    """Dev server command (only for code projects with servers)."""

    # Preview-specific fields (RFC: Universal Project Readiness)
    preview_type: PreviewType = field(default_factory=lambda: PreviewType.NONE)
    """How to preview this project (orthogonal to project_type)."""

    preview_url: str | None = None
    """URL for web-based previews (e.g., http://localhost:5000)."""

    preview_file: str | None = None
    """Primary file for content previews (e.g., chapters/ch-01.md)."""

    # Confidence (0.0-1.0)
    confidence: float = 0.5
    """How confident we are in this analysis."""

    confidence_level: Literal["high", "medium", "low"] = "low"
    """Derived from confidence: high >= 0.85, medium >= 0.65, low < 0.65."""

    detection_signals: tuple[str, ...] = ()
    """What we based this analysis on."""

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)
    """When analysis was performed."""

    classification_source: Literal["heuristic", "llm", "cached"] = "heuristic"
    """How project type was determined."""

    def to_cache_dict(self) -> dict[str, Any]:
        """Convert to dictionary for caching."""
        return {
            "version": 1,
            "analyzed_at": self.analyzed_at.isoformat(),
            "name": self.name,
            "path": str(self.path),
            "project_type": self.project_type.value,
            "project_subtype": self.project_subtype,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "detection_signals": list(self.detection_signals),
            "suggested_workspace_primary": self.suggested_workspace_primary,
            "classification_source": self.classification_source,
            "goals_inferred": any(g.status == "inferred" for g in self.goals),
            "goals": [
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "priority": g.priority,
                    "status": g.status,
                    "confidence": g.confidence,
                }
                for g in self.goals
            ],
            "pipeline": [
                {
                    "id": s.id,
                    "title": s.title,
                    "status": s.status,
                    "description": s.description,
                }
                for s in self.pipeline
            ],
            "current_step": self.current_step,
            "completion_percent": self.completion_percent,
            "dev_command": (
                {
                    "command": self.dev_command.command,
                    "description": self.dev_command.description,
                    "expected_url": self.dev_command.expected_url,
                    "prerequisites": [
                        {
                            "command": p.command,
                            "description": p.description,
                            "check_command": p.check_command,
                        }
                        for p in self.dev_command.prerequisites
                    ],
                }
                if self.dev_command
                else None
            ),
            "suggested_action": (
                {
                    "action_type": self.suggested_action.action_type,
                    "description": self.suggested_action.description,
                    "goal_id": self.suggested_action.goal_id,
                    "command": self.suggested_action.command,
                    "confidence": self.suggested_action.confidence,
                }
                if self.suggested_action
                else None
            ),
            # Preview fields (RFC: Universal Project Readiness)
            "preview_type": self.preview_type.value,
            "preview_url": self.preview_url,
            "preview_file": self.preview_file,
        }

    @classmethod
    def from_cache(cls, data: dict[str, Any]) -> ProjectAnalysis:
        """Create ProjectAnalysis from cached data."""
        goals = tuple(
            InferredGoal(
                id=g["id"],
                title=g["title"],
                description=g.get("description", ""),
                priority=g.get("priority", "medium"),
                status=g.get("status", "inferred"),
                confidence=g.get("confidence", 0.6),
            )
            for g in data.get("goals", [])
        )

        pipeline = tuple(
            PipelineStep(
                id=s["id"],
                title=s["title"],
                status=s["status"],
                description=s.get("description", ""),
            )
            for s in data.get("pipeline", [])
        )

        dev_cmd_data = data.get("dev_command")
        dev_command = None
        if dev_cmd_data:
            dev_command = DevCommand(
                command=dev_cmd_data["command"],
                description=dev_cmd_data["description"],
                expected_url=dev_cmd_data.get("expected_url"),
                prerequisites=tuple(
                    Prerequisite(
                        command=p["command"],
                        description=p["description"],
                        check_command=p.get("check_command"),
                    )
                    for p in dev_cmd_data.get("prerequisites", [])
                ),
            )

        action_data = data.get("suggested_action")
        suggested_action = None
        if action_data:
            suggested_action = SuggestedAction(
                action_type=action_data["action_type"],
                description=action_data["description"],
                goal_id=action_data.get("goal_id"),
                command=action_data.get("command"),
                confidence=action_data.get("confidence", 0.8),
            )

        confidence = data.get("confidence", 0.5)

        # Parse preview fields (RFC: Universal Project Readiness)
        preview_type_value = data.get("preview_type", "none")
        try:
            preview_type = PreviewType(preview_type_value)
        except ValueError:
            preview_type = PreviewType.NONE

        return cls(
            name=data["name"],
            path=Path(data["path"]),
            project_type=ProjectType(data["project_type"]),
            project_subtype=data.get("project_subtype"),
            goals=goals,
            pipeline=pipeline,
            current_step=data.get("current_step"),
            completion_percent=data.get("completion_percent", 0.0),
            suggested_action=suggested_action,
            suggested_workspace_primary=data.get("suggested_workspace_primary", "CodeEditor"),
            dev_command=dev_command,
            preview_type=preview_type,
            preview_url=data.get("preview_url"),
            preview_file=data.get("preview_file"),
            confidence=confidence,
            confidence_level=(
                "high" if confidence >= 0.85 else "medium" if confidence >= 0.65 else "low"
            ),
            detection_signals=tuple(data.get("detection_signals", [])),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            classification_source="cached",
        )


# Workspace primary primitives by project type
# RFC-072 uses this to compose the full workspace layout
WORKSPACE_PRIMARIES: dict[ProjectType, str] = {
    ProjectType.CODE: "CodeEditor",
    ProjectType.DOCUMENTATION: "ProseEditor",
    ProjectType.DATA: "NotebookEditor",
    ProjectType.PLANNING: "Kanban",
    ProjectType.CREATIVE: "ProseEditor",
    ProjectType.MIXED: "CodeEditor",
}
