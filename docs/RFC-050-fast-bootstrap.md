# RFC-050: Fast Bootstrap — Day-1 Intelligence from Git History

**Status**: Draft (Revised)  
**Created**: 2026-01-19  
**Revised**: 2026-01-19 — Added design alternatives, pre-work section, open questions  
**Authors**: Sunwell Team  
**Depends on**: RFC-045 (Project Intelligence)  
**Enables**: Immediate value from first `sunwell init`  
**Confidence**: 81% → 89% (after revision)

---

## Summary

Fast Bootstrap eliminates the cold start problem by mining existing project artifacts — git history, documentation, code patterns, and configuration — to provide **immediate intelligence** before Sunwell has learned anything from conversations.

**Core insight**: Every mature codebase already contains institutional knowledge. It's encoded in commit messages, file ownership, naming conventions, README sections, and code comments. We just need to extract it.

**Design approach**: On `sunwell init`, run a comprehensive **deterministic scan** (Option A — see Design Alternatives) that populates RFC-045's intelligence stores (DecisionMemory, PatternProfile, CodebaseGraph) from git, code, and config. Optional LLM for ambiguous cases. User sees value in the first session, not after weeks of learning.

**One-liner**: ~30 seconds of scanning → immediate "senior engineer who knows your codebase" experience.

> **Note**: Performance targets (30-60s) are estimates based on similar tools. Actual timing will be validated during Phase 1 prototyping against the Sunwell codebase (302 files, ~15K LOC).

---

## Motivation

### The Cold Start Problem

RFC-045 (Project Intelligence) builds intelligence over time through:
- Conversations → Decision Memory
- User edits → Pattern Learning
- Execution → Failure Memory
- Code changes → Codebase Graph

But this takes **weeks** to become valuable:

```
┌────────────────────────────────────────────────────────────────────┐
│                    COLD START TIMELINE                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Day 1                  Day 7                  Day 30              │
│  ─────                  ─────                  ──────              │
│  • 0 decisions          • 3 decisions          • 20+ decisions     │
│  • 0 patterns           • Some patterns        • Rich patterns     │
│  • 0 failures           • 1 failure            • 10+ failures      │
│  • Empty graph          • Partial graph        • Full graph        │
│                                                                    │
│  Intelligence: 0%       Intelligence: 15%      Intelligence: 80%   │
│                                                                    │
│  User experience:       User experience:       User experience:    │
│  "Why doesn't it        "Starting to feel     "Feels like a       │
│   remember anything?"    a bit smarter"        teammate"           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

This is the **churn window** — the first weeks where users evaluate the tool but it hasn't learned enough to demonstrate value.

### What Already Exists

Every mature codebase has embedded intelligence:

| Source | Contains | Intelligence Type |
|--------|----------|-------------------|
| **Git history** | Authors, dates, commit messages | Ownership, change patterns, decisions |
| **Git blame** | Line-by-line authorship | Hot spots, expertise areas |
| **README.md** | Setup, architecture, decisions | Project context, rationale |
| **docstrings** | Function/class documentation | API contracts, patterns |
| **Comments** | TODO, FIXME, design notes | Deferred work, warnings |
| **Config files** | .editorconfig, pyproject.toml, etc. | Style preferences |
| **Directory structure** | Module organization | Architecture patterns |
| **Test structure** | Test naming, coverage | Quality patterns |
| **CI config** | .github/workflows, .gitlab-ci.yml | Quality gates, workflows |

### The Opportunity

```
┌────────────────────────────────────────────────────────────────────┐
│                    FAST BOOTSTRAP TIMELINE                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Minute 0               Minute 1                Day 1              │
│  ────────               ────────                ─────              │
│  $ sunwell init         Scanning...             First session      │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 🔍 Scanning project...                                       │  │
│  │                                                              │  │
│  │ Git history: 847 commits, 12 contributors                    │  │
│  │ Documentation: README.md, CONTRIBUTING.md, docs/             │  │
│  │ Code patterns: snake_case, type hints, Google docstrings     │  │
│  │ Architecture: src/sunwell/ (core), tests/ (pytest)           │  │
│  │                                                              │  │
│  │ ✅ Bootstrap complete                                        │  │
│  │                                                              │  │
│  │ Intelligence bootstrapped:                                   │  │
│  │   • 12 inferred decisions (from commits, README)             │  │
│  │   • 8 style patterns (from code analysis)                    │  │
│  │   • 234 functions, 45 classes in codebase graph              │  │
│  │   • 3 ownership domains (auth: alice, payments: bob, ...)    │  │
│  │                                                              │  │
│  │ Ready. Run `sunwell chat` or `sunwell intel status`          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Intelligence: 60%      Intelligence: 60%      Intelligence: 70%   │
│  (bootstrapped)         (same)                 (refined by usage)  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Day-1 value**: User gets 60% of "senior engineer" experience immediately. Conversations refine from 60% → 90% over time, but never start from zero.

---

## Goals and Non-Goals

### Goals

1. **Immediate pattern recognition** — Code style, naming, imports detected from existing code
2. **Implicit decision extraction** — Infer decisions from commit messages, README, comments
3. **Ownership mapping** — Know who owns what from git blame
4. **Architecture understanding** — Module structure, dependencies from directory layout
5. **Context seeding** — Populate RFC-045 stores without user interaction
6. **Fast execution** — Complete bootstrap in < 60 seconds for typical projects
7. **Incremental updates** — Re-bootstrap incrementally after git pull

### Non-Goals

1. **Perfect accuracy** — Bootstrap patterns are 70% confidence; conversations refine
2. **Deep code understanding** — Semantic analysis is RFC-045; we seed, not replace
3. **External docs scraping** — Wikis, Notion, etc. are future work
4. **Multi-repo intelligence** — Single project focus (RFC-052 future)
5. **Real-time git watching** — We bootstrap on demand, not continuously

---

## Design Overview

### Bootstrap Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BOOTSTRAP PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ sunwell init                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  STAGE 1: SCAN (Deterministic, No LLM)                           │      │
│  │                                                                   │      │
│  │  GitScanner          CodeScanner         DocScanner              │      │
│  │  ├─ commits          ├─ AST patterns     ├─ README.md            │      │
│  │  ├─ blame            ├─ naming conv.     ├─ docstrings           │      │
│  │  ├─ authors          ├─ imports          ├─ comments             │      │
│  │  └─ branches         ├─ type hints       └─ CONTRIBUTING.md      │      │
│  │                      └─ structure                                 │      │
│  │                                                                   │      │
│  │  ConfigScanner       TestScanner                                  │      │
│  │  ├─ pyproject.toml   ├─ test patterns                            │      │
│  │  ├─ .editorconfig    └─ coverage                                 │      │
│  │  └─ CI configs                                                    │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  STAGE 2: EXTRACT (Pattern Matching + Heuristics)                │      │
│  │                                                                   │      │
│  │  RawEvidence                                                      │      │
│  │  ├─ commit_messages[]    → Decision candidates                   │      │
│  │  ├─ naming_samples[]     → Pattern candidates                    │      │
│  │  ├─ doc_sections[]       → Context candidates                    │      │
│  │  └─ blame_map{}          → Ownership candidates                  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  STAGE 3: INFER (Optional LLM for Ambiguous Cases)               │      │
│  │                                                                   │      │
│  │  If commit_message contains decision signal:                     │      │
│  │    → LLM extracts structured Decision                            │      │
│  │                                                                   │      │
│  │  If README contains architecture section:                         │      │
│  │    → LLM extracts architecture context                           │      │
│  │                                                                   │      │
│  │  (Can be skipped with --no-llm for fully deterministic)          │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  STAGE 4: POPULATE (RFC-045 Stores)                              │      │
│  │                                                                   │      │
│  │  DecisionMemory.record_bootstrap(decisions)                      │      │
│  │  PatternProfile.bootstrap(patterns)                              │      │
│  │  CodebaseGraph.build_from_scan(structure)                        │      │
│  │  OwnershipMap.populate(blame_data)                               │      │
│  │                                                                   │      │
│  │  All marked with source="bootstrap", confidence=0.6-0.8          │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  STAGE 5: REPORT                                                  │      │
│  │                                                                   │      │
│  │  BootstrapReport:                                                 │      │
│  │    scan_duration: 28s                                             │      │
│  │    decisions_inferred: 12                                         │      │
│  │    patterns_detected: 8                                           │      │
│  │    codebase_size: 234 functions, 45 classes                      │      │
│  │    ownership_domains: 3                                           │      │
│  │    confidence: 0.72 (average)                                     │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Confidence Levels

