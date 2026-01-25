"""Prompt building utilities for artifact planner."""

from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import ArtifactSpec

if TYPE_CHECKING:
    from sunwell.project.schema import ProjectSchema


def build_discovery_prompt(
    goal: str,
    context: dict[str, Any] | None,
    project_schema: ProjectSchema | None = None,
) -> str:
    """Build the artifact discovery prompt.

    Args:
        goal: The goal to achieve
        context: Optional context dict
        project_schema: Optional project schema for domain-specific types

    Returns:
        Formatted discovery prompt
    """
    context_str = format_context(context)

    # RFC-035: Add schema context if available
    schema_section = ""
    if project_schema:
        schema_section = build_schema_section(project_schema)

    return f"""GOAL: {goal}

CONTEXT:
{context_str}
{schema_section}
=== ARTIFACT DISCOVERY ===

Think about this goal differently. Don't ask "what steps should I take?"
Instead ask: "When this goal is complete, what THINGS will exist?"

For each thing that must exist, identify:
- id: A unique name (e.g., "UserProtocol", "Chapter1", "Hypothesis_A")
- description: What is this thing?
- contract: What must it provide/satisfy? (This is its specification)
- requires: What other artifacts must exist BEFORE this one can be created?
- produces_file: What file will contain this artifact?
- domain_type: Type category (e.g., "protocol", "model", "service", "component")

=== DISCOVERY PRINCIPLES ===

1. CONTRACTS BEFORE IMPLEMENTATIONS
   Interfaces, protocols, outlines, specs — these have no dependencies.
   Implementations require their contracts to exist first.

2. IDENTIFY ALL LEAVES
   Leaves are artifacts with no requirements. They can all be created in parallel.
   Ask: "What can I create right now with no prerequisites?"

3. TRACE TO ROOT
   The root is the final artifact that satisfies the goal.
   Everything flows toward it.

4. SEMANTIC DEPENDENCIES
   A requires B if creating A needs to reference, implement, or build on B.
   "UserModel requires UserProtocol" because it implements that protocol.

=== EXAMPLE ===

Goal: "Build a REST API with user authentication"

```json
[
  {{
    "id": "UserProtocol",
    "description": "Protocol defining User entity",
    "contract": "Protocol with fields: id, email, password_hash, created_at",
    "requires": [],
    "produces_file": "src/protocols/user.py",
    "domain_type": "protocol"
  }},
  {{
    "id": "AuthInterface",
    "description": "Interface for authentication operations",
    "contract": "Protocol: authenticate(), generate_token(), verify_token()",
    "requires": [],
    "produces_file": "src/protocols/auth.py",
    "domain_type": "protocol"
  }},
  {{
    "id": "UserModel",
    "description": "SQLAlchemy model implementing UserProtocol",
    "contract": "Class User(Base) implementing UserProtocol",
    "requires": ["UserProtocol"],
    "produces_file": "src/models/user.py",
    "domain_type": "model"
  }},
  {{
    "id": "AuthService",
    "description": "JWT-based authentication service",
    "contract": "Class implementing AuthInterface with JWT + bcrypt",
    "requires": ["AuthInterface", "UserProtocol"],
    "produces_file": "src/services/auth.py",
    "domain_type": "service"
  }},
  {{
    "id": "UserRoutes",
    "description": "REST endpoints for user operations",
    "contract": "Flask Blueprint: POST /users, GET /users/me, PUT /users/me",
    "requires": ["UserModel", "AuthService"],
    "produces_file": "src/routes/users.py",
    "domain_type": "routes"
  }},
  {{
    "id": "App",
    "description": "Flask application factory",
    "contract": "create_app() initializing Flask, blueprints, database",
    "requires": ["UserRoutes"],
    "produces_file": "src/app.py",
    "domain_type": "application"
  }}
]
```

Analysis:
- Leaves (parallel): UserProtocol, AuthInterface (no requirements)
- Second wave: UserModel, AuthService (require protocols)
- Third wave: UserRoutes (requires model + service)
- Root: App (final convergence)

=== NOW DISCOVER ARTIFACTS FOR ===

Goal: {goal}

Output ONLY valid JSON array of artifacts:"""


