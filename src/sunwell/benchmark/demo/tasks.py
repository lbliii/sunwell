"""Built-in demo tasks for showcasing the Prism Principle (RFC-095).

Each task is designed to produce poor single-shot results but excellent
results when processed through Sunwell's cognitive architecture.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemoTask:
    """A pre-defined demo task.

    Attributes:
        name: Short identifier for the task.
        prompt: The prompt sent to the model.
        description: Human-readable description for display.
        expected_features: Set of quality features expected in good output.
    """

    name: str
    prompt: str
    description: str
    expected_features: frozenset[str]


# =============================================================================
# Built-in Tasks
# =============================================================================

BUILTIN_TASKS: dict[str, DemoTask] = {
    "divide": DemoTask(
        name="divide",
        prompt="Write a Python function to divide two numbers",
        description="Division with error handling",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "zero_division_handling",
            "type_validation",
        ]),
    ),
    "add": DemoTask(
        name="add",
        prompt="Write a Python function to add two numbers",
        description="Addition with proper types",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "type_validation",
        ]),
    ),
    "sort": DemoTask(
        name="sort",
        prompt="Write a Python function to sort a list of numbers",
        description="Sorting with edge case handling",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "empty_list_handling",
            "type_validation",
        ]),
    ),
    "fibonacci": DemoTask(
        name="fibonacci",
        prompt="Write a Python function to calculate the nth fibonacci number",
        description="Fibonacci with optimization",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "negative_input_handling",
            "memoization_or_iteration",
        ]),
    ),
    "validate_email": DemoTask(
        name="validate_email",
        prompt="Write a Python function to validate an email address",
        description="Email validation with edge cases",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "regex_pattern",
            "edge_case_handling",
        ]),
    ),
}


def get_task(name_or_prompt: str) -> DemoTask:
    """Get a demo task by name or create a custom task from a prompt.

    Args:
        name_or_prompt: Either a built-in task name or a custom prompt string.

    Returns:
        DemoTask instance.

    Examples:
        >>> get_task("divide")  # Built-in task
        >>> get_task("Write a function to parse JSON")  # Custom task
    """
    # Check for built-in task
    if name_or_prompt in BUILTIN_TASKS:
        return BUILTIN_TASKS[name_or_prompt]

    # Create custom task with generic expected features
    return DemoTask(
        name="custom",
        prompt=name_or_prompt,
        description="Custom task",
        expected_features=frozenset([
            "type_hints",
            "docstring",
            "error_handling",
        ]),
    )


def list_tasks() -> list[str]:
    """List all available built-in task names."""
    return list(BUILTIN_TASKS.keys())
