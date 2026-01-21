# RFC-070: Lens Library & Management — Browsing, Versioning, and Customization

**Status**: Draft  
**Created**: 2026-01-21  
**Updated**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**:
- RFC-064 (Lens Management) — lens selection for projects
- RFC-043 (Sunwell Studio) — GUI framework  
- RFC-061 (Holy Light Design System) — visual styling

---

## Summary

Provide a comprehensive lens library experience in Sunwell Studio where users can browse, understand, and manage their expertise containers. This RFC extends RFC-064 (which handles lens *selection*) with:

1. **Library Browser** — Browse all lenses with filtering, search, and detailed previews
2. **Lens Detail View** — Understand what a lens does, when to use it, and see its components
3. **Default Management** — Set global and per-project defaults, see which lens is active
4. **Lens Operations** — Fork/clone, edit, delete, and create new lenses
5. **Versioning System** — Track lens versions for benchmarking and rollback

**Three-domain implementation:**
- 🐍 **Python**: Version tracking, lens CRUD operations, CLI commands
- 🦀 **Rust**: Tauri commands for library operations and file management
- 🟠 **Svelte**: Library browser UI, detail views, and management panels

---

## Motivation

### The Problem

RFC-064 enables users to *select* a lens before execution, but users have no way to:

1. **Explore** what lenses are available and what they do
2. **Understand** when to use each lens (use cases, domain expertise)
3. **Customize** lenses for their specific needs (fork and modify)
4. **Track** which lens version produced good results (for rollback/benchmarking)
5. **Organize** their lens collection (delete unused, see defaults)

### User Stories

> "I want to browse my lenses like a library and understand what each one does before picking it."

> "I want to fork the coder lens and add my team's specific heuristics without modifying the original."

> "I made a change to my lens that degraded output quality. I want to roll back to the previous version."

> "I'm benchmarking different lens configurations. I need version tracking to compare results."

### What's Already Built

| Component | Location | Current State |
|-----------|----------|---------------|
| Lens data model | `src/sunwell/core/lens.py:22-47` | ✅ `LensMetadata` with `SemanticVersion` |
| Lens discovery | `src/sunwell/naaru/expertise/discovery.py:92-151` | ✅ Finds lenses in search paths |
| Lens loader | `src/sunwell/schema/loader.py:55-253` | ✅ Parses `.lens` files |
| CLI commands | `src/sunwell/cli/lens.py` | ✅ `list`, `show`, `resolve` |
| Tauri lens commands | `studio/src-tauri/src/lens.rs:116-166` | ✅ `list_lenses`, `get_lens_detail` |
| Lens types (TS) | `studio/src/lib/types.ts:420-455` | ✅ `LensSummary`, `LensDetail` |
| Lens picker | RFC-064 design | 🔜 Modal for selection (not library) |

### CLI Command Mapping

This RFC extends the existing `sunwell lens` command group:

| Command | Status | Description |
|---------|--------|-------------|
| `lens list` | ✅ Exists | List lenses with basic info |
| `lens show <name>` | ✅ Exists | Show lens details |
| `lens resolve <goal>` | ✅ Exists | Debug lens auto-selection |
| `lens library` | 🆕 New | **Browse with filtering, sources, defaults** |
| `lens fork <source> <name>` | 🆕 New | **Create editable copy with versioning** |
| `lens save <name>` | 🆕 New | **Save changes with version bump** |
| `lens delete <name>` | 🆕 New | **Delete a user lens** |
| `lens versions <name>` | 🆕 New | **Show version history** |
| `lens rollback <name> <version>` | 🆕 New | **Restore previous version** |
| `lens set-default [name]` | 🆕 New | **Set/clear global default** |

### Non-Goals

This RFC explicitly **does not** cover:

1. **Fount marketplace** — Community lens registry is a future RFC
2. **AI-assisted lens creation** — Generating lenses from prompts is out of scope
3. **Lens composition UI** — Visual editor for `extends`/`compose` is deferred
4. **Real-time lens switching** — Changing lens mid-execution remains out of scope
5. **Lens analytics dashboard** — Effectiveness metrics visualization is deferred

---

## Design Alternatives

### Versioning Strategy

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **A: Manifest-based** (proposed) | Full control, audit trail, checksums | More complexity, custom tooling | ✅ Chosen |
| **B: Git-based** | Leverage existing tools, familiar workflow | Requires git, harder to browse history | ❌ |
| **C: Database-backed** | Fast queries, rich metadata | Dependency, migration complexity | ❌ Future option |

**Decision**: Manifest-based versioning provides the right balance:
- Works without git (user lenses may not be in repos)
- Simple JSON format, human-readable
- Supports checksums for integrity verification
- Can migrate to database later if needed

### Storage Location

| Approach | Location | Pros | Cons |
|----------|----------|------|------|
| **A: Sibling `.versions/`** (proposed) | `~/.sunwell/lenses/.versions/` | Co-located, easy backup | Directory clutter |
| **B: Separate `history/`** | `~/.sunwell/history/lenses/` | Clean separation | Split management |
| **C: In-lens embedding** | Each `.lens` file has `_versions` key | Self-contained | File bloat |

**Decision**: Sibling `.versions/` directory keeps versions co-located with lenses for easy discovery and backup, while keeping individual lens files clean.

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Disk bloat** from version history | Medium | Low | Cap at 50 versions per lens, prune on save |
| **Concurrent modification** conflicts | Low | Medium | Advisory lock on save, last-write-wins |
| **Path traversal** in lens names | Low | High | Strict slug validation, reject `../` |
| **Large lens files** (>1MB) | Low | Low | Warn on save, suggest splitting |
| **Orphaned versions** after delete | Low | Low | `keep_versions=True` default, cleanup command |
| **Invalid YAML on save** | Medium | Medium | Parse validation before write |

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LENS LIBRARY ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                    │
│  │  Lens Library   │                                                    │
│  │  (Svelte UI)    │                                                    │
│  │                 │                                                    │
│  │  ┌───────────┐  │                                                    │
│  │  │ Browser   │  │◄─── List, filter, search                          │
│  │  └───────────┘  │                                                    │
│  │  ┌───────────┐  │                                                    │
│  │  │ Detail    │  │◄─── Full lens preview                             │
│  │  └───────────┘  │                                                    │
│  │  ┌───────────┐  │                                                    │
│  │  │ Editor    │  │◄─── Fork, edit, create                            │
│  │  └───────────┘  │                                                    │
│  │  ┌───────────┐  │                                                    │
│  │  │ Versions  │  │◄─── Version history, rollback                     │
│  │  └───────────┘  │                                                    │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐     ┌─────────────────┐                           │
│  │  Tauri Backend  │     │  Python CLI     │                           │
│  │  (Rust)         │────►│  (sunwell lens) │                           │
│  │                 │     │                 │                           │
│  │  • list_lenses  │     │  • list         │                           │
│  │  • get_detail   │     │  • show         │                           │
│  │  • fork_lens    │     │  • fork         │                           │
│  │  • save_lens    │     │  • save         │                           │
│  │  • delete_lens  │     │  • delete       │                           │
│  │  • get_versions │     │  • versions     │                           │
│  │  • rollback     │     │  • rollback     │                           │
│  └─────────────────┘     └─────────────────┘                           │
│                                   │                                     │
│                                   ▼                                     │
│                          ┌─────────────────┐                           │
│                          │  Lens Storage   │                           │
│                          │                 │                           │
│                          │  ~/.sunwell/    │                           │
│                          │    lenses/      │◄─── User lenses           │
│                          │      my.lens    │                           │
│                          │      .versions/ │◄─── Version history       │
│                          │    config.yaml  │◄─── Global defaults       │
│                          └─────────────────┘                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Model Extensions

#### 1. LensMetadata Extensions (NEW)

**Current state** (`src/sunwell/core/lens.py:22-46`):
```python
@dataclass(frozen=True, slots=True)
class LensMetadata:
    name: str
    domain: str | None = None
    version: SemanticVersion = ...
    description: str | None = None
    author: str | None = None
    license: str | None = None
    compatible_schemas: tuple[str, ...] = ()  # RFC-035
```

**Proposed additions** — add these fields to `LensMetadata`:

