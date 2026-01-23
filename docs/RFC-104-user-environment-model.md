# RFC-104: User Environment Model

**Status**: ✅ Implemented  
**Author**: @llane  
**Created**: 2026-01-23  
**Updated**: 2026-01-23 (added Goals/Non-Goals, design options, integration analysis)  
**Depends on**: RFC-100 (State DAG)  
**Enhanced by**: RFC-103 (Workspace-Aware Scanning) — optional, enables cross-project linking

---

## Summary

Sunwell should learn where users keep their projects, what patterns exist across them, and which projects represent "gold standards" worth learning from. This enables smarter project discovery, informed planning, and cross-project consistency.

**One-liner**: "Sunwell knows your dev environment and learns from your best work."

---

## Goals and Non-Goals

### Goals

1. **Eliminate cold start** — Remember scanned projects across sessions
2. **Learn user patterns** — Detect project organization conventions automatically
3. **Enable peer references** — Let users mark "gold standard" projects to borrow from
4. **Cross-project awareness** — Know when changes affect multiple projects

### Non-Goals

1. **Not replacing IDE workspaces** — Complements, doesn't replace VS Code/JetBrains workspaces
2. **Not cloud sync (v1)** — All data stays local; cloud sync is future extension
3. **Not auto-fixing** — Alerts about cross-project impact, doesn't auto-apply changes
4. **Not team features (v1)** — Personal environment only; team sharing is future extension
5. **Not replacing `sunwell scan`** — Environment model tracks *which* projects exist; scan provides *health details*

---

## Motivation

### The Cold Start Problem

Every time a user starts a new project or scans an existing one, Sunwell starts from zero:

```bash
$ sunwell scan ~/some-random-path/docs
# Sunwell: "I have no idea what this is or how it relates to anything"
```

But users have patterns:
- "I keep Python projects in `~/github/python/`"
- "My docs projects all use Sphinx with similar conf.py"
- "prompt-library has the best documentation structure"

This knowledge is valuable but currently lives only in the user's head.

### The "Peer Reference" Opportunity

When planning a new docs project, Sunwell could reference the user's existing good work:

```
Planning new API documentation...

Found similar projects in your environment:
  🟢 prompt-library/docs (95% health)
     └─ Diataxis structure, consistent frontmatter, health scripts
  🟢 sunwell/docs (92% health)  
     └─ RFC-driven, good cross-refs, clear navigation

Borrowing patterns:
  ✓ Using Diataxis quadrant structure (from prompt-library)
  ✓ Adding frontmatter schema (from prompt-library)
  ✓ Including health check workflow (from prompt-library)
```

### The Cross-Project Drift Problem

When a shared dependency changes, multiple projects may need updates:

```
SDK v2 → v3 released

Affected projects in your environment:
  📚 acme-docs      - References SDK v2 in 12 files
  📚 acme-tutorials - References SDK v2 in 8 files
  📚 acme-api-ref   - Auto-generated from SDK v2

Suggested: Create coordinated update plan across all 3
```

---

## Integration with Existing Code

### Relationship to `WorkspaceDetector`

The existing `workspace/detector.py` provides **single-project detection**:

```python
# Existing: Detects ONE workspace from a starting path
class WorkspaceDetector:
    def detect(self, start_path: Path) -> Workspace  # Single workspace
    def detect_config(self, start_path: Path) -> WorkspaceConfig  # Single config
```

The User Environment Model provides **multi-project awareness**:

```python
# New: Knows about ALL user's projects across the system
class UserEnvironment:
    roots: list[ProjectRoot]       # Where projects live
    projects: list[ProjectEntry]   # All known projects
    patterns: list[Pattern]        # Cross-project patterns
```

**Integration approach**: Composition, not replacement.

```python
@dataclass(frozen=True, slots=True)
class ProjectEntry:
    """Wraps WorkspaceConfig with environment-level metadata."""
    
    workspace: WorkspaceConfig     # Reuse existing detection
    health_score: float | None     # From StateDag
    last_scanned: datetime | None
    is_reference: bool
    tags: tuple[str, ...]

# Discovery uses existing WorkspaceDetector
def discover_project(path: Path) -> ProjectEntry:
    detector = WorkspaceDetector()
    config = detector.detect_config(path)
    return ProjectEntry(workspace=config, ...)
```

