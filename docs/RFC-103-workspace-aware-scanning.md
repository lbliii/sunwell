# RFC-103: Workspace-Aware Scanning

**Status**: Implemented  
**Author**: @llane  
**Created**: 2026-01-23  
**Updated**: 2026-01-23 (S-tier elevation: topology model, drift probes, user journeys, latency budgets)  
**Depends on**: RFC-100 (Orthogonal IDE)  
**Confidence**: 88%  
**Evidence**: DocsScanner implementation, StateDag architecture, coordinator.rs patterns

---

## Summary

When scanning a docs project, Sunwell should auto-detect related code repositories and offer to link them for cross-reference features like drift detection. This enables the full power of RFC-100's State DAG for brownfield documentation projects.

**One-liner**: "Scan my docs" should intelligently find the related code without manual configuration.

**Key deliverables**:
1. **Workspace topology model** - Graph of related project roots
2. **Detection engine** - Auto-discover related projects with confidence scoring
3. **Drift detection probe** - Compare docs against source code
4. **Source-aware scanner** - StateDagBuilder integration with linked sources
5. **Studio UI** - Non-blocking workspace setup flow

---

## Cross-Stack Integration

This RFC touches **all three stacks**. Implementation requires coordinated changes:

### Python (Analysis Engine)

| File | Change | Phase |
|------|--------|-------|
| \`src/sunwell/analysis/workspace.py\` | **New**: Workspace, WorkspaceLink, WorkspaceDetector | 1 |
| \`src/sunwell/analysis/source_context.py\` | **New**: SourceContext, SymbolIndex for drift detection | 1 |
| \`src/sunwell/analysis/probes/drift.py\` | **New**: DriftProbe implementation | 2 |
| \`src/sunwell/analysis/state_dag.py\` | Add \`source_contexts\` parameter to StateDagBuilder | 2 |
| \`src/sunwell/analysis/scanners/docs.py\` | Add drift_detection, api_accuracy probes | 2 |
| \`src/sunwell/cli/workspace_cmd.py\` | **New**: \`sunwell workspace detect/link/unlink/show\` | 1 |
| \`src/sunwell/cli/scan_cmd.py\` | Add \`--link\`, \`--no-detect\` options | 1 |

### Rust (Tauri Bridge)

| File | Change | Phase |
|------|--------|-------|
| \`studio/src-tauri/src/workspace.rs\` | **New**: Workspace detection and linking commands | 1 |
| \`studio/src-tauri/src/main.rs\` | Register workspace commands | 1 |

### Svelte (Studio UI)

| File | Change | Phase |
|------|--------|-------|
| \`studio/src/stores/workspace.svelte.ts\` | **New**: Workspace state management | 1 |
| \`studio/src/components/workspace/WorkspaceToast.svelte\` | **New**: Non-blocking workspace setup | 1 |
| \`studio/src/components/workspace/ProjectCard.svelte\` | **New**: Compact project representation | 1 |
| \`studio/src/components/workspace/DriftBadge.svelte\` | **New**: Drift warning indicator | 2 |
| \`studio/src/components/coordinator/StateDagView.svelte\` | Add drift column, workspace indicator | 2 |

### Existing Assets to Leverage

| Asset | Location | Reuse For |
|-------|----------|-----------|
| Health color tokens | \`variables.css\` | Confidence badges |
| \`DagNode.svelte\` health indicators | \`studio/src/components/dag/\` | Drift badges |
| Toast notification patterns | \`agent.svelte.ts\` | Workspace setup toast |
| \`coordinator.rs\` command patterns | \`studio/src-tauri/src/\` | Workspace bridge |

---

## User Journeys

### Journey 1: First-Time Workspace Setup

\`\`\`
User runs: sunwell scan ~/projects/acme-docs

1. Detection runs in background (<500ms)
   Found: ../acme-core (pyproject.toml, 95% confidence)
   Found: ../acme-frontend (package.json, same GitHub org, 70%)

2. State DAG loads immediately with basic probes
   - orphan_check, broken_links, freshness run (source-independent)
   - drift_detection shows "Link source code to enable"

3. User sees workspace setup toast (non-blocking, bottom-right):
   +-----------------------------------------------------------+
   | Found related projects                              [x]   |
   |                                                           |
   | [x] ../acme-core     Python backend        95%            |
   | [ ] ../acme-frontend React frontend        70%            |
   |                                                           |
   | Linking enables: drift detection, API verification        |
   |                                                           |
   | [Link Selected] [Skip] [Don't show again]                 |
   +-----------------------------------------------------------+

4. User clicks [Link Selected] on acme-core
   - .sunwell/workspace.json created
   - SourceContext built from acme-core (symbols indexed, <2s)
   - State DAG re-runs drift probes

5. tutorials/ node updates: healthy -> warning (2 drift warnings found)
   "API example uses deprecated auth.login(), source has auth.sign_in()"

TOTAL TIME: <10 seconds from scan to actionable drift warnings
\`\`\`

### Journey 2: Returning User (Workspace Configured)

\`\`\`
User runs: sunwell scan ~/projects/acme-docs

1. Workspace config found in .sunwell/workspace.json
   - No prompt needed
   - SourceContext loaded from linked acme-core
   - All health probes enabled including drift detection

2. State DAG loads with full health context
   tutorials/   warning 72% - 1 drift, 1 stale
   reference/   critical 45% - 5 drift warnings (API changed last week)
   index.md     healthy 95%

3. User clicks reference/ node -> sees drift details:
   +-----------------------------------------------------------+
   | 5 drift warnings                                          |
   |                                                           |
   | X User.create() -> renamed to User.register()             |
   |   reference/api.md:45 vs acme-core/src/users.py:23        |
   |                                                           |
   | X auth.token_ttl -> removed in v2.0                       |
   |   reference/config.md:78 vs acme-core/src/config.py:12    |
   |                                                           |
   | [Fix All] [View Details] [Dismiss]                        |
   +-----------------------------------------------------------+

SEAMLESS - no friction on repeat visits
\`\`\`

### Journey 3: Monorepo (Docs Inside Code)

\`\`\`
Project structure:
acme/
  src/              <- Python code
  docs/             <- Documentation
  pyproject.toml

User runs: sunwell scan ~/projects/acme/docs

1. Detection immediately finds parent:
   - Parent has pyproject.toml -> 95% confidence
   - Parent has src/ with __init__.py -> same project

2. Toast offers to link (default selected):
   "Link parent directory acme/ as source code? [Yes] [No]"

3. User clicks [Yes] -> drift detection enabled

MONOREPO CASE: Detection is 95%+ accurate, single-click to enable
\`\`\`

### Journey 4: Multi-Repo Workspace (Polyglot)

\`\`\`
Project structure:
~/projects/
  acme-docs/        <- Documentation (scanning this)
  acme-backend/     <- Python API
  acme-frontend/    <- TypeScript React app

User runs: sunwell scan ~/projects/acme-docs

1. Detection finds both siblings:
   - acme-backend: pyproject.toml, same GitHub org -> 85%
   - acme-frontend: package.json, same GitHub org -> 75%

2. Toast shows both with checkboxes:
   +-----------------------------------------------------------+
   | Found related projects                                    |
   |                                                           |
   | [x] ../acme-backend   Python      85%                     |
   | [x] ../acme-frontend  TypeScript  75%                     |
   |                                                           |
   | [Link Selected (2)]                                       |
   +-----------------------------------------------------------+

3. User selects both -> workspace links both

4. Drift detection runs against BOTH sources:
   - "API endpoint /users documented but not in backend"
   - "Frontend component <UserCard> not documented"

POLYGLOT: Multiple source roots, unified drift view
\`\`\`

---

## Motivation

### The Problem

Currently, \`sunwell scan ~/my-docs\` treats the docs as an isolated project:

\`\`\`bash
$ sunwell scan ~/projects/acme/docs
# Finds 47 markdown files
# Detects orphans, broken links, freshness
# Cannot detect drift (no source code!)
# Cannot verify code examples
# Cannot check API documentation accuracy
\`\`\`

The docs scanner's most valuable health probes require source code:

| Probe | Requires Source | Current | With RFC-103 |
|-------|-----------------|---------|--------------|
| \`orphan_check\` | No | Works | Works |
| \`broken_links\` | No | Works | Works |
| \`freshness\` | No | Works | Works |
| \`drift_detection\` | **Yes** | Skipped | **Enabled** |
| \`example_verification\` | **Yes** | Skipped | **Enabled** |
| \`api_accuracy\` | **Yes** | Skipped | **Enabled** |

### The Opportunity

Documentation rarely exists in isolation. Common patterns:

\`\`\`
# Monorepo (most common, ~60% of projects)
acme/
  src/           <- Code
  docs/          <- Docs
  pyproject.toml

# Adjacent repos (~30% of projects)
~/projects/
  acme/          <- Code repo
  acme-docs/     <- Docs repo

# Polyglot workspace (~10% of projects)
~/projects/
  acme-backend/  <- Python API
  acme-frontend/ <- TypeScript app
  acme-docs/     <- Docs for both
\`\`\`

In each case, there's a **discoverable relationship** that Sunwell should find automatically.

---

## Design

### Core Concept: Workspace Topology

The workspace is a **graph of related project roots**, not just a flat list of links:

\`\`\`python
@dataclass(frozen=True, slots=True)
class WorkspaceLink:
    """A directed relationship between two project roots."""
    source: Path          # The project being scanned
    target: Path          # A related project
    relationship: Literal["source_code", "documentation", "dependency", "sibling"]
    confidence: float     # 0.0-1.0
    evidence: str         # Human-readable explanation
    language: str | None  # "python", "typescript", "go", etc.
    confirmed: bool       # User has explicitly confirmed this link

@dataclass(frozen=True, slots=True)
class Workspace:
    """A workspace is a graph of related project roots."""
    id: str               # Stable identifier
    primary: Path         # The project user opened/scanned
    links: tuple[WorkspaceLink, ...]
    topology: Literal["monorepo", "polyrepo", "hybrid"]
    created_at: datetime
    updated_at: datetime
    
    @property
    def source_roots(self) -> list[Path]:
        """All linked source code directories."""
        return [link.target for link in self.links 
                if link.relationship == "source_code"]
\`\`\`

### Source Context Model

To enable drift detection, we need to index the linked source code:

\`\`\`python
@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Information about a symbol in source code."""
    name: str
    kind: Literal["function", "class", "method", "constant", "variable"]
    file: Path
    line: int
    signature: str | None
    docstring: str | None
    deprecated: bool
    replacement: str | None

@dataclass
class SourceContext:
    """Indexed source code context for drift detection."""
    root: Path
    language: str
    symbols: dict[str, SymbolInfo]
    indexed_at: datetime
    file_count: int
    symbol_count: int
    
    @classmethod
    async def build(cls, root: Path) -> SourceContext:
        """Index source code for drift detection.
        
        Uses AST parsing for accuracy:
        - Python: ast module
        - TypeScript: tree-sitter or regex fallback
        
        Target: <2s for 10k line project
        """
        ...
\`\`\`

### Drift Detection Probe

The key new health probe enabled by workspace linking:

\`\`\`python
@dataclass(frozen=True, slots=True)
class DriftResult:
    """A single drift warning between doc and source."""
    doc_claim: str        # What the doc says
    source_reality: str   # What the source actually has
    drift_type: Literal["renamed", "removed", "signature_changed", "deprecated"]
    doc_file: Path
    doc_line: int
    source_file: Path | None
    source_line: int | None
    confidence: float
    suggested_fix: str | None

class DriftProbe:
    """Detect drift between documentation and source code."""
    
    def __init__(self, source_contexts: list[SourceContext]):
        self.source_contexts = source_contexts
        self._symbol_index = self._build_unified_index()
    
    async def run(self, node: StateDagNode) -> HealthProbeResult:
        """Check a doc node for drift against source."""
        if not self.source_contexts:
            return HealthProbeResult(
                probe_name="drift_detection",
                score=1.0,
                issues=(),
                metadata={"status": "no_source_linked"}
            )
        
        content = node.path.read_text()
        drift_warnings = []
        
        # Extract code references from doc
        code_refs = self._extract_code_references(content)
        
        for ref in code_refs:
            drift = self._check_reference(ref, node.path)
            if drift:
                drift_warnings.append(drift)
        
        # Calculate score
        if not drift_warnings:
            score = 1.0
        elif len(drift_warnings) <= 2:
            score = 0.7
        elif len(drift_warnings) <= 5:
            score = 0.5
        else:
            score = 0.3
        
        return HealthProbeResult(
            probe_name="drift_detection",
            score=score,
            issues=tuple(self._format_drift(d) for d in drift_warnings[:5]),
            metadata={"drift_count": len(drift_warnings)}
        )
\`\`\`

### Detection Strategies

**Strategy 1: Parent Directory Scan** (95% confidence for monorepos)

\`\`\`python
def detect_from_parent(docs_root: Path) -> list[WorkspaceLink]:
    """Check if docs is inside a larger project."""
    parent = docs_root.parent
    
    project_markers = [
        ("pyproject.toml", "python", 0.95),
        ("package.json", "typescript", 0.90),
        ("Cargo.toml", "rust", 0.95),
        ("go.mod", "go", 0.95),
    ]
    
    for marker, language, confidence in project_markers:
        if (parent / marker).exists():
            return [WorkspaceLink(
                source=docs_root,
                target=parent,
                relationship="source_code",
                confidence=confidence,
                evidence=f"Parent contains {marker}",
                language=language,
                confirmed=False,
            )]
    
    return []
\`\`\`

**Strategy 2: Config File References** (90% confidence)

\`\`\`python
def detect_from_config(docs_root: Path) -> list[WorkspaceLink]:
    """Parse docs config for source references."""
    links = []
    
    # Sphinx: conf.py often has path to source
    conf_py = docs_root / "conf.py"
    if conf_py.exists():
        content = conf_py.read_text()
        sys_path_match = re.search(
            r"sys\.path\.insert\(\d+,\s*['\"]([^'\"]+)['\"]", 
            content
        )
        if sys_path_match:
            rel_path = sys_path_match.group(1)
            source_path = (docs_root / rel_path).resolve()
            if source_path.exists():
                links.append(WorkspaceLink(
                    source=docs_root,
                    target=source_path,
                    relationship="source_code",
                    confidence=0.95,
                    evidence=f"conf.py references {rel_path}",
                    language="python",
                    confirmed=False,
                ))
    
    return links
\`\`\`

**Strategy 3: Git Remote Matching** (85% confidence)

\`\`\`python
def detect_from_git(docs_root: Path) -> list[WorkspaceLink]:
    """Match git remotes across nearby repos."""
    docs_remote = get_git_remote(docs_root)
    if not docs_remote:
        return []
    
    docs_org = extract_org(docs_remote)
    links = []
    
    for sibling in docs_root.parent.iterdir():
        if sibling == docs_root or not sibling.is_dir():
            continue
        
        sibling_remote = get_git_remote(sibling)
        if sibling_remote and extract_org(sibling_remote) == docs_org:
            links.append(WorkspaceLink(
                source=docs_root,
                target=sibling,
                relationship="source_code",
                confidence=0.85,
                evidence=f"Same GitHub org: {docs_org}",
                language=detect_language(sibling),
                confirmed=False,
            ))
    
    return links
\`\`\`

### Integration with StateDagBuilder

The key integration point - where workspace links flow into the scan:

\`\`\`python
class StateDagBuilder:
    def __init__(
        self, 
        root: Path, 
        lens: Lens | None = None,
        source_contexts: list[SourceContext] | None = None,  # NEW
    ):
        self.root = root
        self.lens = lens
        self.source_contexts = source_contexts or []

    async def build(self) -> StateDag:
        scanner = await self._get_scanner()
        nodes = await scanner.scan_nodes(self.root)
        edges = await scanner.extract_edges(self.root, nodes)
        
        # Pass source contexts to health probes
        health_results = await scanner.run_health_probes(
            self.root, 
            nodes,
            source_contexts=self.source_contexts,  # NEW
        )
        
        enriched_nodes = self._enrich_nodes_with_health(nodes, health_results)
        return StateDag(
            root=self.root,
            nodes=enriched_nodes,
            edges=edges,
            metadata={
                "source_roots": [str(ctx.root) for ctx in self.source_contexts],
            }
        )

async def scan_project(
    root: Path,
    lens: Lens | None = None,
    workspace: Workspace | None = None,  # NEW
) -> StateDag:
    """Scan project with optional workspace context."""
    source_contexts = []
    if workspace:
        for source_root in workspace.source_roots:
            ctx = await SourceContext.build(source_root)
            source_contexts.append(ctx)
    
    builder = StateDagBuilder(root, lens, source_contexts)
    return await builder.build()
\`\`\`

---

## Implementation

### Phase 1: Detection Engine + Persistence (1 week)

**New module**: \`src/sunwell/analysis/workspace.py\`

- \`WorkspaceLink\` dataclass
- \`Workspace\` dataclass with topology
- \`WorkspaceConfig\` for JSON persistence
- \`WorkspaceDetector\` with all strategies

**CLI commands**: \`sunwell workspace detect/link/unlink/show\`

### Phase 2: Source Indexing + Drift Probe (1 week)

**New module**: \`src/sunwell/analysis/source_context.py\`

- \`SymbolInfo\` dataclass
- \`SourceContext\` with AST-based indexing

**New module**: \`src/sunwell/analysis/probes/drift.py\`

- \`DriftResult\` dataclass
- \`DriftProbe\` class

**Update**: \`StateDagBuilder\` and \`DocsScanner\`

### Phase 3: Tauri Bridge (3 days)

**New file**: \`studio/src-tauri/src/workspace.rs\`

\`\`\`rust
#[tauri::command]
pub async fn detect_workspace_links(project_path: String) 
    -> Result<Vec<WorkspaceLink>, String>;

#[tauri::command]
pub async fn get_workspace(project_path: String) 
    -> Result<Option<Workspace>, String>;

#[tauri::command]
pub async fn link_workspace(project_path: String, target_path: String) 
    -> Result<(), String>;

#[tauri::command]
pub async fn unlink_workspace(project_path: String, target_path: String) 
    -> Result<(), String>;
\`\`\`

### Phase 4: Studio UI (3 days)

**New store**: \`studio/src/stores/workspace.svelte.ts\`

**New components**:
- \`WorkspaceToast.svelte\` - Non-blocking setup notification
- \`DriftBadge.svelte\` - Drift warning indicator

**Update**: \`StateDagView.svelte\` - Add toast and drift badges

---

## Latency Budget

| Operation | Budget | Strategy |
|-----------|--------|----------|
| Detection (all strategies) | <500ms | Parallel, 200ms timeout each |
| Source indexing (10k lines) | <2s | AST parsing, skip node_modules |
| Drift probe (per node) | <100ms | Pre-built symbol index |
| State DAG with sources | <5s | Streaming progress |
| Workspace link confirmation | <500ms | Async persistence |
| Toast appearance | <100ms | Render immediately |

**Critical**: Detection must not block initial State DAG render. Show DAG immediately with placeholder, then show toast for linking.

---

## CLI Interface

\`\`\`bash
# Detect related projects
sunwell workspace detect ~/my-docs
# Output:
# Found 2 potential source code links:
#   95% ../           Python (pyproject.toml in parent)
#   75% ../acme-api   Python (same GitHub org)

# Link explicitly
sunwell workspace link ~/my-docs --target ~/acme-api

# View current links
sunwell workspace show ~/my-docs
# Output:
# Workspace: ~/my-docs
# Topology: polyrepo
# Links:
#   -> ~/acme-api (source_code, python, confirmed 2026-01-23)
#   Source symbols: 1,247

# Remove a link
sunwell workspace unlink ~/my-docs --target ~/acme-api

# Scan with detection disabled
sunwell scan ~/my-docs --no-detect

# Scan with explicit link (one-time)
sunwell scan ~/my-docs --link ~/acme-api
\`\`\`

---

## Persistence

### Per-Project: \`.sunwell/workspace.json\`

\`\`\`json
{
  "version": 1,
  "id": "a1b2c3d4e5f6",
  "primary": "/Users/me/projects/acme/docs",
  "topology": "polyrepo",
  "links": [
    {
      "source": "/Users/me/projects/acme/docs",
      "target": "/Users/me/projects/acme-api",
      "relationship": "source_code",
      "confidence": 0.95,
      "evidence": "Manually linked by user",
      "language": "python",
      "confirmed": true,
      "created_at": "2026-01-23T12:00:00Z"
    }
  ],
  "created_at": "2026-01-23T12:00:00Z",
  "updated_at": "2026-01-23T14:30:00Z"
}
\`\`\`

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Auto-detection accuracy (monorepo) | >95% |
| Auto-detection accuracy (polyrepo) | >80% |
| User confirmation rate | >85% |
| Drift detection activation | 5x increase |
| Detection latency | <500ms (p95) |
| Indexing latency (10k lines) | <2s (p95) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| False positive links | Require user confirmation, show confidence % |
| Huge linked repos slow indexing | Index lazily, cache results, skip node_modules |
| Stale source index | Re-index on config change, show age |
| Privacy (exposing paths) | Keep workspace.json local, never upload |
| Detection strategies time out | Parallel execution with per-strategy timeout |
| AST parsing fails | Graceful degradation to regex-based extraction |

---

## Open Questions (Resolved)

1. ~~Should workspace links be bidirectional?~~ **No.** Links are directional: docs->code.

2. ~~How to handle moves/renames?~~ **Detect stale links on scan.** Show warning and offer to re-detect.

3. ~~Multi-repo workspaces?~~ **Yes.** The design supports multiple source roots via \`Workspace.links[]\`.

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: Detection + Persistence | 1 week | WorkspaceDetector, CLI, persistence |
| Phase 2: Source Indexing + Drift | 1 week | SourceContext, DriftProbe |
| Phase 3: Tauri Bridge | 3 days | workspace.rs |
| Phase 4: Studio UI | 3 days | Toast, badges |
| **Total** | **~2.5 weeks** | Full workspace-aware scanning |

---

## References

### Internal
- RFC-100: Orthogonal IDE (State DAG foundation)
- \`src/sunwell/analysis/state_dag.py\`: StateDagBuilder
- \`src/sunwell/analysis/scanners/docs.py\`: DocsScanner
- \`studio/src-tauri/src/coordinator.rs\`: Tauri patterns

### External
- [Sphinx autodoc paths](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html)
- [MkDocs repo_url](https://www.mkdocs.org/user-guide/configuration/#repo_url)
- [Python AST module](https://docs.python.org/3/library/ast.html)