```python
# src/sunwell/core/lens.py — ADD to LensMetadata

    # RFC-070: Library metadata for browsing/filtering
    use_cases: tuple[str, ...] = ()
    """When to use this lens (e.g., "API documentation", "Code review")"""
    
    tags: tuple[str, ...] = ()
    """Searchable tags (e.g., "python", "documentation", "testing")"""
    
    icon: str | None = None
    """Optional icon identifier for UI display"""
```

**Schema loader update** — add parsing in `_parse_metadata()` (`src/sunwell/schema/loader.py:255-277`):

```python
# src/sunwell/schema/loader.py — UPDATE _parse_metadata()

    # RFC-070: Parse library metadata
    use_cases = tuple(data.get("use_cases", []))
    tags = tuple(data.get("tags", []))
    icon = data.get("icon")
    
    return LensMetadata(
        # ... existing fields ...
        use_cases=use_cases,
        tags=tags,
        icon=icon,
    )
```

#### 2. Lens Version Tracking (NEW)

```python
# src/sunwell/core/lens.py — ADD new dataclass


@dataclass(frozen=True, slots=True)
class LensVersion:
    """A specific version snapshot of a lens."""
    
    version: SemanticVersion
    created_at: str  # ISO 8601 timestamp
    message: str | None = None  # Version message/changelog
    checksum: str | None = None  # SHA256 of lens content
```

#### 2. Lens Storage Structure

```
~/.sunwell/
├── config.yaml                    # Global config including default lens
├── lenses/
│   ├── my-custom-coder.lens       # User's custom lens
│   ├── team-standards.lens        # Another custom lens
│   └── .versions/                 # Version history
│       ├── my-custom-coder/
│       │   ├── 1.0.0.lens         # Version snapshot
│       │   ├── 1.1.0.lens
│       │   └── manifest.json      # Version metadata
│       └── team-standards/
│           └── ...
└── projects/
    └── <project>/
        └── .sunwell/
            └── config.yaml        # Project-level default lens
```

#### 3. Version Manifest Schema

```json
// ~/.sunwell/lenses/.versions/{lens-name}/manifest.json
{
  "lens_name": "my-custom-coder",
  "current_version": "1.1.0",
  "versions": [
    {
      "version": "1.0.0",
      "created_at": "2026-01-15T10:30:00Z",
      "message": "Initial fork from coder.lens",
      "checksum": "sha256:abc123...",
      "parent_lens": "coder"
    },
    {
      "version": "1.1.0",
      "created_at": "2026-01-20T14:45:00Z",
      "message": "Added team-specific Python heuristics",
      "checksum": "sha256:def456...",
      "parent_version": "1.0.0"
    }
  ]
}
```

---

## Python Implementation

### 1. Lens Manager Module

