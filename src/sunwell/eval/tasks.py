"""Built-in Evaluation Tasks (RFC-098).

Defines the standard evaluation tasks for comparing single-shot vs Sunwell.
Each task is a complex multi-file project that exercises real-world patterns.

Tasks cover different domains:
- forum_app: Web application (Flask + SQLAlchemy)
- cli_tool: Command-line tool (Click + JSON storage)
- rest_api: REST API (FastAPI + Pydantic)
- fixture_minimal: Fast CI fixture (single file)
"""

from sunwell.eval.types import FullStackTask

# =============================================================================
# BUILT-IN TASKS
# =============================================================================

FULL_STACK_TASKS: dict[str, FullStackTask] = {
    "forum_app": FullStackTask(
        name="forum_app",
        prompt="""Build a forum app with users, posts, comments, and upvotes.

Requirements:
- User registration and authentication
- Create, read, update, delete posts
- Nested comments on posts
- Upvote/downvote system
- Flask + SQLAlchemy + SQLite
""",
        description="Full-stack Flask forum application",
        available_tools=frozenset(["create_file", "read_file", "list_dir", "run_command"]),
        expected_structure={
            "src/": {
                "app.py": "required",
                "models/": "required",
                "routes/": "required",
            },
            "requirements.txt": "required",
            "tests/": "optional",
            "README.md": "optional",
        },
        expected_features=frozenset([
            "app_factory_pattern",
            "database_models",
            "crud_routes",
            "error_handling",
            "input_validation",
            "foreign_key_relationships",
        ]),
        reference_path="examples/forum_app",
        estimated_minutes=10,
    ),
    "cli_tool": FullStackTask(
        name="cli_tool",
        prompt="""Build a CLI tool for managing todo items with file persistence.

Requirements:
- Add, list, complete, delete todos
- Priority levels (low, medium, high)
- Due dates
- JSON file storage
- Click for CLI framework
""",
        description="Click-based CLI with JSON storage",
        available_tools=frozenset(["create_file", "read_file", "run_command"]),
        expected_structure={
            "cli.py": "required",
            "storage.py": "required",
            "tests/": "optional",
            "requirements.txt": "required",
        },
        expected_features=frozenset([
            "click_commands",
            "file_persistence",
            "error_handling",
            "help_text",
            "priority_support",
        ]),
        estimated_minutes=5,
    ),
    "rest_api": FullStackTask(
        name="rest_api",
        prompt="""Build a REST API for a bookstore inventory system.

Requirements:
- CRUD operations for books
- Search by title, author, ISBN
- Stock management
- FastAPI + Pydantic
- SQLite database
""",
        description="FastAPI REST API with Pydantic validation",
        available_tools=frozenset(["create_file", "read_file", "list_dir", "run_command"]),
        expected_structure={
            "main.py": "required",
            "models.py": "required",
            "routes/": "optional",
            "requirements.txt": "required",
        },
        expected_features=frozenset([
            "fastapi_app",
            "pydantic_models",
            "crud_endpoints",
            "error_handling",
            "input_validation",
            "search_functionality",
        ]),
        estimated_minutes=8,
    ),
    "fixture_minimal": FullStackTask(
        name="fixture_minimal",
        prompt="""Create a single Python file that prints hello world with proper structure.

Requirements:
- main.py with a main() function
- Proper if __name__ == "__main__" guard
- Type hints
- Docstring
""",
        description="Minimal fixture for fast CI testing",
        available_tools=frozenset(["create_file"]),
        expected_structure={
            "main.py": "required",
        },
        expected_features=frozenset([
            "main_function",
            "name_guard",
            "type_hints",
            "docstring",
        ]),
        estimated_minutes=1,
    ),
}


def get_eval_task(name: str) -> FullStackTask:
    """Get an evaluation task by name.

    Args:
        name: Task name (e.g., "forum_app") or custom prompt.

    Returns:
        FullStackTask for the given name.

    Raises:
        ValueError: If task name is not found (and not a custom prompt).
    """
    if name in FULL_STACK_TASKS:
        return FULL_STACK_TASKS[name]

    # Allow custom prompts by detecting if it's a sentence
    if len(name) > 30 or " " in name:
        return FullStackTask(
            name="custom",
            prompt=name,
            description="Custom evaluation task",
            available_tools=frozenset(["create_file", "read_file", "list_dir", "run_command"]),
            expected_structure={},
            expected_features=frozenset(),
            estimated_minutes=10,
        )

    available = ", ".join(sorted(FULL_STACK_TASKS.keys()))
    raise ValueError(
        f"Unknown task: '{name}'. Available tasks: {available}. "
        "Or provide a custom prompt as a full sentence."
    )


def list_eval_tasks() -> list[tuple[str, str, int]]:
    """List all available evaluation tasks.

    Returns:
        List of (name, description, estimated_minutes) tuples.
    """
    return [
        (task.name, task.description, task.estimated_minutes)
        for task in FULL_STACK_TASKS.values()
    ]