Bootstrap intelligence has **lower confidence** than conversation-derived intelligence:

| Source | Confidence | Rationale |
|--------|------------|-----------|
| Explicit user statement | 0.95 | Direct intent |
| User edit → pattern | 0.85 | Implicit confirmation |
| Commit message → decision | 0.70 | Indirect, may be outdated |
| Code pattern → style | 0.75 | May not be intentional |
| README → context | 0.65 | May be stale |
| Git blame → ownership | 0.80 | May have changed |

**Upgrade path**: Bootstrap intelligence upgrades to higher confidence when:
- User confirms pattern during session
- User references decision without contradiction
- New commits reinforce detected pattern

---

## Design Alternatives

Three approaches were considered for bootstrap intelligence extraction:

### Option A: Full Deterministic Scan (Recommended)

**Approach**: Scan all sources (git, code, docs, config) using deterministic heuristics. Use LLM only for ambiguous decision extraction.

```
┌─────────────────────────────────────────────────────────────┐
│  Deterministic Scanners (90%)  →  Optional LLM (10%)        │
│  ├─ Git log parsing            ├─ Ambiguous commit messages │
│  ├─ AST analysis               └─ Complex architecture docs │
│  ├─ Regex patterns                                          │
│  └─ Config parsing                                          │
└─────────────────────────────────────────────────────────────┘
```

| Pros | Cons |
|------|------|
| Fast (~30s for typical projects) | May miss nuanced decisions |
| Works offline (--no-llm mode) | Regex patterns need tuning |
| Reproducible results | Less accurate for unstructured docs |
| Low cost (minimal LLM calls) | |

**Selected because**: Speed and offline capability are critical for day-1 experience. LLM fallback handles edge cases without blocking.

### Option B: LLM-First Analysis

**Approach**: Feed all project artifacts to LLM for comprehensive analysis.

```
┌─────────────────────────────────────────────────────────────┐
│  Collect Artifacts  →  LLM Analysis  →  Structured Output   │
│  ├─ README.md         "Analyze this    ├─ Decisions         │
│  ├─ Key source files   project and     ├─ Patterns          │
│  └─ Git log summary    extract..."     └─ Architecture      │
└─────────────────────────────────────────────────────────────┘
```

| Pros | Cons |
|------|------|
| Higher accuracy for decisions | Slow (2-5 min for large projects) |
| Understands context better | Requires API key on day 1 |
| Handles unstructured docs | Expensive (~$0.50-2.00 per bootstrap) |
| | Non-deterministic results |

**Rejected because**: Cold start users shouldn't need API setup or pay for bootstrap. Speed is critical for first impression.

### Option C: Lazy Bootstrap (On-Demand)

**Approach**: Don't scan upfront. Extract intelligence when first relevant query occurs.

```
┌─────────────────────────────────────────────────────────────┐
│  User asks about auth  →  Scan auth/ dir  →  Cache result   │
│  User asks about tests →  Scan tests/     →  Cache result   │
│  (Build intelligence incrementally per-topic)               │
└─────────────────────────────────────────────────────────────┘
```

| Pros | Cons |
|------|------|
| Zero upfront cost | First query is slow |
| Only scans what's needed | No proactive intelligence |
| Lower memory usage | Can't suggest patterns user hasn't asked about |
| | Complex cache invalidation |

**Rejected because**: Users expect immediate value. Lazy approach means first session feels unintelligent. Proactive pattern suggestion is a key feature.

### Decision Matrix

| Criterion | Weight | Option A | Option B | Option C |
|-----------|--------|----------|----------|----------|
| Speed (< 60s) | 30% | ✅ 30s | ❌ 3min | ⚠️ varies |
| Offline capable | 20% | ✅ yes | ❌ no | ✅ yes |
| Accuracy | 20% | ⚠️ 75% | ✅ 90% | ⚠️ 75% |
| Day-1 experience | 20% | ✅ immediate | ⚠️ setup needed | ❌ delayed |
| Cost | 10% | ✅ $0 | ❌ $0.50+ | ✅ $0 |
| **Total** | 100% | **88%** | **62%** | **58%** |

**Conclusion**: Option A (Full Deterministic Scan) selected for best balance of speed, offline capability, and day-1 experience.

---

## Pre-Work Required

Before implementing RFC-050, the following RFC-045 changes are needed:

### 1. DecisionMemory API Extension

Add `source` parameter to track bootstrap vs conversation decisions:

```python
# Current signature (intelligence/decisions.py:210-221)
async def record_decision(
    self,
    category: str,
    question: str,
    choice: str,
    rejected: list[tuple[str, str]],
    rationale: str,
    context: str = "",
    session_id: str = "",
    confidence: float = 1.0,
    supersedes: str | None = None,
) -> Decision:

# Required extension
async def record_decision(
    self,
    # ... existing params ...
    source: Literal["conversation", "bootstrap"] = "conversation",  # NEW
    metadata: dict[str, Any] | None = None,  # NEW: for bootstrap provenance
) -> Decision:
```

**File**: `src/sunwell/intelligence/decisions.py`
**Effort**: ~30 min

### 2. PatternProfile.bootstrap() Classmethod

Add factory method for bootstrap-sourced patterns:

```python
# Add to intelligence/patterns.py
@classmethod
def bootstrap(cls, patterns: BootstrapPatterns) -> PatternProfile:
    """Create profile from bootstrap analysis.
    
    All patterns marked with:
    - confidence < 0.8 (can be overridden by edits)
    - evidence from "bootstrap:*" sources
    """
    return cls(
        naming_conventions=patterns.naming,
        import_style=patterns.imports,
        # ... 
        confidence={k: 0.75 for k in fields},
        evidence={k: ["bootstrap:code_analysis"] for k in fields},
    )
```

**File**: `src/sunwell/intelligence/patterns.py`
**Effort**: ~1 hour

### 3. ProjectContext Extension

Add `OwnershipMap` and `bootstrap_status` fields:

```python
# Extend intelligence/context.py
@dataclass
class ProjectContext:
    # Existing fields...
    simulacrum: SimulacrumStore
    decisions: DecisionMemory
    codebase: CodebaseGraph
    patterns: PatternProfile
    failures: FailureMemory
    
    # NEW: From RFC-050
    ownership: OwnershipMap | None = None
    """Code ownership from git blame analysis (optional)."""
    
    bootstrap_status: BootstrapStatus | None = None
    """When/what was bootstrapped."""
```

**File**: `src/sunwell/intelligence/context.py`
**Effort**: ~30 min

### Pre-Work Checklist

- [ ] Extend `DecisionMemory.record_decision()` with `source` param
- [ ] Add `PatternProfile.bootstrap()` classmethod
- [ ] Add `OwnershipMap` to `ProjectContext`
- [ ] Add `BootstrapStatus` tracking
- [ ] Unit tests for new APIs