```python
# src/sunwell/lens/manager.py

"""Lens management operations (RFC-070).

Provides CRUD operations, versioning, and library functionality for lenses.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sunwell.core.lens import Lens
from sunwell.core.types import SemanticVersion
from sunwell.schema.loader import LensLoader


@dataclass(frozen=True, slots=True)
class LensVersionInfo:
    """Version metadata for a lens."""
    
    version: SemanticVersion
    created_at: str
    message: str | None
    checksum: str
    parent_lens: str | None = None
    parent_version: str | None = None


@dataclass(frozen=True, slots=True)
class LensLibraryEntry:
    """Lens with library metadata for UI display."""
    
    lens: Lens
    source: str  # "builtin", "user", "project"
    path: Path
    is_default: bool
    is_editable: bool
    version_count: int
    last_modified: str | None


@dataclass
class LensManager:
    """Manages lens library operations.
    
    Handles listing, loading, forking, editing, deleting,
    and version tracking of lenses.
    """
    
    user_lens_dir: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "lenses"
    )
    builtin_lens_dir: Path = field(
        default_factory=lambda: Path.cwd() / "lenses"
    )
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".sunwell" / "config.yaml"
    )
    
    _loader: LensLoader = field(default_factory=LensLoader, init=False)
    
    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.user_lens_dir.mkdir(parents=True, exist_ok=True)
        (self.user_lens_dir / ".versions").mkdir(exist_ok=True)
    
    # =========================================================================
    # Library Operations
    # =========================================================================
    
    async def list_library(self) -> list[LensLibraryEntry]:
        """List all lenses in the library.
        
        Returns both built-in and user lenses, sorted by source then name.
        """
        entries: list[LensLibraryEntry] = []
        default_lens = self._get_global_default()
        
        # Built-in lenses
        if self.builtin_lens_dir.exists():
            for path in self.builtin_lens_dir.glob("*.lens"):
                lens = await self._load_lens(path)
                if lens:
                    entries.append(LensLibraryEntry(
                        lens=lens,
                        source="builtin",
                        path=path,
                        is_default=lens.metadata.name == default_lens,
                        is_editable=False,
                        version_count=0,  # Built-ins don't track versions
                        last_modified=self._get_mtime(path),
                    ))
        
        # User lenses
        for path in self.user_lens_dir.glob("*.lens"):
            lens = await self._load_lens(path)
            if lens:
                version_count = self._count_versions(lens.metadata.name)
                entries.append(LensLibraryEntry(
                    lens=lens,
                    source="user",
                    path=path,
                    is_default=lens.metadata.name == default_lens,
                    is_editable=True,
                    version_count=version_count,
                    last_modified=self._get_mtime(path),
                ))
        
        # Sort: defaults first, then by source, then by name
        entries.sort(key=lambda e: (
            not e.is_default,
            0 if e.source == "user" else 1,
            e.lens.metadata.name.lower(),
        ))
        
        return entries
    
    async def get_lens_detail(self, name: str) -> Lens | None:
        """Get full lens details by name."""
        # Check user lenses first
        user_path = self.user_lens_dir / f"{name}.lens"
        if user_path.exists():
            return await self._load_lens(user_path)
        
        # Check built-in lenses
        builtin_path = self.builtin_lens_dir / f"{name}.lens"
        if builtin_path.exists():
            return await self._load_lens(builtin_path)
        
        # Try by metadata name
        for entry in await self.list_library():
            if entry.lens.metadata.name.lower() == name.lower():
                return entry.lens
        
        return None
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    async def fork_lens(
        self,
        source_name: str,
        new_name: str,
        message: str | None = None,
    ) -> Path:
        """Fork a lens to create a new editable copy.
        
        Args:
            source_name: Name of lens to fork
            new_name: Name for the new lens (used as filename)
            message: Optional message for version history
            
        Returns:
            Path to the new lens file
            
        Raises:
            ValueError: If source lens not found or new name already exists
        """
        # Find source lens
        source_lens = await self.get_lens_detail(source_name)
        if not source_lens:
            raise ValueError(f"Source lens not found: {source_name}")
        
        # Validate new name
        new_path = self.user_lens_dir / f"{self._slugify(new_name)}.lens"
        if new_path.exists():
            raise ValueError(f"Lens already exists: {new_name}")
        
        # Read source content
        source_path = source_lens.source_path
        if not source_path or not source_path.exists():
            raise ValueError(f"Cannot read source lens: {source_name}")
        
        content = source_path.read_text()
        
        # Update metadata in content
        import yaml
        data = yaml.safe_load(content)
        data["lens"]["metadata"]["name"] = new_name
        data["lens"]["metadata"]["version"] = "1.0.0"
        if "author" not in data["lens"]["metadata"]:
            data["lens"]["metadata"]["author"] = "User"
        
        # Write new lens
        new_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        new_path.write_text(new_content)
        
        # Create initial version
        self._create_version(
            lens_name=self._slugify(new_name),
            version="1.0.0",
            content=new_content,
            message=message or f"Forked from {source_name}",
            parent_lens=source_name,
        )
        
        return new_path
    
    async def save_lens(
        self,
        name: str,
        content: str,
        message: str | None = None,
        bump: str = "patch",  # "major", "minor", "patch"
    ) -> SemanticVersion:
        """Save changes to a user lens with version tracking.
        
        Args:
            name: Lens name (slug)
            content: Full YAML content
            message: Version message
            bump: Which version component to bump
            
        Returns:
            New version number
            
        Raises:
            ValueError: If lens not found or not editable
        """
        path = self.user_lens_dir / f"{name}.lens"
        if not path.exists():
            raise ValueError(f"Lens not found: {name}")
        
        # Parse to validate and get current version
        import yaml
        data = yaml.safe_load(content)
        
        # Get current version
        current_version = SemanticVersion.parse(
            data["lens"]["metadata"].get("version", "0.1.0")
        )
        
        # Bump version
        if bump == "major":
            new_version = SemanticVersion(current_version.major + 1, 0, 0)
        elif bump == "minor":
            new_version = SemanticVersion(
                current_version.major, current_version.minor + 1, 0
            )
        else:
            new_version = SemanticVersion(
                current_version.major, current_version.minor, current_version.patch + 1
            )
        
        # Update version in content
        data["lens"]["metadata"]["version"] = str(new_version)
        new_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        
        # Write file
        path.write_text(new_content)
        
        # Create version snapshot
        self._create_version(
            lens_name=name,
            version=str(new_version),
            content=new_content,
            message=message,
            parent_version=str(current_version),
        )
        
        return new_version
    
    async def delete_lens(self, name: str, keep_versions: bool = True) -> None:
        """Delete a user lens.
        
        Args:
            name: Lens name (slug)
            keep_versions: Whether to keep version history
            
        Raises:
            ValueError: If lens not found or is built-in
        """
        path = self.user_lens_dir / f"{name}.lens"
        if not path.exists():
            raise ValueError(f"Lens not found: {name}")
        
        # Delete lens file
        path.unlink()
        
        # Optionally delete version history
        if not keep_versions:
            version_dir = self.user_lens_dir / ".versions" / name
            if version_dir.exists():
                shutil.rmtree(version_dir)
    
    # =========================================================================
    # Version Operations
    # =========================================================================
    
    def get_versions(self, name: str) -> list[LensVersionInfo]:
        """Get version history for a lens."""
        manifest_path = self.user_lens_dir / ".versions" / name / "manifest.json"
        if not manifest_path.exists():
            return []
        
        data = json.loads(manifest_path.read_text())
        return [
            LensVersionInfo(
                version=SemanticVersion.parse(v["version"]),
                created_at=v["created_at"],
                message=v.get("message"),
                checksum=v["checksum"],
                parent_lens=v.get("parent_lens"),
                parent_version=v.get("parent_version"),
            )
            for v in data.get("versions", [])
        ]
    
    async def rollback(self, name: str, version: str) -> None:
        """Rollback a lens to a previous version.
        
        Args:
            name: Lens name (slug)
            version: Version to rollback to
            
        Raises:
            ValueError: If lens or version not found
        """
        version_path = self.user_lens_dir / ".versions" / name / f"{version}.lens"
        if not version_path.exists():
            raise ValueError(f"Version not found: {name}@{version}")
        
        # Copy version content to main lens file
        lens_path = self.user_lens_dir / f"{name}.lens"
        content = version_path.read_text()
        
        # Save as new version with rollback message
        await self.save_lens(
            name=name,
            content=content,
            message=f"Rolled back to version {version}",
            bump="patch",
        )
    
    # =========================================================================
    # Default Management
    # =========================================================================
    
    def get_global_default(self) -> str | None:
        """Get the global default lens name."""
        return self._get_global_default()
    
    def set_global_default(self, name: str | None) -> None:
        """Set the global default lens."""
        import yaml
        
        config = {}
        if self.config_path.exists():
            config = yaml.safe_load(self.config_path.read_text()) or {}
        
        if name:
            config["default_lens"] = name
        else:
            config.pop("default_lens", None)
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.dump(config))
    
    # =========================================================================
    # Private Helpers
    # =========================================================================
    
    def _get_global_default(self) -> str | None:
        """Get global default from config."""
        import yaml
        
        if not self.config_path.exists():
            return None
        
        config = yaml.safe_load(self.config_path.read_text()) or {}
        return config.get("default_lens")
    
    async def _load_lens(self, path: Path) -> Lens | None:
        """Load a lens from path."""
        try:
            from sunwell.core.types import LensReference
            from sunwell.fount.client import FountClient
            from sunwell.fount.resolver import LensResolver
            
            fount = FountClient()
            loader = LensLoader(fount_client=fount)
            resolver = LensResolver(loader=loader)
            
            source = str(path)
            if not source.startswith("/"):
                source = f"./{source}"
            
            ref = LensReference(source=source)
            return await resolver.resolve(ref)
        except Exception:
            return None
    
    def _create_version(
        self,
        lens_name: str,
        version: str,
        content: str,
        message: str | None,
        parent_lens: str | None = None,
        parent_version: str | None = None,
    ) -> None:
        """Create a version snapshot."""
        version_dir = self.user_lens_dir / ".versions" / lens_name
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Write version file
        version_path = version_dir / f"{version}.lens"
        version_path.write_text(content)
        
        # Update manifest
        manifest_path = version_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        else:
            manifest = {"lens_name": lens_name, "versions": []}
        
        manifest["current_version"] = version
        manifest["versions"].append({
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "checksum": f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:12]}",
            "parent_lens": parent_lens,
            "parent_version": parent_version,
        })
        
        manifest_path.write_text(json.dumps(manifest, indent=2))
    
    def _count_versions(self, name: str) -> int:
        """Count versions for a lens."""
        manifest_path = self.user_lens_dir / ".versions" / name / "manifest.json"
        if not manifest_path.exists():
            return 0
        data = json.loads(manifest_path.read_text())
        return len(data.get("versions", []))
    
    def _get_mtime(self, path: Path) -> str | None:
        """Get file modification time as ISO string."""
        try:
            mtime = path.stat().st_mtime
            return datetime.fromtimestamp(mtime, timezone.utc).isoformat()
        except OSError:
            return None
    
    def _slugify(self, name: str) -> str:
        """Convert name to filesystem-safe slug."""
        import re
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug or "lens"
```

### 2. CLI Commands — Full Experience

The CLI provides the same capabilities as Studio for terminal users:

```bash
# ════════════════════════════════════════════════════════════════
# BROWSING
# ════════════════════════════════════════════════════════════════

# List all lenses with library metadata (extends existing `lens list`)
$ sunwell lens library
┌─────────────────────────────────────────────────────────────────┐
│                          Lens Library                           │
├───┬──────────────┬────────────┬─────────┬──────────────────────┤
│   │ Name         │ Domain     │ Source  │ Description          │
├───┼──────────────┼────────────┼─────────┼──────────────────────┤
│ ★ │ coder        │ software   │ builtin │ Python development   │
│   │ tech-writer  │ docs       │ builtin │ Technical writing    │
│   │ my-coder     │ software   │ user    │ Forked from coder    │
└───┴──────────────┴────────────┴─────────┴──────────────────────┘

# Filter by source
$ sunwell lens library --filter user

# Filter by domain
$ sunwell lens library --filter documentation

# JSON output for scripting
$ sunwell lens library --json | jq '.[].name'

# ════════════════════════════════════════════════════════════════
# FORKING & EDITING
# ════════════════════════════════════════════════════════════════

# Fork a lens to create an editable copy
$ sunwell lens fork coder my-team-coder -m "Team Python standards"
✓ Forked to: ~/.sunwell/lenses/my-team-coder.lens

# Save changes (bumps version automatically)
$ sunwell lens save my-team-coder --file my-team-coder.lens -m "Added type hints heuristic"
✓ Saved my-team-coder v1.1.0

# Save with explicit version bump
$ sunwell lens save my-team-coder --file edited.lens --bump minor -m "Breaking change"
✓ Saved my-team-coder v1.2.0

# ════════════════════════════════════════════════════════════════
# VERSIONING
# ════════════════════════════════════════════════════════════════

# View version history
$ sunwell lens versions my-team-coder
Version History: my-team-coder

 → v1.2.0 (2026-01-21)
   Breaking change
   v1.1.0 (2026-01-20)
   Added type hints heuristic
   v1.0.0 (2026-01-19)
   Forked from coder

# Rollback to previous version
$ sunwell lens rollback my-team-coder 1.1.0
✓ Rolled back my-team-coder to v1.1.0

# ════════════════════════════════════════════════════════════════
# DEFAULTS
# ════════════════════════════════════════════════════════════════

# Set global default lens
$ sunwell lens set-default my-team-coder
✓ Default lens set to: my-team-coder

# Check current default
$ sunwell lens set-default
Current default: my-team-coder

# Clear default (return to auto-select)
$ sunwell lens set-default --clear
✓ Cleared default lens

# ════════════════════════════════════════════════════════════════
# DELETION
# ════════════════════════════════════════════════════════════════

# Delete a user lens (with confirmation)
$ sunwell lens delete my-team-coder
Delete lens 'my-team-coder'? [y/N]: y
✓ Deleted: my-team-coder

# Delete without confirmation
$ sunwell lens delete my-team-coder --yes
✓ Deleted: my-team-coder
```

