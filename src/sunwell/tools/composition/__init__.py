"""Tool composition framework for multi-step workflows.

Enables creating higher-level tools composed of multiple atomic operations
with automatic rollback on failure.

Example:
    # Define a composed tool
    create_module = ComposedTool(
        name="create_module",
        description="Create a Python module with __init__.py",
        steps=(
            ToolStep("mkdir", {"path": "{module_path}"}),
            ToolStep("write_file", {"path": "{module_path}/__init__.py", "content": ""}),
        ),
        rollback_on_failure=True,
    )

    # Execute
    executor = ComposedToolExecutor(tool_executor)
    result = await executor.execute(create_module, {"module_path": "src/mymodule"})
"""

from sunwell.tools.composition.composed import (
    BUILTIN_COMPOSED_TOOLS,
    CREATE_MODULE,
    CREATE_PACKAGE,
    RENAME_WITH_BACKUP,
    ComposedTool,
    ToolStep,
)
from sunwell.tools.composition.executor import (
    ComposedResult,
    ComposedToolExecutor,
    StepResult,
)

__all__ = [
    # Core types
    "ComposedTool",
    "ToolStep",
    # Executor
    "ComposedToolExecutor",
    "ComposedResult",
    "StepResult",
    # Built-in tools
    "BUILTIN_COMPOSED_TOOLS",
    "CREATE_MODULE",
    "CREATE_PACKAGE",
    "RENAME_WITH_BACKUP",
]