**Total pre-work effort**: ~3 hours

---

## Components

### 1. Git Scanner

Extracts intelligence from git history.

```python
@dataclass(frozen=True, slots=True)
class GitEvidence:
    """Evidence extracted from git history."""
    
    commits: tuple[CommitInfo, ...]
    """Recent commits with parsed metadata."""
    
    blame_map: dict[Path, list[BlameRegion]]
    """File → blame regions for ownership."""
    
    contributor_stats: dict[str, ContributorStats]
    """Author → contribution statistics."""
    
    change_frequency: dict[Path, float]
    """File → changes per month (churn)."""
    
    branch_patterns: BranchPatterns
    """Branch naming, merge patterns."""


@dataclass(frozen=True, slots=True)
class CommitInfo:
    """Parsed commit information."""
    
    sha: str
    author: str
    date: datetime
    message: str
    files_changed: tuple[Path, ...]
    
    # Detected signals
    is_decision: bool
    """Commit message contains decision language."""
    
    is_fix: bool
    """Commit message indicates fix (fix:, bugfix, etc.)."""
    
    is_refactor: bool
    """Commit message indicates refactoring."""
    
    mentioned_files: tuple[str, ...]
    """Files/modules explicitly mentioned in message."""


@dataclass(frozen=True, slots=True)
class BlameRegion:
    """A region of code with authorship information."""
    
    start_line: int
    end_line: int
    author: str
    date: datetime
    commit_sha: str


class GitScanner:
    """Extract intelligence from git history."""
    
    def __init__(
        self,
        root: Path,
        max_commits: int = 1000,
        max_age_days: int = 365,
    ):
        self.root = root
        self.max_commits = max_commits
        self.max_age_days = max_age_days
    
    async def scan(self) -> GitEvidence:
        """Scan git history and extract evidence."""
        return GitEvidence(
            commits=await self._scan_commits(),
            blame_map=await self._scan_blame(),
            contributor_stats=await self._compute_contributor_stats(),
            change_frequency=await self._compute_change_frequency(),
            branch_patterns=await self._analyze_branches(),
        )
    
    async def _scan_commits(self) -> tuple[CommitInfo, ...]:
        """Parse recent commits for decision signals.
        
        Decision signal patterns:
        - "decided to", "chose", "switched to"
        - "instead of", "over", "rather than"
        - "because", "since", "due to"
        - Conventional commits: feat:, fix:, refactor:
        """
        commits = []
        
        # git log with custom format
        result = await self._run_git([
            "log", f"--max-count={self.max_commits}",
            f"--since={self.max_age_days} days ago",
            "--format=%H|%an|%aI|%s",
            "--name-only",
        ])
        
        for commit_block in self._parse_log_output(result):
            sha, author, date, message, files = commit_block
            
            commits.append(CommitInfo(
                sha=sha,
                author=author,
                date=datetime.fromisoformat(date),
                message=message,
                files_changed=tuple(Path(f) for f in files),
                is_decision=self._detect_decision(message),
                is_fix=self._detect_fix(message),
                is_refactor=self._detect_refactor(message),
                mentioned_files=self._extract_file_mentions(message),
            ))
        
        return tuple(commits)
    
    async def _scan_blame(self) -> dict[Path, list[BlameRegion]]:
        """Run git blame on key files for ownership mapping.
        
        Only blame:
        - Files > 100 lines (significant)
        - Modified in last 90 days (active)
        - Not in vendor/generated directories
        """
        blame_map = {}
        
        # Get active, significant files
        active_files = await self._get_active_files()
        
        for file in active_files[:50]:  # Limit for performance
            regions = await self._blame_file(file)
            if regions:
                blame_map[file] = regions
        
        return blame_map
    
    def _detect_decision(self, message: str) -> bool:
        """Detect if commit message contains decision language."""
        decision_patterns = [
            r"\b(decided|chose|selected|picked|switched to|moved to)\b",
            r"\b(instead of|over|rather than|not|rejected)\b",
            r"\b(because|since|due to|in order to|so that)\b",
            r"^(feat|refactor|chore|BREAKING)(\(.+\))?:",  # Conventional commits
        ]
        
        message_lower = message.lower()
        for pattern in decision_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        return False
    
    def _detect_fix(self, message: str) -> bool:
        """Detect if commit is a fix."""
        fix_patterns = [
            r"^fix(\(.+\))?:",
            r"\b(fix|bugfix|hotfix|patch)\b",
            r"\b(resolve|close|closes)\s+#\d+",
        ]
        message_lower = message.lower()
        return any(re.search(p, message_lower) for p in fix_patterns)
```

---

### 2. Code Scanner

Analyzes code for patterns without execution.

```python
@dataclass(frozen=True, slots=True)
class CodeEvidence:
    """Evidence extracted from code analysis."""
    
    naming_patterns: NamingPatterns
    """Detected naming conventions."""
    
    import_patterns: ImportPatterns
    """Import organization style."""
    
    type_hint_usage: TypeHintUsage
    """Type annotation prevalence."""
    
    docstring_style: DocstringStyle
    """Docstring format (Google, NumPy, Sphinx, none)."""
    
    module_structure: ModuleStructure
    """Directory organization patterns."""
    
    test_patterns: TestPatterns
    """Testing conventions and coverage."""


@dataclass(frozen=True, slots=True)
class NamingPatterns:
    """Detected naming conventions with evidence counts."""
    
    function_style: Literal["snake_case", "camelCase", "mixed"]
    function_samples: int
    
    class_style: Literal["PascalCase", "camelCase", "mixed"]
    class_samples: int
    
    constant_style: Literal["UPPER_SNAKE", "lower_snake", "mixed"]
    constant_samples: int
    
    private_prefix: Literal["_", "__", "none", "mixed"]
    private_samples: int


@dataclass(frozen=True, slots=True)
class TypeHintUsage:
    """Type annotation prevalence analysis."""
    
    level: Literal["none", "minimal", "public_only", "comprehensive"]
    """Detected level of type hint usage."""
    
    functions_with_hints: int
    functions_total: int
    
    uses_modern_syntax: bool
    """Uses list[] vs List[], str | None vs Optional."""


class CodeScanner:
    """Analyze code patterns without execution."""
    
    def __init__(self, root: Path, include_globs: list[str] | None = None):
        self.root = root
        self.include_globs = include_globs or ["**/*.py"]
    
    async def scan(self) -> CodeEvidence:
        """Scan codebase and extract patterns."""
        files = self._collect_files()
        
        # Parse all files with tree-sitter (fast) or ast (Python-only)
        parsed = await self._parse_files(files)
        
        return CodeEvidence(
            naming_patterns=self._analyze_naming(parsed),
            import_patterns=self._analyze_imports(parsed),
            type_hint_usage=self._analyze_type_hints(parsed),
            docstring_style=self._analyze_docstrings(parsed),
            module_structure=self._analyze_structure(files),
            test_patterns=self._analyze_tests(parsed),
        )
    
    def _analyze_naming(self, parsed: list[ParsedFile]) -> NamingPatterns:
        """Analyze naming conventions across codebase.
        
        Strategy:
        1. Extract all function/class/constant names
        2. Classify each name's style
        3. Vote for dominant style (>70% threshold)
        """
        function_names = []
        class_names = []
        constant_names = []
        private_names = []
        
        for file in parsed:
            function_names.extend(file.function_names)
            class_names.extend(file.class_names)
            constant_names.extend(file.constant_names)
            private_names.extend(file.private_names)
        
        return NamingPatterns(
            function_style=self._classify_style(function_names),
            function_samples=len(function_names),
            class_style=self._classify_style(class_names),
            class_samples=len(class_names),
            constant_style=self._classify_style(constant_names),
            constant_samples=len(constant_names),
            private_prefix=self._classify_private(private_names),
            private_samples=len(private_names),
        )
    
    def _classify_style(self, names: list[str]) -> str:
        """Classify naming style from samples."""
        if not names:
            return "mixed"
        
        snake = sum(1 for n in names if self._is_snake_case(n))
        camel = sum(1 for n in names if self._is_camel_case(n))
        pascal = sum(1 for n in names if self._is_pascal_case(n))
        
        total = len(names)
        threshold = 0.7
        
        if snake / total > threshold:
            return "snake_case"
        elif camel / total > threshold:
            return "camelCase"
        elif pascal / total > threshold:
            return "PascalCase"
        else:
            return "mixed"
    
    def _analyze_docstrings(self, parsed: list[ParsedFile]) -> DocstringStyle:
        """Detect docstring format from samples.
        
        Google: Args:, Returns:, Raises:
        NumPy: Parameters\n----------
        Sphinx: :param name: description
        """
        docstrings = []
        for file in parsed:
            docstrings.extend(file.docstrings)
        
        if not docstrings:
            return DocstringStyle(style="none", samples=0, consistency=1.0)
        
        google_count = sum(1 for d in docstrings if self._is_google_docstring(d))
        numpy_count = sum(1 for d in docstrings if self._is_numpy_docstring(d))
        sphinx_count = sum(1 for d in docstrings if self._is_sphinx_docstring(d))
        
        total = len(docstrings)
        
        if google_count / total > 0.5:
            return DocstringStyle(style="google", samples=total, consistency=google_count/total)
        elif numpy_count / total > 0.5:
            return DocstringStyle(style="numpy", samples=total, consistency=numpy_count/total)
        elif sphinx_count / total > 0.5:
            return DocstringStyle(style="sphinx", samples=total, consistency=sphinx_count/total)
        else:
            return DocstringStyle(style="mixed", samples=total, consistency=0.0)
```

