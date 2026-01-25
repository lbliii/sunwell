"""User Environment Model (RFC-104).

Sunwell learns where users keep their projects, what patterns exist
across them, and which projects represent "gold standards" worth
learning from.

Usage:
    from sunwell.knowledge.environment import (
        load_environment,
        save_environment,
        discover_roots,
        discover_projects_in_root,
        extract_patterns,
        suggest_references,
    )

    # Load existing or create new
    env = load_environment()

    # Discover new projects
    roots = discover_roots()
    for root in roots:
        projects = discover_projects_in_root(root.path)
        env.roots.append(root)
        env.projects.extend(projects)

    # Extract patterns
    env.patterns = extract_patterns(env.projects)

    # Suggest references
    refs = suggest_references(env.projects)
    for category, path in refs.items():
        env.set_reference(category, path)

    # Save
    save_environment(env)
"""

from sunwell.knowledge.environment.discovery import (
    create_project_entry_from_path,
    discover_projects_in_root,
    discover_roots,
)
from sunwell.knowledge.environment.model import (
    Pattern,
    ProjectEntry,
    ProjectRoot,
    UserEnvironment,
)
from sunwell.knowledge.environment.patterns import (
    extract_patterns,
    get_patterns_for_project,
    suggest_patterns_for_new_project,
)
from sunwell.knowledge.environment.references import (
    add_reference,
    check_reference_health,
    find_similar_references,
    get_reference_for_new_project,
    list_references,
    remove_reference,
    suggest_references,
)
from sunwell.knowledge.environment.storage import (
    clear_cache,
    environment_exists,
    export_environment,
    get_environment_age,
    get_environment_path,
    import_environment,
    load_environment,
    reset_environment,
    save_environment,
)

__all__ = [
    # Models
    "UserEnvironment",
    "ProjectEntry",
    "ProjectRoot",
    "Pattern",
    # Discovery
    "discover_roots",
    "discover_projects_in_root",
    "create_project_entry_from_path",
    # Patterns
    "extract_patterns",
    "get_patterns_for_project",
    "suggest_patterns_for_new_project",
    # References
    "suggest_references",
    "check_reference_health",
    "add_reference",
    "remove_reference",
    "list_references",
    "get_reference_for_new_project",
    "find_similar_references",
    # Storage
    "load_environment",
    "save_environment",
    "reset_environment",
    "clear_cache",
    "get_environment_path",
    "environment_exists",
    "get_environment_age",
    "export_environment",
    "import_environment",
]