### 3. CLI Implementation

```python
# src/sunwell/cli/lens.py (extend existing)

@lens.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--filter", "filter_by", help="Filter by: builtin, user, or domain name")
def library(json_output: bool, filter_by: str | None) -> None:
    """Browse the lens library."""
    asyncio.run(_library(json_output, filter_by))


async def _library(json_output: bool, filter_by: str | None) -> None:
    """List all lenses in the library."""
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    entries = await manager.list_library()
    
    if filter_by:
        if filter_by in ("builtin", "user"):
            entries = [e for e in entries if e.source == filter_by]
        else:
            entries = [e for e in entries if e.lens.metadata.domain == filter_by]
    
    if json_output:
        data = [
            {
                "name": e.lens.metadata.name,
                "domain": e.lens.metadata.domain,
                "version": str(e.lens.metadata.version),
                "description": e.lens.metadata.description,
                "source": e.source,
                "path": str(e.path),
                "is_default": e.is_default,
                "is_editable": e.is_editable,
                "version_count": e.version_count,
                "heuristics_count": len(e.lens.heuristics),
                "skills_count": len(e.lens.skills),
                "use_cases": list(getattr(e.lens.metadata, 'use_cases', ())),
                "tags": list(getattr(e.lens.metadata, 'tags', ())),
            }
            for e in entries
        ]
        print(json.dumps(data, indent=2))
        return
    
    # Rich table output
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    table = Table(title="Lens Library")
    table.add_column("", style="dim")  # Default indicator
    table.add_column("Name", style="cyan")
    table.add_column("Domain", style="magenta")
    table.add_column("Source")
    table.add_column("Description")
    table.add_column("Version")
    
    for entry in entries:
        default_mark = "★" if entry.is_default else ""
        source_style = "green" if entry.source == "user" else "dim"
        table.add_row(
            default_mark,
            entry.lens.metadata.name,
            entry.lens.metadata.domain or "-",
            f"[{source_style}]{entry.source}[/]",
            (entry.lens.metadata.description or "-")[:40],
            str(entry.lens.metadata.version),
        )
    
    console.print(table)


@lens.command()
@click.argument("source_name")
@click.argument("new_name")
@click.option("--message", "-m", help="Version message")
def fork(source_name: str, new_name: str, message: str | None) -> None:
    """Fork a lens to create an editable copy."""
    asyncio.run(_fork(source_name, new_name, message))


async def _fork(source_name: str, new_name: str, message: str | None) -> None:
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    try:
        path = await manager.fork_lens(source_name, new_name, message)
        console.print(f"[green]✓[/green] Forked to: {path}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command()
@click.argument("name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def versions(name: str, json_output: bool) -> None:
    """Show version history for a lens."""
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    version_list = manager.get_versions(name)
    
    if json_output:
        data = [
            {
                "version": str(v.version),
                "created_at": v.created_at,
                "message": v.message,
                "checksum": v.checksum,
            }
            for v in version_list
        ]
        print(json.dumps(data, indent=2))
        return
    
    if not version_list:
        console.print(f"No version history for: {name}")
        return
    
    console.print(f"[bold]Version History: {name}[/bold]\n")
    for v in reversed(version_list):  # Most recent first
        marker = "→" if v == version_list[-1] else " "
        console.print(f" {marker} [cyan]v{v.version}[/cyan] ({v.created_at[:10]})")
        if v.message:
            console.print(f"   {v.message}")


@lens.command()
@click.argument("name")
@click.argument("version")
def rollback(name: str, version: str) -> None:
    """Rollback a lens to a previous version."""
    asyncio.run(_rollback(name, version))


async def _rollback(name: str, version: str) -> None:
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    try:
        await manager.rollback(name, version)
        console.print(f"[green]✓[/green] Rolled back {name} to v{version}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command()
@click.argument("name")
@click.option("--file", "-f", type=click.Path(exists=True), required=True, help="Path to edited lens file")
@click.option("--message", "-m", help="Version message")
@click.option("--bump", type=click.Choice(["major", "minor", "patch"]), default="patch", help="Version bump type")
def save(name: str, file: str, message: str | None, bump: str) -> None:
    """Save changes to a user lens with version tracking.
    
    Examples:
    
        sunwell lens save my-coder --file edited.lens -m "Added heuristic"
        
        sunwell lens save my-coder --file edited.lens --bump minor
    """
    asyncio.run(_save(name, file, message, bump))


async def _save(name: str, file: str, message: str | None, bump: str) -> None:
    from pathlib import Path
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    content = Path(file).read_text()
    
    try:
        new_version = await manager.save_lens(
            name=name,
            content=content,
            message=message,
            bump=bump,
        )
        console.print(f"[green]✓[/green] Saved {name} v{new_version}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command()
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def delete(name: str, yes: bool) -> None:
    """Delete a user lens."""
    if not yes:
        if not click.confirm(f"Delete lens '{name}'?"):
            return
    
    asyncio.run(_delete(name))


async def _delete(name: str) -> None:
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    try:
        await manager.delete_lens(name)
        console.print(f"[green]✓[/green] Deleted: {name}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@lens.command(name="set-default")
@click.argument("name", required=False)
@click.option("--clear", is_flag=True, help="Clear the default lens")
def set_default(name: str | None, clear: bool) -> None:
    """Set the global default lens."""
    from sunwell.lens.manager import LensManager
    
    manager = LensManager()
    
    if clear:
        manager.set_global_default(None)
        console.print("[green]✓[/green] Cleared default lens")
    elif name:
        manager.set_global_default(name)
        console.print(f"[green]✓[/green] Default lens set to: {name}")
    else:
        current = manager.get_global_default()
        if current:
            console.print(f"Current default: [cyan]{current}[/cyan]")
        else:
            console.print("No default lens set (auto-select enabled)")
```

---

## Rust Implementation

### 1. Extended Types

```rust
// studio/src-tauri/src/lens.rs (extend existing)

/// Lens library entry for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensLibraryEntry {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub source: String,  // "builtin", "user"
    pub path: String,
    pub is_default: bool,
    pub is_editable: bool,
    pub version_count: usize,
    pub last_modified: Option<String>,
    pub heuristics_count: usize,
    pub skills_count: usize,
    pub use_cases: Vec<String>,
    pub tags: Vec<String>,
}

/// Version info for a lens.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensVersionInfo {
    pub version: String,
    pub created_at: String,
    pub message: Option<String>,
    pub checksum: String,
}

/// Result of lens fork operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForkResult {
    pub success: bool,
    pub path: String,
    pub message: String,
}

/// Result of lens save operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaveResult {
    pub success: bool,
    pub new_version: String,
    pub message: String,
}
```

### 2. New Tauri Commands