---

### 3. Documentation Scanner

Extracts context from README and other docs.

```python
@dataclass(frozen=True, slots=True)
class DocEvidence:
    """Evidence extracted from documentation."""
    
    project_name: str | None
    """Project name from README title or pyproject.toml."""
    
    project_description: str | None
    """One-line description."""
    
    architecture_sections: tuple[ArchitectureSection, ...]
    """Detected architecture/design sections."""
    
    decision_sections: tuple[DecisionSection, ...]
    """Sections that explain why decisions were made."""
    
    setup_instructions: SetupInstructions | None
    """How to set up the project."""
    
    contribution_guidelines: ContributionGuidelines | None
    """From CONTRIBUTING.md."""


@dataclass(frozen=True, slots=True)
class ArchitectureSection:
    """A section describing architecture or design."""
    
    source_file: Path
    heading: str
    content: str
    mentions_modules: tuple[str, ...]
    """Module names mentioned in this section."""


@dataclass(frozen=True, slots=True)
class DecisionSection:
    """A section explaining a decision."""
    
    source_file: Path
    heading: str
    content: str
    
    # Extracted structure
    question: str | None
    """What was decided? (inferred)"""
    
    choice: str | None
    """What was chosen?"""
    
    rationale: str | None
    """Why?"""


class DocScanner:
    """Extract intelligence from documentation files."""
    
    DOC_FILES = [
        "README.md",
        "README.rst",
        "README",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "DECISIONS.md",
        "ADR.md",
        "docs/architecture.md",
        "docs/design.md",
        "CONTRIBUTING.md",
    ]
    
    def __init__(self, root: Path):
        self.root = root
    
    async def scan(self) -> DocEvidence:
        """Scan documentation files."""
        docs = self._find_doc_files()
        
        architecture_sections = []
        decision_sections = []
        
        for doc_path in docs:
            content = doc_path.read_text()
            sections = self._parse_markdown_sections(content)
            
            for section in sections:
                if self._is_architecture_section(section):
                    architecture_sections.append(
                        ArchitectureSection(
                            source_file=doc_path,
                            heading=section.heading,
                            content=section.content,
                            mentions_modules=self._extract_module_mentions(section.content),
                        )
                    )
                
                if self._is_decision_section(section):
                    decision_sections.append(
                        self._extract_decision(doc_path, section)
                    )
        
        return DocEvidence(
            project_name=self._extract_project_name(),
            project_description=self._extract_description(),
            architecture_sections=tuple(architecture_sections),
            decision_sections=tuple(decision_sections),
            setup_instructions=self._extract_setup(),
            contribution_guidelines=self._extract_contributing(),
        )
    
    def _is_architecture_section(self, section: MarkdownSection) -> bool:
        """Detect architecture/design sections."""
        keywords = [
            "architecture", "design", "structure", "overview",
            "how it works", "internals", "modules", "components",
        ]
        heading_lower = section.heading.lower()
        return any(kw in heading_lower for kw in keywords)
    
    def _is_decision_section(self, section: MarkdownSection) -> bool:
        """Detect decision/rationale sections."""
        keywords = [
            "decision", "why", "rationale", "choice", "chose",
            "trade-off", "tradeoff", "comparison", "vs",
        ]
        heading_lower = section.heading.lower()
        return any(kw in heading_lower for kw in keywords)
    
    def _extract_decision(
        self,
        source: Path,
        section: MarkdownSection,
    ) -> DecisionSection:
        """Extract structured decision from section."""
        content = section.content
        
        # Simple heuristics for question/choice/rationale
        question = None
        choice = None
        rationale = None
        
        # Look for question patterns
        if match := re.search(r"\b(why|how|what|which)\b[^.?]*\?", content, re.I):
            question = match.group(0).strip()
        
        # Look for choice patterns
        if match := re.search(r"\b(chose|selected|decided on|using|use)\s+(\w+)", content, re.I):
            choice = match.group(2).strip()
        
        # Look for rationale patterns
        if match := re.search(r"\b(because|since|due to|in order to)\b([^.]+)", content, re.I):
            rationale = match.group(0).strip()
        
        return DecisionSection(
            source_file=source,
            heading=section.heading,
            content=content,
            question=question,
            choice=choice,
            rationale=rationale,
        )
```

---

### 4. Config Scanner

Extracts patterns from configuration files.

