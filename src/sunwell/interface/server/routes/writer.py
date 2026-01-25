"""Document writing and workflow routes (RFC-086)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sunwell.interface.server.routes.models import (
    ActiveWorkflowsResponse,
    DiataxisDetection,
    DiataxisResponse,
    DiataxisScores,
    FixAllResponse,
    SkillExecuteResponse,
    ValidationResponse,
    ValidationWarning,
    WorkflowChainItem,
    WorkflowChainsResponse,
    WorkflowExecutionResponse,
    WorkflowRouteResponse,
    WorkflowStatusResponse,
)

router = APIRouter(prefix="/api", tags=["writer"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class DiataxisRequest(BaseModel):
    content: str
    file_path: str | None = None


class ValidateRequest(BaseModel):
    content: str
    file_path: str | None = None
    lens_name: str = "tech-writer"


class FixAllRequest(BaseModel):
    content: str
    warnings: list[dict[str, Any]]
    lens_name: str


class ExecuteSkillRequest(BaseModel):
    skill_id: str
    content: str
    file_path: str | None = None
    lens_name: str


class RouteIntentRequest(BaseModel):
    user_input: str


class StartWorkflowRequest(BaseModel):
    chain_name: str
    target_file: str | None = None


class WorkflowIdRequest(BaseModel):
    execution_id: str


# ═══════════════════════════════════════════════════════════════
# WRITER ROUTES (RFC-086)
# ═══════════════════════════════════════════════════════════════


@router.post("/writer/diataxis")
async def detect_diataxis(request: DiataxisRequest) -> DiataxisResponse:
    """Detect Diataxis content type."""
    content_lower = request.content.lower()
    tutorial_score = 0.0
    how_to_score = 0.0
    explanation_score = 0.0
    reference_score = 0.0

    if any(k in content_lower for k in ["tutorial", "learn", "quickstart"]):
        tutorial_score += 0.3
    if any(k in content_lower for k in ["how to", "guide", "configure"]):
        how_to_score += 0.3
    if any(k in content_lower for k in ["understand", "architecture", "concepts"]):
        explanation_score += 0.3
    if any(k in content_lower for k in ["reference", "api", "parameters"]):
        reference_score += 0.3

    scores = DiataxisScores(
        tutorial=tutorial_score,
        how_to=how_to_score,
        explanation=explanation_score,
        reference=reference_score,
    )

    # Find the best match
    score_map = {
        "TUTORIAL": tutorial_score,
        "HOW_TO": how_to_score,
        "EXPLANATION": explanation_score,
        "REFERENCE": reference_score,
    }
    best = max(score_map.items(), key=lambda x: x[1])

    return DiataxisResponse(
        detection=DiataxisDetection(
            detected_type=best[0] if best[1] > 0 else None,
            confidence=best[1],
            signals=[],
            scores=scores,
        ),
        warnings=[],
    )


@router.post("/writer/validate")
async def validate_document(request: ValidateRequest) -> ValidationResponse:
    """Validate document content for common issues.

    Performs basic linting checks including:
    - Trailing whitespace
    - Multiple blank lines
    - Missing headers
    - Broken links (relative only)
    - Long lines

    Returns ValidationResponse with warnings (auto-converted to camelCase).
    """
    import re

    content = request.content
    lines = content.split("\n")
    warnings: list[ValidationWarning] = []

    for i, line in enumerate(lines, 1):
        # Trailing whitespace
        if line.rstrip() != line and line.strip():
            warnings.append(ValidationWarning(
                line=i,
                rule="trailing_whitespace",
                message="Line has trailing whitespace",
                severity="warning",
                suggestion="Remove trailing whitespace",
            ))

        # Long lines (>120 chars)
        if len(line) > 120 and not line.strip().startswith("```"):
            warnings.append(ValidationWarning(
                line=i,
                rule="long_line",
                message=f"Line exceeds 120 characters ({len(line)})",
                severity="info",
            ))

        # Multiple consecutive blank lines
        if i > 1 and not line.strip() and not lines[i - 2].strip():
            warnings.append(ValidationWarning(
                line=i,
                rule="multiple_blank_lines",
                message="Multiple consecutive blank lines",
                severity="warning",
                suggestion="Collapse to single blank line",
            ))

    # Check for broken relative links (markdown only)
    if request.file_path and request.file_path.endswith(".md"):
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for match in link_pattern.finditer(content):
            link_text, link_target = match.groups()
            if not link_target.startswith(("http://", "https://", "#", "mailto:")):
                # Relative link - check if file exists
                if request.file_path:
                    file_dir = Path(request.file_path).parent
                    target_path = file_dir / link_target
                    if not target_path.exists():
                        line_num = content[:match.start()].count("\n") + 1
                        warnings.append(ValidationWarning(
                            line=line_num,
                            rule="broken_link",
                            message=f"Broken relative link: {link_target}",
                            severity="error",
                        ))

    # Check for missing title (first H1)
    if not any(line.strip().startswith("# ") for line in lines[:10]):
        warnings.append(ValidationWarning(
            line=1,
            rule="missing_title",
            message="Document is missing a title (H1 header)",
            severity="warning",
        ))

    return ValidationResponse(warnings=warnings)


@router.post("/writer/fix-all")
async def fix_all_issues(request: FixAllRequest) -> FixAllResponse:
    """Fix all fixable issues in the document.

    Currently supports:
    - Removing trailing whitespace
    - Collapsing multiple blank lines
    """
    import re

    content = request.content
    fixed_count = 0

    # Track which rules to fix (use 'rule' field from ValidationWarning)
    fixable_rules = {w.get("rule") for w in request.warnings}

    # Fix trailing whitespace
    if "trailing_whitespace" in fixable_rules:
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.rstrip()
            if stripped != line and line.strip():
                fixed_count += 1
            new_lines.append(stripped)
        content = "\n".join(new_lines)

    # Fix multiple blank lines (collapse to single)
    if "multiple_blank_lines" in fixable_rules:
        original_len = len(content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        if len(content) != original_len:
            fixed_count += 1

    return FixAllResponse(content=content, fixed=fixed_count)


@router.post("/writer/execute-skill")
async def execute_skill(request: ExecuteSkillRequest) -> SkillExecuteResponse:
    """Execute a lens skill."""
    return SkillExecuteResponse(message=f"Skill {request.skill_id} executed")


# ═══════════════════════════════════════════════════════════════
# WORKFLOW ROUTES (RFC-086)
# ═══════════════════════════════════════════════════════════════


@router.post("/workflow/route")
async def route_workflow_intent(request: RouteIntentRequest) -> WorkflowRouteResponse:
    """Route natural language to workflow."""
    return WorkflowRouteResponse(
        category="information",
        confidence=0.5,
        signals=[],
        suggested_workflow=None,
        tier="fast",
    )


@router.post("/workflow/start")
async def start_workflow(request: StartWorkflowRequest) -> WorkflowExecutionResponse:
    """Start a workflow chain."""
    import uuid

    return WorkflowExecutionResponse(
        id=str(uuid.uuid4()),
        chain_name=request.chain_name,
        description=f"Workflow: {request.chain_name}",
        current_step=0,
        total_steps=3,
        steps=[],
        status="running",
        started_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        context={"working_dir": str(Path.cwd())},
    )


@router.post("/workflow/stop")
async def stop_workflow(request: WorkflowIdRequest) -> WorkflowStatusResponse:
    """Stop a workflow."""
    return WorkflowStatusResponse(status="stopped")


@router.post("/workflow/resume")
async def resume_workflow(request: WorkflowIdRequest) -> WorkflowExecutionResponse:
    """Resume a workflow."""
    return WorkflowExecutionResponse(
        id=request.execution_id,
        chain_name="unknown",
        description="Resumed workflow",
        current_step=0,
        total_steps=3,
        steps=[],
        status="running",
        started_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        context={"working_dir": str(Path.cwd())},
    )


@router.post("/workflow/skip-step")
async def skip_workflow_step(request: WorkflowIdRequest) -> WorkflowStatusResponse:
    """Skip current workflow step."""
    return WorkflowStatusResponse(status="skipped")


@router.get("/workflow/chains")
async def list_workflow_chains() -> WorkflowChainsResponse:
    """List available workflow chains."""
    return WorkflowChainsResponse(
        chains=[
            WorkflowChainItem(
                name="feature-docs",
                description="Document a new feature",
                steps=[],
                checkpoint_after=[],
                tier="full",
            ),
            WorkflowChainItem(
                name="health-check",
                description="Validate existing docs",
                steps=[],
                checkpoint_after=[],
                tier="light",
            ),
            WorkflowChainItem(
                name="quick-fix",
                description="Fast issue resolution",
                steps=[],
                checkpoint_after=[],
                tier="fast",
            ),
        ]
    )


@router.get("/workflow/active")
async def list_active_workflows() -> ActiveWorkflowsResponse:
    """List active workflows."""
    return ActiveWorkflowsResponse(workflows=[])
