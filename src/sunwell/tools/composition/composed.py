"""Composed tool definitions.

Provides:
- ToolStep: A single step in a composed tool
- ComposedTool: A tool composed of multiple steps
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolStep:
    """A single step in a composed tool.

    Arguments can include template variables like {module_path} that will
    be substituted from the composed tool's input arguments.

    Example:
        ToolStep("write_file", {"path": "{base_path}/config.json", "content": "{config}"})
    """

    tool_name: str
    """Name of the tool to call."""

    arguments: dict[str, Any]
    """Arguments template. Use {var} for substitution from input args."""

    condition: str | None = None
    """Optional condition expression. Step runs only if condition evaluates to true.
    Example: "file_exists" or "not skip_init"
    """

    rollback_tool: str | None = None
    """Tool to call for rollback (default: inferred from tool_name)."""

    rollback_arguments: dict[str, Any] | None = None
    """Arguments for rollback tool."""

    def get_resolved_arguments(self, input_args: dict[str, Any]) -> dict[str, Any]:
        """Resolve template variables in arguments.

        Args:
            input_args: Input arguments to substitute

        Returns:
            Arguments with templates resolved
        """
        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # Simple template substitution
                result = value
                for key, val in input_args.items():
                    result = result.replace(f"{{{key}}}", str(val))
                return result
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value

        return {k: resolve_value(v) for k, v in self.arguments.items()}

    def should_run(self, input_args: dict[str, Any]) -> bool:
        """Check if this step should run based on condition.

        Args:
            input_args: Input arguments for condition evaluation

        Returns:
            True if step should run
        """
        if self.condition is None:
            return True

        # Simple condition evaluation
        # Supports: "var", "not var", "var == value", "var != value"
        condition = self.condition.strip()

        if condition.startswith("not "):
            var_name = condition[4:].strip()
            return not input_args.get(var_name, False)

        if "==" in condition:
            var_name, expected = [x.strip() for x in condition.split("==", 1)]
            actual = str(input_args.get(var_name, ""))
            return actual == expected.strip("'\"")

        if "!=" in condition:
            var_name, expected = [x.strip() for x in condition.split("!=", 1)]
            actual = str(input_args.get(var_name, ""))
            return actual != expected.strip("'\"")

        # Simple truthy check
        return bool(input_args.get(condition, False))


@dataclass(frozen=True, slots=True)
class ComposedTool:
    """A tool composed of multiple atomic operations.

    Composed tools execute a sequence of steps as a single operation.
    If rollback_on_failure is True and a step fails, previous steps
    are rolled back in reverse order.

    Example:
        create_package = ComposedTool(
            name="create_package",
            description="Create a Python package with standard structure",
            steps=(
                ToolStep("mkdir", {"path": "{package_path}"}),
                ToolStep("write_file", {
                    "path": "{package_path}/__init__.py",
                    "content": '"""Package {name}."""\\n'
                }),
                ToolStep("write_file", {
                    "path": "{package_path}/py.typed",
                    "content": ""
                }),
            ),
            parameters={
                "type": "object",
                "properties": {
                    "package_path": {"type": "string", "description": "Path for the package"},
                    "name": {"type": "string", "description": "Package name"},
                },
                "required": ["package_path", "name"],
            },
            rollback_on_failure=True,
        )
    """

    name: str
    """Name of the composed tool."""

    description: str
    """Description of what the tool does."""

    steps: tuple[ToolStep, ...]
    """Sequence of steps to execute."""

    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    """JSON Schema for input parameters."""

    rollback_on_failure: bool = True
    """Whether to rollback completed steps if a step fails."""

    stop_on_error: bool = True
    """Whether to stop execution on first error (vs. continue and report)."""

    def get_rollback_actions(self, completed_steps: list[tuple[ToolStep, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
        """Get rollback actions for completed steps.

        Args:
            completed_steps: List of (step, resolved_args) tuples that completed

        Returns:
            List of (tool_name, args) tuples for rollback in reverse order
        """
        rollback_actions: list[tuple[str, dict[str, Any]]] = []

        for step, resolved_args in reversed(completed_steps):
            if step.rollback_tool:
                # Explicit rollback defined
                rollback_args = step.rollback_arguments or resolved_args
                rollback_actions.append((step.rollback_tool, rollback_args))
            else:
                # Infer rollback from tool type
                if step.tool_name == "write_file":
                    # Rollback: delete the file
                    rollback_actions.append(("delete_file", {"path": resolved_args["path"]}))
                elif step.tool_name == "mkdir":
                    # Note: Can't easily rollback mkdir if files were created inside
                    # Just skip - this is a known limitation
                    pass
                elif step.tool_name == "copy_file":
                    # Rollback: delete the copy
                    rollback_actions.append(("delete_file", {"path": resolved_args["destination"]}))
                elif step.tool_name == "rename_file":
                    # Rollback: rename back
                    rollback_actions.append(("rename_file", {
                        "source": resolved_args["destination"],
                        "destination": resolved_args["source"],
                    }))
                # Other tools don't have obvious rollbacks

        return rollback_actions


# =============================================================================
# Built-in Composed Tools
# =============================================================================

CREATE_MODULE = ComposedTool(
    name="create_module",
    description="Create a Python module directory with __init__.py",
    steps=(
        ToolStep("mkdir", {"path": "{module_path}"}),
        ToolStep("write_file", {
            "path": "{module_path}/__init__.py",
            "content": '"""{module_name} module."""\n',
        }),
    ),
    parameters={
        "type": "object",
        "properties": {
            "module_path": {"type": "string", "description": "Path for the module directory"},
            "module_name": {"type": "string", "description": "Module name for docstring"},
        },
        "required": ["module_path", "module_name"],
    },
)

CREATE_PACKAGE = ComposedTool(
    name="create_package",
    description="Create a Python package with standard structure (src layout)",
    steps=(
        ToolStep("mkdir", {"path": "{package_path}"}),
        ToolStep("write_file", {
            "path": "{package_path}/__init__.py",
            "content": '"""{package_name} - {description}"""\n\n__version__ = "0.1.0"\n',
        }),
        ToolStep("write_file", {
            "path": "{package_path}/py.typed",
            "content": "",
        }),
    ),
    parameters={
        "type": "object",
        "properties": {
            "package_path": {"type": "string", "description": "Path for the package"},
            "package_name": {"type": "string", "description": "Package name"},
            "description": {"type": "string", "description": "Package description", "default": "A Python package"},
        },
        "required": ["package_path", "package_name"],
    },
)

RENAME_WITH_BACKUP = ComposedTool(
    name="rename_with_backup",
    description="Rename a file, keeping a backup of the original",
    steps=(
        ToolStep("copy_file", {"source": "{source}", "destination": "{source}.backup"}),
        ToolStep("rename_file", {"source": "{source}", "destination": "{destination}"}),
    ),
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source file path"},
            "destination": {"type": "string", "description": "Destination file path"},
        },
        "required": ["source", "destination"],
    },
)

# Registry of built-in composed tools
BUILTIN_COMPOSED_TOOLS: dict[str, ComposedTool] = {
    CREATE_MODULE.name: CREATE_MODULE,
    CREATE_PACKAGE.name: CREATE_PACKAGE,
    RENAME_WITH_BACKUP.name: RENAME_WITH_BACKUP,
}