```python
@dataclass(frozen=True, slots=True)
class ConfigEvidence:
    """Evidence from configuration files."""
    
    python_version: str | None
    """From pyproject.toml or .python-version."""
    
    formatter: Literal["black", "ruff", "yapf", "autopep8", "none"] | None
    """Detected formatter from config."""
    
    linter: Literal["ruff", "flake8", "pylint", "none"] | None
    """Detected linter."""
    
    type_checker: Literal["mypy", "pyright", "ty", "none"] | None
    """Detected type checker."""
    
    test_framework: Literal["pytest", "unittest", "nose", "none"] | None
    """Detected test framework."""
    
    line_length: int | None
    """Configured line length."""
    
    ci_provider: Literal["github", "gitlab", "jenkins", "none"] | None
    """Detected CI/CD provider."""
    
    ci_checks: tuple[str, ...]
    """Checks run in CI (lint, test, typecheck, etc.)."""


class ConfigScanner:
    """Extract patterns from configuration files."""
    
    CONFIG_FILES = {
        "pyproject.toml": "_parse_pyproject",
        "setup.cfg": "_parse_setup_cfg",
        ".editorconfig": "_parse_editorconfig",
        ".pre-commit-config.yaml": "_parse_precommit",
        "ruff.toml": "_parse_ruff",
        "mypy.ini": "_parse_mypy",
        ".github/workflows/*.yml": "_parse_github_actions",
        ".gitlab-ci.yml": "_parse_gitlab_ci",
    }
    
    def __init__(self, root: Path):
        self.root = root
    
    async def scan(self) -> ConfigEvidence:
        """Scan configuration files."""
        evidence = {}
        
        for pattern, parser_name in self.CONFIG_FILES.items():
            files = list(self.root.glob(pattern))
            if files:
                parser = getattr(self, parser_name)
                for file in files:
                    evidence.update(parser(file))
        
        return ConfigEvidence(
            python_version=evidence.get("python_version"),
            formatter=evidence.get("formatter"),
            linter=evidence.get("linter"),
            type_checker=evidence.get("type_checker"),
            test_framework=evidence.get("test_framework"),
            line_length=evidence.get("line_length"),
            ci_provider=evidence.get("ci_provider"),
            ci_checks=tuple(evidence.get("ci_checks", [])),
        )
    
    def _parse_pyproject(self, path: Path) -> dict:
        """Parse pyproject.toml for tool configurations."""
        import tomllib
        
        content = tomllib.loads(path.read_text())
        result = {}
        
        # Python version
        if requires := content.get("project", {}).get("requires-python"):
            result["python_version"] = requires
        
        # Ruff
        if "tool" in content and "ruff" in content["tool"]:
            result["formatter"] = "ruff"
            result["linter"] = "ruff"
            if line_length := content["tool"]["ruff"].get("line-length"):
                result["line_length"] = line_length
        
        # Black
        if "tool" in content and "black" in content["tool"]:
            result["formatter"] = "black"
            if line_length := content["tool"]["black"].get("line-length"):
                result["line_length"] = line_length
        
        # Mypy
        if "tool" in content and "mypy" in content["tool"]:
            result["type_checker"] = "mypy"
        
        # Pytest
        if "tool" in content and "pytest" in content["tool"]:
            result["test_framework"] = "pytest"
        
        return result
    
    def _parse_github_actions(self, path: Path) -> dict:
        """Parse GitHub Actions workflow for CI patterns."""
        import yaml
        
        content = yaml.safe_load(path.read_text())
        result = {"ci_provider": "github", "ci_checks": []}
        
        for job in content.get("jobs", {}).values():
            for step in job.get("steps", []):
                run = step.get("run", "")
                
                if "ruff" in run or "flake8" in run:
                    result["ci_checks"].append("lint")
                if "pytest" in run or "python -m unittest" in run:
                    result["ci_checks"].append("test")
                if "mypy" in run or "pyright" in run:
                    result["ci_checks"].append("typecheck")
        
        return result
```

---

### 5. Bootstrap Orchestrator

Coordinates all scanners and populates RFC-045 stores.

```python
@dataclass
class BootstrapResult:
    """Result of bootstrap process."""
    
    duration: timedelta
    """How long the scan took."""
    
    decisions_inferred: int
    """Decisions added to DecisionMemory."""
    
    patterns_detected: int
    """Patterns added to PatternProfile."""
    
    codebase_functions: int
    codebase_classes: int
    
    ownership_domains: int
    """Distinct ownership areas identified."""
    
    average_confidence: float
    """Average confidence of bootstrapped data."""
    
    warnings: tuple[str, ...]
    """Any warnings during bootstrap."""


class BootstrapOrchestrator:
    """Orchestrate the bootstrap process."""
    
    def __init__(
        self,
        root: Path,
        context: ProjectContext,
        use_llm: bool = True,
        verbose: bool = False,
    ):
        self.root = root
        self.context = context
        self.use_llm = use_llm
        self.verbose = verbose
        
        self.git_scanner = GitScanner(root)
        self.code_scanner = CodeScanner(root)
        self.doc_scanner = DocScanner(root)
        self.config_scanner = ConfigScanner(root)
    
    async def bootstrap(self) -> BootstrapResult:
        """Run full bootstrap process."""
        start = datetime.now()
        warnings = []
        
        # Stage 1: Scan all sources (parallel)
        git_evidence, code_evidence, doc_evidence, config_evidence = await asyncio.gather(
            self.git_scanner.scan(),
            self.code_scanner.scan(),
            self.doc_scanner.scan(),
            self.config_scanner.scan(),
        )
        
        # Stage 2: Convert evidence to intelligence
        decisions = await self._infer_decisions(git_evidence, doc_evidence)
        patterns = self._infer_patterns(code_evidence, config_evidence)
        ownership = self._infer_ownership(git_evidence)
        
        # Stage 3: Populate RFC-045 stores
        decisions_count = await self._populate_decisions(decisions)
        patterns_count = await self._populate_patterns(patterns)
        await self._populate_codebase_graph(code_evidence)
        ownership_count = await self._populate_ownership(ownership)
        
        # Stage 4: Build report
        duration = datetime.now() - start
        
        return BootstrapResult(
            duration=duration,
            decisions_inferred=decisions_count,
            patterns_detected=patterns_count,
            codebase_functions=len(code_evidence.module_structure.functions),
            codebase_classes=len(code_evidence.module_structure.classes),
            ownership_domains=ownership_count,
            average_confidence=0.72,  # Bootstrap default
            warnings=tuple(warnings),
        )
    
    async def _infer_decisions(
        self,
        git: GitEvidence,
        doc: DocEvidence,
    ) -> list[BootstrapDecision]:
        """Infer decisions from git commits and docs.
        
        Sources (in priority order):
        1. Doc decision sections (most explicit)
        2. Commit messages with decision language
        3. Config file choices (implicit decisions)
        """
        decisions = []
        
        # From documentation
        for section in doc.decision_sections:
            if section.question and section.choice:
                decisions.append(BootstrapDecision(
                    source="doc",
                    source_file=section.source_file,
                    question=section.question,
                    choice=section.choice,
                    rationale=section.rationale,
                    confidence=0.75,  # Docs may be stale
                ))
        
        # From commits
        decision_commits = [c for c in git.commits if c.is_decision]
        
        if self.use_llm and decision_commits:
            # Use LLM to extract structured decisions from commit messages
            decisions.extend(await self._llm_extract_decisions(decision_commits))
        else:
            # Simple heuristic extraction
            for commit in decision_commits[:20]:  # Limit for performance
                if extracted := self._heuristic_extract_decision(commit):
                    decisions.append(extracted)
        
        return decisions
    
    def _infer_patterns(
        self,
        code: CodeEvidence,
        config: ConfigEvidence,
    ) -> PatternProfile:
        """Build PatternProfile from code and config analysis."""
        
        return PatternProfile(
            naming_conventions={
                "function": code.naming_patterns.function_style,
                "class": code.naming_patterns.class_style,
                "constant": code.naming_patterns.constant_style,
            },
            import_style=code.import_patterns.style,
            type_annotation_level=code.type_hint_usage.level,
            docstring_style=code.docstring_style.style,
            
            # From config
            line_length=config.line_length or 100,
            formatter=config.formatter,
            linter=config.linter,
            
            # Mark as bootstrap-sourced
            confidence={
                "naming_conventions": 0.75,
                "import_style": 0.70,
                "type_annotation_level": 0.80,
                "docstring_style": 0.85,
            },
            evidence={
                "naming_conventions": ["bootstrap:code_analysis"],
                "docstring_style": ["bootstrap:code_analysis"],
            },
        )
    
    def _infer_ownership(
        self,
        git: GitEvidence,
    ) -> dict[str, OwnershipDomain]:
        """Infer code ownership from git blame and commit history.
        
        Strategy:
        1. Cluster files by primary author (>50% blame)
        2. Identify domains by directory structure
        3. Find experts per domain (most commits)
        """
        domains = {}
        
        # Group files by directory
        dir_to_files: dict[str, list[Path]] = {}
        for file_path, blame_regions in git.blame_map.items():
            dir_name = file_path.parent.name or "root"
            dir_to_files.setdefault(dir_name, []).append(file_path)
        
        # For each directory, find primary contributor
        for dir_name, files in dir_to_files.items():
            author_lines: dict[str, int] = {}
            
            for file_path in files:
                if file_path in git.blame_map:
                    for region in git.blame_map[file_path]:
                        lines = region.end_line - region.start_line
                        author_lines[region.author] = author_lines.get(region.author, 0) + lines
            
            if author_lines:
                primary_author = max(author_lines, key=author_lines.get)
                total_lines = sum(author_lines.values())
                
                domains[dir_name] = OwnershipDomain(
                    name=dir_name,
                    primary_owner=primary_author,
                    ownership_percentage=author_lines[primary_author] / total_lines,
                    files=tuple(files),
                    secondary_owners=tuple(
                        a for a in author_lines if a != primary_author
                    )[:3],
                )
        
        return domains
    
    async def _populate_decisions(
        self,
        decisions: list[BootstrapDecision],
    ) -> int:
        """Populate DecisionMemory with bootstrapped decisions."""
        count = 0
        
        for decision in decisions:
            # Check for duplicates
            existing = await self.context.decisions.find_relevant_decisions(
                decision.question,
                top_k=1,
            )
            
            if existing and self._is_similar(existing[0].question, decision.question):
                continue  # Skip duplicate
            
            await self.context.decisions.record_decision(
                category=decision.infer_category(),
                question=decision.question,
                choice=decision.choice,
                rejected=[],  # Bootstrap doesn't know what was rejected
                rationale=decision.rationale or "Inferred from bootstrap scan",
                source="bootstrap",
                confidence=decision.confidence,
            )
            count += 1
        
        return count
```