```rust
// studio/src-tauri/src/lens.rs (add commands)

/// Get lens library with full metadata.
#[tauri::command]
pub async fn get_lens_library(filter: Option<String>) -> Result<Vec<LensLibraryEntry>, String> {
    let mut args = vec!["lens", "library", "--json"];
    
    if let Some(ref f) = filter {
        args.push("--filter");
        args.push(f);
    }
    
    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to get lens library: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse lens library: {}", e))
}

/// Fork a lens to create an editable copy.
#[tauri::command]
pub async fn fork_lens(
    source_name: String,
    new_name: String,
    message: Option<String>,
) -> Result<ForkResult, String> {
    let mut args = vec!["lens", "fork", &source_name, &new_name];
    
    let msg_owned: String;
    if let Some(ref m) = message {
        msg_owned = format!("-m={}", m);
        args.push(&msg_owned);
    }
    
    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to fork lens: {}", e))?;
    
    let success = output.status.success();
    let message = if success {
        String::from_utf8_lossy(&output.stdout).to_string()
    } else {
        String::from_utf8_lossy(&output.stderr).to_string()
    };
    
    Ok(ForkResult {
        success,
        path: format!("~/.sunwell/lenses/{}.lens", new_name.to_lowercase().replace(' ', "-")),
        message,
    })
}

/// Save changes to a lens with version tracking.
#[tauri::command]
pub async fn save_lens(
    name: String,
    content: String,
    message: Option<String>,
    bump: Option<String>,
) -> Result<SaveResult, String> {
    // Write content to temp file
    let temp_path = std::env::temp_dir().join(format!("{}-edit.lens", name));
    std::fs::write(&temp_path, &content)
        .map_err(|e| format!("Failed to write temp file: {}", e))?;
    
    // Call Python CLI with the content
    let mut args = vec!["lens", "save", &name, "--file", temp_path.to_str().unwrap()];
    
    let msg_owned: String;
    if let Some(ref m) = message {
        msg_owned = format!("-m={}", m);
        args.push(&msg_owned);
    }
    
    let bump_owned: String;
    if let Some(ref b) = bump {
        bump_owned = format!("--bump={}", b);
        args.push(&bump_owned);
    }
    
    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to save lens: {}", e))?;
    
    // Clean up temp file
    let _ = std::fs::remove_file(&temp_path);
    
    let success = output.status.success();
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    
    Ok(SaveResult {
        success,
        new_version: if success { 
            // Parse version from output
            stdout.lines().find(|l| l.contains("v")).unwrap_or("").to_string()
        } else { 
            String::new() 
        },
        message: if success { stdout } else { String::from_utf8_lossy(&output.stderr).to_string() },
    })
}

/// Delete a user lens.
#[tauri::command]
pub async fn delete_lens(name: String) -> Result<(), String> {
    let output = Command::new("sunwell")
        .args(["lens", "delete", &name, "--yes"])
        .output()
        .map_err(|e| format!("Failed to delete lens: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    Ok(())
}

/// Get version history for a lens.
#[tauri::command]
pub async fn get_lens_versions(name: String) -> Result<Vec<LensVersionInfo>, String> {
    let output = Command::new("sunwell")
        .args(["lens", "versions", &name, "--json"])
        .output()
        .map_err(|e| format!("Failed to get lens versions: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse lens versions: {}", e))
}

/// Rollback a lens to a previous version.
#[tauri::command]
pub async fn rollback_lens(name: String, version: String) -> Result<(), String> {
    let output = Command::new("sunwell")
        .args(["lens", "rollback", &name, &version])
        .output()
        .map_err(|e| format!("Failed to rollback lens: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    Ok(())
}

/// Set the global default lens.
#[tauri::command]
pub async fn set_default_lens(name: Option<String>) -> Result<(), String> {
    let args: Vec<&str> = if let Some(ref n) = name {
        vec!["lens", "set-default", n]
    } else {
        vec!["lens", "set-default", "--clear"]
    };
    
    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to set default lens: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    Ok(())
}

/// Get raw lens content for editing.
#[tauri::command]
pub async fn get_lens_content(name: String) -> Result<String, String> {
    // Find lens path
    let user_path = dirs::home_dir()
        .ok_or("Could not find home directory")?
        .join(".sunwell")
        .join("lenses")
        .join(format!("{}.lens", name));
    
    if user_path.exists() {
        return std::fs::read_to_string(&user_path)
            .map_err(|e| format!("Failed to read lens: {}", e));
    }
    
    // Try builtin path
    let builtin_path = std::env::current_dir()
        .map_err(|e| e.to_string())?
        .join("lenses")
        .join(format!("{}.lens", name));
    
    if builtin_path.exists() {
        return std::fs::read_to_string(&builtin_path)
            .map_err(|e| format!("Failed to read lens: {}", e));
    }
    
    Err(format!("Lens not found: {}", name))
}
```

### 3. Register Commands

```rust
// studio/src-tauri/src/main.rs (add to invoke_handler)

.invoke_handler(tauri::generate_handler![
    // ... existing commands ...
    
    // Lens library (RFC-070)
    lens::get_lens_library,
    lens::fork_lens,
    lens::save_lens,
    lens::delete_lens,
    lens::get_lens_versions,
    lens::rollback_lens,
    lens::set_default_lens,
    lens::get_lens_content,
])
```

---

## Svelte Implementation

### 1. Extended Types

```typescript
// studio/src/lib/types.ts (add to LENS TYPES section)

// RFC-070: Extended lens library types
export interface LensLibraryEntry {
  name: string;
  domain: string | null;
  version: string;
  description: string | null;
  source: 'builtin' | 'user';
  path: string;
  is_default: boolean;
  is_editable: boolean;
  version_count: number;
  last_modified: string | null;
  heuristics_count: number;
  skills_count: number;
  use_cases: string[];
  tags: string[];
}

export interface LensVersionInfo {
  version: string;
  created_at: string;
  message: string | null;
  checksum: string;
}

export interface ForkResult {
  success: boolean;
  path: string;
  message: string;
}

export interface SaveResult {
  success: boolean;
  new_version: string;
  message: string;
}
```

### 2. Lens Library Store

