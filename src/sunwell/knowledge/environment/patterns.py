"""Pattern extraction for User Environment Model (RFC-104).

Learns patterns across scanned projects to understand user conventions.
Patterns are re-extracted on each environment scan (cheap to compute).
"""


from sunwell.knowledge.environment.model import Pattern, ProjectEntry

# =============================================================================
# Pattern Extraction
# =============================================================================


def extract_patterns(projects: list[ProjectEntry]) -> list[Pattern]:
    """Learn patterns across scanned projects.

    Extracts structural and configuration patterns from the projects
    to understand user conventions.

    Args:
        projects: List of ProjectEntry objects to analyze.

    Returns:
        List of Pattern objects representing detected patterns.
    """
    if not projects:
        return []

    patterns: list[Pattern] = []

    # Structure patterns
    patterns.extend(_extract_structure_patterns(projects))

    # Configuration patterns
    patterns.extend(_extract_config_patterns(projects))

    # Tool patterns
    patterns.extend(_extract_tool_patterns(projects))

    # Filter to meaningful patterns (confidence > 0.5 or frequency >= 2)
    return [p for p in patterns if p.confidence >= 0.5 or p.frequency >= 2]


# =============================================================================
# Structure Patterns
# =============================================================================


def _extract_structure_patterns(projects: list[ProjectEntry]) -> list[Pattern]:
    """Extract directory structure patterns."""
    patterns: list[Pattern] = []
    paths = [p.path for p in projects]

    # src/ layout pattern
    src_layout = [p for p in paths if (p / "src").is_dir()]
    if len(src_layout) >= 2:
        patterns.append(
            Pattern(
                name="src_layout",
                description="Projects use src/ directory layout",
                frequency=len(src_layout),
                examples=tuple(src_layout[:5]),
                confidence=len(src_layout) / len(projects),
            )
        )

    # tests/ directory pattern
    tests_dir = [p for p in paths if (p / "tests").is_dir()]
    if len(tests_dir) >= 2:
        patterns.append(
            Pattern(
                name="tests_directory",
                description="Projects have tests/ directory",
                frequency=len(tests_dir),
                examples=tuple(tests_dir[:5]),
                confidence=len(tests_dir) / len(projects),
            )
        )

    # docs/ directory pattern
    docs_dir = [p for p in paths if (p / "docs").is_dir()]
    if len(docs_dir) >= 2:
        patterns.append(
            Pattern(
                name="docs_directory",
                description="Projects have docs/ directory",
                frequency=len(docs_dir),
                examples=tuple(docs_dir[:5]),
                confidence=len(docs_dir) / len(projects),
            )
        )

    # scripts/ directory pattern
    scripts_dir = [p for p in paths if (p / "scripts").is_dir()]
    if len(scripts_dir) >= 2:
        patterns.append(
            Pattern(
                name="scripts_directory",
                description="Projects have scripts/ directory",
                frequency=len(scripts_dir),
                examples=tuple(scripts_dir[:5]),
                confidence=len(scripts_dir) / len(projects),
            )
        )

    return patterns


# =============================================================================
# Configuration Patterns
# =============================================================================


def _extract_config_patterns(projects: list[ProjectEntry]) -> list[Pattern]:
    """Extract configuration file patterns."""
    patterns: list[Pattern] = []
    paths = [p.path for p in projects]

    # pyproject.toml pattern (Python)
    python_projects = [e for e in projects if e.project_type == "python"]
    if python_projects:
        pyproject_paths = [p.path for p in python_projects if (p.path / "pyproject.toml").exists()]
        if len(pyproject_paths) >= 2:
            patterns.append(
                Pattern(
                    name="pyproject_config",
                    description="Python projects use pyproject.toml",
                    frequency=len(pyproject_paths),
                    examples=tuple(pyproject_paths[:5]),
                    confidence=len(pyproject_paths) / len(python_projects),
                )
            )

    # README pattern
    readme_projects = [
        p for p in paths if (p / "README.md").exists() or (p / "README.rst").exists()
    ]
    if len(readme_projects) >= 2:
        patterns.append(
            Pattern(
                name="readme_present",
                description="Projects have README documentation",
                frequency=len(readme_projects),
                examples=tuple(readme_projects[:5]),
                confidence=len(readme_projects) / len(projects),
            )
        )

    # LICENSE pattern
    license_projects = [p for p in paths if (p / "LICENSE").exists() or (p / "LICENSE.md").exists()]
    if len(license_projects) >= 2:
        patterns.append(
            Pattern(
                name="license_present",
                description="Projects have LICENSE file",
                frequency=len(license_projects),
                examples=tuple(license_projects[:5]),
                confidence=len(license_projects) / len(projects),
            )
        )

    # Makefile pattern
    makefile_projects = [p for p in paths if (p / "Makefile").exists()]
    if len(makefile_projects) >= 2:
        patterns.append(
            Pattern(
                name="makefile_build",
                description="Projects use Makefile for build tasks",
                frequency=len(makefile_projects),
                examples=tuple(makefile_projects[:5]),
                confidence=len(makefile_projects) / len(projects),
            )
        )

    return patterns


