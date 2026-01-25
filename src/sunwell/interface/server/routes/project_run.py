"""Project run endpoints (RFC-066)."""

import uuid

from fastapi import APIRouter

from sunwell.foundation.utils import normalize_path
from sunwell.interface.server.routes._models import (
    ProjectRunAnalysisResponse,
    ProjectRunResponse,
    SuccessResponse,
)
from sunwell.interface.server.routes.project_models import (
    AnalyzeRunRequest,
    ProjectRunRequest,
    StopRunRequest,
)

router = APIRouter(prefix="/project", tags=["project"])


@router.post("/analyze-run")
async def analyze_project_for_run(
    request: AnalyzeRunRequest,
) -> ProjectRunAnalysisResponse:
    """Analyze project for running."""
    project_path = normalize_path(request.path)

    command = "echo 'No run command detected'"
    expected_url = None

    if (project_path / "package.json").exists():
        command = "npm run dev"
        expected_url = "http://localhost:5173"
    elif (project_path / "pyproject.toml").exists():
        command = "python -m http.server 8000"
        expected_url = "http://localhost:8000"
    elif (project_path / "index.html").exists():
        command = "python -m http.server 3000"
        expected_url = "http://localhost:3000"

    return ProjectRunAnalysisResponse(
        command=command,
        expected_url=expected_url,
        install_command="npm install" if (project_path / "package.json").exists() else None,
        requires_install=False,
    )


@router.post("/run")
async def run_project(request: ProjectRunRequest) -> ProjectRunResponse:
    """Run a project."""
    return ProjectRunResponse(
        run_id=str(uuid.uuid4()),
        status="started",
    )


@router.post("/run/stop")
async def stop_project_run(request: StopRunRequest) -> SuccessResponse:
    """Stop a project run."""
    return SuccessResponse(success=True, message="stopped")


@router.post("/analyze-for-run")
async def analyze_project_for_run_alias(
    request: AnalyzeRunRequest,
) -> ProjectRunAnalysisResponse:
    """Alias for analyze-run (frontend compatibility)."""
    return await analyze_project_for_run(request)