```typescript
// studio/src/stores/lensLibrary.svelte.ts

/**
 * Lens Library Store — Full lens management (RFC-070)
 * 
 * Extends the basic lens store with library browsing,
 * editing, versioning, and management features.
 */

import { invoke } from '@tauri-apps/api/core';
import type { 
  LensLibraryEntry, 
  LensDetail, 
  LensVersionInfo,
  ForkResult,
  SaveResult,
} from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface LensLibraryState {
  /** All lenses in the library */
  entries: LensLibraryEntry[];
  
  /** Currently selected lens for detail view */
  selectedLens: LensLibraryEntry | null;
  
  /** Full detail of selected lens */
  detail: LensDetail | null;
  
  /** Raw YAML content for editor */
  editorContent: string | null;
  
  /** Version history for selected lens */
  versions: LensVersionInfo[];
  
  /** Filter state */
  filter: {
    source: 'all' | 'builtin' | 'user';
    domain: string | null;
    search: string;
  };
  
  /** Loading states */
  isLoading: boolean;
  isLoadingDetail: boolean;
  isLoadingVersions: boolean;
  isSaving: boolean;
  
  /** Error state */
  error: string | null;
  
  /** UI state */
  view: 'library' | 'detail' | 'editor' | 'versions';
}

function createInitialState(): LensLibraryState {
  return {
    entries: [],
    selectedLens: null,
    detail: null,
    editorContent: null,
    versions: [],
    filter: {
      source: 'all',
      domain: null,
      search: '',
    },
    isLoading: false,
    isLoadingDetail: false,
    isLoadingVersions: false,
    isSaving: false,
    error: null,
    view: 'library',
  };
}

export let lensLibrary = $state<LensLibraryState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

/** Filtered entries based on current filter state */
export const filteredEntries = $derived(() => {
  let entries = lensLibrary.entries;
  
  // Filter by source
  if (lensLibrary.filter.source !== 'all') {
    entries = entries.filter(e => e.source === lensLibrary.filter.source);
  }
  
  // Filter by domain
  if (lensLibrary.filter.domain) {
    entries = entries.filter(e => e.domain === lensLibrary.filter.domain);
  }
  
  // Filter by search
  if (lensLibrary.filter.search) {
    const q = lensLibrary.filter.search.toLowerCase();
    entries = entries.filter(e => 
      e.name.toLowerCase().includes(q) ||
      e.description?.toLowerCase().includes(q) ||
      e.tags.some(t => t.toLowerCase().includes(q))
    );
  }
  
  return entries;
});

/** Get unique domains for filter dropdown */
export const availableDomains = $derived(() => {
  const domains = new Set<string>();
  for (const entry of lensLibrary.entries) {
    if (entry.domain) domains.add(entry.domain);
  }
  return Array.from(domains).sort();
});

/** The global default lens */
export const defaultLens = $derived(() => {
  return lensLibrary.entries.find(e => e.is_default) ?? null;
});

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load the full lens library.
 */
export async function loadLibrary(): Promise<void> {
  if (lensLibrary.isLoading) return;
  
  lensLibrary.isLoading = true;
  lensLibrary.error = null;
  
  try {
    const entries = await invoke<LensLibraryEntry[]>('get_lens_library', {
      filter: null,
    });
    lensLibrary.entries = entries;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load lens library:', e);
  } finally {
    lensLibrary.isLoading = false;
  }
}

/**
 * Select a lens and load its details.
 */
export async function selectLens(entry: LensLibraryEntry): Promise<void> {
  lensLibrary.selectedLens = entry;
  lensLibrary.view = 'detail';
  lensLibrary.isLoadingDetail = true;
  
  try {
    const detail = await invoke<LensDetail>('get_lens_detail', { 
      name: entry.name 
    });
    lensLibrary.detail = detail;
  } catch (e) {
    console.error('Failed to load lens detail:', e);
    lensLibrary.detail = null;
  } finally {
    lensLibrary.isLoadingDetail = false;
  }
}

/**
 * Open the lens editor.
 */
export async function openEditor(entry: LensLibraryEntry): Promise<void> {
  if (!entry.is_editable) return;
  
  lensLibrary.selectedLens = entry;
  lensLibrary.view = 'editor';
  lensLibrary.isLoadingDetail = true;
  
  try {
    // Get the slug name from path
    const slug = entry.path.split('/').pop()?.replace('.lens', '') ?? entry.name;
    const content = await invoke<string>('get_lens_content', { name: slug });
    lensLibrary.editorContent = content;
  } catch (e) {
    console.error('Failed to load lens content:', e);
    lensLibrary.editorContent = null;
    lensLibrary.error = `Failed to load lens: ${e}`;
  } finally {
    lensLibrary.isLoadingDetail = false;
  }
}

/**
 * Save lens changes with version tracking.
 */
export async function saveLens(
  content: string,
  message?: string,
  bump: 'major' | 'minor' | 'patch' = 'patch',
): Promise<SaveResult | null> {
  if (!lensLibrary.selectedLens?.is_editable) return null;
  
  lensLibrary.isSaving = true;
  lensLibrary.error = null;
  
  try {
    const slug = lensLibrary.selectedLens.path
      .split('/').pop()?.replace('.lens', '') ?? lensLibrary.selectedLens.name;
    
    const result = await invoke<SaveResult>('save_lens', {
      name: slug,
      content,
      message: message ?? null,
      bump,
    });
    
    if (result.success) {
      // Refresh library to get updated version
      await loadLibrary();
      lensLibrary.editorContent = content;
    } else {
      lensLibrary.error = result.message;
    }
    
    return result;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to save lens:', e);
    return null;
  } finally {
    lensLibrary.isSaving = false;
  }
}

/**
 * Fork a lens to create an editable copy.
 */
export async function forkLens(
  sourceName: string,
  newName: string,
  message?: string,
): Promise<ForkResult | null> {
  lensLibrary.isSaving = true;
  lensLibrary.error = null;
  
  try {
    const result = await invoke<ForkResult>('fork_lens', {
      sourceName,
      newName,
      message: message ?? null,
    });
    
    if (result.success) {
      // Refresh library to show new lens
      await loadLibrary();
    } else {
      lensLibrary.error = result.message;
    }
    
    return result;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to fork lens:', e);
    return null;
  } finally {
    lensLibrary.isSaving = false;
  }
}

/**
 * Delete a user lens.
 */
export async function deleteLens(name: string): Promise<boolean> {
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    await invoke('delete_lens', { name: slug });
    
    // Refresh library
    await loadLibrary();
    
    // Clear selection if deleted lens was selected
    if (lensLibrary.selectedLens?.name === name) {
      lensLibrary.selectedLens = null;
      lensLibrary.view = 'library';
    }
    
    return true;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to delete lens:', e);
    return false;
  }
}

/**
 * Load version history for a lens.
 */
export async function loadVersions(name: string): Promise<void> {
  lensLibrary.isLoadingVersions = true;
  
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    const versions = await invoke<LensVersionInfo[]>('get_lens_versions', { 
      name: slug 
    });
    lensLibrary.versions = versions;
    lensLibrary.view = 'versions';
  } catch (e) {
    console.error('Failed to load versions:', e);
    lensLibrary.versions = [];
  } finally {
    lensLibrary.isLoadingVersions = false;
  }
}

/**
 * Rollback a lens to a previous version.
 */
export async function rollbackLens(name: string, version: string): Promise<boolean> {
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    await invoke('rollback_lens', { name: slug, version });
    
    // Refresh data
    await loadLibrary();
    await loadVersions(name);
    
    return true;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to rollback lens:', e);
    return false;
  }
}

/**
 * Set the global default lens.
 */
export async function setDefaultLens(name: string | null): Promise<boolean> {
  try {
    await invoke('set_default_lens', { name });
    
    // Update local state
    for (const entry of lensLibrary.entries) {
      entry.is_default = entry.name === name;
    }
    
    return true;
  } catch (e) {
    lensLibrary.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to set default lens:', e);
    return false;
  }
}

/**
 * Update filter state.
 */
export function setFilter(filter: Partial<LensLibraryState['filter']>): void {
  lensLibrary.filter = { ...lensLibrary.filter, ...filter };
}

/**
 * Navigate back to library view.
 */
export function goToLibrary(): void {
  lensLibrary.view = 'library';
  lensLibrary.selectedLens = null;
  lensLibrary.detail = null;
  lensLibrary.editorContent = null;
  lensLibrary.versions = [];
}

/**
 * Reset library state.
 */
export function resetLibrary(): void {
  Object.assign(lensLibrary, createInitialState());
}
```

### 3. Lens Library Browser Component