---

### 6. Ownership Map

New component for RFC-045: tracks code ownership.

```python
@dataclass(frozen=True, slots=True)
class OwnershipDomain:
    """A domain of code ownership."""
    
    name: str
    """Domain name (usually directory or module)."""
    
    primary_owner: str
    """Git author who owns most of this code."""
    
    ownership_percentage: float
    """What percentage of code primary_owner wrote."""
    
    files: tuple[Path, ...]
    """Files in this domain."""
    
    secondary_owners: tuple[str, ...]
    """Other significant contributors."""


class OwnershipMap:
    """Track code ownership derived from git history."""
    
    def __init__(self, path: Path):
        self._path = path / "ownership.json"
        self._domains: dict[str, OwnershipDomain] = {}
    
    async def populate(self, domains: dict[str, OwnershipDomain]) -> None:
        """Populate ownership from bootstrap."""
        self._domains = domains
        self._save()
    
    def get_owner(self, file: Path) -> str | None:
        """Get the likely owner of a file."""
        # Find the domain containing this file
        for domain in self._domains.values():
            if file in domain.files:
                return domain.primary_owner
        
        # Try directory match
        dir_name = file.parent.name
        if dir_name in self._domains:
            return self._domains[dir_name].primary_owner
        
        return None
    
    def get_experts(self, file: Path) -> list[str]:
        """Get experts for a file (owner + secondary)."""
        for domain in self._domains.values():
            if file in domain.files:
                return [domain.primary_owner, *domain.secondary_owners]
        return []
    
    def suggest_reviewer(self, changed_files: list[Path]) -> str | None:
        """Suggest a reviewer for a set of changes."""
        owners = [self.get_owner(f) for f in changed_files]
        owners = [o for o in owners if o]
        
        if not owners:
            return None
        
        # Most common owner among changed files
        from collections import Counter
        return Counter(owners).most_common(1)[0][0]
```

---

## Configuration

```yaml
# .sunwell/config.yaml
bootstrap:
  enabled: true
  
  # Run modes
  on_init: true           # Run on `sunwell init`
  on_git_pull: false      # Re-run after git pull (experimental)
  
  # LLM usage
  use_llm: true           # Use LLM for ambiguous decision extraction
  llm_budget: 10          # Max LLM calls during bootstrap
  
  # Git scanning
  git:
    max_commits: 1000     # How far back to scan
    max_age_days: 365     # Ignore commits older than this
    blame_limit: 50       # Max files to git blame
  
  # Confidence thresholds
  confidence:
    decision_from_doc: 0.75
    decision_from_commit: 0.65
    pattern_from_code: 0.75
    ownership_from_blame: 0.80
  
  # What to scan
  include:
    - "*.py"
    - "*.md"
    - "pyproject.toml"
    - ".github/**"
  
  exclude:
    - "vendor/"
    - "generated/"
    - "node_modules/"
    - ".venv/"
```

---

## CLI Integration

```bash
# Initialize project with bootstrap
sunwell init                    # Full bootstrap (default)
sunwell init --no-bootstrap     # Skip bootstrap (empty intelligence)
sunwell init --no-llm           # Bootstrap without LLM calls

# Manual bootstrap control
sunwell bootstrap               # Re-run bootstrap
sunwell bootstrap --incremental # Only scan changes since last bootstrap
sunwell bootstrap --report      # Show what would be bootstrapped

# View bootstrapped data
sunwell intel status            # Shows bootstrap vs learned counts
sunwell intel decisions --source bootstrap  # View bootstrap decisions
sunwell intel patterns                       # View detected patterns
sunwell intel ownership                      # View ownership map

# Debug/inspect
sunwell bootstrap --verbose     # Detailed output during scan
sunwell bootstrap --dry-run     # Scan but don't populate stores
```

### Example Session

```
$ sunwell init

🔍 Initializing Sunwell for /Users/dev/myproject

Scanning project...
  ├─ Git history: 847 commits, 12 contributors
  ├─ Code files: 234 Python files, 45,231 lines
  ├─ Documentation: README.md, CONTRIBUTING.md, docs/
  └─ Configuration: pyproject.toml, .github/workflows/

Extracting intelligence...
  ├─ Decisions: 12 inferred (8 from commits, 4 from docs)
  ├─ Patterns: 8 detected
  │   • Functions: snake_case (97% of 412 samples)
  │   • Classes: PascalCase (100% of 45 samples)
  │   • Type hints: comprehensive (89% of functions)
  │   • Docstrings: Google style (78% consistency)
  │   • Formatter: ruff (from pyproject.toml)
  │   • Line length: 100 (from pyproject.toml)
  ├─ Codebase graph: 234 functions, 45 classes
  └─ Ownership: 3 domains identified
      • auth/: alice (67%)
      • payments/: bob (54%)
      • api/: shared (no dominant owner)

✅ Bootstrap complete in 28 seconds

Intelligence status:
  • Decisions: 12 (bootstrap) + 0 (learned) = 12 total
  • Patterns: 8 (bootstrap), confidence: 0.75 average
  • Codebase: 100% scanned

Run `sunwell chat` to start. Your patterns and decisions are ready.
```

---

## Integration with RFC-045

### Decision Memory Integration

```python
# RFC-045 DecisionMemory extended for bootstrap
class DecisionMemory:
    async def record_decision(
        self,
        category: str,
        question: str,
        choice: str,
        rejected: list[tuple[str, str]],
        rationale: str,
        source: Literal["conversation", "bootstrap"] = "conversation",
        confidence: float = 0.85,
    ) -> Decision:
        """Record a decision.
        
        Bootstrap decisions are marked with:
        - source="bootstrap"
        - Lower confidence (0.6-0.8)
        - No rejected options (not known)
        
        Bootstrap decisions upgrade to conversation confidence when:
        - User references them without contradiction
        - Explicit confirmation during chat
        """
        decision = Decision(
            id=self._generate_id(category, question),
            category=category,
            question=question,
            choice=choice,
            rejected=tuple(RejectedOption(o, r) for o, r in rejected),
            rationale=rationale,
            confidence=confidence,
            timestamp=datetime.now(UTC),
            session_id="bootstrap" if source == "bootstrap" else self._current_session,
            metadata={"source": source},
        )
        
        self._decisions[decision.id] = decision
        self._save()
        return decision
```

