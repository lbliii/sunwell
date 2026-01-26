"""Goal Inference (RFC-079).

Infer reasonable goals from project context when no backlog exists.
"""

import json
import re

from sunwell.knowledge.project.intent_types import InferredGoal, ProjectType
from sunwell.knowledge.project.signals import ProjectSignals, format_dir_tree, format_recent_commits
from sunwell.models import GenerateOptions, ModelProtocol, sanitize_llm_content

# Pre-compiled regex for JSON extraction
_JSON_OBJECT_PATTERN = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)

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
    if signals.has_src_dir:
        state_parts.append("Has src/ directory")
    if signals.has_docs_dir:
        state_parts.append("Has docs/ directory")

    return "; ".join(state_parts) if state_parts else "Fresh project"


async def infer_goals_from_context(
    signals: ProjectSignals,
    project_type: ProjectType,
    model: ModelProtocol,
    subtype: str | None = None,
) -> tuple[InferredGoal, ...]:
    """Infer reasonable goals when no backlog exists.

    Args:
        signals: Collected project signals.
        project_type: Classified project type.
        model: LLM model for inference.
        subtype: Optional project subtype.

    Returns:
        Tuple of inferred goals.
    """
    prompt = GOAL_INFERENCE_PROMPT.format(
        project_name=signals.path.name,
        project_type=project_type.value,
        subtype=subtype or "generic",
        readme_excerpt=signals.readme_content[:800] if signals.readme_content else "No README",
        recent_files=", ".join(f.name for f in signals.recent_files[:5]),
        recent_commits=format_recent_commits(signals.git_status, limit=5),
        state_signals=describe_state(signals),
    )

    result = await model.generate(
        prompt,
        options=GenerateOptions(
            temperature=0.4,
            max_tokens=500,
        ),
    )

    return _parse_goals_response(result.text, signals.path.name)


def _parse_goals_response(response: str, project_name: str) -> tuple[InferredGoal, ...]:
    """Parse LLM JSON response into InferredGoals."""
    try:
        data = _extract_json(response)
        goals = []
        for g in data.get("goals", []):
            goals.append(
                InferredGoal(
                    id=g.get("id", f"goal-{len(goals)+1}"),
                    title=sanitize_llm_content(g["title"]) or "",
                    description=sanitize_llm_content(g.get("description", "")) or "",
                    priority=g.get("priority", "medium"),
                    status="inferred",
                    confidence=g.get("confidence", 0.6),
                )
            )
        return tuple(goals) if goals else _fallback_goal(project_name)
    except (ValueError, KeyError, json.JSONDecodeError):
        return _fallback_goal(project_name)


def _fallback_goal(project_name: str) -> tuple[InferredGoal, ...]:
    """Return a fallback goal when inference fails."""
    return (
        InferredGoal(
            id="explore",
            title=f"Explore {project_name}",
            description="Review the project structure and understand the codebase",
            priority="medium",
            status="inferred",
            confidence=0.5,
        ),
    )


async def classify_with_llm(
    signals: ProjectSignals,
    model: ModelProtocol,
) -> tuple[ProjectType, str | None, float]:
    """Use LLM for ambiguous project classification.

    Args:
        signals: Collected project signals.
        model: LLM model for classification.

    Returns:
        Tuple of (project_type, subtype, confidence).
    """
    prompt = PROJECT_CLASSIFICATION_PROMPT.format(
        path=signals.path.name,
        readme_excerpt=signals.readme_content[:500] if signals.readme_content else "No README",
        top_level_files=", ".join(
            f.name for f in signals.path.iterdir() if f.is_file()
        )[:200],
        dir_tree=format_dir_tree(signals.path, max_depth=2),
        recent_commits=format_recent_commits(signals.git_status, limit=5),
    )

    result = await model.generate(
        prompt,
        options=GenerateOptions(
            temperature=0.2,
            max_tokens=300,
        ),
    )

    try:
        data = _extract_json(result.text)
        project_type = ProjectType(data["project_type"])
        subtype = sanitize_llm_content(data["subtype"]) if data.get("subtype") else None
        confidence = data.get("confidence", 0.7)
        return project_type, subtype, confidence
    except (ValueError, KeyError, json.JSONDecodeError):
        return ProjectType.MIXED, None, 0.5


def _extract_json(response: str) -> dict:
    """Extract JSON from LLM response (handles markdown code blocks)."""
    json_str = response.strip()

    # Handle markdown code blocks
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        parts = response.split("```")
        if len(parts) >= 2:
            json_str = parts[1]

    # Try to parse
    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        # Try to find JSON object in response
        match = _JSON_OBJECT_PATTERN.search(response)
        if match:
            return json.loads(match.group())
        raise