### Relationship to `StateDag`

The existing `analysis/state_dag.py` provides **detailed project health**:

```python
# Existing: Deep scan of a single project
class StateDag:
    root: Path
    nodes: list[StateDagNode]      # All artifacts
    overall_health: float          # Aggregate health
```

The User Environment Model provides **lightweight health tracking**:

```python
# New: Summary health for project catalog (not full scan)
@dataclass
class ProjectEntry:
    health_score: float | None     # Cached from last StateDag
    last_scanned: datetime | None  # When was StateDag built
```

**Integration approach**: Environment caches StateDag summaries.

```python
def update_project_health(project: ProjectEntry, dag: StateDag) -> ProjectEntry:
    """Update environment entry from a fresh scan."""
    return ProjectEntry(
        workspace=project.workspace,
        health_score=dag.overall_health,
        last_scanned=dag.scanned_at,
        is_reference=project.is_reference,
        tags=project.tags,
    )
```

### Relationship to RFC-103 (Workspace-Aware Scanning)

RFC-103 proposes **cross-project linking** (docs → source code). This RFC proposes **environment awareness** (knowing all projects).

| Feature | RFC-103 | RFC-104 |
|---------|---------|---------|
| Scope | Scan-time discovery | Persistent catalog |
| Focus | Docs ↔ code linking | All project types |
| Trigger | `sunwell scan` | `sunwell env scan` |
| Output | `WorkspaceLink` | `UserEnvironment` |

**Integration**: RFC-103 *enhances* RFC-104 but is not required.

- Without RFC-103: Environment knows projects exist, but doesn't auto-link them
- With RFC-103: Environment auto-discovers docs/code relationships

```python
# RFC-104 alone
env.projects = [sunwell, prompt-library, pachyderm]

# RFC-104 + RFC-103
env.projects = [sunwell, prompt-library, pachyderm]
env.links = [
    WorkspaceLink(source=sunwell_docs, target=sunwell_src, relationship="source_code")
]
```

---

## Design Options

### Option A: Extend WorkspaceDetector (Minimal)

Add environment awareness directly to existing `workspace/` module.

**Pros**: Minimal new code, reuses detection logic  
**Cons**: Conflates single-project and multi-project concerns

```python
# workspace/detector.py
class WorkspaceDetector:
    def detect_all(self, roots: list[Path]) -> list[WorkspaceConfig]:
        """Detect all projects under given roots."""
        ...
```

### Option B: New Environment Module (Recommended) ✅

Create dedicated `environment/` module that composes existing components.

**Pros**: Clean separation, explicit composition, room to grow  
**Cons**: More files, need to maintain integration

```python
# environment/model.py
@dataclass
class ProjectEntry:
    workspace: WorkspaceConfig  # Reuse existing
    health_score: float | None  # Cache StateDag result
    ...

# environment/discovery.py
def discover_projects(root: Path) -> list[ProjectEntry]:
    detector = WorkspaceDetector()
    # Use detector for each found project
```

### Option C: StateDag Extension

Extend StateDag to support multi-project scans and cache globally.

**Pros**: Single source of truth for health  
**Cons**: Overloads StateDag's purpose, expensive to maintain

**Decision**: Option B (new module with composition) balances separation of concerns with code reuse.

---

## Design

### Core Concept: Environment Graph

The User Environment Model is a persistent graph of:

```
Environment
├── Project Roots (where projects live)
│   ├── ~/Documents/github/python/     [15 projects]
│   ├── ~/Documents/gitlab/tech-docs/  [8 projects]
│   └── ~/Documents/github/go/         [3 projects]
│
├── Project Catalog (what exists)
│   ├── sunwell        {type: python, health: 92%, last_scan: 2h ago}
│   ├── prompt-library {type: docs, health: 95%, last_scan: 1d ago}
│   └── pachyderm      {type: go, health: 78%, last_scan: 1w ago}
│
├── Patterns (learned regularities)
│   ├── "Python projects use pyproject.toml + src/ layout"
│   ├── "Docs projects use Sphinx with NVIDIA theme"
│   └── "All projects have .cursor/rules/ directories"
│
└── Reference Projects (gold standards)
    ├── prompt-library/docs  → "Best docs structure"
    └── sunwell/src          → "Best Python patterns"
```

