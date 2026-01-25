"""SkillLibrary - Local skill storage that grows through learning (RFC-111 Phase 5).

The skill library provides:
1. Storage for learned/composed/imported skills
2. Discovery of available skills
3. Versioning and provenance tracking
4. Export to various formats (YAML, Anthropic SKILL.md)

Skills are stored in .sunwell/skills/ with this structure:
    .sunwell/skills/
    ├── learned/
    │   └── audit-api-docs/
    │       ├── SKILL.yaml
    │       └── META.yaml
    ├── composed/
    │   └── full-code-review/
    │       ├── SKILL.yaml
    │       └── META.yaml
    └── imported/
        └── external-skill/
            ├── SKILL.yaml
            └── META.yaml
"""

import re
import json
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from sunwell.planning.skills.types import (
    Skill,
    SkillDependency,
    SkillMetadata,
    SkillType,
)

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_RE_SKILL_NAME = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_RE_SKILL_DESC = re.compile(r"^#\s+.+\n\n(.+?)(?:\n\n|\Z)", re.MULTILINE | re.DOTALL)


SkillSource = Literal["learned", "composed", "imported", "builtin"]


@dataclass(frozen=True, slots=True)
class SkillProvenance:
    """Provenance information for a library skill."""

    source: SkillSource
    """How this skill was created."""

    created_at: str
    """ISO timestamp when skill was added to library."""

    version: str = "1.0.0"
    """Semantic version of the skill."""

    session_id: str | None = None
    """Session ID if learned from execution."""

    parent_skills: tuple[str, ...] = ()
    """Skills this was composed from."""

    imported_from: str | None = None
    """Path/URL if imported."""