# =============================================================================
# Tool Patterns
# =============================================================================


def _extract_tool_patterns(projects: list[ProjectEntry]) -> list[Pattern]:
    """Extract development tool patterns."""
    patterns: list[Pattern] = []
    paths = [p.path for p in projects]

    # Cursor rules pattern
    cursor_rules = [p for p in paths if (p / ".cursor" / "rules").is_dir()]
    if len(cursor_rules) >= 2:
        patterns.append(
            Pattern(
                name="cursor_rules",
                description="Projects have .cursor/rules/ directories",
                frequency=len(cursor_rules),
                examples=tuple(cursor_rules[:5]),
                confidence=len(cursor_rules) / len(projects),
            )
        )

    # .sunwell config pattern
    sunwell_config = [p for p in paths if (p / ".sunwell").is_dir()]
    if len(sunwell_config) >= 2:
        patterns.append(
            Pattern(
                name="sunwell_config",
                description="Projects have .sunwell/ configuration",
                frequency=len(sunwell_config),
                examples=tuple(sunwell_config[:5]),
                confidence=len(sunwell_config) / len(projects),
            )
        )

    # Git repository pattern (almost always true, but track it)
    git_repos = [e.path for e in projects if e.is_git]
    if len(git_repos) >= 2:
        patterns.append(
            Pattern(
                name="git_version_control",
                description="Projects use Git version control",
                frequency=len(git_repos),
                examples=tuple(git_repos[:5]),
                confidence=len(git_repos) / len(projects),
            )
        )

    # Pre-commit hooks pattern
    precommit = [p for p in paths if (p / ".pre-commit-config.yaml").exists()]
    if len(precommit) >= 2:
        patterns.append(
            Pattern(
                name="precommit_hooks",
                description="Projects use pre-commit hooks",
                frequency=len(precommit),
                examples=tuple(precommit[:5]),
                confidence=len(precommit) / len(projects),
            )
        )

    # CI/CD patterns
    github_actions = [p for p in paths if (p / ".github" / "workflows").is_dir()]
    if len(github_actions) >= 2:
        patterns.append(
            Pattern(
                name="github_actions",
                description="Projects use GitHub Actions CI/CD",
                frequency=len(github_actions),
                examples=tuple(github_actions[:5]),
                confidence=len(github_actions) / len(projects),
            )
        )

    return patterns


# =============================================================================
# Pattern Utilities
# =============================================================================


def get_patterns_for_project(
    project: ProjectEntry,
    all_patterns: list[Pattern],
) -> list[Pattern]:
    """Get patterns that a specific project exhibits.

    Args:
        project: The project to check.
        all_patterns: All known patterns.

    Returns:
        List of patterns this project exhibits.
    """
    return [p for p in all_patterns if project.path in p.examples]


def suggest_patterns_for_new_project(
    project_type: str,
    all_patterns: list[Pattern],
) -> list[Pattern]:
    """Suggest patterns that a new project should adopt.

    Returns high-confidence patterns for the given project type.

    Args:
        project_type: Type of project being created.
        all_patterns: All known patterns.

    Returns:
        List of patterns to suggest.
    """
    # Filter to high-confidence patterns
    return [p for p in all_patterns if p.confidence >= 0.7]
