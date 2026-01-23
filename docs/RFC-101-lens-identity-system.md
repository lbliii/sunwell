# RFC-101: Sunwell Identity System

**Status**: Implemented ✅  
**Author**: Lawrence Lane  
**Created**: 2026-01-23  
**Implemented**: 2026-01-23  
**Target Version**: v0.4 (Phase 1), v0.5 (Phase 2)  
**Confidence**: 90%  
**Depends On**: RFC-070 (Lens Library Management)  
**Evidence**: `src/sunwell/core/identity.py`, `src/sunwell/lens/identity.py`, `src/sunwell/binding/identity.py`, `src/sunwell/simulacrum/identity.py`

---

## Summary

Introduce a unified identity system (`SunwellURI`) that prevents name clashes, enables cross-device sync, and provides efficient resolution across **lenses**, **bindings**, and **sessions**. The current slug-based identity has fundamental limitations that cause problems at scale.

**Phased delivery**:

| Phase | Scope | Target | Timeline |
|-------|-------|--------|----------|
| **1** | `SunwellURI` core + Lens identity | v0.4 | 4 weeks |
| **2** | Binding + Session identity | v0.5 | 2 weeks |
| **Deferred** | Spells, Projects | Future | TBD |

**Core changes**:

1. **Canonical URIs**: `sunwell:lens/builtin/tech-writer@2.0.0` vs `sunwell:binding/myproject/writer`
2. **Content-addressable versioning**: SHA256 checksums for lens versions (Phase 1)
3. **Namespace isolation**: Built-in, user, and project resources can share slugs without collision
4. **Lazy loading**: Index-based lookups, not filesystem scans

**Performance targets**:

- Library list: <50ms for 1000 lenses
- Version history: <20ms for 50 versions
- Resource resolution: <10ms with warm cache

---

## Motivation

### The Identity Problem (Systemic)

The same anti-pattern exists across **5 subsystems**:

| Subsystem | Current Identity | Problem |
|-----------|------------------|---------|
| **Lenses** | `{slug}.lens` | User shadows builtin silently |
| **Bindings** | `{name}.json` | No namespace, no UUID |
| **Sessions** | `{name}_dag.json` | Cross-project collision |
| **Spells** | `{incantation}` | Cannot target specific layer |
| **Projects** | `{path}` | Move folder = lose identity |

### Evidence: Lens Shadowing (Critical)

```python
# src/sunwell/lens/manager.py:151-168
async def get_lens_detail(self, name: str) -> Lens | None:
    # Check user lenses first (by slug)
    user_path = self.user_lens_dir / f"{name}.lens"
    if user_path.exists():
        return self._load_lens_sync(user_path)  # User ALWAYS wins
    
    # Built-in is NEVER returned if user has same slug
    builtin_path = self.builtin_lens_dir / f"{name}.lens"
```

**Scenario**: User forks `tech-writer` to customize it, names it `tech-writer`. Now:

- Built-in `tech-writer` is invisible
- Updates to built-in never reach user
- No warning this happened

### Evidence: Session Collision

```python
# src/sunwell/simulacrum/core/store.py:300-304
def new_session(self, name: str | None = None) -> str:
    self._session_id = name or datetime.now().strftime("%Y%m%d_%H%M%S")
    return self._session_id
```

**Problem**: Project A's "debug" session collides with Project B's "debug" session in shared memory store.

### Evidence: Binding Fragility

```python
# src/sunwell/binding.py:219-224
def get(self, name: str) -> Binding | None:
    path = self.bindings_dir / f"{name}.json"
    if not path.exists():
        return None
    return Binding.load(path)
```

**Problem**: No UUID means renaming a binding creates a new identity. Cross-device sync impossible.

### What We Need

1. **Explicit namespacing**: `builtin:tech-writer` is not `user:tech-writer`
2. **Stable identity**: UUID that survives renames/moves
3. **Efficient indexing**: No re-scanning filesystem every operation
4. **Version pinning**: Reference exact version for reproducibility (lenses only)