```svelte
<!-- studio/src/components/LensLibrary.svelte -->
<!--
  LensLibrary — Full lens library browser (RFC-070)
  
  Browse, filter, and manage lenses with detail views and editing.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';
  import { 
    lensLibrary, 
    filteredEntries,
    availableDomains,
    defaultLens,
    loadLibrary,
    selectLens,
    openEditor,
    forkLens,
    deleteLens,
    setFilter,
    setDefaultLens,
    goToLibrary,
  } from '../stores/lensLibrary.svelte';
  import LensDetailView from './LensDetailView.svelte';
  import LensEditor from './LensEditor.svelte';
  import LensVersions from './LensVersions.svelte';
  
  interface Props {
    onSelect?: (lensName: string) => void;
    showSelectButton?: boolean;
  }
  
  let { onSelect, showSelectButton = false }: Props = $props();
  
  // Fork modal state
  let showForkModal = $state(false);
  let forkSourceName = $state('');
  let forkNewName = $state('');
  let forkMessage = $state('');
  let isForkingLens = $state(false);
  
  // Delete confirmation state
  let showDeleteModal = $state(false);
  let deleteTargetName = $state('');
  
  onMount(() => {
    if (lensLibrary.entries.length === 0) {
      loadLibrary();
    }
  });
  
  function handleForkClick(sourceName: string) {
    forkSourceName = sourceName;
    forkNewName = `${sourceName}-custom`;
    forkMessage = '';
    showForkModal = true;
  }
  
  async function handleForkConfirm() {
    if (!forkNewName.trim()) return;
    
    isForkingLens = true;
    const result = await forkLens(forkSourceName, forkNewName, forkMessage || undefined);
    isForkingLens = false;
    
    if (result?.success) {
      showForkModal = false;
    }
  }
  
  function handleDeleteClick(name: string) {
    deleteTargetName = name;
    showDeleteModal = true;
  }
  
  async function handleDeleteConfirm() {
    await deleteLens(deleteTargetName);
    showDeleteModal = false;
  }
  
  function getDomainIcon(domain: string | null): string {
    const icons: Record<string, string> = {
      'software': '💻',
      'code': '💻',
      'documentation': '📝',
      'review': '🔍',
      'test': '🧪',
      'general': '🔮',
    };
    return icons[domain || 'general'] || '🔮';
  }
</script>

<div class="lens-library">
  {#if lensLibrary.view === 'library'}
    <!-- Library Browser -->
    <header class="library-header">
      <h2>Lens Library</h2>
      <p class="subtitle">Browse and manage your expertise containers</p>
    </header>
    
    <!-- Filters -->
    <div class="filters">
      <input
        type="text"
        placeholder="Search lenses..."
        class="search-input"
        bind:value={lensLibrary.filter.search}
        oninput={(e) => setFilter({ search: e.currentTarget.value })}
      />
      
      <select 
        class="filter-select"
        bind:value={lensLibrary.filter.source}
        onchange={(e) => setFilter({ source: e.currentTarget.value as any })}
      >
        <option value="all">All Sources</option>
        <option value="user">My Lenses</option>
        <option value="builtin">Built-in</option>
      </select>
      
      <select 
        class="filter-select"
        bind:value={lensLibrary.filter.domain}
        onchange={(e) => setFilter({ domain: e.currentTarget.value || null })}
      >
        <option value="">All Domains</option>
        {#each availableDomains() as domain}
          <option value={domain}>{domain}</option>
        {/each}
      </select>
    </div>
    
    <!-- Lens Grid -->
    {#if lensLibrary.isLoading}
      <div class="loading-state">Loading lenses...</div>
    {:else if lensLibrary.error}
      <div class="error-state">{lensLibrary.error}</div>
    {:else if filteredEntries().length === 0}
      <div class="empty-state">No lenses found</div>
    {:else}
      <div class="lens-grid">
        {#each filteredEntries() as entry (entry.path)}
          <div 
            class="lens-card"
            class:is-default={entry.is_default}
            class:is-user={entry.source === 'user'}
          >
            <div class="card-header">
              <span class="lens-icon">{getDomainIcon(entry.domain)}</span>
              <div class="lens-title">
                <h3>{entry.name}</h3>
                <span class="lens-version">v{entry.version}</span>
              </div>
              {#if entry.is_default}
                <span class="default-badge">Default</span>
              {/if}
            </div>
            
            <p class="lens-description">
              {entry.description || 'No description'}
            </p>
            
            <div class="lens-meta">
              <span class="meta-item" title="Heuristics">
                📋 {entry.heuristics_count}
              </span>
              <span class="meta-item" title="Skills">
                ⚡ {entry.skills_count}
              </span>
              {#if entry.version_count > 0}
                <span class="meta-item" title="Versions">
                  📚 {entry.version_count}
                </span>
              {/if}
              <span class="meta-source">{entry.source}</span>
            </div>
            
            {#if entry.tags.length > 0}
              <div class="lens-tags">
                {#each entry.tags.slice(0, 3) as tag}
                  <span class="tag">{tag}</span>
                {/each}
              </div>
            {/if}
            
            <div class="card-actions">
              <Button 
                variant="ghost" 
                size="sm"
                onclick={() => selectLens(entry)}
              >
                View
              </Button>
              
              {#if showSelectButton && onSelect}
                <Button 
                  variant="primary" 
                  size="sm"
                  onclick={() => onSelect(entry.name)}
                >
                  Select
                </Button>
              {/if}
              
              <div class="action-menu">
                <Button variant="ghost" size="sm" onclick={() => handleForkClick(entry.name)}>
                  Fork
                </Button>
                
                {#if entry.is_editable}
                  <Button variant="ghost" size="sm" onclick={() => openEditor(entry)}>
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onclick={() => handleDeleteClick(entry.name)}>
                    Delete
                  </Button>
                {/if}
                
                {#if !entry.is_default}
                  <Button variant="ghost" size="sm" onclick={() => setDefaultLens(entry.name)}>
                    Set Default
                  </Button>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
    
  {:else if lensLibrary.view === 'detail'}
    <LensDetailView onBack={goToLibrary} />
    
  {:else if lensLibrary.view === 'editor'}
    <LensEditor onBack={goToLibrary} />
    
  {:else if lensLibrary.view === 'versions'}
    <LensVersions onBack={goToLibrary} />
  {/if}
</div>

<!-- Fork Modal -->
<Modal 
  isOpen={showForkModal} 
  onClose={() => showForkModal = false} 
  title="Fork Lens"
>
  <div class="fork-modal">
    <p>Create an editable copy of <strong>{forkSourceName}</strong></p>
    
    <label class="field">
      <span>New Name</span>
      <input 
        type="text" 
        bind:value={forkNewName}
        placeholder="my-custom-lens"
      />
    </label>
    
    <label class="field">
      <span>Message (optional)</span>
      <input 
        type="text" 
        bind:value={forkMessage}
        placeholder="Initial fork from..."
      />
    </label>
    
    <div class="modal-actions">
      <Button variant="ghost" onclick={() => showForkModal = false}>
        Cancel
      </Button>
      <Button 
        variant="primary" 
        onclick={handleForkConfirm}
        disabled={isForkingLens || !forkNewName.trim()}
      >
        {isForkingLens ? 'Forking...' : 'Fork Lens'}
      </Button>
    </div>
  </div>
</Modal>

<!-- Delete Confirmation Modal -->
<Modal 
  isOpen={showDeleteModal} 
  onClose={() => showDeleteModal = false} 
  title="Delete Lens"
>
  <div class="delete-modal">
    <p>Are you sure you want to delete <strong>{deleteTargetName}</strong>?</p>
    <p class="warning">This action cannot be undone. Version history will be preserved.</p>
    
    <div class="modal-actions">
      <Button variant="ghost" onclick={() => showDeleteModal = false}>
        Cancel
      </Button>
      <Button variant="danger" onclick={handleDeleteConfirm}>
        Delete
      </Button>
    </div>
  </div>
</Modal>

<style>
  .lens-library {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--spacing-lg);
    overflow-y: auto;
  }
  
  .library-header {
    margin-bottom: var(--spacing-lg);
  }
  
  .library-header h2 {
    font-size: var(--font-xl);
    margin: 0 0 var(--spacing-xs);
  }
  
  .subtitle {
    color: var(--text-secondary);
    margin: 0;
  }
  
  .filters {
    display: flex;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
    flex-wrap: wrap;
  }
  
  .search-input {
    flex: 1;
    min-width: 200px;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
  }
  
  .search-input:focus {
    outline: none;
    border-color: var(--gold);
  }
  
  .filter-select {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    cursor: pointer;
  }
  
  .lens-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--spacing-md);
  }
  
  .lens-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--spacing-md);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    transition: all 0.15s ease;
  }
  
  .lens-card:hover {
    border-color: var(--border-default);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
  
  .lens-card.is-default {
    border-color: var(--gold);
    background: var(--gold-surface);
  }
  
  .lens-card.is-user {
    border-left: 3px solid var(--accent-green);
  }
  
  .card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }
  
  .lens-icon {
    font-size: 1.5rem;
    line-height: 1;
  }
  
  .lens-title {
    flex: 1;
    min-width: 0;
  }
  
  .lens-title h3 {
    margin: 0;
    font-size: var(--font-md);
    font-weight: 600;
  }
  
  .lens-version {
    font-size: var(--font-xs);
    color: var(--text-tertiary);
  }
  
  .default-badge {
    font-size: var(--font-xs);
    padding: 2px 6px;
    background: var(--gold);
    color: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-weight: 500;
  }
  
  .lens-description {
    color: var(--text-secondary);
    font-size: var(--font-sm);
    margin: 0;
    line-height: 1.4;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  
  .lens-meta {
    display: flex;
    gap: var(--spacing-md);
    font-size: var(--font-xs);
    color: var(--text-tertiary);
  }
  
  .meta-source {
    margin-left: auto;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .lens-tags {
    display: flex;
    gap: var(--spacing-xs);
    flex-wrap: wrap;
  }
  
  .tag {
    font-size: var(--font-xs);
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }
  
  .card-actions {
    display: flex;
    gap: var(--spacing-xs);
    margin-top: auto;
    padding-top: var(--spacing-sm);
    border-top: 1px solid var(--border-subtle);
  }
  
  .action-menu {
    display: flex;
    gap: var(--spacing-xs);
    margin-left: auto;
  }
  
  .loading-state,
  .error-state,
  .empty-state {
    padding: var(--spacing-xl);
    text-align: center;
    color: var(--text-secondary);
  }
  
  .error-state {
    color: var(--error);
  }
  
  /* Modal styles */
  .fork-modal,
  .delete-modal {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    min-width: 350px;
  }
  
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .field span {
    font-size: var(--font-sm);
    color: var(--text-secondary);
  }
  
  .field input {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
  }
  
  .field input:focus {
    outline: none;
    border-color: var(--gold);
  }
  
  .warning {
    color: var(--warning);
    font-size: var(--font-sm);
  }
  
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    padding-top: var(--spacing-md);
  }
</style>
```