### Data Model

Uses composition with existing types from `workspace/detector.py`.

```python
from sunwell.workspace.detector import WorkspaceConfig

@dataclass(frozen=True, slots=True)
class ProjectRoot:
    """A directory where the user keeps projects."""
    path: Path
    discovered_at: datetime
    project_count: int
    primary_type: str  # "python", "docs", "go", "mixed"
    scan_frequency: str  # "often", "sometimes", "rarely"

@dataclass(frozen=True, slots=True)
class ProjectEntry:
    """A known project in the user's environment.
    
    Composes WorkspaceConfig (existing) with environment-level metadata.
    """
    workspace: WorkspaceConfig  # Reuse existing workspace detection
    health_score: float | None  # Cached from last StateDag scan
    last_scanned: datetime | None
    patterns: tuple[str, ...]   # Detected patterns
    is_reference: bool          # User marked as gold standard
    tags: tuple[str, ...]       # User-defined tags
    
    @property
    def path(self) -> Path:
        return self.workspace.root
    
    @property
    def name(self) -> str:
        return self.workspace.name
    
    @property
    def project_type(self) -> str:
        """Infer type from workspace markers."""
        if self.workspace.is_git:
            # Check for docs markers vs code markers
            root = self.workspace.root
            if (root / "conf.py").exists() or (root / "mkdocs.yml").exists():
                return "docs"
            if (root / "pyproject.toml").exists():
                return "python"
            if (root / "go.mod").exists():
                return "go"
            if (root / "package.json").exists():
                return "node"
        return "unknown"

@dataclass(frozen=True, slots=True)
class Pattern:
    """A learned pattern across projects."""
    name: str
    description: str
    frequency: int                    # How many projects exhibit this
    examples: tuple[Path, ...]        # Projects that have this pattern
    confidence: float

@dataclass
class UserEnvironment:
    """The complete environment model.
    
    Stored at ~/.sunwell/environment.json
    """
    roots: list[ProjectRoot]
    projects: list[ProjectEntry]
    patterns: list[Pattern]
    reference_projects: dict[str, Path]  # category → path
    version: int = 1
    updated_at: datetime = field(default_factory=datetime.now)
    
    def find_similar(self, project: Path) -> list[ProjectEntry]:
        """Find projects similar to the given one."""
        target = self.get_project(project)
        if not target:
            return []
        return [
            p for p in self.projects
            if p.project_type == target.project_type and p.path != project
        ]
    
    def get_project(self, path: Path) -> ProjectEntry | None:
        """Get a project by path."""
        path = path.resolve()
        return next((p for p in self.projects if p.path.resolve() == path), None)
    
    def get_reference_for(self, category: str) -> ProjectEntry | None:
        """Get the gold standard project for a category."""
        ref_path = self.reference_projects.get(category)
        return self.get_project(ref_path) if ref_path else None
    
    def suggest_location(self, project_type: str) -> Path | None:
        """Suggest where to create a new project of this type."""
        for root in self.roots:
            if root.primary_type == project_type:
                return root.path
        return self.roots[0].path if self.roots else None
```

### Learning Mechanisms

**1. Root Discovery** — Uses existing `WorkspaceDetector` internally
```python
from sunwell.workspace.detector import WorkspaceDetector

# Scan depth: 2 levels (e.g., ~/github/python/* but not ~/github/python/sunwell/tests/*)
MAX_SCAN_DEPTH = 2
MIN_PROJECTS_FOR_ROOT = 2

def discover_roots(home: Path) -> list[ProjectRoot]:
    """Find directories that contain multiple projects."""
    candidates = [
        home / "Documents" / "github",
        home / "Documents" / "gitlab", 
        home / "projects",
        home / "code",
        home / "dev",
        home / "src",
    ]
    
    detector = WorkspaceDetector()
    roots = []
    
    for candidate in candidates:
        if not candidate.exists():
            continue
            
        # Find project markers within depth limit
        projects = _find_projects_in_root(candidate, detector, MAX_SCAN_DEPTH)
        
        if len(projects) >= MIN_PROJECTS_FOR_ROOT:
            primary_type = _infer_primary_type(projects)
            roots.append(ProjectRoot(
                path=candidate,
                discovered_at=datetime.now(),
                project_count=len(projects),
                primary_type=primary_type,
                scan_frequency="sometimes",
            ))
    
    return roots

def _find_projects_in_root(root: Path, detector: WorkspaceDetector, max_depth: int) -> list[Path]:
    """Find project directories within root, respecting depth limit."""
    projects = []
    for path in root.iterdir():
        if not path.is_dir() or path.name.startswith("."):
            continue
        config = detector.detect_config(path)
        if config.is_git or config.has_sunwell_config:
            projects.append(path)
    return projects
```

