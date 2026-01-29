"""Prompt building utilities for artifact planner."""

from typing import TYPE_CHECKING, Any

from sunwell.planning.naaru.artifacts import ArtifactSpec
from sunwell.planning.naaru.expertise.language import Language, detect_language

if TYPE_CHECKING:
    from sunwell.knowledge.project.schema import ProjectSchema


# Language-specific examples for artifact discovery
# These guide the LLM to produce appropriate file paths and structures
DISCOVERY_EXAMPLES: dict[Language, str] = {
    Language.PYTHON: '''Goal: "Build a data processing pipeline"

```json
[
  {
    "id": "DataSchema",
    "description": "Schema defining input data structure",
    "contract": "Dataclass with fields: id, timestamp, payload, source",
    "requires": [],
    "produces_file": "src/schemas/data.py",
    "domain_type": "schema"
  },
  {
    "id": "ProcessorProtocol",
    "description": "Protocol for data processors",
    "contract": "Protocol: process(data: DataSchema) -> Result, validate(data) -> bool",
    "requires": [],
    "produces_file": "src/protocols/processor.py",
    "domain_type": "protocol"
  },
  {
    "id": "Pipeline",
    "description": "Main pipeline orchestrator",
    "contract": "Class: run(input) -> output, combining validation and transformation",
    "requires": ["ProcessorProtocol", "DataSchema"],
    "produces_file": "src/pipeline.py",
    "domain_type": "application"
  }
]
```''',
    Language.TYPESCRIPT: '''Goal: "Build a todo app in Svelte"

```json
[
  {
    "id": "TodoType",
    "description": "TypeScript type for todo items",
    "contract": "Type with fields: id, title, completed, createdAt",
    "requires": [],
    "produces_file": "src/lib/types/todo.ts",
    "domain_type": "type"
  },
  {
    "id": "TodoStore",
    "description": "Svelte store for todo state management",
    "contract": "Writable store with add, toggle, remove methods",
    "requires": ["TodoType"],
    "produces_file": "src/lib/stores/todos.ts",
    "domain_type": "store"
  },
  {
    "id": "TodoItem",
    "description": "Svelte component for single todo",
    "contract": "Component: displays todo, handles toggle/delete",
    "requires": ["TodoType"],
    "produces_file": "src/lib/components/TodoItem.svelte",
    "domain_type": "component"
  },
  {
    "id": "TodoList",
    "description": "Main todo list component",
    "contract": "Component: renders list, handles add new todo",
    "requires": ["TodoStore", "TodoItem"],
    "produces_file": "src/routes/+page.svelte",
    "domain_type": "page"
  }
]
```''',
    Language.JAVASCRIPT: '''Goal: "Build a REST API with Express"

```json
[
  {
    "id": "UserModel",
    "description": "User data model",
    "contract": "Schema with fields: id, email, name, createdAt",
    "requires": [],
    "produces_file": "src/models/user.js",
    "domain_type": "model"
  },
  {
    "id": "UserController",
    "description": "User route handlers",
    "contract": "CRUD handlers: create, read, update, delete",
    "requires": ["UserModel"],
    "produces_file": "src/controllers/userController.js",
    "domain_type": "controller"
  },
  {
    "id": "UserRoutes",
    "description": "Express router for user endpoints",
    "contract": "Router with /users endpoints",
    "requires": ["UserController"],
    "produces_file": "src/routes/users.js",
    "domain_type": "router"
  }
]
```''',
    Language.RUST: '''Goal: "Build a CLI tool"

```json
[
  {
    "id": "Config",
    "description": "Configuration struct",
    "contract": "Struct with serde derive for config loading",
    "requires": [],
    "produces_file": "src/config.rs",
    "domain_type": "model"
  },
  {
    "id": "Args",
    "description": "CLI argument parser",
    "contract": "Clap derive struct for CLI args",
    "requires": [],
    "produces_file": "src/args.rs",
    "domain_type": "cli"
  },
  {
    "id": "Main",
    "description": "Main entry point",
    "contract": "Main function: parse args, load config, run",
    "requires": ["Config", "Args"],
    "produces_file": "src/main.rs",
    "domain_type": "application"
  }
]
```''',
    Language.GO: '''Goal: "Build an HTTP server"

```json
[
  {
    "id": "Models",
    "description": "Data models",
    "contract": "Struct definitions with json tags",
    "requires": [],
    "produces_file": "internal/models/models.go",
    "domain_type": "model"
  },
  {
    "id": "Handlers",
    "description": "HTTP handlers",
    "contract": "Handler functions for routes",
    "requires": ["Models"],
    "produces_file": "internal/handlers/handlers.go",
    "domain_type": "handler"
  },
  {
    "id": "Main",
    "description": "Main entry point",
    "contract": "Main: setup router, start server",
    "requires": ["Handlers"],
    "produces_file": "cmd/server/main.go",
    "domain_type": "application"
  }
]
```''',
}