---

## Implementation Plan

### Phase 1: Python Backend (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `LensManager` class | High | Medium |
| Add `lens library` CLI command | High | Small |
| Add `lens fork` CLI command | High | Medium |
| Add `lens versions` CLI command | Medium | Small |
| Add `lens rollback` CLI command | Medium | Small |
| Add `lens delete` CLI command | Medium | Small |
| Add `lens set-default` CLI command | Medium | Small |
| Add version snapshot storage | High | Medium |
| Extend `LensMetadata` with `use_cases`, `tags` | Low | Small |

### Phase 2: Rust Backend (1-2 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add `LensLibraryEntry` type | High | Small |
| Add `get_lens_library` command | High | Small |
| Add `fork_lens` command | High | Small |
| Add `save_lens` command | High | Medium |
| Add `delete_lens` command | Medium | Small |
| Add `get_lens_versions` command | Medium | Small |
| Add `rollback_lens` command | Medium | Small |
| Add `set_default_lens` command | Medium | Small |
| Add `get_lens_content` command | High | Small |

### Phase 3: Svelte Frontend (3-4 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `lensLibrary.svelte.ts` store | High | Medium |
| Create `LensLibrary.svelte` browser | High | Large |
| Create `LensDetailView.svelte` | High | Medium |
| Create `LensEditor.svelte` | Medium | Medium |
| Create `LensVersions.svelte` | Medium | Medium |
| Add library route to Studio | High | Small |
| Style with Holy Light design system | Medium | Medium |

### Phase 4: Integration (1 day)

| Task | Priority | Effort |
|------|----------|--------|
| Connect library to lens picker (RFC-064) | High | Small |
| Add library access from home screen | Medium | Small |
| Add keyboard shortcuts | Low | Small |
| Documentation | Medium | Small |

---

## Testing Strategy

### Python Tests

```python
# tests/test_lens_manager.py

@pytest.mark.asyncio
async def test_list_library():
    """Should list both builtin and user lenses."""
    manager = LensManager()
    entries = await manager.list_library()
    
    assert len(entries) > 0
    assert any(e.source == "builtin" for e in entries)


@pytest.mark.asyncio
async def test_fork_lens(tmp_path: Path):
    """Should create an editable copy with version tracking."""
    manager = LensManager(user_lens_dir=tmp_path / "lenses")
    
    path = await manager.fork_lens("coder", "my-coder", "Test fork")
    
    assert path.exists()
    assert (tmp_path / "lenses" / ".versions" / "my-coder" / "1.0.0.lens").exists()


@pytest.mark.asyncio
async def test_save_with_version_bump(tmp_path: Path):
    """Should bump version and create snapshot on save."""
    # ... setup ...
    
    new_version = await manager.save_lens(
        name="my-coder",
        content=modified_content,
        message="Added heuristic",
        bump="minor",
    )
    
    assert new_version == SemanticVersion(1, 1, 0)
    assert (tmp_path / "lenses" / ".versions" / "my-coder" / "1.1.0.lens").exists()


@pytest.mark.asyncio
async def test_rollback(tmp_path: Path):
    """Should restore previous version content."""
    # ... setup with multiple versions ...
    
    await manager.rollback("my-coder", "1.0.0")
    
    lens = await manager.get_lens_detail("my-coder")
    # Should have rolled-back content with new version number
```

### Frontend Tests

```typescript
// studio/src/stores/lensLibrary.svelte.test.ts

describe('lensLibrary store', () => {
  beforeEach(() => {
    resetLibrary();
  });
  
  it('should filter by source', () => {
    lensLibrary.entries = [
      { ...mockEntry, source: 'user' },
      { ...mockEntry, source: 'builtin' },
    ];
    setFilter({ source: 'user' });
    
    expect(filteredEntries().length).toBe(1);
    expect(filteredEntries()[0].source).toBe('user');
  });
  
  it('should search by name and tags', () => {
    lensLibrary.entries = [
      { ...mockEntry, name: 'coder', tags: ['python'] },
      { ...mockEntry, name: 'writer', tags: ['docs'] },
    ];
    setFilter({ search: 'python' });
    
    expect(filteredEntries().length).toBe(1);
    expect(filteredEntries()[0].name).toBe('coder');
  });
});
```

---

## Migration Strategy

### Existing User Lenses

User lenses in `~/.sunwell/lenses/` that predate RFC-070 will be handled gracefully:

```yaml
migration_behavior:
  existing_lens_without_versions:
    - No `.versions/` directory exists
    - First save creates initial version snapshot
    - Version set to current lens version or "1.0.0"
    - Message: "Migrated from pre-RFC-070"
  
  existing_lens_missing_new_fields:
    - `use_cases`, `tags`, `icon` default to empty/null
    - No error, fields are optional
    - User can add via editor
  
  builtin_lenses:
    - Never modified, no migration needed
    - Can be forked to user lenses
```

### Implementation

```python
# LensManager._ensure_migrated() — called on first access

def _ensure_migrated(self, name: str, lens_path: Path) -> None:
    """Ensure lens has version tracking initialized."""
    version_dir = self.user_lens_dir / ".versions" / name
    if version_dir.exists():
        return  # Already migrated
    
    # Create initial version from current state
    content = lens_path.read_text()
    self._create_version(
        lens_name=name,
        version=self._get_current_version(content),
        content=content,
        message="Migrated from pre-RFC-070",
    )
```

---

## Security Considerations

1. **Path traversal** — Validate lens names contain only safe characters via `_slugify()`
2. **Content validation** — Parse YAML before saving to catch injection attempts
3. **Read-only built-ins** — Built-in lenses cannot be modified or deleted
4. **Version limit** — Cap version history at 50 versions per lens (prevent disk bloat)
5. **Slug validation** — Reject names containing `..`, `/`, `\`, or null bytes

---

## Performance Considerations

| Operation | Expected Latency | Notes |
|-----------|------------------|-------|
| List library | ~50-100ms | File system scan |
| Load detail | ~10-30ms | Single file read + parse |
| Fork lens | ~20-50ms | File copy + version write |
| Save lens | ~30-50ms | File write + version snapshot |
| Load versions | ~10-20ms | JSON file read |

**Optimizations:**
- Cache library list for 30 seconds
- Lazy load version history (only on explicit request)
- Debounce editor autosave

---

## Open Questions & Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should version history be git-tracked? | **Excluded via `.gitignore`** | User lenses are personal; versions bloat repos |
| What happens when parent lens is deleted after fork? | **Fork continues working** | Forks are independent copies, not references |
| Version cap behavior when exceeded? | **Oldest auto-pruned on save** | FIFO deletion, warning shown to user |
| Integrate with project versioning (RFC-043)? | **Deferred** | Project versions are separate concern |

---

## Future Extensions

1. **Fount marketplace** — Browse and install community lenses
2. **Lens diff view** — Visual comparison between versions
3. **AI-assisted creation** — Generate lenses from natural language descriptions
4. **Composition editor** — Visual editor for `extends`/`compose` relationships
5. **Effectiveness analytics** — Track and compare lens performance
6. **Team sharing** — Share lenses via Git or direct export

---

## References

- RFC-064 — Lens Management (selection)
- `src/sunwell/core/lens.py` — Lens data model
- `src/sunwell/schema/loader.py` — Lens parsing
- `studio/src-tauri/src/lens.rs` — Existing Tauri commands
- `studio/src/lib/types.ts` — Existing TypeScript types