**2. Pattern Extraction** — Learns from detected `WorkspaceConfig` data
```python
def extract_patterns(projects: list[ProjectEntry]) -> list[Pattern]:
    """Learn patterns across scanned projects."""
    patterns = []
    
    # Structure patterns (check actual filesystem)
    src_layout_count = sum(1 for p in projects if (p.path / "src").is_dir())
    if src_layout_count >= len(projects) * 0.5:  # >50% have src/
        patterns.append(Pattern(
            name="src_layout",
            description="Projects use src/ directory layout",
            frequency=src_layout_count,
            examples=tuple(p.path for p in projects if (p.path / "src").is_dir())[:5],
            confidence=src_layout_count / len(projects),
        ))
    
    # Config patterns (from WorkspaceConfig.is_git, markers)
    pyproject_count = sum(1 for p in projects if (p.path / "pyproject.toml").exists())
    if pyproject_count >= 2:
        patterns.append(Pattern(
            name="pyproject_config",
            description="Python projects use pyproject.toml",
            frequency=pyproject_count,
            examples=tuple(p.path for p in projects if (p.path / "pyproject.toml").exists())[:5],
            confidence=pyproject_count / max(1, sum(1 for p in projects if p.project_type == "python")),
        ))
    
    # Cursor rules pattern
    cursor_rules_count = sum(1 for p in projects if (p.path / ".cursor" / "rules").is_dir())
    if cursor_rules_count >= 2:
        patterns.append(Pattern(
            name="cursor_rules",
            description="Projects have .cursor/rules/ directories",
            frequency=cursor_rules_count,
            examples=tuple(p.path for p in projects if (p.path / ".cursor" / "rules").is_dir())[:5],
            confidence=cursor_rules_count / len(projects),
        ))
    
    return patterns
```

**3. Reference Selection** — Based on cached `StateDag.overall_health`
```python
REFERENCE_HEALTH_THRESHOLD = 0.90  # Only suggest projects with 90%+ health

def suggest_references(projects: list[ProjectEntry]) -> dict[str, Path]:
    """Identify gold standard projects by category."""
    references = {}
    
    # Group by type
    by_type: dict[str, list[ProjectEntry]] = {}
    for p in projects:
        by_type.setdefault(p.project_type, []).append(p)
    
    # Best per type (must meet threshold)
    for ptype, type_projects in by_type.items():
        with_health = [p for p in type_projects if p.health_score is not None]
        if not with_health:
            continue
        best = max(with_health, key=lambda p: p.health_score or 0)
        if best.health_score and best.health_score >= REFERENCE_HEALTH_THRESHOLD:
            references[ptype] = best.path
    
    return references
```

### User Interactions

**1. Environment Setup (First Run)**
```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 Learning Your Environment                                │
│                                                             │
│ Found project directories:                                  │
│                                                             │
│ ☑ ~/Documents/github/python/     15 projects                │
│ ☑ ~/Documents/gitlab/tech-docs/  8 projects                 │
│ ☐ ~/Downloads/                   (excluded - not projects)  │
│                                                             │
│ [Add Directory...]                                          │
│                                                             │
│ [Continue]                                                  │
└─────────────────────────────────────────────────────────────┘
```

