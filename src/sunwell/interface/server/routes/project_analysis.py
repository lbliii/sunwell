"""Project analysis endpoints: analyze, monorepo, files, status."""

from pathlib import Path

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes._models import (
    MonorepoCheckResponse,
    MonorepoSubProject,
    ProjectAnalysisResponse,
    ProjectFileEntry,
    ProjectFileResponse,
    ProjectFilesResponse,
    ProjectStatusResponse,
)
from sunwell.interface.server.routes.project_models import (
    AnalyzeRequest,
    MonorepoRequest,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.post("/monorepo")
async def check_monorepo(request: MonorepoRequest) -> MonorepoCheckResponse:
    """Check if path is a monorepo and return sub-projects.

    Uses monorepo detection to find npm workspaces, Cargo workspaces,
    Python services patterns, etc.
    """
    from sunwell.knowledge.project.monorepo import detect_sub_projects, is_monorepo

    path = normalize_path(request.path)

    if not path.exists():
        return MonorepoCheckResponse(
            is_monorepo=False,
            sub_projects=[],
            pattern=None,
        )

    try:
        is_mono = is_monorepo(path)
        sub_projects: list[MonorepoSubProject] = []

        if is_mono:
            detected = detect_sub_projects(path)
            for sub in detected:
                sub_projects.append(
                    MonorepoSubProject(
                        path=str(sub.path),
                        name=sub.name,
                        project_type=sub.project_type,
                    )
                )

        return MonorepoCheckResponse(
            is_monorepo=is_mono,
            sub_projects=sub_projects,
            pattern=None,
        )
    except Exception:
        return MonorepoCheckResponse(
            is_monorepo=False,
            sub_projects=[],
            pattern=None,
        )


@router.post("/analyze")
async def analyze_project(request: AnalyzeRequest) -> ProjectAnalysisResponse:
    """Analyze project structure."""
    try:
        from sunwell.knowledge.project import ProjectAnalyzer

        path = normalize_path(request.path)
        if not path.exists():
            return ProjectAnalysisResponse(
                project_type=None,
                language=None,
                framework=None,
                confidence=0.0,
            )

        analyzer = ProjectAnalyzer(path)
        analysis = analyzer.analyze()
        analysis_dict = analysis.to_dict() if hasattr(analysis, "to_dict") else {}

        return ProjectAnalysisResponse(
            project_type=analysis_dict.get("project_type"),
            language=analysis_dict.get("language"),
            framework=analysis_dict.get("framework"),
            confidence=analysis_dict.get("confidence", 0.0),
        )
    except Exception:
        return ProjectAnalysisResponse(
            project_type=None,
            language=None,
            framework=None,
            confidence=0.0,
        )


@router.get("/files")
async def list_project_files(
    path: str | None = None, max_depth: int = 3
) -> ProjectFilesResponse:
    """List project files."""
    target = normalize_path(path) if path else Path.cwd()
    if not target.exists():
        return ProjectFilesResponse(files=[])

    def list_dir(p: Path, depth: int) -> list[ProjectFileEntry]:
        if depth > max_depth:
            return []
        entries: list[ProjectFileEntry] = []
        try:
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.name in ("node_modules", "__pycache__", "venv", ".venv", "target"):
                    continue
                if item.is_dir():
                    entries.append(
                        ProjectFileEntry(
                            name=item.name,
                            path=str(item),
                            is_dir=True,
                            children=list_dir(item, depth + 1),
                        )
                    )
                else:
                    entries.append(
                        ProjectFileEntry(
                            name=item.name,
                            path=str(item),
                            is_dir=False,
                            size=item.stat().st_size,
                        )
                    )
        except PermissionError:
            pass
        return entries

    return ProjectFilesResponse(files=list_dir(target, 0))


@router.get("/file")
async def get_project_file(
    path: str, max_size: int = 50000
) -> ProjectFileResponse:
    """Get file contents."""
    try:
        file_path = normalize_path(path)
        if not file_path.exists():
            return ProjectFileResponse(
                content="", size=0, truncated=False, error="File not found"
            )
        file_size = file_path.stat().st_size
        if file_size > max_size:
            return ProjectFileResponse(
                content="",
                size=file_size,
                truncated=True,
                error=f"File too large (max {max_size} bytes)",
            )
        return ProjectFileResponse(
            content=file_path.read_text(),
            size=file_size,
            truncated=False,
        )
    except Exception as e:
        return ProjectFileResponse(content="", size=0, truncated=False, error=str(e))


@router.get("/status")
async def get_project_status(path: str) -> ProjectStatusResponse:
    """Get project status."""
    project_path = normalize_path(path)
    return ProjectStatusResponse(
        exists=project_path.exists(),
        has_sunwell=(project_path / ".sunwell").exists(),
        has_git=(project_path / ".git").exists(),
    )