@dataclass(slots=True)
class SkillLibrary:
    """Local skill library that grows through learning.

    Provides persistent storage for skills that are:
    - Learned: Extracted from successful sessions
    - Composed: Combined from existing skills
    - Imported: Copied from another project

    Usage:
        library = SkillLibrary(Path(".sunwell/skills"))
        
        # Save a learned skill
        path = library.save_skill(skill, source="learned", session_id="123")
        
        # Discover all skills
        skills = library.discover_skills()
        
        # Load a specific skill
        skill = library.load_skill("audit-api-docs")
    """

    library_path: Path
    """Base path for skill storage (e.g., .sunwell/skills/)."""

    _skill_cache: dict[str, Skill] = field(default_factory=dict)
    """In-memory cache of loaded skills."""

    _metadata_cache: dict[str, SkillMetadata] = field(default_factory=dict)
    """In-memory cache of skill metadata."""

    def __post_init__(self) -> None:
        """Ensure library directories exist."""
        self.library_path = Path(self.library_path)
        for source in ("learned", "composed", "imported"):
            (self.library_path / source).mkdir(parents=True, exist_ok=True)

    def save_skill(
        self,
        skill: Skill,
        source: SkillSource,
        *,
        session_id: str | None = None,
        parent_skills: tuple[str, ...] = (),
        imported_from: str | None = None,
    ) -> Path:
        """Save a skill to the library.

        Args:
            skill: The skill to save
            source: How the skill was created
            session_id: Session ID if learned
            parent_skills: Parent skill names if composed
            imported_from: Source path/URL if imported

        Returns:
            Path to the saved skill directory
        """
        # Determine directory based on source
        skill_dir = self.library_path / source / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Write SKILL.yaml
        skill_file = skill_dir / "SKILL.yaml"
        skill_data = self._skill_to_dict(skill)
        with open(skill_file, "w") as f:
            yaml.dump(skill_data, f, default_flow_style=False, sort_keys=False)

        # Write META.yaml with provenance
        meta_file = skill_dir / "META.yaml"
        provenance = SkillProvenance(
            source=source,
            created_at=datetime.now().isoformat(),
            session_id=session_id,
            parent_skills=parent_skills,
            imported_from=imported_from,
        )
        meta_data = {
            "source": provenance.source,
            "created_at": provenance.created_at,
            "version": provenance.version,
        }
        if provenance.session_id:
            meta_data["session_id"] = provenance.session_id
        if provenance.parent_skills:
            meta_data["parent_skills"] = list(provenance.parent_skills)
        if provenance.imported_from:
            meta_data["imported_from"] = provenance.imported_from

        with open(meta_file, "w") as f:
            yaml.dump(meta_data, f, default_flow_style=False)

        # Update caches
        self._skill_cache[skill.name] = skill
        self._metadata_cache[skill.name] = SkillMetadata.from_skill(skill)

        return skill_dir

    def load_skill(self, name: str) -> Skill | None:
        """Load a skill from the library by name.

        Args:
            name: Skill name

        Returns:
            The Skill if found, None otherwise
        """
        # Check cache first
        if name in self._skill_cache:
            return self._skill_cache[name]

        # Search in all source directories
        for source in ("learned", "composed", "imported"):
            skill_file = self.library_path / source / name / "SKILL.yaml"
            if skill_file.exists():
                skill = self._load_skill_from_file(skill_file)
                if skill:
                    self._skill_cache[name] = skill
                    return skill

        return None

    def load_metadata(self, name: str) -> SkillMetadata | None:
        """Load skill metadata (lightweight, for routing).

        Args:
            name: Skill name

        Returns:
            SkillMetadata if found
        """
        # Check cache
        if name in self._metadata_cache:
            return self._metadata_cache[name]

        # Try to load full skill and extract metadata
        skill = self.load_skill(name)
        if skill:
            metadata = SkillMetadata.from_skill(skill)
            self._metadata_cache[name] = metadata
            return metadata

        return None

    def discover_skills(
        self,
        source_filter: SkillSource | None = None,
    ) -> list[SkillMetadata]:
        """Discover all skills in the library.

        Args:
            source_filter: Optional filter by source type

        Returns:
            List of SkillMetadata for all discovered skills
        """
        skills: list[SkillMetadata] = []
        sources = [source_filter] if source_filter else ["learned", "composed", "imported"]

        for source in sources:
            source_dir = self.library_path / source
            if not source_dir.exists():
                continue

            for skill_dir in source_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.yaml"
                if skill_file.exists():
                    metadata = self._load_metadata_from_file(skill_file)
                    if metadata:
                        skills.append(metadata)
                        self._metadata_cache[metadata.name] = metadata

        return skills

    def list_skills(
        self,
        source_filter: SkillSource | None = None,
    ) -> list[dict]:
        """List all skills with summary info.

        Args:
            source_filter: Optional filter by source type

        Returns:
            List of dicts with skill info
        """
        result: list[dict] = []
        sources = [source_filter] if source_filter else ["learned", "composed", "imported"]

        for source in sources:
            source_dir = self.library_path / source
            if not source_dir.exists():
                continue

            for skill_dir in source_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.yaml"
                meta_file = skill_dir / "META.yaml"

                if skill_file.exists():
                    try:
                        with open(skill_file) as f:
                            data = yaml.safe_load(f)

                        meta = {}
                        if meta_file.exists():
                            with open(meta_file) as f:
                                meta = yaml.safe_load(f) or {}

                        result.append({
                            "name": data.get("name", skill_dir.name),
                            "description": data.get("description", ""),
                            "source": source,
                            "created_at": meta.get("created_at"),
                            "version": meta.get("version", "1.0.0"),
                            "path": str(skill_dir),
                        })
                    except (yaml.YAMLError, OSError):
                        continue

        return sorted(result, key=lambda s: s.get("created_at") or "", reverse=True)

    def delete_skill(self, name: str) -> bool:
        """Delete a skill from the library.

        Args:
            name: Skill name

        Returns:
            True if deleted, False if not found
        """
        import shutil

        for source in ("learned", "composed", "imported"):
            skill_dir = self.library_path / source / name
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
                self._skill_cache.pop(name, None)
                self._metadata_cache.pop(name, None)
                return True

        return False

    def get_provenance(self, name: str) -> SkillProvenance | None:
        """Get provenance information for a skill.

        Args:
            name: Skill name

        Returns:
            SkillProvenance if found
        """
        for source in ("learned", "composed", "imported"):
            meta_file = self.library_path / source / name / "META.yaml"
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        data = yaml.safe_load(f) or {}
                    return SkillProvenance(
                        source=data.get("source", source),
                        created_at=data.get("created_at", ""),
                        version=data.get("version", "1.0.0"),
                        session_id=data.get("session_id"),
                        parent_skills=tuple(data.get("parent_skills", [])),
                        imported_from=data.get("imported_from"),
                    )
                except (yaml.YAMLError, OSError):
                    continue
        return None

    def import_skill(
        self,
        source_path: Path,
        name: str | None = None,
    ) -> Skill | None:
        """Import a skill from an external path.

        Args:
            source_path: Path to SKILL.yaml or skill directory
            name: Optional name override

        Returns:
            The imported Skill if successful
        """
        # Determine the skill file
        if source_path.is_dir():
            skill_file = source_path / "SKILL.yaml"
            if not skill_file.exists():
                skill_file = source_path / "SKILL.md"
        else:
            skill_file = source_path

        if not skill_file.exists():
            return None

        # Load the skill
        if skill_file.suffix == ".yaml":
            skill = self._load_skill_from_file(skill_file)
        elif skill_file.suffix == ".md":
            skill = self._load_skill_from_markdown(skill_file)
        else:
            return None

        if not skill:
            return None

        # Override name if provided
        if name and name != skill.name:
            skill = Skill(
                name=name,
                description=skill.description,
                skill_type=skill.skill_type,
                instructions=skill.instructions,
                scripts=skill.scripts,
                templates=skill.templates,
                resources=skill.resources,
                depends_on=skill.depends_on,
                produces=skill.produces,
                requires=skill.requires,
                triggers=skill.triggers,
                allowed_tools=skill.allowed_tools,
            )

        # Save to library
        self.save_skill(
            skill,
            source="imported",
            imported_from=str(source_path),
        )

        return skill

    def _skill_to_dict(self, skill: Skill) -> dict:
        """Convert Skill to YAML-serializable dict."""
        data: dict = {
            "name": skill.name,
            "description": skill.description,
            "type": skill.skill_type.value,
        }

        if skill.instructions:
            data["instructions"] = skill.instructions

        if skill.depends_on:
            data["depends_on"] = [{"source": d.source} for d in skill.depends_on]

        if skill.produces:
            data["produces"] = list(skill.produces)

        if skill.requires:
            data["requires"] = list(skill.requires)

        if skill.triggers:
            data["triggers"] = list(skill.triggers)

        if skill.allowed_tools:
            data["allowed_tools"] = list(skill.allowed_tools)

        if skill.preset:
            data["preset"] = skill.preset

        if skill.scripts:
            data["scripts"] = [
                {"name": s.name, "content": s.content, "language": s.language}
                for s in skill.scripts
            ]

        if skill.templates:
            data["templates"] = [
                {"name": t.name, "content": t.content}
                for t in skill.templates
            ]

        return data

    def _load_skill_from_file(self, path: Path) -> Skill | None:
        """Load a Skill from SKILL.yaml."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            return self._dict_to_skill(data, path)
        except (yaml.YAMLError, OSError, ValueError):
            return None

    def _dict_to_skill(self, data: dict, source_path: Path | None = None) -> Skill:
        """Convert dict to Skill."""
        from sunwell.planning.skills.types import Script, Template

        # Parse dependencies
        depends_on: list[SkillDependency] = []
        for dep in data.get("depends_on", []):
            if isinstance(dep, str):
                depends_on.append(SkillDependency(source=dep))
            elif isinstance(dep, dict):
                depends_on.append(SkillDependency(source=dep.get("source", "")))

        # Parse scripts
        scripts: list[Script] = []
        for s in data.get("scripts", []):
            scripts.append(Script(
                name=s.get("name", "script.py"),
                content=s.get("content", ""),
                language=s.get("language", "python"),
            ))

        # Parse templates
        templates: list[Template] = []
        for t in data.get("templates", []):
            templates.append(Template(
                name=t.get("name", "template"),
                content=t.get("content", ""),
            ))

        # Determine skill type
        skill_type_str = data.get("type", "inline")
        skill_type = SkillType(skill_type_str)

        return Skill(
            name=data["name"],
            description=data.get("description", ""),
            skill_type=skill_type,
            instructions=data.get("instructions"),
            depends_on=tuple(depends_on),
            produces=tuple(data.get("produces", [])),
            requires=tuple(data.get("requires", [])),
            triggers=tuple(data.get("triggers", [])),
            allowed_tools=tuple(data.get("allowed_tools", [])),
            preset=data.get("preset"),
            scripts=tuple(scripts),
            templates=tuple(templates),
            path=str(source_path) if source_path else None,
        )

    def _load_metadata_from_file(self, path: Path) -> SkillMetadata | None:
        """Load SkillMetadata from SKILL.yaml (lightweight)."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            # Parse dependencies
            depends_on: list[SkillDependency] = []
            for dep in data.get("depends_on", []):
                if isinstance(dep, str):
                    depends_on.append(SkillDependency(source=dep))
                elif isinstance(dep, dict):
                    depends_on.append(SkillDependency(source=dep.get("source", "")))

            return SkillMetadata(
                name=data["name"],
                description=data.get("description", ""),
                skill_type=SkillType(data.get("type", "inline")),
                depends_on=tuple(depends_on),
                produces=tuple(data.get("produces", [])),
                requires=tuple(data.get("requires", [])),
                triggers=tuple(data.get("triggers", [])),
                source_path=path,
            )
        except (yaml.YAMLError, OSError, KeyError, ValueError):
            return None

    def _load_skill_from_markdown(self, path: Path) -> Skill | None:
        """Load a Skill from SKILL.md (Anthropic format)."""
        try:
            content = path.read_text()
            return self._parse_anthropic_skill_md(content, path)
        except OSError:
            return None

    def _parse_anthropic_skill_md(
        self,
        content: str,
        source_path: Path,
    ) -> Skill | None:
        """Parse Anthropic Agent Skills SKILL.md format."""
        # Extract name from first heading
        name_match = _RE_SKILL_NAME.search(content)
        if not name_match:
            return None
        name = name_match.group(1).lower().replace(" ", "-")

        # Extract description (first paragraph after heading)
        desc_match = _RE_SKILL_DESC.search(content)
        description = desc_match.group(1).strip() if desc_match else ""

        # The rest is instructions
        instructions = content

        return Skill(
            name=name,
            description=description[:200],
            skill_type=SkillType.LOCAL,
            instructions=instructions,
            path=str(source_path),
        )

    def stats(self) -> dict:
        """Get library statistics."""
        stats = {
            "total_skills": 0,
            "by_source": {},
        }

        for source in ("learned", "composed", "imported"):
            source_dir = self.library_path / source
            if source_dir.exists():
                count = sum(1 for d in source_dir.iterdir() if d.is_dir())
                stats["by_source"][source] = count
                stats["total_skills"] += count

        return stats