---

## Design

### Part 1: Core Infrastructure

A unified URI scheme for all identifiable resources:

```
sunwell:<resource_type>/<namespace>/<slug>[@<version>]
```

| Component | Format | Required | Examples |
|-----------|--------|----------|----------|
| **Resource Type** | `lens`, `binding`, `session` | Yes | Fixed set |
| **Namespace** | `builtin`, `user`, `project`, or project slug | Yes | Context-dependent |
| **Slug** | `[a-z0-9-]+` | Yes | Filesystem-safe |
| **Version** | Semver, `latest`, or `sha:` prefix | No | Lenses only |

**Examples**:

```
sunwell:lens/builtin/tech-writer@2.0.0      # Built-in lens, exact version
sunwell:lens/user/my-custom-writer@latest   # User lens, current version
sunwell:lens/myproject/team-standards       # Project lens (implicit @latest)
sunwell:lens/builtin/coder@sha:a1b2c3       # Content-addressed (immutable)

sunwell:binding/myproject/writer            # Binding in project
sunwell:binding/global/default-writer       # Global binding

sunwell:session/myproject/debug             # Session scoped to project
sunwell:session/myproject/20260123_143022   # Auto-generated session name
```

#### Base Implementation

```python
# src/sunwell/core/identity.py (NEW)

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ResourceType = Literal["lens", "binding", "session"]
Namespace = Literal["builtin", "user", "project", "global"] | str


@dataclass(frozen=True, slots=True)
class SunwellURI:
    """Canonical resource identifier."""
    
    resource_type: ResourceType
    namespace: str
    slug: str
    version: str | None = None  # Only meaningful for lenses
    
    @classmethod
    def parse(cls, uri: str) -> "SunwellURI":
        """Parse 'sunwell:type/namespace/slug[@version]'."""
        if not uri.startswith("sunwell:"):
            raise ValueError(f"Invalid URI scheme: {uri}")
        
        rest = uri[8:]  # Remove "sunwell:"
        
        # Extract version if present
        if "@" in rest:
            path, version = rest.rsplit("@", 1)
        else:
            path, version = rest, None
        
        parts = path.split("/")
        if len(parts) < 3:
            raise ValueError(f"Invalid URI format: {uri}")
        
        return cls(
            resource_type=parts[0],
            namespace=parts[1],
            slug="/".join(parts[2:]),  # Allow nested slugs
            version=version,
        )
    
    def __str__(self) -> str:
        base = f"sunwell:{self.resource_type}/{self.namespace}/{self.slug}"
        return f"{base}@{self.version}" if self.version else base
    
    @property
    def is_builtin(self) -> bool:
        return self.namespace == "builtin"
    
    @property
    def is_versioned(self) -> bool:
        return self.version is not None and self.version != "latest"
    
    def with_version(self, version: str) -> "SunwellURI":
        """Return new URI with specified version."""
        return SunwellURI(
            self.resource_type, self.namespace, self.slug, version
        )


@dataclass(frozen=True, slots=True)
class ResourceIdentity:
    """Immutable resource identity with UUID."""
    
    id: UUID
    uri: SunwellURI
    created_at: str  # ISO format
    
    @classmethod
    def create(cls, uri: SunwellURI) -> "ResourceIdentity":
        from datetime import UTC, datetime
        from uuid import uuid4
        return cls(
            id=uuid4(),
            uri=uri,
            created_at=datetime.now(UTC).isoformat(),
        )
```

#### Backwards Compatibility

```python
def parse_legacy_name(name: str, resource_type: ResourceType) -> SunwellURI:
    """Convert bare slug to full URI with deprecation warning.
    
    Resolution order for lenses: user -> builtin
    Resolution order for bindings: project -> global
    """
    import warnings
    warnings.warn(
        f"Bare slug '{name}' is deprecated. Use full URI: sunwell:{resource_type}/...",
        DeprecationWarning,
        stacklevel=3,
    )
    
    # Legacy resolution logic here
    # Returns fully-qualified URI
```

