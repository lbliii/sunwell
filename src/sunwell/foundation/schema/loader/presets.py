"""Preset handling for skill permissions (RFC-092)."""

from pathlib import Path

import yaml


def load_presets() -> dict[str, dict]:
    """Load permission presets from YAML (RFC-092).

    Presets are loaded lazily and cached. Searches for permission-presets.yaml
    in standard locations:
    1. Package skills directory
    2. Current working directory skills/
    """
    # Search paths for presets file
    search_paths: list[Path] = []

    # Check package skills directory
    from importlib.resources import files

    try:
        package_presets = files("sunwell") / "skills" / "permission-presets.yaml"
        if package_presets.is_file():
            search_paths.append(Path(str(package_presets)))
    except (ImportError, TypeError):
        pass

    # Check current working directory
    search_paths.append(Path.cwd() / "skills" / "permission-presets.yaml")
    search_paths.append(Path.cwd() / "permission-presets.yaml")

    # Find and load the file
    for path in search_paths:
        if path.exists():
            data = yaml.safe_load(path.read_text())
            return data.get("presets", {}) if data else {}

    # No presets file found - return empty dict
    return {}


def resolve_preset(skill_data: dict, presets: dict[str, dict]) -> dict:
    """Resolve preset inheritance for a skill (RFC-092).

    If skill has a preset, merge preset permissions/security into skill data.
    Skill-specific values override preset values.

    Args:
        skill_data: Raw skill dict from YAML
        presets: Presets dictionary

    Returns:
        Skill dict with resolved permissions/security
    """
    preset_name = skill_data.get("preset")
    if not preset_name:
        return skill_data

    preset = presets.get(preset_name)

    if preset is None:
        raise ValueError(
            f"Unknown permission preset: '{preset_name}'. "
            f"Available presets: {list(presets.keys())}"
        )

    # Create a copy to avoid mutating original
    resolved = dict(skill_data)

    # Merge permissions (skill overrides preset)
    if "permissions" in preset:
        preset_perms = dict(preset["permissions"])
        skill_perms = resolved.get("permissions", {})
        if skill_perms:
            deep_merge(preset_perms, skill_perms)
        resolved["permissions"] = preset_perms

    # Merge security (skill overrides preset)
    if "security" in preset:
        preset_sec = dict(preset["security"])
        skill_sec = resolved.get("security", {})
        if skill_sec:
            deep_merge(preset_sec, skill_sec)
        resolved["security"] = preset_sec

    return resolved


def deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base (mutates base).

    Used for merging skill-specific permissions into preset permissions.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
