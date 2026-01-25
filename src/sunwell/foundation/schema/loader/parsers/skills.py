"""Skills parsing (RFC-011, RFC-070, RFC-092)."""

from pathlib import Path

from sunwell.foundation.utils import safe_yaml_load
from sunwell.planning.skills.types import (
    Resource,
    Script,
    Skill,
    SkillRetryPolicy,
    SkillType,
    SkillValidation,
    Template,
    TrustLevel,
)


def parse_skills(
    data: list[dict],
    base_path: Path | None,
    resolve_preset_fn,
    parse_skill_fn,
) -> tuple[Skill, ...]:
    """Parse list of skills, supporting includes from external files.

    Skills can be:
    - Inline skill definitions (dict with 'name', 'description', etc.)
    - Include directives (dict with 'include' key pointing to skill file)

    Example:
        skills:
          - include: core-skills.yaml    # Load all skills from file
          - include: core-skills.yaml::search-codebase  # Load specific skill
          - name: custom-skill           # Inline skill
            description: My custom skill
    """
    skills = []
    for s in data:
        if "include" in s:
            # Include directive - load from external file
            include_path = s["include"]
            included = load_skill_include(include_path, base_path, parse_skill_fn)
            skills.extend(included)
        else:
            # Regular skill definition
            skill = parse_skill_fn(s)
            skills.append(skill)
    return tuple(skills)


def load_skill_include(
    include_ref: str,
    base_path: Path | None,
    parse_skill_fn,
) -> list[Skill]:
    """Load skills from an external file.

    Supports:
    - "core-skills.yaml" - load all skills from file
    - "core-skills.yaml::skill-name" - load specific skill by name
    - "core-skills.yaml::skill1,skill2" - load multiple specific skills
    """
    # Parse include reference
    if "::" in include_ref:
        file_path, skill_filter = include_ref.split("::", 1)
        skill_names = {s.strip() for s in skill_filter.split(",")}
    else:
        file_path = include_ref
        skill_names = None  # Load all

    # Resolve path relative to base_path (lens directory) or skills directory
    search_paths = []
    if base_path:
        search_paths.append(base_path / file_path)
        search_paths.append(base_path.parent / "skills" / file_path)

    # Also check the standard skills directory
    from importlib.resources import files
    try:
        package_skills = files("sunwell") / "skills" / file_path
        if package_skills.is_file():
            search_paths.append(Path(str(package_skills)))
    except (ImportError, TypeError):
        pass

    # Add current working directory
    search_paths.append(Path.cwd() / file_path)
    search_paths.append(Path.cwd() / "skills" / file_path)

    # Find the file
    skill_file = None
    for p in search_paths:
        if p.exists():
            skill_file = p
            break

    if not skill_file:
        raise ValueError(
            f"Skill include not found: {include_ref}. "
            f"Searched: {[str(p) for p in search_paths]}"
        )

    # Load and parse the skill file
    skill_data = safe_yaml_load(skill_file)

    # The file should have a 'skills' key
    if "skills" not in skill_data:
        raise ValueError(
            f"Skill file {skill_file} must have a 'skills' key"
        )

    # Parse skills from the file
    all_skills = []
    for s in skill_data["skills"]:
        skill = parse_skill_fn(s)
        all_skills.append(skill)

    # Filter if specific skills requested
    if skill_names:
        all_skills = [s for s in all_skills if s.name in skill_names]
        missing = skill_names - {s.name for s in all_skills}
        if missing:
            raise ValueError(
                f"Skills not found in {skill_file}: {missing}"
            )

    return all_skills


def parse_skill(data: dict, resolve_preset_fn) -> Skill:
    """Parse a single skill definition.

    RFC-070: Also parses triggers for automatic skill discovery.
    RFC-092: Resolves preset inheritance for permissions/security.
    """
    # RFC-092: Resolve preset inheritance first
    resolved_data = resolve_preset_fn(data)

    # Determine skill type
    skill_type_str = resolved_data.get("type", "inline")
    skill_type = SkillType(skill_type_str)

    # Parse trust level
    trust_str = resolved_data.get("trust", "sandboxed")
    trust = TrustLevel(trust_str)

    # RFC-070: Parse triggers for automatic discovery
    triggers = resolved_data.get("triggers", [])
    if isinstance(triggers, str):
        triggers = triggers.split()
    triggers = tuple(triggers)

    # Parse scripts
    scripts = ()
    if "scripts" in resolved_data:
        scripts = tuple(
            Script(
                name=sc["name"],
                content=sc["content"],
                language=sc.get("language", "python"),
                description=sc.get("description"),
            )
            for sc in resolved_data["scripts"]
        )

    # Parse templates
    templates = ()
    if "templates" in resolved_data:
        templates = tuple(
            Template(
                name=t["name"],
                content=t["content"],
            )
            for t in resolved_data["templates"]
        )

    # Parse resources
    resources = ()
    if "resources" in resolved_data:
        resources = tuple(
            Resource(
                name=r["name"],
                url=r.get("url"),
                path=r.get("path"),
            )
            for r in resolved_data["resources"]
        )

    # Parse validation binding
    validate_with = SkillValidation()
    if "validate_with" in resolved_data:
        vw = resolved_data["validate_with"]
        validate_with = SkillValidation(
            validators=tuple(vw.get("validators", [])),
            personas=tuple(vw.get("personas", [])),
            min_confidence=vw.get("min_confidence", 0.7),
        )

    # Parse allowed_tools (can be space-delimited string or list)
    allowed_tools = resolved_data.get("allowed_tools", [])
    if isinstance(allowed_tools, str):
        allowed_tools = allowed_tools.split()
    allowed_tools = tuple(allowed_tools)

    # RFC-092: Get preset name and resolved permissions/security
    preset_name = data.get("preset")  # Original data has preset name
    permissions = resolved_data.get("permissions")
    security = resolved_data.get("security")

    return Skill(
        name=resolved_data["name"],
        description=resolved_data["description"],
        skill_type=skill_type,
        preset=preset_name,
        triggers=triggers,
        permissions=permissions,
        security=security,
        compatibility=resolved_data.get("compatibility"),
        allowed_tools=allowed_tools,
        instructions=resolved_data.get("instructions"),
        scripts=scripts,
        templates=templates,
        resources=resources,
        source=resolved_data.get("source"),
        path=resolved_data.get("path"),
        trust=trust,
        timeout=resolved_data.get("timeout", 30),
        override=resolved_data.get("override", False),
        validate_with=validate_with,
    )


def parse_skill_retry(data: dict) -> SkillRetryPolicy:
    """Parse skill retry policy."""
    return SkillRetryPolicy(
        max_attempts=data.get("max_attempts", 3),
        backoff_ms=tuple(data.get("backoff_ms", [100, 500, 2000])),
        retry_on=tuple(data.get("retry_on", ["timeout", "validation_failure"])),
        abort_on=tuple(data.get("abort_on", ["security_violation", "script_crash"])),
    )