---

### Part 2: Lens Identity (Phase 1)

#### Lens-Specific URI

```python
# src/sunwell/lens/identity.py

from sunwell.core.identity import SunwellURI, ResourceIdentity


@dataclass(frozen=True, slots=True)
class LensLineage:
    """Fork tracking for lenses."""
    
    forked_from: str | None  # LensURI as string
    forked_at: str | None    # ISO format


@dataclass(frozen=True, slots=True)
class LensVersionInfo:
    """Version metadata (no content)."""
    
    version: str
    sha256: str
    created_at: str
    message: str | None
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LensManifest:
    """Full lens manifest."""
    
    identity: ResourceIdentity
    display_name: str
    lineage: LensLineage
    current_version: str
    versions: tuple[LensVersionInfo, ...]
    
    # Index fields (pre-computed for fast listing)
    domain: str | None
    tags: tuple[str, ...]
    heuristics_count: int
    skills_count: int
```

#### Storage Layout

```
~/.sunwell/lenses/
  index.json                    # Global index (fast library listing)
  my-custom-writer/
    manifest.json               # Identity + version list
    current.lens                # Symlink to v1.3.0.lens
    v1.0.0.lens
    v1.1.0.lens
    v1.2.0.lens
    v1.3.0.lens
  another-lens/
    manifest.json
    current.lens
```

#### Global Index

```json
{
  "version": 1,
  "updated_at": "2026-01-23T12:00:00Z",
  "lenses": {
    "sunwell:lens/user/my-custom-writer": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "display_name": "My Custom Writer",
      "domain": "documentation",
      "current_version": "1.3.0",
      "version_count": 4,
      "is_default": false,
      "last_modified": "2026-01-20T14:00:00Z"
    },
    "sunwell:lens/builtin/tech-writer": {
      "id": "00000000-0000-0000-0000-000000000001",
      "display_name": "Technical Writer",
      "domain": "documentation",
      "current_version": "2.0.0",
      "version_count": 1,
      "is_default": true,
      "last_modified": "2026-01-01T00:00:00Z"
    }
  }
}
```

**Performance**: Library listing reads one file, not N lens files.

#### API Changes

| Method | Old Signature | New Signature |
|--------|---------------|---------------|
| `get_lens_detail` | `(name: str)` | `(uri: str)` |
| `fork_lens` | `(source: str, new_name: str)` | `(source_uri: str, new_slug: str)` |
| `delete_lens` | `(name: str)` | `(uri: str)` |
| `get_versions` | `(name: str)` | `(uri: str)` |
| **NEW** | n/a | `resolve_uri(name: str) -> str` |
| **NEW** | n/a | `get_by_checksum(sha: str) -> Lens` |

---

### Part 3: Binding and Session Identity (Phase 2)

#### Binding Identity

Bindings are simpler than lenses: no versioning, just namespace isolation.

```python
# src/sunwell/binding/identity.py

@dataclass(frozen=True, slots=True)
class BindingManifest:
    """Binding identity metadata."""
    
    identity: ResourceIdentity
    display_name: str
    lens_uri: str  # Reference to lens (not path!)
    provider: str
    model: str
    # ... rest of binding config
```

**Storage layout**:

```
~/.sunwell/bindings/
  index.json                    # Global index
  global/                       # Global bindings (cross-project)
    default-writer.json
  projects/
    myproject/                  # Project-scoped bindings
      writer.json
      reviewer.json
```

**Key change**: `lens_path: str` becomes `lens_uri: str`. Bindings reference lenses by URI, not path.

#### Session Identity

Sessions need project scoping to prevent collisions.

```python
# src/sunwell/simulacrum/identity.py

@dataclass(frozen=True, slots=True)
class SessionManifest:
    """Session identity metadata."""
    
    identity: ResourceIdentity
    display_name: str
    turn_count: int
    created_at: str
    last_accessed: str
```

