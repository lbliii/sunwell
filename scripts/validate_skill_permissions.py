#!/usr/bin/env python
"""Validate all skills have permissions declared (directly or via preset).

RFC-092: Skill Permission Defaults validation script.

This script ensures that all built-in skills have explicit permission declarations,
either through a preset reference or direct permissions block.

Usage:
    python scripts/validate_skill_permissions.py
    python scripts/validate_skill_permissions.py --strict  # Fail on any non-compliant
    python scripts/validate_skill_permissions.py --verbose  # Show all skills
"""


import sys
from pathlib import Path

import yaml


def load_presets(skills_dir: Path) -> set[str]:
    """Load preset names from permission-presets.yaml."""
    presets_path = skills_dir / "permission-presets.yaml"
    if not presets_path.exists():
        return set()

    with open(presets_path) as f:
        data = yaml.safe_load(f) or {}

    return set(data.get("presets", {}).keys())


def validate_skills(
    skills_dir: Path, presets: set[str]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Validate all skills have permissions.

    Returns:
        (compliant_skills, non_compliant_skills) where each is a list of (file, name) tuples
    """
    compliant: list[tuple[str, str]] = []
    non_compliant: list[tuple[str, str]] = []

    for skill_file in sorted(skills_dir.glob("*.yaml")):
        if skill_file.name == "permission-presets.yaml":
            continue

        with open(skill_file) as f:
            data = yaml.safe_load(f) or {}

        for skill in data.get("skills", []):
            name = skill.get("name", "unknown")
            has_permissions = "permissions" in skill
            has_preset = skill.get("preset") in presets

            if has_permissions or has_preset:
                compliant.append((skill_file.name, name))
            else:
                non_compliant.append((skill_file.name, name))

    return compliant, non_compliant


def print_summary(
    compliant: list[tuple[str, str]],
    non_compliant: list[tuple[str, str]],
    verbose: bool = False,
) -> None:
    """Print validation summary."""
    total = len(compliant) + len(non_compliant)
    pct = (len(compliant) / total * 100) if total > 0 else 0

    print("\n📋 Skill Permission Validation (RFC-092)")
    print("=" * 60)
    print(f"Total Skills:     {total}")
    print(f"✅ Compliant:     {len(compliant)} ({pct:.1f}%)")
    print(f"❌ Non-compliant: {len(non_compliant)}")
    print()

    if non_compliant:
        print("⚠️  Skills without permissions:")
        print("-" * 60)

        # Group by file
        by_file: dict[str, list[str]] = {}
        for file, name in non_compliant:
            if file not in by_file:
                by_file[file] = []
            by_file[file].append(name)

        for file, names in sorted(by_file.items()):
            print(f"\n  {file}:")
            for name in names:
                print(f"    - {name}")

        print()
        print("💡 To fix: Add `preset: <preset-name>` to each skill")
        print("   Available presets: read-only, workspace-write, safe-shell,")
        print("                      git-read, git-write, search-only, elevated")

    if verbose and compliant:
        print("\n✅ Compliant skills:")
        print("-" * 60)

        by_file: dict[str, list[str]] = {}
        for file, name in compliant:
            if file not in by_file:
                by_file[file] = []
            by_file[file].append(name)

        for file, names in sorted(by_file.items()):
            print(f"\n  {file}:")
            for name in names:
                print(f"    - {name}")


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate skill permission declarations (RFC-092)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any skills are non-compliant",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show all skills including compliant"
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path(__file__).parent.parent / "skills",
        help="Path to skills directory",
    )
    args = parser.parse_args()

    skills_dir = args.skills_dir
    if not skills_dir.exists():
        print(f"Error: Skills directory not found: {skills_dir}")
        return 1

    presets = load_presets(skills_dir)
    if not presets:
        print("⚠️  No presets found in permission-presets.yaml")

    compliant, non_compliant = validate_skills(skills_dir, presets)
    print_summary(compliant, non_compliant, verbose=args.verbose)

    if args.strict and non_compliant:
        print("\n❌ Validation failed (--strict mode)")
        return 1

    if not non_compliant:
        print("\n✅ All skills have permissions declared!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