# Default example for unknown languages
DEFAULT_EXAMPLE = DISCOVERY_EXAMPLES[Language.PYTHON]

# Language to file extension mapping
LANGUAGE_EXTENSIONS: dict[Language, str] = {
    Language.PYTHON: "py",
    Language.TYPESCRIPT: "ts",
    Language.JAVASCRIPT: "js",
    Language.RUST: "rs",
    Language.GO: "go",
    Language.UNKNOWN: "py",
}

# Language display names
LANGUAGE_NAMES: dict[Language, str] = {
    Language.PYTHON: "Python",
    Language.TYPESCRIPT: "TypeScript",
    Language.JAVASCRIPT: "JavaScript",
    Language.RUST: "Rust",
    Language.GO: "Go",
    Language.UNKNOWN: "Python",
}


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

    # Detect language from goal to select appropriate example
    lang_result = detect_language(goal)
    language = lang_result.language
    language_name = LANGUAGE_NAMES.get(language, "Python")
    example = DISCOVERY_EXAMPLES.get(language, DEFAULT_EXAMPLE)

    # Add language hint if detected with confidence
    language_hint = ""
    if lang_result.is_confident:
        language_hint = f"""
=== DETECTED LANGUAGE: {language_name} ===

Based on your goal, this appears to be a {language_name} project.
Use appropriate file extensions and patterns for {language_name}.
"""

    return f"""GOAL: {goal}

CONTEXT:
{context_str}
{schema_section}{language_hint}
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

=== EXAMPLE ({language_name}) ===

{example}

Analysis:
- Leaves (parallel): artifacts with no requirements
- Subsequent waves: artifacts requiring previous
- Root: final artifact satisfying the goal

=== IMPORTANT: MATCH EXISTING PATTERNS ===

If the workspace context shows existing code patterns (frameworks, naming conventions,
directory structure), generate artifacts that are CONSISTENT with those patterns.
Do NOT introduce new frameworks or patterns that conflict with what already exists.

=== NOW DISCOVER ARTIFACTS FOR ===

Goal: {goal}

Output ONLY valid JSON array of artifacts (use {language_name} file extensions):"""


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
        "IMPORTANT: Use ONLY types from this schema for domain_type.",
        "Artifacts with unknown types will be rejected during validation.",
        "If no type fits well, omit domain_type rather than inventing new types.",
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
    goal: str | None = None,
) -> str:
    """Build prompt for creating artifact content.

    Args:
        artifact: Artifact specification to create
        context: Optional context with completed dependencies
        goal: Optional goal for language detection fallback

    Returns:
        Formatted creation prompt
    """
    # Determine file extension for language hints
    file_ext = ""
    if artifact.produces_file and "." in artifact.produces_file:
        file_ext = artifact.produces_file.split(".")[-1]
    else:
        # Detect language from goal if available, otherwise default to py
        if goal:
            lang_result = detect_language(goal)
            file_ext = LANGUAGE_EXTENSIONS.get(lang_result.language, "py")
        else:
            file_ext = "py"

    # Map extension to language name (expanded mapping)
    language_hint = {
        "py": "Python",
        "js": "JavaScript",
        "ts": "TypeScript",
        "tsx": "TypeScript (React)",
        "jsx": "JavaScript (React)",
        "svelte": "Svelte",
        "vue": "Vue",
        "rs": "Rust",
        "go": "Go",
        "java": "Java",
        "md": "Markdown",
        "json": "JSON",
        "yaml": "YAML",
        "yml": "YAML",
    }.get(file_ext, file_ext.upper() if file_ext else "Python")

    # Build context section
    context_section = ""
    if context and "completed" in context:
        completed_desc = "\n".join(
            f"- {aid}: {info.get('description', 'completed')}"
            for aid, info in context.get("completed", {}).items()
        )
        context_section = f"\n\nCOMPLETED DEPENDENCIES:\n{completed_desc}"

    # Determine default file path based on detected language
    default_file = f"{artifact.id.lower()}.{file_ext}"

    return f"""Create the following artifact:

ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}
CONTRACT: {artifact.contract}
FILE: {artifact.produces_file or default_file}
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