**Storage layout**:

```
~/.sunwell/memory/
  index.json                    # Session index
  projects/
    myproject/
      debug_dag.json
      debug_meta.json
    otherproject/
      debug_dag.json            # No collision!
```

**Key change**: Sessions are scoped by project, not global.

---

## Implementation Plan

### Phase 1: Core + Lens Identity (4 weeks)

| Week | Tasks |
|------|-------|
| **1** | `SunwellURI` base class, `LensIndex` infrastructure |
| **2** | Migration shims, backwards-compatible `get_lens_detail()` |
| **3** | New storage layout, manifest generation, symlink handling |
| **4** | UI integration (Studio), CLI updates, index rebuild command |

### Phase 2: Binding + Session Identity (2 weeks)

| Week | Tasks |
|------|-------|
| **5** | `BindingManifest`, binding index, project-scoped storage |
| **6** | `SessionManifest`, session scoping, memory store migration |

### Migration Strategy

#### Lens Migration (Phase 1)

1. **Soft migration**: Add `index.json` alongside existing flat structure
2. **Dual support**: Both structures work, new lenses use directories
3. **Full migration**: Auto-migrate on startup, remove flat file support

```bash
# Manual migration command
sunwell lens migrate --dry-run
sunwell lens migrate
```

#### Binding/Session Migration (Phase 2)

1. **Add project scope**: New bindings/sessions are project-scoped
2. **Legacy fallback**: Unscoped items treated as "global" or "default" project
3. **Optional migration**: `sunwell migrate --all`

---

## CLI Changes

### Phase 1: Lens Commands

```bash
# Old (still works, warns)
sunwell lens show tech-writer

# New (explicit)
sunwell lens show sunwell:lens/builtin/tech-writer
sunwell lens show sunwell:lens/user/my-writer@1.2.0

# List with namespace filter
sunwell lens list --namespace user
sunwell lens list --namespace builtin

# Rebuild index (recovery)
sunwell lens index --rebuild
```

### Phase 2: Binding/Session Commands

```bash
# Bindings with project scope
sunwell bind writer --project myproject --lens sunwell:lens/user/tech-writer
sunwell bind --list --project myproject

# Sessions with project scope
sunwell chat --session debug --project myproject
sunwell session list --project myproject
```

---

## Performance Analysis

### Current State

| Operation | Complexity | Bottleneck |
|-----------|------------|------------|
| List lenses | O(N) | Parses each `.lens` YAML |
| List bindings | O(N) | Reads each `.json` |
| List sessions | O(N) | Scans directory |

### After RFC-101

| Operation | Complexity | Method |
|-----------|------------|--------|
| List lenses | **O(1)** | Read `index.json` |
| List bindings | **O(1)** | Read `index.json` |
| List sessions | **O(1)** | Read `index.json` |
| Resolve URI | O(1) | Index lookup |
| Rebuild index | O(N) | One-time or on corruption |

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Index corruption** | Medium | Medium | Rebuild on checksum mismatch, manifests are source of truth |
| **Symlink issues** (Windows) | Medium | Low | Fall back to copy, use junction points |
| **Migration data loss** | Low | High | Backup before migrate, dry-run mode |
| **URI parsing edge cases** | Low | Low | Comprehensive test suite, fuzzing |
| **Backwards compat breakage** | Medium | Medium | Long deprecation period, clear migration docs |
| **Phase 2 scope creep** | Medium | Medium | Strict scope: no versioning for bindings/sessions |

---

## Explicitly Deferred

### Spells (Different Problem)

Spells use **intentional layered resolution**: user then project then lens then cantrips. The "shadowing" is a feature for customization. A future RFC could add explicit layer targeting:

```
::cantrip:help     # Force cantrip layer
::user:help        # Force user layer
```

But this is **not an identity problem**. It is a resolution precedence problem.

### Projects (Lower Priority)

Projects use path-based identity which works for now. Adding UUIDs would help with:

- Project renames without losing history
- Cross-device project sync