**2. Mark Reference Project**
```
┌─────────────────────────────────────────────────────────────┐
│ ⭐ Mark as Reference                                        │
│                                                             │
│ prompt-library/docs has excellent health (95%)              │
│                                                             │
│ Use as reference for:                                       │
│ ☑ Documentation structure                                   │
│ ☑ Frontmatter patterns                                      │
│ ☐ CI/CD workflows                                           │
│                                                             │
│ [Save as Reference]    [Not Now]                            │
└─────────────────────────────────────────────────────────────┘
```

**3. Planning with References**
```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Planning: New API Documentation                          │
│                                                             │
│ Reference: prompt-library/docs (your gold standard)         │
│                                                             │
│ Borrowing:                                                  │
│ ├─ ✓ Diataxis quadrant structure                            │
│ ├─ ✓ Frontmatter schema (title, description, category)      │
│ ├─ ✓ Health check scripts (check_health.py)                 │
│ └─ ○ Navigation pattern (adapting for API focus)            │
│                                                             │
│ [View Reference] [Customize] [Continue Planning]            │
└─────────────────────────────────────────────────────────────┘
```

**4. Cross-Project Alert**
```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ Cross-Project Impact Detected                            │
│                                                             │
│ You updated: sunwell/src/api/users.py                       │
│                                                             │
│ Related documentation may need updates:                     │
│ ├─ sunwell/docs/api/users.md         (same repo)            │
│ ├─ acme-tutorials/auth-guide.md      (references users API) │
│ └─ internal-wiki/sunwell-setup.md    (external docs)        │
│                                                             │
│ [Review Impact] [Dismiss]                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Storage

### Location

```
~/.sunwell/
├── environment.json       # Main environment model
├── project_cache/         # Cached State DAGs
│   ├── sunwell.json
│   └── prompt-library.json
└── patterns/              # Learned patterns
    └── v1.json
