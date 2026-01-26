"""Project response models (RFC-113, RFC-117, RFC-132, RFC-140)."""

from sunwell.interface.server.routes.models.base import CamelModel


class ProjectLearningsResponse(CamelModel):
    """Project learnings from memory and checkpoints."""

    original_goal: str | None
    decisions: list[str]
    failures: list[str]
    completed_tasks: list[str]
    pending_tasks: list[str]


class DefaultProjectItem(CamelModel):
    """Default project details."""

    id: str
    name: str
    root: str


class DefaultProjectResponse(CamelModel):
    """Default project response."""

    project: DefaultProjectItem | None
    warning: str | None = None


class RecentProjectItem(CamelModel):
    """A project in the recent projects list."""

    path: str
    name: str
    project_type: str
    description: str | None = None
    last_opened: int


class RecentProjectsResponse(CamelModel):
    """List of recent projects."""

    recent: list[RecentProjectItem]


class ScannedProjectTask(CamelModel):
    """A task from a scanned project checkpoint."""

    id: str
    description: str
    completed: bool


class ScannedProjectItem(CamelModel):
    """A project found during scanning."""

    id: str
    path: str
    display_path: str
    name: str
    status: str
    last_goal: str | None = None
    tasks_completed: int | None = None
    tasks_total: int | None = None
    tasks: list[ScannedProjectTask] | None = None
    last_activity: str | None = None


class ScanProjectsResponse(CamelModel):
    """Result of project scanning."""

    projects: list[ScannedProjectItem]
    total: int


class ResumeTaskItem(CamelModel):
    """A task from a resumed checkpoint."""

    id: str
    description: str
    completed: bool


class ResumeProjectResponse(CamelModel):
    """Resume checkpoint information."""

    goal: str | None
    tasks: list[ResumeTaskItem]
    phase: str | None
    checkpoint_exists: bool


class ProjectDeleteResponse(CamelModel):
    """Result of deleting a project."""

    success: bool
    message: str


class ProjectArchiveResponse(CamelModel):
    """Result of archiving a project."""

    success: bool
    message: str
    archive_path: str | None = None


class ProjectIterateResponse(CamelModel):
    """Result of iterating a project."""

    success: bool
    message: str
    new_path: str | None = None


class MonorepoSubProject(CamelModel):
    """A sub-project within a monorepo."""

    path: str
    name: str
    project_type: str | None = None


class MonorepoCheckResponse(CamelModel):
    """Result of monorepo detection."""

    is_monorepo: bool
    sub_projects: list[MonorepoSubProject]
    pattern: str | None = None


class ProjectAnalysisResponse(CamelModel):
    """Project analysis results (RFC-079)."""

    # Identity
    name: str
    path: str

    # Classification
    project_type: str | None
    project_subtype: str | None = None

    # Confidence
    confidence: float
    confidence_level: str = "low"
    detection_signals: list[str] = []

    # Metadata
    analyzed_at: str = ""
    classification_source: str = "heuristic"


class ProjectFileEntry(CamelModel):
    """A file or directory entry in the project."""

    name: str
    path: str
    is_dir: bool
    size: int | None = None
    children: list[ProjectFileEntry] | None = None


class ProjectFilesResponse(CamelModel):
    """Tree of project files."""

    files: list[ProjectFileEntry]


class ProjectRunAnalysisResponse(CamelModel):
    """Analysis for running a project."""

    command: str
    expected_url: str | None = None
    install_command: str | None = None
    requires_install: bool = False


class ProjectRunResponse(CamelModel):
    """Result of starting a project run."""

    run_id: str | None
    status: str


class ProjectFileResponse(CamelModel):
    """Content of a project file."""

    content: str
    size: int
    truncated: bool
    error: str | None = None


class ProjectStatusResponse(CamelModel):
    """Project directory status."""

    exists: bool
    has_sunwell: bool
    has_git: bool


class ProjectIntelligenceResponse(CamelModel):
    """Project intelligence data."""

    signals: list[dict[str, str | int | float | bool | None]]
    context_quality: float


class CurrentProjectItem(CamelModel):
    """Current project details."""

    id: str
    name: str
    root: str
    trust: str
    project_type: str | None = None


class CurrentProjectResponse(CamelModel):
    """Current project information."""

    project: CurrentProjectItem | None
    workspace_root: str