But this is lower priority than lenses/bindings/sessions.

### Fount Marketplace (Future)

When we add the Fount lens marketplace, we will need:

- `sunwell:lens/fount/{author}/{lens}@{version}`
- Signature verification
- License tracking

This will be a separate RFC building on the URI infrastructure.

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Library list latency | <50ms @ 1000 lenses | Benchmark script |
| Version lookup latency | <20ms @ 50 versions | Benchmark script |
| Zero shadowing incidents | 0 user reports | Issue tracker |
| Migration success rate | >99% | Telemetry |
| API backwards compat | 100% for 2 releases | Integration tests |
| Session collision rate | 0 (was possible) | Unit tests |

---

## Open Questions

1. **Project discovery**: How do we determine the "current project" for scoping?
   - Option A: Walk up to find `.sunwell/` directory
   - Option B: Explicit `--project` flag always
   - Option C: Environment variable `SUNWELL_PROJECT`

2. **Global vs project bindings**: Should global bindings be visible in projects?
   - Option A: Yes, with lower priority than project bindings
   - Option B: No, explicit copy required

3. **Cross-device sync**: Should UUIDs be deterministic (hash of content) or random?
   - Random: Simpler, but same content = different ID on different devices
   - Deterministic: Enables deduplication, but content changes = new ID

---

## Appendix: Full Type Definitions

```python
# src/sunwell/core/identity.py

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

ResourceType = Literal["lens", "binding", "session"]


@dataclass(frozen=True, slots=True)
class SunwellURI:
    """Canonical resource identifier."""
    
    resource_type: ResourceType
    namespace: str
    slug: str
    version: str | None = None
    
    @classmethod
    def parse(cls, uri: str) -> "SunwellURI": ...
    def __str__(self) -> str: ...
    def with_version(self, version: str) -> "SunwellURI": ...
    
    @property
    def is_builtin(self) -> bool: ...
    @property
    def is_versioned(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class ResourceIdentity:
    """Immutable resource identity."""
    
    id: UUID
    uri: SunwellURI
    created_at: str


# src/sunwell/lens/identity.py

@dataclass(frozen=True, slots=True)
class LensLineage:
    """Fork tracking."""
    
    forked_from: str | None
    forked_at: str | None


@dataclass(frozen=True, slots=True)
class LensVersionInfo:
    """Version metadata (no content)."""
    
    version: str
    sha256: str
    created_at: str
    message: str | None
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LensManifest:
    """Full lens manifest."""
    
    identity: ResourceIdentity
    display_name: str
    lineage: LensLineage
    current_version: str
    versions: tuple[LensVersionInfo, ...]
    domain: str | None
    tags: tuple[str, ...]
    heuristics_count: int
    skills_count: int


@dataclass(frozen=True, slots=True)
class LensIndexEntry:
    """Lightweight entry for global index."""
    
    uri: str
    id: str
    display_name: str
    namespace: str
    domain: str | None
    current_version: str
    version_count: int
    is_default: bool
    last_modified: str


# src/sunwell/binding/identity.py

@dataclass(frozen=True, slots=True)
class BindingManifest:
    """Binding identity metadata."""
    
    identity: ResourceIdentity
    display_name: str
    lens_uri: str
    provider: str
    model: str
    created_at: str
    last_used: str
    use_count: int


# src/sunwell/simulacrum/identity.py

@dataclass(frozen=True, slots=True)
class SessionManifest:
    """Session identity metadata."""
    
    identity: ResourceIdentity
    display_name: str
    turn_count: int
    learning_count: int
    created_at: str
    last_accessed: str
```

---

## References

- RFC-070: Lens Library Management (current implementation)
- RFC-064: Lens Selection for Projects
- Content-addressable storage: https://en.wikipedia.org/wiki/Content-addressable_storage
- Semantic Versioning 2.0.0: https://semver.org/
- URI Generic Syntax (RFC 3986): https://www.rfc-editor.org/rfc/rfc3986