def build_schema_section(project_schema: ProjectSchema) -> str:
    """Build schema context for RFC-035 integration.

    Args:
        project_schema: Project schema to extract context from

    Returns:
        Formatted schema section string
    """
    schema = project_schema
    lines = [
        "",
        f"=== PROJECT SCHEMA: {schema.name} ===",
        f"Type: {schema.project_type}",
        "",
        "AVAILABLE ARTIFACT TYPES:",
    ]

    for name, artifact_type in schema.artifact_types.items():
        lines.append(f"- {name}: {artifact_type.description}")
        if artifact_type.is_contract:
            lines.append("  (Contract type - no dependencies)")
        if artifact_type.requires_patterns:
            requires = ", ".join(artifact_type.requires_patterns)
            lines.append(f"  Typical requires: {requires}")

    if schema.planning_config.phases:
        lines.extend(["", "PLANNING PHASES:"])
        for phase in schema.planning_config.phases:
            parallel = "⚡ parallel" if phase.parallel else "→ sequential"
            lines.append(f"- {phase.name} ({parallel})")
            if phase.artifact_types:
                types = ", ".join(phase.artifact_types)
                lines.append(f"  Artifact types: {types}")

    lines.extend([
        "",
        "When discovering artifacts, prefer types from this schema.",
        "Set domain_type to match schema artifact types.",
        "",
    ])

    return "\n".join(lines)


def format_context(context: dict[str, Any] | None) -> str:
    """Format context for the discovery prompt.

    Args:
        context: Context dict with workspace info

    Returns:
        Formatted context string
    """
    if not context:
        return "No additional context."

    lines = []

    # RFC-126: Include full workspace context if available
    if "workspace_context" in context:
        lines.append(context["workspace_context"])
    else:
        # Fallback to individual fields
        if "cwd" in context:
            lines.append(f"Working directory: {context['cwd']}")
        if "project_name" in context:
            lines.append(f"Project: {context['project_name']}")
        if "project_type" in context and context["project_type"] != "unknown":
            ptype = context["project_type"]
            framework = context.get("project_framework")
            lines.append(f"Type: {ptype}" + (f" ({framework})" if framework else ""))
        if "key_files" in context:
            files = context["key_files"][:10]
            lines.append(f"Key files: {', '.join(files)}")
        if "entry_points" in context:
            entries = context["entry_points"][:5]
            lines.append(f"Entry points: {', '.join(entries)}")
        if "description" in context:
            lines.append(f"Description: {context['description']}")

    if "files" in context:
        files = context["files"][:15]
        lines.append(f"Existing files: {', '.join(str(f) for f in files)}")

    return "\n".join(lines) or "No additional context."


def build_creation_prompt(
    artifact: ArtifactSpec,
    context: dict[str, Any] | None = None,
) -> str:
    """Build prompt for creating artifact content.

    Args:
        artifact: Artifact specification to create
        context: Optional context with completed dependencies

    Returns:
        Formatted creation prompt
    """
    # Determine file extension for language hints
    file_ext = ""
    if artifact.produces_file and "." in artifact.produces_file:
        file_ext = artifact.produces_file.split(".")[-1]
    else:
        file_ext = "py"

    language_hint = {
        "py": "Python",
        "js": "JavaScript",
        "ts": "TypeScript",
        "rs": "Rust",
        "go": "Go",
        "java": "Java",
        "md": "Markdown",
        "json": "JSON",
        "yaml": "YAML",
        "yml": "YAML",
    }.get(file_ext, "Python")

    # Build context section
    context_section = ""
    if context and "completed" in context:
        completed_desc = "\n".join(
            f"- {aid}: {info.get('description', 'completed')}"
            for aid, info in context.get("completed", {}).items()
        )
        context_section = f"\n\nCOMPLETED DEPENDENCIES:\n{completed_desc}"

    return f"""Create the following artifact:

ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}
CONTRACT: {artifact.contract}
FILE: {artifact.produces_file or f"{artifact.id.lower()}.py"}
TYPE: {artifact.domain_type or "component"}
REQUIRES: {list(artifact.requires) if artifact.requires else "none"}
{context_section}

=== REQUIREMENTS ===

Generate {language_hint} code that:
1. Fully satisfies the CONTRACT specified above
2. Is complete and ready to use (no placeholders or TODOs)
3. Follows best practices for {language_hint}
4. Includes necessary imports
5. Has clear docstrings/comments

=== OUTPUT FORMAT ===

Output ONLY the code for this file. No explanations before or after.
Start directly with the code (imports, class definitions, etc.).

```{file_ext}
"""