```

### Schema

```json
{
  "version": 1,
  "updated_at": "2026-01-23T12:00:00Z",
  "roots": [
    {
      "path": "/Users/me/Documents/github/python",
      "discovered_at": "2026-01-20T10:00:00Z",
      "project_count": 15,
      "primary_type": "python"
    }
  ],
  "projects": [
    {
      "path": "/Users/me/Documents/github/python/sunwell",
      "name": "sunwell",
      "project_type": "python",
      "health_score": 0.92,
      "last_scanned": "2026-01-23T10:00:00Z",
      "is_reference": false,
      "tags": ["ai", "agent", "docs"]
    }
  ],
  "references": {
    "docs": "/Users/me/Documents/gitlab/tech-docs/prompt-library",
    "python": "/Users/me/Documents/github/python/sunwell"
  },
  "patterns": [
    {
      "name": "pyproject_toml",
      "description": "Python projects use pyproject.toml",
      "frequency": 14,
      "confidence": 0.93
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Project Discovery (Week 1)
- Scan common directories for project roots
- Build initial project catalog
- Store in `~/.sunwell/environment.json`
- CLI: `sunwell env scan`, `sunwell env list`

### Phase 2: Pattern Learning (Week 2)
- Extract patterns from scanned projects
- Identify commonalities (config, structure, tools)
- CLI: `sunwell env patterns`

### Phase 3: Reference Projects (Week 3)
- Auto-suggest high-health projects as references
- Allow user to mark/unmark references
- CLI: `sunwell env reference add/remove`

### Phase 4: Planning Integration (Week 4)
- Inject reference patterns into planning
- Show "borrowing from X" in plan output
- CLI: `sunwell plan --reference prompt-library`

### Phase 5: Cross-Project Alerts (Future)
- Track cross-project dependencies
- Alert when changes may impact other projects
- Suggest coordinated updates

---

## File Changes

### Python

| File | Change | Integrates With |
|------|--------|-----------------|
| `src/sunwell/environment/__init__.py` | **New**: Package init | — |
| `src/sunwell/environment/model.py` | **New**: UserEnvironment, ProjectEntry, Pattern, ProjectRoot | `workspace.detector.WorkspaceConfig` |
| `src/sunwell/environment/discovery.py` | **New**: Root and project discovery | `workspace.detector.WorkspaceDetector` |
| `src/sunwell/environment/patterns.py` | **New**: Pattern extraction | — |
| `src/sunwell/environment/references.py` | **New**: Reference project management | `analysis.state_dag.StateDag` |
| `src/sunwell/environment/storage.py` | **New**: JSON persistence to `~/.sunwell/` | `config.py` patterns |
| `src/sunwell/cli/env_cmd.py` | **New**: `sunwell env` command group | — |
| `src/sunwell/cli/main.py` | Register env commands | — |
| `src/sunwell/cli/scan_cmd.py` | **Modify**: Update environment after scan | `environment.model` |

### Rust (Tauri)

| File | Change |
|------|--------|
| `studio/src-tauri/src/environment.rs` | **New**: Environment Tauri commands |
| `studio/src-tauri/src/main.rs` | Register environment commands |

### Svelte (Studio)

| File | Change |
|------|--------|
| `studio/src/stores/environment.svelte.ts` | **New**: Environment state |
| `studio/src/components/environment/EnvironmentSetup.svelte` | **New**: First-run setup |
| `studio/src/components/environment/ProjectCatalog.svelte` | **New**: Project browser |
| `studio/src/components/environment/ReferenceSelector.svelte` | **New**: Mark references |
| `studio/src/components/environment/CrossProjectAlert.svelte` | **New**: Impact alerts |

---

## CLI Interface

```bash
# Discover and catalog projects
sunwell env scan
# Found 3 project roots with 26 projects total

# List known projects
sunwell env list
# ~/github/python/sunwell      Python  🟢 92%  2h ago
# ~/gitlab/tech-docs/prompt-library  Docs  🟢 95%  1d ago
# ...

# Show learned patterns
sunwell env patterns
# pyproject_toml: 14/15 Python projects (93%)
# src_layout: 12/15 Python projects (80%)
# sphinx_docs: 6/8 docs projects (75%)

# Mark a reference project
sunwell env reference add ~/prompt-library --category docs

# List references
sunwell env references
# docs: ~/prompt-library (95% health)
# python: ~/sunwell (92% health)

# Plan with reference
sunwell plan "Create API docs" --reference prompt-library

# Find similar projects
sunwell env similar ~/new-docs-project
# Similar to: prompt-library (docs, Sphinx)
# Similar to: sunwell/docs (docs, Markdown)
```

---

## Privacy Considerations

| Data | Storage | Sharing |
|------|---------|---------|
| Project paths | Local only | Never uploaded |
| Health scores | Local cache | Never uploaded |
| Patterns | Local only | Could opt-in to anonymized pattern sharing |
| References | Local only | Never uploaded |

The environment model is **entirely local**. No project information leaves the user's machine.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Projects discovered | >90% of actual projects found |
| Pattern accuracy | >85% of patterns are meaningful |
| Reference usage | >50% of plans use a reference |
| Cross-project alerts | <10% false positive rate |
| Time to find project | <2s for any known project |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Scanning too many directories | Limit depth, respect .gitignore |
| Stale project data | Re-scan on access, show "last scanned" |
| Wrong pattern inference | Show confidence, allow user override |
| Privacy concerns | All data local, clear documentation |
| Reference project becomes bad | Track health over time, warn if declining |

---

## Integration: `sunwell scan` Updates Environment

When users run `sunwell scan`, the environment is automatically updated:

```python
# cli/scan_cmd.py (modification)
async def _scan_async(path: str, ...):
    dag = await scan_project(root, lens)
    
    # NEW: Update environment with scan results
    from sunwell.environment import load_environment, save_environment
    
    env = load_environment()  # Load ~/.sunwell/environment.json
    env = update_project_from_dag(env, root, dag)  # Update health, last_scanned
    save_environment(env)
    
    _display_results(dag, verbose)
```

This provides automatic environment learning without separate commands:

```bash
$ sunwell scan ~/projects/my-api
# ... scan output ...
# Environment updated: my-api (92% health, Python)

$ sunwell env list
# my-api    Python  🟢 92%  just now    ← Auto-added from scan
```

---

## Rejected Alternatives

> Note: For viable design alternatives (extend WorkspaceDetector vs new module), see **Design Options** section above.

### A: IDE Integration (VS Code recent projects)
Read from IDE's recent projects list. **Rejected**: Not all users use VS Code, limited metadata, requires OS-specific paths.

### B: Recursive Git Discovery (find all .git dirs)
Walk filesystem recursively looking for `.git`. **Rejected**: Too slow on large filesystems, finds vendored repos in `node_modules`, `.git` presence doesn't indicate user's project.

### C: Manual-only Catalog
Require users to explicitly add each project. **Rejected**: Too much friction, users won't maintain it, cold start problem persists.

### D: Cloud-synced Environment (v1)
Store environment model in cloud for cross-machine sync. **Rejected for v1**: Privacy concerns, complexity, requires auth infrastructure. Planned for future opt-in extension.

---

## Future Extensions

1. **Team environments**: Share reference projects across team
2. **Environment templates**: "Set up my env like coworker X"
3. **Cross-machine sync**: Opt-in cloud storage of environment model
4. **Pattern marketplace**: Share/discover patterns from community
5. **Automated reference updates**: When reference project improves, propagate

---

## Design Decisions

### Q1: How deep to scan?

**Decision**: Scan known root candidates 2 levels deep, not recursive.

```
~/github/           ← Root candidate
├── python/         ← Level 1 (scan subdirs)
│   ├── sunwell/    ← Level 2 (detected as project)
│   └── bengal/     ← Level 2 (detected as project)
└── go/             ← Level 1 (scan subdirs)
    └── pachyderm/  ← Level 2 (detected as project)
```

**Rationale**: 
- Recursive scanning is too slow and finds vendored repos
- 2 levels covers common patterns (`~/github/<org>/<project>`)
- Users can add custom roots via `sunwell env root add`

### Q2: Pattern persistence?

**Decision**: Re-learn patterns on each environment scan, don't persist separately.

```python
# On every `sunwell env scan`:
patterns = extract_patterns(env.projects)  # Fresh extraction
env.patterns = patterns
env.save()  # Persisted with environment
```

**Rationale**:
- Patterns are cheap to compute (<1s for typical environments)
- Fresh extraction ensures patterns reflect current state
- No risk of stale pattern data

### Q3: Reference decay?

**Decision**: Warn when reference project health drops below 85%, but don't auto-remove.

```python
def check_reference_health(env: UserEnvironment) -> list[str]:
    """Return warnings for degraded reference projects."""
    warnings = []
    for category, path in env.reference_projects.items():
        project = env.get_project(path)
        if project and project.health_score and project.health_score < 0.85:
            warnings.append(
                f"Reference '{category}' ({path.name}) health dropped to "
                f"{project.health_score*100:.0f}%. Consider `sunwell env reference remove {category}`"
            )
    return warnings
```

**Rationale**:
- User explicitly chose references; auto-removal is surprising
- Warning gives user agency to fix or replace
- 85% threshold allows some variance before warning

### Q4: Multi-machine support?

**Decision**: Not in v1. Environment model is machine-local.

**Future approach** (v2+):
- Opt-in cloud sync via `~/.sunwell/environment.json` → cloud storage
- Paths stored as relative to home or with machine tag
- Merge strategy: union of projects, most recent wins for conflicts

**Rationale for v1 local-only**:
- Simpler implementation
- No privacy concerns
- Users can manually replicate setup via `sunwell env export/import`

---

## Key Code References

| Component | Existing File | Reuse |
|-----------|---------------|-------|
| Workspace detection | `src/sunwell/workspace/detector.py:98-205` | `WorkspaceDetector.detect_config()` |
| Project health | `src/sunwell/analysis/state_dag.py:114-151` | `StateDag.overall_health` |
| Storage patterns | `src/sunwell/config.py:282-286` | `~/.sunwell/` directory structure |
| Scan command | `src/sunwell/cli/scan_cmd.py:24-92` | Update after scan |

---

## References

- RFC-100: Orthogonal IDE (State DAG foundation) — **Evaluated, 88%**
- RFC-103: Workspace-Aware Scanning (project linking) — **Draft** (enhances but not required)
- [JetBrains Recent Projects](https://www.jetbrains.com/help/idea/opening-reopening-and-closing-projects.html)
- [VS Code Workspaces](https://code.visualstudio.com/docs/editor/workspaces)