### Pattern Profile Integration

```python
# RFC-045 PatternProfile extended for bootstrap
class PatternProfile:
    @classmethod
    def bootstrap(cls, patterns: BootstrapPatterns) -> PatternProfile:
        """Create profile from bootstrap analysis.
        
        All patterns marked with:
        - confidence < 0.8 (can be overridden by edits)
        - evidence from "bootstrap:*" sources
        """
        return cls(
            naming_conventions=patterns.naming,
            import_style=patterns.imports,
            type_annotation_level=patterns.type_hints,
            docstring_style=patterns.docstrings,
            confidence={k: 0.75 for k in patterns.__dataclass_fields__},
            evidence={k: ["bootstrap:code_analysis"] for k in patterns.__dataclass_fields__},
        )
    
    def learn_from_edit(
        self,
        original: str,
        edited: str,
    ) -> None:
        """Learn from user edit.
        
        If edit contradicts bootstrap pattern:
        - Override bootstrap pattern
        - Upgrade confidence to 0.85 (user-confirmed)
        """
        # ... existing learning logic
        
        # If this contradicts a bootstrap pattern, upgrade
        for field, bootstrap_evidence in self.evidence.items():
            if "bootstrap:" in str(bootstrap_evidence):
                # User edit overrides bootstrap
                self.evidence[field] = [self._current_session]
                self.confidence[field] = 0.85
```

### Ownership Map Integration

```python
# New in RFC-045: OwnershipMap as ProjectContext component
@dataclass
class ProjectContext:
    """Unified context combining all intelligence sources."""
    
    # Existing from RFC-045
    simulacrum: SimulacrumStore
    decisions: DecisionMemory
    codebase: CodebaseGraph
    patterns: PatternProfile
    failures: FailureMemory
    
    # NEW: From RFC-050
    ownership: OwnershipMap
    """Code ownership from git blame analysis."""
    
    bootstrap_status: BootstrapStatus
    """Status of bootstrap (when run, what was found)."""
```

---

## Incremental Updates

After initial bootstrap, Sunwell can update intelligence incrementally:

```python
class IncrementalBootstrap:
    """Update bootstrap intelligence after changes."""
    
    def __init__(self, root: Path, context: ProjectContext):
        self.root = root
        self.context = context
        self._last_commit = self._read_last_commit()
    
    async def update_if_needed(self) -> BootstrapUpdate | None:
        """Check for new commits and update intelligence.
        
        Called on session start or after git pull.
        """
        current_commit = await self._get_head_commit()
        
        if current_commit == self._last_commit:
            return None  # No changes
        
        # Get commits since last update
        new_commits = await self._get_commits_since(self._last_commit)
        
        # Extract decisions from new commits only
        new_decisions = await self._extract_decisions_from(new_commits)
        
        # Update ownership for changed files
        changed_files = self._get_changed_files(new_commits)
        await self._update_ownership(changed_files)
        
        # Update codebase graph for changed files
        await self._update_codebase_graph(changed_files)
        
        # Record update
        self._last_commit = current_commit
        self._save_last_commit()
        
        return BootstrapUpdate(
            new_commits=len(new_commits),
            new_decisions=len(new_decisions),
            files_updated=len(changed_files),
        )
```

---

## Risks and Mitigations

### Risk 1: Stale Documentation

**Problem**: README hasn't been updated in a year; bootstrap extracts wrong decisions.

**Mitigation**:
- Lower confidence (0.65) for doc-sourced decisions
- Show "source: README.md, last modified 2024-01-01" in decision display
- Warn if doc is older than recent commits
- User can explicitly dismiss stale decisions

### Risk 2: Inconsistent Code Patterns

**Problem**: Codebase has mixed styles (legacy + new code); bootstrap detects "mixed".

**Mitigation**:
- Report consistency percentage (e.g., "snake_case: 72%")
- Weight recent files higher than old files
- Don't assert pattern if < 70% consistency
- Allow explicit configuration to override

### Risk 3: Git History Noise

**Problem**: Many commits don't contain decision language; false positives.

**Mitigation**:
- Strict decision detection patterns
- LLM validation for ambiguous cases
- Limit to recent commits (1 year default)
- User can exclude specific commits

### Risk 4: Slow Bootstrap

**Problem**: Large monorepos take too long to scan.

**Mitigation**:
- Parallel scanning (git, code, docs run concurrently)
- Limit git blame to 50 most-active files
- Cache AST parsing results
- Progressive scan (show partial results as they complete)

### Risk 5: Privacy Concerns

**Problem**: Git blame reveals author names; sensitive for some teams.

**Mitigation**:
- Opt-out for ownership scanning (`bootstrap.git.blame_enabled: false`)
- Option to anonymize authors ("Author 1", "Author 2")
- Ownership data stored locally only
- Clear data on request

---

## Testing Strategy

### Unit Tests

```python
class TestGitScanner:
    async def test_detects_decision_commits(self):
        """Commits with decision language are flagged."""
        scanner = GitScanner(tmp_path)
        
        # Create git repo with decision commit
        await run_git(tmp_path, ["init"])
        await run_git(tmp_path, ["commit", "--allow-empty", 
            "-m", "feat: chose SQLAlchemy over Django ORM because we need async"])
        
        evidence = await scanner.scan()
        
        assert len(evidence.commits) == 1
        assert evidence.commits[0].is_decision is True
    
    async def test_computes_ownership(self):
        """Ownership computed from git blame."""
        ...


class TestCodeScanner:
    async def test_detects_naming_patterns(self):
        """Naming conventions detected from code."""
        scanner = CodeScanner(tmp_path)
        
        # Create Python file with snake_case
        (tmp_path / "module.py").write_text("""
def get_user_data():
    pass

def fetch_orders():
    pass
        """)
        
        evidence = await scanner.scan()
        
        assert evidence.naming_patterns.function_style == "snake_case"
        assert evidence.naming_patterns.function_samples == 2
    
    async def test_detects_docstring_style(self):
        """Docstring style detected from samples."""
        ...


class TestBootstrapOrchestrator:
    async def test_full_bootstrap(self, sample_project):
        """Full bootstrap populates all stores."""
        context = ProjectContext.create_empty(sample_project)
        orchestrator = BootstrapOrchestrator(sample_project, context)
        
        result = await orchestrator.bootstrap()
        
        assert result.decisions_inferred > 0
        assert result.patterns_detected > 0
        assert len(context.decisions._decisions) > 0
```

### Integration Tests

```python
class TestBootstrapIntegration:
    async def test_bootstrap_to_chat(self, sample_project):
        """Bootstrapped intelligence available in chat."""
        # Run bootstrap
        await run_cli(sample_project, ["init"])
        
        # Start chat, ask about decisions
        response = await run_cli(
            sample_project, 
            ["chat", "--message", "What database are we using?"]
        )
        
        # Should mention bootstrapped decision
        assert "SQLAlchemy" in response or "database" in response.lower()
    
    async def test_incremental_update(self, sample_project):
        """New commits update bootstrap intelligence."""
        # Initial bootstrap
        await run_cli(sample_project, ["init"])
        initial_count = await get_decision_count(sample_project)
        
        # Add commit with decision
        await run_git(sample_project, ["commit", "--allow-empty",
            "-m", "refactor: switched to Redis because we need distributed cache"])
        
        # Re-bootstrap incrementally
        await run_cli(sample_project, ["bootstrap", "--incremental"])
        new_count = await get_decision_count(sample_project)
        
        assert new_count > initial_count
```

---

## Implementation Plan

### Phase 0: Pre-Work (Before Phase 1)

Complete RFC-045 API extensions (see "Pre-Work Required" section):

- [ ] Add `source` param to `DecisionMemory.record_decision()`
- [ ] Add `PatternProfile.bootstrap()` classmethod
- [ ] Add `OwnershipMap` and `bootstrap_status` to `ProjectContext`
- [ ] Unit tests for new APIs

**Effort**: ~3 hours | **Blocking**: Phase 3 (Orchestrator)

### Phase 1: Core Scanners + Validation (Week 1)

- [ ] `GitScanner` — Commit parsing, decision detection, blame
- [ ] `CodeScanner` — Naming patterns, type hints, docstrings
- [ ] Unit tests for both scanners
- [ ] **Validation**: Run scanners on Sunwell repo, document timing
- [ ] **Validation**: Review 50 extracted decisions, calculate precision

### Phase 2: Doc and Config Scanners (Week 2)

- [ ] `DocScanner` — README, architecture sections, decision sections
- [ ] `ConfigScanner` — pyproject.toml, CI configs
- [ ] Unit tests

### Phase 3: Bootstrap Orchestrator (Week 3)

- [ ] `BootstrapOrchestrator` — Coordinate scanners, inference logic
- [ ] RFC-045 integration — `DecisionMemory.record_decision(source="bootstrap")`
- [ ] `PatternProfile.bootstrap()` method
- [ ] CLI: `sunwell init` with bootstrap

### Phase 4: Ownership and Polish (Week 4)

- [ ] `OwnershipMap` — New RFC-045 component
- [ ] `IncrementalBootstrap` — Update after git pull
- [ ] CLI: `sunwell bootstrap`, `sunwell intel ownership`
- [ ] Configuration options
- [ ] Integration tests
- [ ] Documentation

---

## Success Criteria

> **Validation plan**: Targets below will be validated during Phase 1 prototyping against the Sunwell codebase. Metrics marked with † require user studies post-launch.

| Metric | Target | Measurement | Validation |
|--------|--------|-------------|------------|
| Bootstrap time | < 60s | Scan time for 100K LOC project | Phase 1: Benchmark on Sunwell (15K LOC) |
| Decision extraction | > 70% precision | Manual review of 50 bootstrapped decisions | Phase 1: Review against Sunwell commits |
| Pattern detection | > 85% accuracy | Compare to ground truth on test corpus | Phase 1: Compare to manual audit |
| Day-1 intelligence † | > 50% | User survey: "helpful from first session" | Post-launch survey |
| Incremental speed | < 5s | Update time after 10-commit pull | Phase 4: Benchmark |

### Phase 1 Validation Checklist

- [ ] Run `GitScanner` on Sunwell repo, measure time
- [ ] Extract decisions from 100 recent commits, manually score precision
- [ ] Compare detected patterns to actual conventions in codebase
- [ ] Document any regex pattern failures for tuning

---

## Open Questions

Questions to resolve during implementation:

### Q1: Multi-Language Projects

**Question**: How should bootstrap handle projects with multiple languages (e.g., Python backend + TypeScript frontend)?

**Proposed answer**: Scan each language separately with language-specific scanners. Store patterns per-language in `PatternProfile`:

```python
naming_conventions: dict[str, dict[str, str]] = {
    "python": {"function": "snake_case", "class": "PascalCase"},
    "typescript": {"function": "camelCase", "class": "PascalCase"},
}
```

**Status**: Design decision needed in Phase 1.

### Q2: Memory Budget for Large Repos

**Question**: What's the memory footprint for monorepos with 10K+ files?

**Constraints**:
- Max memory: 500MB during bootstrap
- Files in memory: Stream, don't load all at once
- Blame data: Only for top 50 most-active files
- AST parsing: Parse and discard, don't retain trees

**Proposed limits**:
```yaml
bootstrap:
  limits:
    max_files_in_memory: 100
    max_blame_files: 50
    max_commits_to_parse: 1000
    max_memory_mb: 500
```

**Status**: Validate during Phase 1 prototyping.

### Q3: Git History Rewriting

**Question**: How to handle `git push --force` after bootstrap has run?

**Proposed answer**: Detect via `git reflog` on next session start. If history diverged:
1. Log warning: "Git history changed since bootstrap"
2. Offer: `sunwell bootstrap --refresh` to re-scan
3. Don't auto-refresh (avoid surprise slow startup)

**Status**: Implement in Phase 4 (incremental updates).

### Q4: OwnershipMap Privacy

**Question**: Should `OwnershipMap` be opt-in due to author name sensitivity?

**Proposed answer**: Yes, opt-in by default:
```yaml
bootstrap:
  ownership:
    enabled: false  # Opt-in
    anonymize: false  # If true, use "Author 1", "Author 2"
```

**Status**: Config option, implement in Phase 4.

---

## Future Work

1. **External doc scraping** — Mine Notion, Confluence, Wiki
2. **PR/Issue mining** — Extract decisions from GitHub PRs and issues  
3. **Cross-repo patterns** — Learn patterns from user's other projects
4. **Team intelligence** — Shared bootstrap across team members
5. **Continuous learning** — Background bootstrap as code changes

---

## Summary

Fast Bootstrap transforms the Sunwell experience from "blank slate that learns over weeks" to "immediately helpful assistant that refines over time":

| Component | Extracts | Populates | Confidence |
|-----------|----------|-----------|------------|
| `GitScanner` | Commits, blame, authors | DecisionMemory, OwnershipMap | 0.65-0.80 |
| `CodeScanner` | Naming, types, docstrings | PatternProfile, CodebaseGraph | 0.75 |
| `DocScanner` | README, architecture | DecisionMemory, context | 0.65-0.75 |
| `ConfigScanner` | pyproject.toml, CI | PatternProfile | 0.85 |

### The Result

```
Before Bootstrap:                    After Bootstrap:
─────────────────                    ────────────────
Day 1: 0% intelligence               Day 1: 60% intelligence
Day 7: 15% intelligence              Day 7: 75% intelligence  
Day 30: 80% intelligence             Day 30: 90% intelligence

First session: "Why doesn't         First session: "Wow, it already
it remember anything?"               knows our style and decisions!"
```

**The cold start problem is solved.** Users get value from minute one.

---

## References

### RFCs

- RFC-045: Project Intelligence — `src/sunwell/intelligence/`
- RFC-046: Autonomous Backlog — Signal extraction patterns
- RFC-049: External Integration — Future: issue tracker mining

### Implementation Files (to be created)

```
src/sunwell/bootstrap/
├── __init__.py
├── types.py              # Evidence, BootstrapDecision, etc.
├── scanners/
│   ├── __init__.py
│   ├── git.py           # GitScanner
│   ├── code.py          # CodeScanner
│   ├── docs.py          # DocScanner
│   └── config.py        # ConfigScanner
├── orchestrator.py       # BootstrapOrchestrator
├── incremental.py        # IncrementalBootstrap
└── ownership.py          # OwnershipMap

# Modified files
src/sunwell/intelligence/context.py   # Add OwnershipMap, bootstrap_status
src/sunwell/intelligence/decisions.py # Add source="bootstrap" support
src/sunwell/intelligence/patterns.py  # Add bootstrap() classmethod
src/sunwell/cli/main.py              # Add `sunwell init`, `sunwell bootstrap`
```

---

*Last updated: 2026-01-19*
