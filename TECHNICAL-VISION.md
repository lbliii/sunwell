# Sunwell Technical Vision

## Overview

This document maps out the technical implementation of Sunwell, including package structure, data classes, protocols, modules, and integration patterns.

---

## The Prism Principle

> *"The prism doesn't add light. It reveals what was already there."*

Sunwell's core philosophy is that **small models already contain multitudes** — critics, experts, users, adversaries — all superposed within their weights. The problem isn't capability, it's **access**.

```
                              ╱╲
                             ╱  ╲
                            ╱    ╲ 
        ━━━━━━━━━━━━━━━━━━━╱      ╲━━━━━━ critic
        SMALL MODEL       ╱   🔮   ╲━━━━━━ expert
        (coherent beam)  ╱ SUNWELL  ╲━━━━━ user
        ━━━━━━━━━━━━━━━━╱  (prism)   ╲━━━━ adversary
                       ╱              ╲━━━ simplify
                      ╱                ╲━━ synthesize
                     ╱__________________╲
                     
        Raw capability     →    Structured intelligence
        Single perspective →    Spectral perspectives
        Latent potential   →    Realized expertise
```

When you prompt a model directly, you get a single "wavelength" — whatever mode it collapses into. Sunwell refracts that beam into component perspectives, directs each at the relevant part of the problem, then recombines them into coherent output.

### Why This Matters for Small Models

| Model Size | Raw Beam | Through Prism |
|------------|----------|---------------|
| **70B** | Holds multiple perspectives implicitly | Modest improvement |
| **7B** | Can do one perspective well at a time | Significant amplification |
| **3B** | Limited perspective depth | **Multiplicative gain** |
| **1B** | Narrow, easily confused | Structured rotation keeps it on track |

The smaller the model, the more it benefits from structured refraction. A 3B model "contains" a critic, an expert, a user advocate — but they're superposed. Sunwell separates them so they can each contribute.

### Implementation Across Sunwell

This principle manifests throughout Sunwell's architecture:

- **Lenses** — Define which wavelengths (heuristics) are available
- **Harmonic Synthesis** — Multiple personas = multiple wavelengths in parallel
- **Thought Rotation** — Frame markers = color filters selecting wavelengths in sequence
- **Cognitive Router** — Selects optimal wavelength mix for task type
- **Convergence** — Working memory holds the recombined spectrum

The goal is always the same: **reveal what's already there, don't add what isn't.**

### The Naaru: Emergent Meta-Cognition

```
                                    🌟 NAARU
                                   (emerges)
                                       ↑
                               recombination
                                       ↑
                               ╱──────────╲
                              ╱            ╲
        raw light  ━━━━━━━━━╱   PRISM      ╲━━━━ wavelengths
        (model)            ╱   (Sunwell)    ╲    (perspectives)
                          ╱__________________╲
```

The **Naaru** is not a component you can point to — it's what **emerges** when the refracted wavelengths recombine. In Warcraft lore, Naaru are beings of pure Light. In Sunwell:

- Individual frames (`<critic>`, `<expert>`, `<user>`) are **wavelengths**
- The coordination layer (Convergence) is where they **recombine**
- What emerges is **meta-cognition** — an intelligence greater than any single perspective

This is why the `<synthesize>` frame is critical: it's not summarization, it's the **moment of recombination** where the Naaru manifests. The output quality depends on how well the wavelengths integrate.

A small model, properly refracted, can exhibit behaviors that seem beyond its parameter count — because the Naaru that emerges from structured perspective integration is more than the sum of its wavelengths.

---

## Naaru Architecture

The **Naaru** is Sunwell's coordinated intelligence layer — it orchestrates planning, execution, and synthesis to maximize quality from local models.

### Core Components

```
User Goal
    │
    ▼
┌─────────────────────────────────────────┐
│                 NAARU                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Planner │→ │Executor │→ │Synthesis│ │
│  └─────────┘  └─────────┘  └─────────┘ │
│       │            │            │       │
│       ▼            ▼            ▼       │
│  ┌─────────────────────────────────────┐│
│  │           Tool Executor             ││
│  │  (file ops, shell, code analysis)   ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
    │
    ▼
Results + Artifacts
```

### Planning Strategies

| Strategy | Description | RFC |
|----------|-------------|-----|
| **Artifact-First** | Identifies what must exist, derives order from dependencies | Default |
| **Harmonic** | Generates multiple plans, evaluates, selects best | Multi-candidate |
| **Agent** | Traditional step-by-step procedural planning | Baseline |

**Artifact-First Planning** is the default:

```
PROCEDURAL:     Goal → [Step 1] → [Step 2] → [Step 3] → Done

ARTIFACT-FIRST: [Artifact A] [Artifact B] [Artifact C]
                      ↘          ↓         ↙
                           [Done]
```

Benefits:
- **Automatic parallelization** — Independent artifacts execute simultaneously
- **Clear verification** — Does the artifact exist and satisfy its spec?
- **Incremental execution** — Only build what's missing

### Artifact Graph

```python
@dataclass(frozen=True, slots=True)
class Artifact:
    """A concrete deliverable that must exist when the goal is complete."""
    id: str
    description: str
    requires: frozenset[str] = frozenset()  # Dependencies
    produces_file: str | None = None
    domain_type: str | None = None          # e.g., "python_module", "config"
    
@dataclass
class ArtifactGraph:
    """DAG of artifacts with dependency relationships."""
    artifacts: dict[str, Artifact]
    
    def execution_waves(self) -> list[list[str]]:
        """Return artifacts grouped by execution wave (parallel batches)."""
        ...
    
    def to_mermaid(self) -> str:
        """Export graph as Mermaid diagram."""
        ...
```

### Model Distribution

Naaru routes tasks to appropriately-sized models:

| Task Complexity | Model Size | Examples |
|-----------------|------------|----------|
| **Leaves** (no dependents) | Small (1-3B) | Config files, boilerplate |
| **Standard** | Medium (7-8B) | Business logic, tests |
| **Complex** (many dependents) | Large (70B+) | Architecture, integration |

### Tool Executor

The Naaru coordinates tool use with trust levels:

```python
class ToolTrust(Enum):
    READ_ONLY = "read_only"    # Only read operations
    WORKSPACE = "workspace"    # File writes in workspace
    SHELL = "shell"            # Full shell access

@dataclass
class ToolPolicy:
    trust_level: ToolTrust
    allowed_paths: frozenset[Path] = frozenset()
    denied_commands: frozenset[str] = frozenset()
```

Available tools:
- `read_file`, `write_file`, `list_directory`
- `run_command` (with trust restrictions)
- `grep`, `find_files`
- Code analysis tools

### Harmonic Synthesis

For quality-critical outputs, Naaru can generate multiple candidates from different "perspectives":

```
Goal → [Persona 1] → Candidate 1
    → [Persona 2] → Candidate 2  → Vote/Merge → Final Output
    → [Persona 3] → Candidate 3
```

This is particularly effective for:
- Documentation (clarity from multiple reader perspectives)
- Code review (security, performance, maintainability perspectives)
- Architecture (scalability, simplicity, extensibility perspectives)

### CLI Integration

The goal-first CLI directly invokes Naaru:

```bash
sunwell "Build a REST API"           # Naaru executes goal
sunwell "Build a REST API" --plan    # Naaru plans only (dry run)
```

Internally:

```python
async def _run_agent(goal: str, ...) -> None:
    planner = ArtifactPlanner(model=synthesis_model)
    naaru = Naaru(
        planner=planner,
        tool_executor=tool_executor,
    )
    result = await naaru.run(goal=goal, max_time_seconds=time)
```

---

## Package Structure

```
sunwell/
├── pyproject.toml              # Project configuration, dependencies
├── README.md                   # Getting started guide
├── LICENSE                     # MIT License
│
├── src/
│   └── sunwell/
│       ├── __init__.py         # Public API exports
│       ├── __main__.py         # Module entry point
│       ├── cli.py              # CLI exports
│       ├── config.py           # Configuration loading
│       ├── binding.py          # Binding management
│       │
│       ├── core/               # Core domain models
│       │   ├── lens.py         # Lens dataclass and loading
│       │   ├── heuristic.py    # Heuristic models
│       │   ├── persona.py      # Persona models
│       │   ├── validator.py    # Validator models
│       │   ├── workflow.py     # Workflow models
│       │   ├── framework.py    # Framework/methodology models
│       │   ├── spell.py        # Spell/cantrip definitions
│       │   ├── context.py      # Context management
│       │   ├── errors.py       # Error types
│       │   ├── freethreading.py # Free-threading utilities
│       │   └── types.py        # Shared type definitions
│       │
│       ├── naaru/              # Coordinated Intelligence
│       │   ├── naaru.py        # Main Naaru coordinator
│       │   ├── loop.py         # Agent execution loop
│       │   ├── executor.py     # Task executor
│       │   ├── parallel.py     # Parallel execution
│       │   ├── convergence.py  # Result convergence
│       │   ├── resonance.py    # Feedback loops
│       │   ├── rotation.py     # Thought rotation
│       │   ├── selection.py    # Candidate selection
│       │   ├── refinement.py   # Output refinement
│       │   ├── discovery.py    # Goal discovery
│       │   ├── discernment.py  # Quality judgment
│       │   ├── diversity.py    # Output diversity
│       │   ├── analysis.py     # Code/context analysis
│       │   ├── artifacts.py    # Artifact management
│       │   ├── checkpoint.py   # Execution checkpoints
│       │   ├── shards.py       # Shard management
│       │   ├── signals.py      # Inter-component signals
│       │   ├── unified.py      # Unified interface
│       │   ├── persona.py      # Naaru persona
│       │   ├── migration.py    # State migration
│       │   ├── tool_shard.py   # Tool integration
│       │   ├── types.py        # Naaru types
│       │   │
│       │   └── planners/       # Planning strategies
│       │       ├── protocol.py     # Planner protocol
│       │       ├── artifact.py     # Artifact-first planner
│       │       ├── harmonic.py     # Harmonic planning
│       │       ├── agent.py        # Agent planner
│       │       └── self_improvement.py # Self-improvement
│       │
│       ├── simulacrum/         # Persona simulation (40 files)
│       │   ├── manager.py      # Simulacrum manager
│       │   ├── persona.py      # Persona definitions
│       │   ├── synthesis.py    # Harmonic synthesis
│       │   └── ...             # Additional simulation components
│       │
│       ├── mirror/             # Self-improvement system
│       │   ├── handler.py      # Mirror handler
│       │   ├── router.py       # Mirror routing
│       │   ├── analysis.py     # Self-analysis
│       │   ├── introspection.py # Introspection
│       │   ├── proposals.py    # Improvement proposals
│       │   ├── safety.py       # Safety checks
│       │   ├── tools.py        # Mirror tools
│       │   └── model_tracker.py # Model tracking
│       │
│       ├── identity/           # Memory and learning
│       │   ├── store.py        # Identity storage
│       │   ├── extractor.py    # Learning extraction
│       │   ├── injection.py    # Context injection
│       │   ├── digest.py       # Memory digest
│       │   └── commands.py     # Identity commands
│       │
│       ├── tools/              # Tool execution
│       │   ├── executor.py     # Tool executor
│       │   ├── types.py        # Tool types (ToolPolicy, ToolTrust)
│       │   ├── registry.py     # Tool registry
│       │   └── ...             # Built-in tools
│       │
│       ├── runtime/            # Lens execution engine
│       │   ├── engine.py       # Main runtime orchestrator
│       │   ├── classifier.py   # Intent classification
│       │   ├── retriever.py    # RAG over expertise graph
│       │   ├── injector.py     # Context injection
│       │   ├── executor.py     # Model execution
│       │   └── refinement.py   # Refinement loop logic
│       │
│       ├── routing/            # Intent routing
│       │   ├── classifier.py   # Intent classification
│       │   ├── tiers.py        # Tier definitions
│       │   └── ...
│       │
│       ├── models/             # LLM provider adapters
│       │   ├── protocol.py     # Model protocol definition
│       │   ├── openai.py       # OpenAI adapter
│       │   ├── anthropic.py    # Anthropic adapter
│       │   ├── ollama.py       # Ollama adapter (primary)
│       │   └── mock.py         # Mock for testing
│       │
│       ├── embedding/          # Vector embedding and search
│       │   ├── protocol.py     # Embedding protocol
│       │   ├── index.py        # Vector index management
│       │   ├── ollama.py       # Ollama embeddings
│       │   └── simple.py       # Simple embeddings
│       │
│       ├── fount/              # Lens fount client
│       │   ├── client.py       # Fount API client
│       │   ├── resolver.py     # Dependency resolution
│       │   └── cache.py        # Local lens cache
│       │
│       ├── schema/             # Schema validation
│       │   ├── loader.py       # YAML/JSON loading
│       │   └── validator.py    # Schema validation
│       │
│       ├── context/            # Context resolution
│       │   ├── resolver.py     # Context resolver
│       │   ├── reference.py    # Reference resolution
│       │   ├── ide.py          # IDE integration
│       │   └── constants.py    # Context constants
│       │
│       ├── project/            # Project management
│       │   └── ...             # Project-level operations
│       │
│       ├── workspace/          # Workspace context
│       │   └── ...             # Workspace management
│       │
│       ├── skills/             # Skill system
│       │   ├── executor.py     # Skill execution
│       │   └── ...             # Skill definitions
│       │
│       ├── types/              # Type definitions
│       │   ├── config.py       # Config types (NaaruConfig)
│       │   └── ...             # Additional types
│       │
│       ├── benchmark/          # Benchmarking system
│       │   ├── cli.py          # Benchmark CLI
│       │   ├── runner.py       # Benchmark runner
│       │   ├── evaluator.py    # Output evaluation
│       │   ├── types.py        # Benchmark types
│       │   └── naaru/          # Naaru-specific benchmarks
│       │
│       └── cli/                # Command-line interface
│           ├── main.py         # Goal-first CLI entry
│           ├── chat.py         # Interactive chat
│           ├── setup.py        # First-time setup
│           ├── bind.py         # Binding management
│           ├── config_cmd.py   # Config commands
│           ├── agent_cmd.py    # Agent commands
│           ├── naaru_cmd.py    # Naaru commands (alias)
│           ├── session.py      # Session management
│           ├── apply.py        # Legacy apply (deprecated)
│           ├── ask.py          # Legacy ask (deprecated)
│           ├── lens.py         # Lens management
│           ├── skill.py        # Skill commands
│           ├── runtime_cmd.py  # Runtime diagnostics
│           ├── state.py        # State management
│           └── helpers.py      # CLI utilities
│
├── tests/                      # Test suite
│
├── lenses/                     # Example lenses
│   ├── tech-writer.lens
│   ├── code-reviewer.lens
│   ├── coder.lens
│   └── helper.lens
│
├── benchmark/                  # Benchmark tasks and results
│   ├── tasks/
│   └── results/
│
└── docs/                       # Design documents
```

---

## Core Data Classes

### `sunwell/core/types.py`

```python
"""Shared type definitions across Sunwell."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal

# === Enums ===

class Severity(Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Tier(Enum):
    """Router execution tiers."""
    FAST_PATH = 0      # No retrieval, no validation
    STANDARD = 1       # Retrieval + basic validation
    DEEP_LENS = 2      # Full retrieval + personas + refinement


class ValidationMethod(Enum):
    """Heuristic validation methods."""
    TRIANGULATION = "triangulation"
    PATTERN_MATCH = "pattern_match"
    CHECKLIST = "checklist"


class IntentCategory(Enum):
    """High-level intent categories for routing."""
    TRIVIAL = auto()       # Typos, formatting
    STANDARD = auto()      # General content creation
    COMPLEX = auto()       # Architecture, audits, high-stakes
    AMBIGUOUS = auto()     # Needs clarification


# === Value Objects ===

@dataclass(frozen=True, slots=True)
class SemanticVersion:
    """Semantic version for lens versioning."""
    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version
    
    @classmethod
    def parse(cls, version_str: str) -> "SemanticVersion":
        """Parse a semver string like '1.2.3' or '1.2.3-beta'."""
        ...


@dataclass(frozen=True, slots=True)
class LensReference:
    """Reference to a lens (local path or fount reference)."""
    source: str                           # e.g., "sunwell/tech-writer", "./my.lens"
    version: str | None = None            # e.g., "^1.0", "2.0.0"
    
    @property
    def is_local(self) -> bool:
        return self.source.startswith("./") or self.source.startswith("/")
    
    @property
    def is_fount(self) -> bool:
        return not self.is_local


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence score with explanation."""
    score: float                          # 0.0 - 1.0
    explanation: str | None = None
    
    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Confidence score must be between 0 and 1, got {self.score}")


# === Error Types ===

class ErrorCategory(Enum):
    """Categories of errors in Sunwell."""
    LENS_LOADING = "lens_loading"         # Schema/parsing errors
    LENS_RESOLUTION = "lens_resolution"   # Inheritance/composition errors
    MODEL_ERROR = "model_error"           # LLM provider errors
    VALIDATION_ERROR = "validation_error" # Validator execution errors
    EMBEDDING_ERROR = "embedding_error"   # Vector operations errors
    FOUNT_ERROR = "fount_error"           # Fount communication errors
    PLUGIN_ERROR = "plugin_error"         # Custom plugin errors
    SANDBOX_ERROR = "sandbox_error"       # Script isolation errors


@dataclass(frozen=True, slots=True)
class SunwellError:
    """Base error type for all Sunwell errors."""
    category: ErrorCategory
    message: str
    recoverable: bool = True
    cause: Exception | None = None
    context: dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


@dataclass(frozen=True, slots=True)
class ValidationExecutionError:
    """Error during validator execution."""
    validator_name: str
    error_type: Literal["script_failed", "timeout", "invalid_output", "sandbox_violation"]
    message: str
    exit_code: int | None = None
    stderr: str | None = None
    recoverable: bool = True


@dataclass(frozen=True, slots=True)
class ModelError:
    """Error from LLM provider."""
    provider: str
    error_type: Literal["rate_limit", "auth_failed", "context_exceeded", "timeout", "api_error"]
    message: str
    retry_after: float | None = None      # Seconds to wait before retry
    recoverable: bool = True


@dataclass(frozen=True, slots=True)
class LensResolutionError:
    """Error resolving lens inheritance/composition."""
    lens_name: str
    error_type: Literal["not_found", "circular_dependency", "version_conflict", "merge_conflict"]
    message: str
    conflicting_lenses: tuple[str, ...] = ()
```

### `sunwell/core/heuristic.py`

```python
"""Heuristic data models."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Example:
    """Good/bad example for a heuristic."""
    good: tuple[str, ...] = ()
    bad: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Heuristic:
    """A professional heuristic (thinking pattern)."""
    name: str
    rule: str                                    # Core principle
    test: str | None = None                      # How to check compliance
    always: tuple[str, ...] = ()                 # Always do these
    never: tuple[str, ...] = ()                  # Never do these
    examples: Example = field(default_factory=Example)
    priority: int = 1                            # 1-10, higher = more important
    
    def to_prompt_fragment(self) -> str:
        """Convert to prompt injection format using t-strings (PEP 750)."""
        always_text = ", ".join(self.always) if self.always else None
        never_text = ", ".join(self.never) if self.never else None
        
        # T-string template for structured, inspectable prompt building
        template = t"""### {self.name}
**Rule**: {self.rule}"""
        
        if always_text:
            template = t"{template}\n**Always**: {always_text}"
        if never_text:
            template = t"{template}\n**Never**: {never_text}"
        
        return str(template)


@dataclass(frozen=True, slots=True)
class AntiHeuristic:
    """A pattern to avoid (anti-pattern)."""
    name: str
    description: str
    triggers: tuple[str, ...]                    # Phrases that indicate this anti-pattern
    correction: str                              # How to fix


@dataclass(frozen=True, slots=True)
class CommunicationStyle:
    """Communication/tone configuration."""
    tone: tuple[str, ...] = ()                   # e.g., ("professional", "concise")
    structure: str | None = None                 # Output structure pattern
```

### `sunwell/core/persona.py`

```python
"""Persona data models for stakeholder simulation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Persona:
    """A stakeholder persona for testing outputs."""
    name: str
    description: str | None = None
    background: str | None = None                # What they know
    goals: tuple[str, ...] = ()                  # What they want
    friction_points: tuple[str, ...] = ()        # What frustrates them
    attack_vectors: tuple[str, ...] = ()         # How they critique
    evaluation_prompt: str | None = None         # Custom eval prompt
    output_format: str | None = None             # How to report findings
    
    def to_evaluation_prompt(self, content: str) -> str:
        """Generate the persona evaluation prompt."""
        if self.evaluation_prompt:
            return self.evaluation_prompt.format(content=content)
        
        return f"""You are a {self.name}: {self.description or self.background}

Your goals: {', '.join(self.goals)}
What frustrates you: {', '.join(self.friction_points)}

Review this content and identify problems from your perspective:

---
{content}
---

Questions to consider:
{chr(10).join(f'- {q}' for q in self.attack_vectors)}

Provide specific, actionable feedback."""
```

### `sunwell/core/validator.py`

```python
"""Validator data models."""

from dataclasses import dataclass
from sunwell.core.types import Severity, ValidationMethod


@dataclass(frozen=True, slots=True)
class DeterministicValidator:
    """Script-based, reproducible validator."""
    name: str
    script: str                                  # Path or inline script
    severity: Severity = Severity.ERROR
    description: str | None = None


@dataclass(frozen=True, slots=True)
class HeuristicValidator:
    """AI-based validator (judgment calls)."""
    name: str
    check: str                                   # What to verify
    method: ValidationMethod = ValidationMethod.PATTERN_MATCH
    confidence_threshold: float = 0.8
    severity: Severity = Severity.WARNING
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result from running a validator."""
    validator_name: str
    passed: bool
    severity: Severity
    message: str | None = None
    confidence: float | None = None              # For heuristic validators
    details: dict | None = None                  # Additional context
```

### `sunwell/core/framework.py`

```python
"""Framework/methodology data models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameworkCategory:
    """A category within a framework (e.g., TUTORIAL in Diataxis)."""
    name: str
    purpose: str
    structure: tuple[str, ...] = ()              # Expected sections
    includes: tuple[str, ...] = ()               # What belongs here
    excludes: tuple[str, ...] = ()               # What doesn't belong
    triggers: tuple[str, ...] = ()               # Keywords that indicate this category


@dataclass(frozen=True, slots=True)
class Framework:
    """A professional methodology (Diataxis, IRAC, AIDA, etc.)."""
    name: str
    description: str | None = None
    decision_tree: str | None = None             # How to categorize work
    categories: tuple[FrameworkCategory, ...] = ()
    
    def classify(self, content: str) -> FrameworkCategory | None:
        """Classify content into a category based on triggers."""
        content_lower = content.lower()
        for category in self.categories:
            if any(trigger in content_lower for trigger in category.triggers):
                return category
        return None
```

### `sunwell/core/workflow.py`

```python
"""Workflow data models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    action: str                                  # What to do
    quality_gates: tuple[str, ...] = ()          # Validators to run after


@dataclass(frozen=True, slots=True)
class Workflow:
    """A multi-step process."""
    name: str
    trigger: str | None = None                   # When to use this workflow
    steps: tuple[WorkflowStep, ...] = ()
    state_management: bool = False               # Persist across sessions?


@dataclass(frozen=True, slots=True)
class Refiner:
    """An improvement operation."""
    name: str
    purpose: str
    when: str | None = None                      # Conditions to trigger
    operations: tuple[str, ...] = ()
```

### `sunwell/core/lens.py`

```python
"""Lens data model - the core expertise container."""

from dataclasses import dataclass, field
from pathlib import Path

from sunwell.core.types import SemanticVersion, LensReference, Tier
from sunwell.core.heuristic import Heuristic, AntiHeuristic, CommunicationStyle
from sunwell.core.persona import Persona
from sunwell.core.validator import DeterministicValidator, HeuristicValidator
from sunwell.core.framework import Framework
from sunwell.core.workflow import Workflow, Refiner


@dataclass(frozen=True, slots=True)
class LensMetadata:
    """Lens metadata."""
    name: str
    domain: str | None = None
    version: SemanticVersion = field(default_factory=lambda: SemanticVersion(0, 1, 0))
    description: str | None = None
    author: str | None = None
    license: str | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    """Evidence/citation configuration."""
    format: str = "file:line"                    # Citation format
    types: tuple[str, ...] = ()                  # Evidence categories
    required_contexts: tuple[str, ...] = ()      # When citations are required


@dataclass(frozen=True, slots=True)
class RouterTier:
    """A routing tier configuration."""
    level: Tier
    name: str
    triggers: tuple[str, ...] = ()               # Keywords that trigger this tier
    retrieval: bool = True
    validation: bool = True
    personas: tuple[str, ...] = ()               # Persona names to run
    require_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class Router:
    """Intent routing configuration."""
    tiers: tuple[RouterTier, ...] = ()
    intent_categories: tuple[str, ...] = ()
    signals: dict[str, str] = field(default_factory=dict)  # keyword → intent


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    """Quality gate requirements."""
    min_confidence: float = 0.7
    required_validators: tuple[str, ...] = ()    # Must-pass validators
    persona_agreement: float = 0.5               # Min % of personas that must approve
    retry_limit: int = 3                         # Max refinement loops


@dataclass(slots=True)
class Lens:
    """
    The core expertise container.
    
    A Lens represents a professional perspective that can be applied
    to LLM interactions. It contains heuristics (how to think),
    frameworks (methodology), personas (testing), and validators
    (quality gates).
    """
    metadata: LensMetadata
    
    # Inheritance/composition
    extends: LensReference | None = None
    compose: tuple[LensReference, ...] = ()
    
    # Core heuristics
    heuristics: tuple[Heuristic, ...] = ()
    anti_heuristics: tuple[AntiHeuristic, ...] = ()
    communication: CommunicationStyle | None = None
    
    # Methodology
    framework: Framework | None = None
    
    # Testing
    personas: tuple[Persona, ...] = ()
    
    # Quality gates
    deterministic_validators: tuple[DeterministicValidator, ...] = ()
    heuristic_validators: tuple[HeuristicValidator, ...] = ()
    
    # Workflows
    workflows: tuple[Workflow, ...] = ()
    refiners: tuple[Refiner, ...] = ()
    
    # Evidence
    provenance: Provenance | None = None
    
    # Routing
    router: Router | None = None
    
    # Quality policy
    quality_policy: QualityPolicy = field(default_factory=QualityPolicy)
    
    # Source tracking
    source_path: Path | None = None
    
    @property
    def all_validators(self) -> tuple[DeterministicValidator | HeuristicValidator, ...]:
        """All validators (deterministic + heuristic)."""
        return self.deterministic_validators + self.heuristic_validators
    
    def get_persona(self, name: str) -> Persona | None:
        """Get a persona by name."""
        for p in self.personas:
            if p.name == name:
                return p
        return None
    
    def to_context(self, components: list[str] | None = None) -> str:
        """
        Convert lens to context injection format.
        
        If components is None, includes all components.
        Otherwise, only includes specified component names.
        """
        ...
```

---

## Protocols (Interfaces)

### `sunwell/models/protocol.py`

```python
"""Model protocol - provider-agnostic LLM interface."""

from typing import Protocol, AsyncIterator, runtime_checkable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenerateOptions:
    """Options for model generation."""
    temperature: float = 0.7
    max_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Result from model generation."""
    content: str
    model: str
    usage: "TokenUsage | None" = None
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@runtime_checkable
class ModelProtocol(Protocol):
    """
    Protocol for LLM providers.
    
    Implementations: OpenAI, Anthropic, Ollama, Mock, etc.
    """
    
    @property
    def model_id(self) -> str:
        """The model identifier (e.g., 'gpt-4', 'claude-3-opus')."""
        ...
    
    async def generate(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """Generate a response for the given prompt."""
        ...
    
    async def generate_stream(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response for the given prompt."""
        ...


@runtime_checkable
class ModelWithTools(Protocol):
    """Extended protocol for models with tool/function calling."""
    
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list["ToolDefinition"],
        *,
        options: GenerateOptions | None = None,
    ) -> "ToolResult":
        ...
```

### `sunwell/embedding/protocol.py`

```python
"""Embedding protocol for vector operations."""

from typing import Protocol, Sequence, runtime_checkable
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Result from embedding operation."""
    vectors: NDArray[np.float32]                 # Shape: (n_texts, embedding_dim)
    model: str
    dimensions: int


@runtime_checkable
class EmbeddingProtocol(Protocol):
    """
    Protocol for embedding providers.
    
    Implementations: OpenAI, local sentence-transformers, etc.
    """
    
    @property
    def dimensions(self) -> int:
        """The embedding dimensions."""
        ...
    
    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResult:
        """Embed one or more texts."""
        ...
    
    async def embed_single(self, text: str) -> NDArray[np.float32]:
        """Embed a single text. Convenience method."""
        result = await self.embed([text])
        return result.vectors[0]
```

### `sunwell/validation/protocol.py`

```python
"""Validation protocol for custom validators."""

from typing import Protocol, runtime_checkable
from sunwell.core.validator import ValidationResult


@runtime_checkable
class ValidatorProtocol(Protocol):
    """Protocol for custom validator implementations."""
    
    @property
    def name(self) -> str:
        """Validator name."""
        ...
    
    async def validate(
        self,
        content: str,
        context: "ValidationContext | None" = None,
    ) -> ValidationResult:
        """Run validation on content."""
        ...
```

---

## Runtime Components

### `sunwell/runtime/engine.py`

```python
"""Main runtime engine - orchestrates lens execution."""

from dataclasses import dataclass, field
from typing import AsyncIterator

from sunwell.core.lens import Lens
from sunwell.core.types import Tier, Confidence
from sunwell.models.protocol import ModelProtocol, GenerateOptions
from sunwell.runtime.classifier import IntentClassifier
from sunwell.runtime.retriever import ExpertiseRetriever
from sunwell.runtime.injector import ContextInjector
from sunwell.validation.runner import ValidationRunner


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result from lens execution."""
    content: str
    tier: Tier
    confidence: Confidence
    validation_results: tuple["ValidationResult", ...]
    persona_results: tuple["PersonaResult", ...] = ()
    refinement_count: int = 0
    token_usage: "TokenUsage | None" = None
    retrieved_components: tuple[str, ...] = ()   # Names of retrieved components


@dataclass
class RuntimeEngine:
    """
    The main Sunwell runtime engine.
    
    Orchestrates:
    1. Intent classification → determine tier
    2. Expertise retrieval → select relevant components
    3. Context injection → build prompt
    4. Model execution → generate response
    5. Validation → run quality gates
    6. Refinement → iterate if needed
    """
    model: ModelProtocol
    lens: Lens
    
    # Optional dependencies
    embedder: "EmbeddingProtocol | None" = None
    telemetry: "TelemetryContext | None" = None
    cache: "LensCache | None" = None
    embedding_cache: "EmbeddingCache | None" = None
    
    # Sub-components (lazily initialized)
    _classifier: IntentClassifier | None = field(default=None, init=False)
    _retriever: ExpertiseRetriever | None = field(default=None, init=False)
    _injector: ContextInjector | None = field(default=None, init=False)
    _validator: ValidationRunner | None = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    
    async def execute(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
        force_tier: Tier | None = None,
    ) -> ExecutionResult:
        """
        Execute a prompt through the lens.
        
        1. Classify intent to determine execution tier
        2. Retrieve relevant expertise components
        3. Inject context and execute model
        4. Run validation and persona testing
        5. Refine if needed (up to retry_limit)
        
        Error handling:
        - ModelError: Retry with exponential backoff (up to 3 times)
        - ValidationExecutionError: Log and continue if recoverable
        - SandboxError: Fail fast, surface to user
        """
        if not self._initialized:
            await self._initialize_components()
        
        # Start telemetry trace
        trace_ctx = self.telemetry.trace("execution", lens_name=self.lens.metadata.name) if self.telemetry else nullcontext()
        
        async with trace_ctx as span:
            try:
                # Step 1: Classify intent
                tier = force_tier or self._classify_intent(prompt)
                if span:
                    span.set_attribute("tier", tier.name)
                
                # Step 2: Retrieve relevant components (skip for FAST_PATH)
                retrieved_components: tuple[str, ...] = ()
                if tier != Tier.FAST_PATH and self._retriever:
                    retrieval = await self._retriever.retrieve(prompt)
                    retrieved_components = tuple(
                        h.name for h in retrieval.heuristics
                    )
                    if span:
                        span.set_attribute("components_retrieved", len(retrieved_components))
                
                # Step 3: Build context and execute
                context = self._injector.build_context(
                    self.lens,
                    retrieved_components,
                )
                
                full_prompt = f"{context}\n\n---\n\n{prompt}"
                
                result = await self._execute_with_retry(full_prompt, options)
                
                # Step 4: Validate (skip for FAST_PATH)
                validation_results: tuple[ValidationResult, ...] = ()
                if tier != Tier.FAST_PATH:
                    validation_results = await self._validator.run_all(result.content)
                
                # Step 5: Persona testing (DEEP_LENS only)
                persona_results: tuple[PersonaResult, ...] = ()
                if tier == Tier.DEEP_LENS and self.lens.personas:
                    persona_results = await self._run_personas(result.content)
                
                # Step 6: Refinement loop if needed
                refinement_count = 0
                while not self._passes_quality_policy(validation_results, persona_results):
                    if refinement_count >= self.lens.quality_policy.retry_limit:
                        break
                    
                    result = await self._refine(result.content, validation_results)
                    validation_results = await self._validator.run_all(result.content)
                    refinement_count += 1
                
                # Compute confidence
                confidence = self._compute_confidence(validation_results, persona_results)
                
                return ExecutionResult(
                    content=result.content,
                    tier=tier,
                    confidence=confidence,
                    validation_results=validation_results,
                    persona_results=persona_results,
                    refinement_count=refinement_count,
                    token_usage=result.usage,
                    retrieved_components=retrieved_components,
                )
            
            except ModelError as e:
                if span:
                    span.set_attribute("error", str(e))
                raise
    
    async def execute_stream(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
        on_validation: Callable[[StreamChunk], Awaitable[None]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream execution with progressive validation.
        
        Yields StreamChunk objects that include:
        - Content chunks as they arrive
        - Early warnings from anti-pattern detection
        - Partial validation results
        - Final validation after completion
        """
        if not self._initialized:
            await self._initialize_components()
        
        # Build context
        tier = self._classify_intent(prompt)
        
        if tier != Tier.FAST_PATH and self._retriever:
            retrieval = await self._retriever.retrieve(prompt)
            components = tuple(h.name for h in retrieval.heuristics)
        else:
            components = ()
        
        context = self._injector.build_context(self.lens, components)
        full_prompt = f"{context}\n\n---\n\n{prompt}"
        
        # Create streaming validator
        stream_validator = StreamingValidator(
            config=StreamValidationConfig(),
            lens=self.lens,
            model=self.model,
        )
        
        # Stream with validation
        raw_stream = self.model.generate_stream(full_prompt, options=options)
        
        async for chunk in stream_validator.process_stream(raw_stream, on_validation):
            yield chunk
    
    async def _execute_with_retry(
        self,
        prompt: str,
        options: GenerateOptions | None,
        max_retries: int = 3,
    ) -> GenerateResult:
        """Execute model call with exponential backoff retry."""
        import asyncio
        
        last_error: ModelError | None = None
        
        for attempt in range(max_retries):
            try:
                return await self.model.generate(prompt, options=options)
            except Exception as e:
                last_error = ModelError(
                    provider=self.model.model_id,
                    error_type="api_error",
                    message=str(e),
                    retry_after=2 ** attempt,
                    recoverable=attempt < max_retries - 1,
                )
                
                if not last_error.recoverable:
                    raise last_error
                
                await asyncio.sleep(last_error.retry_after or 1)
        
        raise last_error
    
    async def _initialize_components(self) -> None:
        """Initialize sub-components (classifier, retriever, etc.)."""
        self._classifier = IntentClassifier(lens=self.lens)
        self._injector = ContextInjector()
        self._validator = ValidationRunner(lens=self.lens, model=self.model)
        
        # Initialize retriever with caching
        if self.embedder:
            # Check for cached embedding index
            cached_index = None
            if self.embedding_cache:
                cached_index = self.embedding_cache.get_index(
                    self.lens,
                    self.embedder.__class__.__name__,
                )
            
            self._retriever = ExpertiseRetriever(
                lens=self.lens,
                embedder=self.embedder,
            )
            
            if cached_index:
                self._retriever._index = cached_index
            else:
                await self._retriever.initialize()
                
                # Cache the built index
                if self.embedding_cache and self._retriever._index:
                    self.embedding_cache.set_index(
                        self.lens,
                        self.embedder.__class__.__name__,
                        self._retriever._index,
                    )
        
        self._initialized = True
    
    def _classify_intent(self, prompt: str) -> Tier:
        """Classify prompt intent to determine tier."""
        if self._classifier:
            result = self._classifier.classify(prompt)
            return result.tier
        return Tier.STANDARD  # Default
    
    def _passes_quality_policy(
        self,
        validations: tuple[ValidationResult, ...],
        personas: tuple[PersonaResult, ...],
    ) -> bool:
        """Check if results pass the lens quality policy."""
        policy = self.lens.quality_policy
        
        # Check required validators
        for req in policy.required_validators:
            if not any(v.validator_name == req and v.passed for v in validations):
                return False
        
        # Check persona agreement
        if personas:
            approved = sum(1 for p in personas if p.approved)
            if approved / len(personas) < policy.persona_agreement:
                return False
        
        return True
    
    def _compute_confidence(
        self,
        validations: tuple[ValidationResult, ...],
        personas: tuple[PersonaResult, ...],
    ) -> Confidence:
        """Compute overall confidence score."""
        if not validations:
            return Confidence(score=0.5, explanation="No validation performed")
        
        # Weight: validators (60%), personas (40%)
        val_score = sum(1 for v in validations if v.passed) / len(validations)
        
        if personas:
            persona_score = sum(1 for p in personas if p.approved) / len(personas)
            final_score = 0.6 * val_score + 0.4 * persona_score
        else:
            final_score = val_score
        
        return Confidence(
            score=final_score,
            explanation=f"{sum(1 for v in validations if v.passed)}/{len(validations)} validators passed",
        )
```

### `sunwell/runtime/retriever.py`

```python
"""RAG over expertise graph - retrieves relevant lens components."""

from dataclasses import dataclass, field
from typing import Sequence

from sunwell.core.lens import Lens
from sunwell.core.heuristic import Heuristic
from sunwell.core.persona import Persona
from sunwell.core.validator import HeuristicValidator
from sunwell.embedding.protocol import EmbeddingProtocol
from sunwell.embedding.index import VectorIndex


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Result from expertise retrieval."""
    heuristics: tuple[Heuristic, ...]
    personas: tuple[Persona, ...]
    validators: tuple[HeuristicValidator, ...]
    relevance_scores: dict[str, float]           # component_name → score


@dataclass
class ExpertiseRetriever:
    """
    RAG over the expertise graph.
    
    On lens load:
    1. Embed each component's description and triggers
    2. Build vector index
    
    On query:
    1. Embed the task prompt
    2. Retrieve top-k relevant components
    3. Return selected heuristics, validators, personas
    """
    lens: Lens
    embedder: EmbeddingProtocol
    top_k: int = 5
    relevance_threshold: float = 0.7
    
    _index: "VectorIndexProtocol | None" = field(default=None, init=False)
    _component_map: dict[str, object] = field(default_factory=dict, init=False)
    
    async def initialize(self) -> None:
        """Build the vector index from lens components."""
        from sunwell.embedding.index import InMemoryIndex
        
        # Collect all embeddable components
        components: list[tuple[str, str, object]] = []  # (id, text, obj)
        
        # Heuristics
        for h in self.lens.heuristics:
            text = self._component_to_embedding_text(h)
            components.append((f"heuristic:{h.name}", text, h))
        
        # Personas
        for p in self.lens.personas:
            text = self._component_to_embedding_text(p)
            components.append((f"persona:{p.name}", text, p))
        
        # Heuristic validators
        for v in self.lens.heuristic_validators:
            text = self._component_to_embedding_text(v)
            components.append((f"validator:{v.name}", text, v))
        
        if not components:
            return
        
        # Embed all components
        texts = [text for _, text, _ in components]
        embeddings = await self.embedder.embed(texts)
        
        # Build index
        self._index = InMemoryIndex(_dimensions=self.embedder.dimensions)
        
        ids = [id for id, _, _ in components]
        metadata = [{"type": id.split(":")[0]} for id in ids]
        
        self._index.add_batch(ids, embeddings.vectors, metadata)
        
        # Build component map for retrieval
        for id, _, obj in components:
            self._component_map[id] = obj
    
    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant components for a query."""
        if not self._index:
            # No index, return empty (or all if below threshold)
            return RetrievalResult(
                heuristics=self.lens.heuristics,
                personas=(),
                validators=(),
                relevance_scores={},
            )
        
        # Embed query
        query_embedding = await self.embedder.embed_single(query)
        
        # Search
        k = top_k or self.top_k
        results = self._index.search(
            query_embedding,
            top_k=k,
            threshold=self.relevance_threshold,
        )
        
        # Categorize results
        heuristics = []
        personas = []
        validators = []
        scores = {}
        
        for result in results:
            component = self._component_map.get(result.id)
            scores[result.id] = result.score
            
            if result.id.startswith("heuristic:"):
                heuristics.append(component)
            elif result.id.startswith("persona:"):
                personas.append(component)
            elif result.id.startswith("validator:"):
                validators.append(component)
        
        return RetrievalResult(
            heuristics=tuple(heuristics),
            personas=tuple(personas),
            validators=tuple(validators),
            relevance_scores=scores,
        )
    
    def _component_to_embedding_text(self, component: object) -> str:
        """Convert a component to text for embedding."""
        if isinstance(component, Heuristic):
            parts = [component.name, component.rule]
            if component.always:
                parts.extend(component.always)
            if component.never:
                parts.extend(component.never)
            return " ".join(parts)
        
        elif isinstance(component, Persona):
            parts = [component.name]
            if component.description:
                parts.append(component.description)
            if component.background:
                parts.append(component.background)
            parts.extend(component.goals)
            parts.extend(component.attack_vectors)
            return " ".join(parts)
        
        elif isinstance(component, HeuristicValidator):
            return f"{component.name} {component.check}"
        
        return str(component)
```

### `sunwell/runtime/classifier.py`

```python
"""Intent classification for routing."""

from dataclasses import dataclass
from sunwell.core.types import IntentCategory, Tier
from sunwell.core.lens import Lens, Router


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Result from intent classification."""
    category: IntentCategory
    tier: Tier
    confidence: float
    signals: tuple[str, ...]                     # Keywords that triggered this


@dataclass
class IntentClassifier:
    """
    Classifies user intent to determine execution tier.
    
    Uses keyword signals + optional LLM classification for ambiguous cases.
    """
    lens: Lens
    
    def classify(self, prompt: str) -> ClassificationResult:
        """
        Classify a prompt's intent.
        
        1. Check for keyword triggers in router config
        2. If ambiguous, use LLM classification (optional)
        3. Map to execution tier
        """
        ...
    
    def _check_keyword_triggers(self, prompt: str) -> Tier | None:
        """Check if prompt matches any tier's keyword triggers."""
        ...
```

---

## Embedding and Vector Search

### `sunwell/embedding/protocol.py` (Vector Index Protocol)

```python
"""Vector index protocol - pluggable backend for vector storage."""

from typing import Protocol, runtime_checkable, Sequence
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single search result."""
    id: str
    score: float
    metadata: dict


@runtime_checkable
class VectorIndexProtocol(Protocol):
    """
    Protocol for vector index backends.
    
    Implementations:
    - InMemoryIndex: NumPy-based, for development/small lenses
    - FAISSIndex: For large-scale production
    - QdrantIndex: For distributed deployments
    - PineconeIndex: For managed cloud deployments
    """
    
    @property
    def dimensions(self) -> int:
        """The embedding dimensions this index was built for."""
        ...
    
    @property
    def count(self) -> int:
        """Number of vectors in the index."""
        ...
    
    def add(
        self,
        id: str,
        vector: NDArray[np.float32],
        metadata: dict | None = None,
    ) -> None:
        """Add a single vector to the index."""
        ...
    
    def add_batch(
        self,
        ids: Sequence[str],
        vectors: NDArray[np.float32],
        metadata: Sequence[dict] | None = None,
    ) -> None:
        """Add multiple vectors to the index."""
        ...
    
    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        ...
    
    def delete(self, id: str) -> bool:
        """Delete a vector by ID. Returns True if found and deleted."""
        ...
    
    def clear(self) -> None:
        """Remove all vectors from the index."""
        ...
    
    def save(self, path: str) -> None:
        """Persist the index to disk."""
        ...
    
    @classmethod
    def load(cls, path: str) -> "VectorIndexProtocol":
        """Load an index from disk."""
        ...
```

### `sunwell/embedding/index.py` (In-Memory Implementation)

```python
"""In-memory vector index implementation."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import numpy as np
from numpy.typing import NDArray

from sunwell.embedding.protocol import VectorIndexProtocol, SearchResult


@dataclass
class InMemoryIndex:
    """
    Simple in-memory vector index using NumPy.
    
    Best for:
    - Development and testing
    - Small lenses (< 1000 components)
    - Scenarios where persistence isn't critical
    
    For production with larger lenses, use FAISSIndex or QdrantIndex.
    """
    _dimensions: int
    
    _vectors: NDArray[np.float32] | None = field(default=None, init=False)
    _ids: list[str] = field(default_factory=list, init=False)
    _metadata: list[dict] = field(default_factory=list, init=False)
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def count(self) -> int:
        return len(self._ids)
    
    def add(
        self,
        id: str,
        vector: NDArray[np.float32],
        metadata: dict | None = None,
    ) -> None:
        """Add a single vector to the index."""
        if vector.shape[0] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vector.shape[0]}")
        
        if self._vectors is None:
            self._vectors = vector.reshape(1, -1)
        else:
            self._vectors = np.vstack([self._vectors, vector])
        
        self._ids.append(id)
        self._metadata.append(metadata or {})
    
    def add_batch(
        self,
        ids: list[str],
        vectors: NDArray[np.float32],
        metadata: list[dict] | None = None,
    ) -> None:
        """Add multiple vectors to the index."""
        if vectors.shape[1] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vectors.shape[1]}")
        
        if self._vectors is None:
            self._vectors = vectors
        else:
            self._vectors = np.vstack([self._vectors, vectors])
        
        self._ids.extend(ids)
        self._metadata.extend(metadata or [{} for _ in ids])
    
    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using cosine similarity."""
        if self._vectors is None or len(self._ids) == 0:
            return []
        
        # Normalize for cosine similarity
        query_norm = query_vector / np.linalg.norm(query_vector)
        vectors_norm = self._vectors / np.linalg.norm(self._vectors, axis=1, keepdims=True)
        
        # Compute similarities
        similarities = np.dot(vectors_norm, query_norm)
        
        # Get top-k indices
        if threshold is not None:
            mask = similarities >= threshold
            indices = np.where(mask)[0]
            indices = indices[np.argsort(similarities[indices])[::-1][:top_k]]
        else:
            indices = np.argsort(similarities)[::-1][:top_k]
        
        return [
            SearchResult(
                id=self._ids[i],
                score=float(similarities[i]),
                metadata=self._metadata[i],
            )
            for i in indices
        ]
    
    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        try:
            idx = self._ids.index(id)
            self._ids.pop(idx)
            self._metadata.pop(idx)
            if self._vectors is not None:
                self._vectors = np.delete(self._vectors, idx, axis=0)
            return True
        except ValueError:
            return False
    
    def clear(self) -> None:
        """Remove all vectors from the index."""
        self._vectors = None
        self._ids.clear()
        self._metadata.clear()
    
    def save(self, path: str) -> None:
        """Persist the index to disk."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        
        if self._vectors is not None:
            np.save(p / "vectors.npy", self._vectors)
        
        with open(p / "metadata.json", "w") as f:
            json.dump({"ids": self._ids, "metadata": self._metadata, "dims": self._dimensions}, f)
    
    @classmethod
    def load(cls, path: str) -> "InMemoryIndex":
        """Load an index from disk."""
        p = Path(path)
        
        with open(p / "metadata.json") as f:
            data = json.load(f)
        
        index = cls(_dimensions=data["dims"])
        index._ids = data["ids"]
        index._metadata = data["metadata"]
        
        vectors_path = p / "vectors.npy"
        if vectors_path.exists():
            index._vectors = np.load(vectors_path)
        
        return index
```

---

## Schema Loading

### `sunwell/schema/loader.py`

```python
"""Load lens definitions from YAML/JSON files."""

from pathlib import Path
from typing import Any

import yaml

from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.heuristic import Heuristic, AntiHeuristic, CommunicationStyle, Example
from sunwell.core.persona import Persona
from sunwell.core.validator import DeterministicValidator, HeuristicValidator
from sunwell.core.framework import Framework, FrameworkCategory
from sunwell.core.workflow import Workflow, WorkflowStep, Refiner
from sunwell.core.types import SemanticVersion, LensReference, Severity, ValidationMethod


class LensLoader:
    """Load lens definitions from files."""
    
    def load(self, path: Path) -> Lens:
        """Load a lens from a YAML file."""
        ...
    
    def load_string(self, content: str) -> Lens:
        """Load a lens from a YAML string."""
        ...
    
    def _parse_lens(self, data: dict[str, Any]) -> Lens:
        """Parse raw dict into Lens dataclass."""
        ...
    
    def _parse_metadata(self, data: dict[str, Any]) -> LensMetadata:
        ...
    
    def _parse_heuristics(self, data: list[dict]) -> tuple[Heuristic, ...]:
        ...
    
    def _parse_personas(self, data: list[dict]) -> tuple[Persona, ...]:
        ...
    
    # ... more parsing methods


class LensResolver:
    """
    Resolve lens inheritance and composition.
    
    Handles the complete resolution of a lens's dependency graph,
    including inheritance chains, compositions, and conflict resolution.
    """
    
    def __init__(
        self,
        loader: LensLoader,
        fount_client: "FountClient | None" = None,
        cache: "LensCache | None" = None,
    ):
        self.loader = loader
        self.fount = fount_client
        self.cache = cache
        self._resolution_stack: list[str] = []  # For circular dependency detection
    
    async def resolve(self, lens: Lens) -> Lens:
        """
        Resolve a lens's inheritance chain and compositions.
        
        Resolution order:
        1. Check for circular dependencies
        2. Resolve `extends` (single inheritance)
        3. Resolve `compose` (multiple compositions)
        4. Apply priority-based merging
        5. Validate final lens integrity
        
        Returns a fully-resolved lens with all inherited/composed components.
        """
        lens_id = f"{lens.metadata.name}@{lens.metadata.version}"
        
        # Circular dependency check
        if lens_id in self._resolution_stack:
            cycle = " -> ".join(self._resolution_stack + [lens_id])
            raise LensResolutionError(
                lens_name=lens.metadata.name,
                error_type="circular_dependency",
                message=f"Circular dependency detected: {cycle}",
            )
        
        self._resolution_stack.append(lens_id)
        
        try:
            resolved = lens
            
            # Step 1: Resolve inheritance (extends)
            if lens.extends:
                base_lens = await self._load_lens_reference(lens.extends)
                base_resolved = await self.resolve(base_lens)  # Recursive
                resolved = self._merge_lenses(base_resolved, resolved, is_inheritance=True)
            
            # Step 2: Resolve compositions (compose)
            if lens.compose:
                composed_lenses = []
                for ref in lens.compose:
                    composed = await self._load_lens_reference(ref)
                    composed_resolved = await self.resolve(composed)
                    composed_lenses.append((ref, composed_resolved))
                
                # Sort by priority (from LensReference metadata or default)
                composed_lenses.sort(key=lambda x: getattr(x[0], 'priority', 1))
                
                for ref, composed_lens in composed_lenses:
                    resolved = self._merge_lenses(resolved, composed_lens, is_inheritance=False)
            
            return resolved
        
        finally:
            self._resolution_stack.pop()
    
    async def _load_lens_reference(self, ref: LensReference) -> Lens:
        """Load a lens from a reference (local path or fount)."""
        # Check cache first
        if self.cache:
            cached = self.cache.get(ref)
            if cached:
                return cached
        
        if ref.is_local:
            lens = self.loader.load(Path(ref.source))
        else:
            if not self.fount:
                raise LensResolutionError(
                    lens_name=ref.source,
                    error_type="not_found",
                    message=f"Fount not configured, cannot resolve: {ref.source}",
                )
            lens = await self.fount.fetch(ref.source, ref.version)
        
        # Cache for future use
        if self.cache:
            self.cache.set(ref, lens)
        
        return lens
    
    def _merge_lenses(
        self,
        base: Lens,
        child: Lens,
        is_inheritance: bool = True,
    ) -> Lens:
        """
        Merge child lens into base using priority-based resolution.
        
        Merge Strategy:
        - Heuristics: Child's heuristics override base's by name; 
          priority field determines conflict resolution
        - Validators: Union of all validators; child overrides by name
        - Personas: Union of all personas; child overrides by name
        - Framework: Child's framework replaces base's entirely
        - Communication: Child's style overrides base's
        - Workflows: Union with child taking precedence for same-named
        - Quality Policy: Child's policy replaces base's
        
        Priority Matrix (from RFC):
        - 10: Safety/Security - Hard constraints, never overridden
        -  8: Legal/Compliance - Mandatory requirements
        -  5: Domain Framework - Core methodology
        -  3: Company Style - Internal standards
        -  1: General Heuristic - Base principles
        """
        # Merge heuristics with priority resolution
        merged_heuristics = self._merge_heuristics(
            base.heuristics, child.heuristics
        )
        merged_anti_heuristics = self._merge_by_name(
            base.anti_heuristics, child.anti_heuristics
        )
        
        # Merge validators (union, child overrides)
        merged_det_validators = self._merge_by_name(
            base.deterministic_validators, child.deterministic_validators
        )
        merged_heur_validators = self._merge_by_name(
            base.heuristic_validators, child.heuristic_validators
        )
        
        # Merge personas (union, child overrides)
        merged_personas = self._merge_by_name(base.personas, child.personas)
        
        # Merge workflows (union, child overrides)
        merged_workflows = self._merge_by_name(base.workflows, child.workflows)
        merged_refiners = self._merge_by_name(base.refiners, child.refiners)
        
        return Lens(
            metadata=child.metadata,  # Child's metadata wins
            extends=None,  # Already resolved
            compose=(),    # Already resolved
            heuristics=merged_heuristics,
            anti_heuristics=merged_anti_heuristics,
            communication=child.communication or base.communication,
            framework=child.framework or base.framework,
            personas=merged_personas,
            deterministic_validators=merged_det_validators,
            heuristic_validators=merged_heur_validators,
            workflows=merged_workflows,
            refiners=merged_refiners,
            provenance=child.provenance or base.provenance,
            router=child.router or base.router,
            quality_policy=child.quality_policy if child.quality_policy != QualityPolicy() else base.quality_policy,
            source_path=child.source_path,
        )
    
    def _merge_heuristics(
        self,
        base: tuple[Heuristic, ...],
        child: tuple[Heuristic, ...],
    ) -> tuple[Heuristic, ...]:
        """
        Merge heuristics with priority-based conflict resolution.
        
        When two heuristics conflict (determined by name or semantic overlap):
        - Higher priority wins
        - Equal priority triggers warning but child wins
        """
        result: dict[str, Heuristic] = {}
        
        # Add base heuristics
        for h in base:
            result[h.name] = h
        
        # Merge child heuristics
        for h in child:
            if h.name in result:
                existing = result[h.name]
                # Higher priority wins
                if h.priority >= existing.priority:
                    result[h.name] = h
                # else: keep existing (higher priority)
            else:
                result[h.name] = h
        
        # Sort by priority (highest first) for consistent ordering
        return tuple(sorted(result.values(), key=lambda x: -x.priority))
    
    def _merge_by_name(
        self,
        base: tuple,
        child: tuple,
    ) -> tuple:
        """Generic merge by name attribute. Child overrides base."""
        result: dict[str, object] = {}
        
        for item in base:
            result[item.name] = item
        
        for item in child:
            result[item.name] = item  # Child always wins
        
        return tuple(result.values())
```

---

## CLI Commands

### Goal-First Interface

The primary interface is goal-first — users state what they want, the agent figures out the rest:

```bash
sunwell "Build a REST API with auth"     # Execute goal
sunwell "Build an app" --plan            # Show plan only
sunwell chat                              # Interactive mode
```

### Command Hierarchy

```yaml
# TIER 1: The 90% Path
sunwell "goal"           # Execute goal (DEFAULT)
sunwell chat             # Interactive mode
sunwell setup            # First-time setup

# TIER 2: Power User
sunwell bind ...         # Manage saved configurations
sunwell config ...       # Global settings

# TIER 3: Advanced
sunwell agent ...        # Agent commands
  sunwell agent run      # Explicit agent mode
  sunwell agent resume   # Resume from checkpoint
  sunwell agent status   # Show state

sunwell apply ...        # Legacy (deprecated)
sunwell ask ...          # Legacy (deprecated)
sunwell benchmark ...    # Quality testing
sunwell sessions ...     # Memory management
```

### `sunwell/cli/main.py`

```python
"""Main CLI entry point - Goal-first interface."""

import click
from pathlib import Path


class GoalFirstGroup(click.Group):
    """Custom group that allows 'sunwell "goal"' syntax."""
    
    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        
        command_names = set(self.list_commands(ctx))
        first_arg = args[0]
        
        # If first arg is NOT a command, treat it as a goal
        if first_arg not in command_names and not first_arg.startswith("-"):
            ctx.ensure_object(dict)
            ctx.obj["_goal"] = first_arg
            args = args[1:]
        
        return super().parse_args(ctx, args)


@click.group(cls=GoalFirstGroup, invoke_without_command=True)
@click.option("--plan", is_flag=True, help="Show plan without executing")
@click.option("--model", "-m", help="Override model selection")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--time", "-t", default=300, help="Max execution time (seconds)")
@click.option("--trust", type=click.Choice(["read_only", "workspace", "shell"]),
              default=None, help="Override tool trust level")
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx, plan: bool, model: str | None, verbose: bool, 
         time: int, trust: str | None) -> None:
    """Sunwell — AI agent for software tasks.

    Just tell it what you want:
    
        sunwell "Build a REST API with auth"
        sunwell "Write docs for the CLI module"
        sunwell "Refactor auth.py to use async"

    For planning without execution:
    
        sunwell "Build an app" --plan

    For interactive mode:
    
        sunwell chat
    """
    goal = ctx.obj.get("_goal") if ctx.obj else None
    
    if goal and ctx.invoked_subcommand is None:
        # Execute goal with Naaru agent
        ctx.invoke(_run_goal, goal=goal, dry_run=plan, model=model,
                   verbose=verbose, time=time, trust=trust or "workspace")


async def _run_agent(goal: str, time: int, trust: str, dry_run: bool,
                     verbose: bool, model_override: str | None) -> None:
    """Execute agent mode with artifact-first planning."""
    from sunwell.naaru import Naaru
    from sunwell.naaru.planners import ArtifactPlanner
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolPolicy, ToolTrust
    
    # Setup planner (artifact-first by default)
    planner = ArtifactPlanner(model=synthesis_model)
    
    if dry_run:
        # Show plan without executing
        graph = await planner.discover_graph(goal, {"cwd": str(Path.cwd())})
        _show_artifact_plan(graph)
        return
    
    # Full execution with Naaru coordinator
    naaru = Naaru(
        sunwell_root=Path.cwd(),
        synthesis_model=synthesis_model,
        planner=planner,
        tool_executor=tool_executor,
    )
    
    result = await naaru.run(goal=goal, max_time_seconds=time)
    _show_result(result)
```

---

## Dependencies

### `pyproject.toml`

```toml
[project]
name = "sunwell"
version = "0.1.0"
description = "RAG for Judgment - Dynamic expertise retrieval for LLMs"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.14"
authors = [{ name = "llane" }]
keywords = [
    "llm",
    "rag",
    "expertise",
    "ai",
    "prompt-engineering",
    "free-threading",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.14",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

# Sunwell is optimized for free-threaded Python (3.14t)
# For best performance, use: /usr/local/bin/python3.14t -m sunwell

dependencies = [
    "pyyaml>=6.0",
    "numpy>=1.24",
    "click>=8.1",
    "httpx>=0.25",
    "rich>=13.0",
]

[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.18"]
ollama = ["ollama>=0.1"]
embeddings = ["sentence-transformers>=2.2"]
api = ["fastapi>=0.109", "uvicorn>=0.27"]
all = ["sunwell[openai,anthropic,ollama,embeddings,api]"]
benchmark = [
    "tiktoken>=0.5.0",   # Accurate token counting
    "scipy>=1.10.0",     # Statistical tests
    "ruff>=0.2.0",       # Deterministic linting
    "mypy>=1.8.0",       # Deterministic type checks
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.2",
    "mypy>=1.8",
    "pre-commit>=3.6",
]

[project.scripts]
sunwell = "sunwell.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sunwell"]

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.14"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
# Prefer free-threaded Python for true parallelism
python-preference = "managed"
```

---

## Key Design Decisions

### 1. Immutable Data Classes

All core models use `frozen=True` and `slots=True` for:
- **Thread safety**: Safe for concurrent access
- **Memory efficiency**: Slots reduce memory overhead
- **Predictability**: No accidental mutation

### 2. Protocol-Based Interfaces

Using `typing.Protocol` for:
- **Flexibility**: Easy to swap implementations
- **Testability**: Mock implementations for testing
- **No coupling**: No base class inheritance required

### 3. Async-First + Free Threading

All I/O operations are async, and CPU-bound work leverages free threading (PEP 779):
- **Concurrency**: Multiple model calls, validations in parallel
- **Streaming**: Support streaming responses natively
- **Performance**: No blocking on network I/O
- **True Parallelism**: Free-threaded Python enables parallel validator execution without GIL contention

### 4. Composition Over Inheritance

Lens composition uses:
- **`extends`**: Single inheritance chain
- **`compose`**: Multiple lenses with priority-based merging
- **Explicit resolution**: No implicit MRO complexity

### 5. Layered Architecture

```
┌─────────────────────────────────────────┐
│                  CLI                     │  ← User interface
├─────────────────────────────────────────┤
│               Runtime Engine             │  ← Orchestration
├─────────────────────────────────────────┤
│  Retriever │ Classifier │ Validator     │  ← Components
├─────────────────────────────────────────┤
│              Core Models                 │  ← Domain objects
├─────────────────────────────────────────┤
│  Models Protocol │ Embedding Protocol   │  ← Interfaces
└─────────────────────────────────────────┘
```

---

## Python 3.14 Features

Sunwell is built to leverage modern Python 3.14 capabilities:

### Template Strings (PEP 750)

T-strings provide structured, inspectable templates for prompt construction. Unlike f-strings which eagerly interpolate, t-strings return a `Template` object that can be validated, transformed, and composed.

```python
"""Template-based prompt construction using PEP 750 t-strings."""

from string.templatelib import Template, Interpolation
from dataclasses import dataclass


@dataclass
class PromptBuilder:
    """
    Build prompts using t-strings for type-safe, inspectable templates.
    
    Benefits over f-strings:
    - Templates can be validated before rendering
    - Interpolations are inspectable (for logging, security checks)
    - Templates can be composed and transformed
    - Clear separation between template structure and values
    """
    
    def build_context_injection(
        self,
        heuristics: list["Heuristic"],
        task: str,
        context: dict[str, str],
    ) -> Template:
        """Build a context-injected prompt using t-strings."""
        heuristic_text = self._format_heuristics(heuristics)
        
        # T-string template - inspectable and composable
        return t"""You are an expert assistant with the following expertise:

## Heuristics
{heuristic_text}

## Task
{task}

## Additional Context
{self._format_context(context)}

Apply your expertise to complete this task."""
    
    def build_persona_evaluation(
        self,
        persona: "Persona",
        content: str,
    ) -> Template:
        """Build persona evaluation prompt."""
        return t"""You are a {persona.name}: {persona.description}

Your goals: {', '.join(persona.goals)}
What frustrates you: {', '.join(persona.friction_points)}

Review this content and identify problems from your perspective:

---
{content}
---

Questions to consider:
{self._format_attack_vectors(persona.attack_vectors)}

Provide specific, actionable feedback."""
    
    def validate_template(self, template: Template) -> list[str]:
        """
        Validate a template before rendering.
        
        T-strings allow inspection of interpolations for:
        - Security checks (no sensitive data in prompts)
        - Length estimation
        - Required field validation
        """
        issues = []
        
        for part in template:
            if isinstance(part, Interpolation):
                # Check for potentially sensitive interpolations
                if any(sensitive in str(part.value).lower() 
                       for sensitive in ["password", "api_key", "secret"]):
                    issues.append(f"Potential sensitive data in template: {part.expr}")
        
        return issues
    
    def render_with_escaping(self, template: Template) -> str:
        """Render template with proper escaping for prompt injection prevention."""
        parts = []
        for part in template:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, Interpolation):
                # Escape user-provided content to prevent prompt injection
                escaped = self._escape_for_prompt(str(part.value))
                parts.append(escaped)
        return "".join(parts)
    
    def _escape_for_prompt(self, text: str) -> str:
        """Escape text to prevent prompt injection attacks."""
        # Remove or escape control sequences
        return text.replace("```", "'''").replace("---", "—-—")
    
    def _format_heuristics(self, heuristics: list["Heuristic"]) -> str:
        """Format heuristics for prompt injection."""
        return "\n\n".join(h.to_prompt_fragment() for h in heuristics)
    
    def _format_context(self, context: dict[str, str]) -> str:
        return "\n".join(f"- **{k}**: {v}" for k, v in context.items())
    
    def _format_attack_vectors(self, vectors: tuple[str, ...]) -> str:
        return "\n".join(f"- {v}" for v in vectors)
```

### Free Threading (PEP 779)

Free-threaded Python removes the GIL for true parallelism in CPU-bound operations:

```python
"""Parallel execution using free-threaded Python."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import asyncio


@dataclass
class ParallelValidator:
    """
    Run validators in true parallel using free threading.
    
    With PEP 779, CPU-bound validation (regex, parsing, checksums)
    can run in parallel threads without GIL contention.
    """
    max_workers: int = 4
    
    async def validate_parallel(
        self,
        content: str,
        validators: list["DeterministicValidator"],
    ) -> list["ValidationResult"]:
        """
        Run multiple validators in parallel.
        
        - I/O-bound validators: Use asyncio concurrency
        - CPU-bound validators: Use thread pool with free threading
        """
        loop = asyncio.get_running_loop()
        
        # Separate CPU-bound from I/O-bound validators
        cpu_bound = [v for v in validators if self._is_cpu_bound(v)]
        io_bound = [v for v in validators if not self._is_cpu_bound(v)]
        
        results = []
        
        # Run CPU-bound validators in thread pool (true parallelism with free threading)
        if cpu_bound:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    loop.run_in_executor(executor, self._run_sync_validator, v, content)
                    for v in cpu_bound
                ]
                cpu_results = await asyncio.gather(*futures)
                results.extend(cpu_results)
        
        # Run I/O-bound validators with asyncio concurrency
        if io_bound:
            io_results = await asyncio.gather(
                *[self._run_async_validator(v, content) for v in io_bound]
            )
            results.extend(io_results)
        
        return results
    
    def _is_cpu_bound(self, validator: "DeterministicValidator") -> bool:
        """Determine if a validator is CPU-bound."""
        # Script validators and regex-heavy validators are CPU-bound
        return validator.script.endswith((".py", ".sh")) or "regex" in validator.name.lower()
    
    def _run_sync_validator(
        self,
        validator: "DeterministicValidator",
        content: str,
    ) -> "ValidationResult":
        """Run a CPU-bound validator synchronously."""
        # This runs in a thread with true parallelism (no GIL)
        ...
    
    async def _run_async_validator(
        self,
        validator: "DeterministicValidator", 
        content: str,
    ) -> "ValidationResult":
        """Run an I/O-bound validator asynchronously."""
        ...
```

### Context Variables for Execution State

Use `contextvars` to propagate execution context through async call stacks:

```python
"""Execution context using contextvars."""

from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from typing import Any
import uuid


# Context variables for execution state
current_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
current_lens_name: ContextVar[str] = ContextVar("lens_name", default="")
current_tier: ContextVar[int] = ContextVar("tier", default=1)
execution_metadata: ContextVar[dict[str, Any]] = ContextVar("metadata", default={})


@dataclass
class ExecutionContext:
    """
    Manage execution context using contextvars.
    
    Benefits:
    - Automatically propagates through async/await chains
    - No need to pass context explicitly through every function
    - Thread-safe with free threading
    - Isolates context between concurrent executions
    """
    
    @staticmethod
    def initialize(lens_name: str, tier: int = 1) -> str:
        """Initialize a new execution context. Returns trace_id."""
        trace_id = str(uuid.uuid4())[:16]
        current_trace_id.set(trace_id)
        current_lens_name.set(lens_name)
        current_tier.set(tier)
        execution_metadata.set({})
        return trace_id
    
    @staticmethod
    def get_trace_id() -> str:
        """Get current trace ID from context."""
        return current_trace_id.get()
    
    @staticmethod
    def get_lens_name() -> str:
        """Get current lens name from context."""
        return current_lens_name.get()
    
    @staticmethod
    def set_metadata(key: str, value: Any) -> None:
        """Set metadata in current context."""
        meta = execution_metadata.get().copy()
        meta[key] = value
        execution_metadata.set(meta)
    
    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get all metadata from current context."""
        return execution_metadata.get().copy()


# Usage in telemetry - automatic context propagation
class ContextAwareTelemetry:
    """Telemetry that automatically uses execution context."""
    
    def emit(self, event_type: str, **data) -> None:
        """Emit event with automatic context from contextvars."""
        from sunwell.telemetry.types import TelemetryEvent, EventType
        from datetime import datetime
        
        event = TelemetryEvent(
            event_type=EventType[event_type],
            timestamp=datetime.now(),
            trace_id=ExecutionContext.get_trace_id(),  # Auto from context
            span_id=str(uuid.uuid4())[:8],
            lens_name=ExecutionContext.get_lens_name(),  # Auto from context
            data={**data, **ExecutionContext.get_metadata()},
        )
        self._emit(event)
    
    def _emit(self, event: "TelemetryEvent") -> None:
        ...


# Context propagation in async execution
async def execute_with_context(lens: "Lens", prompt: str) -> "ExecutionResult":
    """Execute with automatic context propagation."""
    # Initialize context for this execution
    trace_id = ExecutionContext.initialize(lens.metadata.name)
    
    # All downstream async calls automatically see this context
    result = await _classify_intent(prompt)      # Has access to trace_id
    components = await _retrieve_expertise(prompt)  # Has access to trace_id
    response = await _generate_response(prompt)   # Has access to trace_id
    
    return response
```

### Subinterpreters for Sandbox Isolation (PEP 734)

Use Python subinterpreters for isolated validator execution:

```python
"""Sandbox using PEP 734 subinterpreters."""

from interpreters import Interpreter, create
from dataclasses import dataclass
import pickle


@dataclass 
class SubinterpreterSandbox:
    """
    Execute untrusted validator scripts in isolated subinterpreters.
    
    Benefits over subprocess:
    - Lower overhead (no process spawn)
    - Shared memory for large data transfer
    - True isolation (separate GIL, separate state)
    - Python-native (no shell escaping issues)
    
    Benefits over threading:
    - Complete isolation (no shared globals)
    - Can't access main interpreter state
    - Safer for untrusted code
    """
    
    async def execute(
        self,
        script: str,
        input_data: str,
        timeout_seconds: float = 30.0,
    ) -> "SandboxResult":
        """Execute script in isolated subinterpreter."""
        import asyncio
        
        # Create isolated interpreter
        interp = create()
        
        # Prepare the execution code
        exec_code = f'''
import sys
input_data = {repr(input_data)}

# Execute the validator script
{script}

# Capture result
result = validate(input_data) if 'validate' in dir() else None
'''
        
        try:
            # Run with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(interp.exec, exec_code),
                timeout=timeout_seconds,
            )
            
            return SandboxResult(
                exit_code=0,
                stdout=str(result),
                stderr="",
                duration_ms=0,  # TODO: measure
            )
        except asyncio.TimeoutError:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                duration_ms=timeout_seconds * 1000,
                timed_out=True,
            )
        finally:
            # Clean up interpreter
            interp.close()
```

### Zstandard Compression (PEP 784)

Use built-in `compression.zstd` for lens caching:

```python
"""Cache compression using PEP 784 built-in zstd."""

from compression import zstd
from pathlib import Path
import json


class CompressedLensCache:
    """
    Lens cache with Zstandard compression.
    
    Benefits of zstd over gzip:
    - 3-5x faster compression
    - 2-3x faster decompression  
    - Better compression ratios
    - Built into Python 3.14 (no external dependency)
    """
    
    def __init__(self, cache_dir: Path, compression_level: int = 3):
        self.cache_dir = cache_dir
        self.compression_level = compression_level
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, key: str, data: dict) -> None:
        """Save compressed lens data to cache."""
        path = self.cache_dir / f"{key}.lens.zst"
        
        # Serialize to JSON bytes
        json_bytes = json.dumps(data).encode("utf-8")
        
        # Compress with zstd
        compressed = zstd.compress(json_bytes, level=self.compression_level)
        
        path.write_bytes(compressed)
    
    def load(self, key: str) -> dict | None:
        """Load and decompress lens data from cache."""
        path = self.cache_dir / f"{key}.lens.zst"
        
        if not path.exists():
            return None
        
        # Decompress
        compressed = path.read_bytes()
        json_bytes = zstd.decompress(compressed)
        
        return json.loads(json_bytes.decode("utf-8"))
    
    def save_embedding_index(self, key: str, vectors: "NDArray", metadata: dict) -> None:
        """Save compressed embedding index."""
        import numpy as np
        
        path = self.cache_dir / f"{key}.embeddings.zst"
        
        # Serialize numpy array to bytes
        buffer = io.BytesIO()
        np.save(buffer, vectors)
        array_bytes = buffer.getvalue()
        
        # Combine with metadata
        combined = {
            "vectors": array_bytes.hex(),  # Hex-encode binary data
            "metadata": metadata,
        }
        
        json_bytes = json.dumps(combined).encode("utf-8")
        compressed = zstd.compress(json_bytes, level=self.compression_level)
        
        path.write_bytes(compressed)
```

### Modern Exception Handling (PEP 758)

Use bracket-free `except` syntax:

```python
"""Modern exception handling with PEP 758."""

async def execute_with_recovery(prompt: str) -> "ExecutionResult":
    """Execute with modern exception handling."""
    try:
        return await _execute_internal(prompt)
    
    # PEP 758: No brackets needed for except
    except TimeoutError:
        return _create_timeout_result()
    
    except RateLimitError as e:
        # Retry with backoff
        await asyncio.sleep(e.retry_after)
        return await execute_with_recovery(prompt)
    
    except ValidationError, ModelError:  # Multiple exceptions, no brackets
        return _create_error_result()
    
    # Exception groups with except*
    except* NetworkError as eg:
        # Handle all network errors in the group
        for exc in eg.exceptions:
            log_network_error(exc)
        raise
```

---

## Caching Strategy

### `sunwell/cache/manager.py`

```python
"""Caching layer for lens loading and embeddings."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar
import hashlib
import json
import time

from sunwell.core.lens import Lens
from sunwell.core.types import LensReference


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[T]):
    """A cached item with metadata."""
    value: T
    created_at: float
    checksum: str
    ttl: float | None = None  # Time-to-live in seconds
    
    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


@dataclass
class CacheConfig:
    """Configuration for the caching layer."""
    base_dir: Path = field(default_factory=lambda: Path.home() / ".sunwell" / "cache")
    lens_ttl: float | None = None         # None = never expire
    embedding_ttl: float = 86400          # 24 hours
    max_size_mb: int = 500                # Max cache size
    enable_memory_cache: bool = True      # In-memory LRU
    memory_cache_size: int = 50           # Max items in memory


class LensCache:
    """
    Multi-layer cache for lens definitions.
    
    Layer 1: In-memory LRU (fast, volatile)
    Layer 2: Filesystem (persistent, checksum-validated)
    
    Cache invalidation:
    - Checksum-based: lens file content hash
    - TTL-based: configurable expiration
    - Manual: `sunwell cache clear`
    """
    
    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self._memory: dict[str, CacheEntry[Lens]] = {}
        self._access_order: list[str] = []  # For LRU eviction
        
        # Ensure cache directory exists
        self.config.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, ref: LensReference) -> Lens | None:
        """Get a lens from cache, checking all layers."""
        cache_key = self._make_key(ref)
        
        # Layer 1: Memory
        if cache_key in self._memory:
            entry = self._memory[cache_key]
            if not entry.is_expired:
                self._touch(cache_key)
                return entry.value
            else:
                del self._memory[cache_key]
        
        # Layer 2: Filesystem
        cache_path = self._cache_path(cache_key)
        if cache_path.exists():
            entry = self._load_from_disk(cache_path)
            if entry and not entry.is_expired:
                # Promote to memory cache
                if self.config.enable_memory_cache:
                    self._memory[cache_key] = entry
                    self._touch(cache_key)
                return entry.value
        
        return None
    
    def set(self, ref: LensReference, lens: Lens, source_content: str | None = None) -> None:
        """Store a lens in cache."""
        cache_key = self._make_key(ref)
        checksum = self._compute_checksum(source_content or str(lens.metadata))
        
        entry = CacheEntry(
            value=lens,
            created_at=time.time(),
            checksum=checksum,
            ttl=self.config.lens_ttl,
        )
        
        # Memory cache with LRU eviction
        if self.config.enable_memory_cache:
            self._memory[cache_key] = entry
            self._touch(cache_key)
            self._evict_if_needed()
        
        # Filesystem cache
        self._save_to_disk(cache_key, entry)
    
    def invalidate(self, ref: LensReference) -> None:
        """Remove a lens from all cache layers."""
        cache_key = self._make_key(ref)
        
        if cache_key in self._memory:
            del self._memory[cache_key]
            self._access_order.remove(cache_key)
        
        cache_path = self._cache_path(cache_key)
        if cache_path.exists():
            cache_path.unlink()
    
    def clear(self) -> None:
        """Clear all caches."""
        self._memory.clear()
        self._access_order.clear()
        
        for path in self.config.base_dir.glob("*.lens.cache"):
            path.unlink()
    
    def _make_key(self, ref: LensReference) -> str:
        """Generate a cache key from a lens reference."""
        version = ref.version or "latest"
        return f"{ref.source}@{version}".replace("/", "_")
    
    def _cache_path(self, key: str) -> Path:
        return self.config.base_dir / f"{key}.lens.cache"
    
    def _compute_checksum(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _touch(self, key: str) -> None:
        """Update access order for LRU."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if over memory limit."""
        while len(self._memory) > self.config.memory_cache_size:
            oldest = self._access_order.pop(0)
            del self._memory[oldest]
    
    def _save_to_disk(self, key: str, entry: CacheEntry[Lens]) -> None:
        """Persist cache entry to filesystem."""
        # Implementation: serialize lens to YAML + metadata JSON
        ...
    
    def _load_from_disk(self, path: Path) -> CacheEntry[Lens] | None:
        """Load cache entry from filesystem."""
        # Implementation: deserialize and validate checksum
        ...


class EmbeddingCache:
    """
    Cache for lens embedding indexes.
    
    Stores pre-computed vector indexes to avoid re-embedding
    on every lens load. Invalidated when lens content changes.
    """
    
    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self._index_dir = self.config.base_dir / "embeddings"
        self._index_dir.mkdir(parents=True, exist_ok=True)
    
    def get_index(self, lens: Lens, embedder_id: str) -> "VectorIndexProtocol | None":
        """Get cached embedding index for a lens."""
        cache_key = self._make_key(lens, embedder_id)
        index_path = self._index_dir / cache_key
        
        if not index_path.exists():
            return None
        
        # Check if lens has changed
        meta_path = index_path / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            
            if meta.get("lens_checksum") != self._lens_checksum(lens):
                # Lens changed, invalidate cache
                self.invalidate(lens, embedder_id)
                return None
        
        # Load and return index
        from sunwell.embedding.index import InMemoryIndex
        return InMemoryIndex.load(str(index_path))
    
    def set_index(
        self,
        lens: Lens,
        embedder_id: str,
        index: "VectorIndexProtocol",
    ) -> None:
        """Cache an embedding index for a lens."""
        cache_key = self._make_key(lens, embedder_id)
        index_path = self._index_dir / cache_key
        index_path.mkdir(parents=True, exist_ok=True)
        
        # Save index
        index.save(str(index_path))
        
        # Save metadata for invalidation
        with open(index_path / "meta.json", "w") as f:
            json.dump({
                "lens_checksum": self._lens_checksum(lens),
                "embedder_id": embedder_id,
                "created_at": time.time(),
            }, f)
    
    def invalidate(self, lens: Lens, embedder_id: str) -> None:
        """Invalidate cached index for a lens."""
        cache_key = self._make_key(lens, embedder_id)
        index_path = self._index_dir / cache_key
        
        if index_path.exists():
            import shutil
            shutil.rmtree(index_path)
    
    def _make_key(self, lens: Lens, embedder_id: str) -> str:
        return f"{lens.metadata.name}_{lens.metadata.version}_{embedder_id}"
    
    def _lens_checksum(self, lens: Lens) -> str:
        """Compute checksum of lens content for change detection."""
        content = json.dumps({
            "heuristics": [h.name for h in lens.heuristics],
            "personas": [p.name for p in lens.personas],
            "validators": [v.name for v in lens.all_validators],
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

---

## Streaming Validation

### `sunwell/runtime/streaming.py`

```python
"""Streaming execution with progressive validation."""

from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Awaitable
from enum import Enum

from sunwell.core.types import Severity
from sunwell.core.validator import ValidationResult


class StreamState(Enum):
    """State of streaming execution."""
    GENERATING = "generating"
    VALIDATING = "validating"
    REFINING = "refining"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A chunk of streamed output with metadata."""
    content: str
    state: StreamState
    cumulative_content: str               # Full content so far
    partial_validations: tuple[ValidationResult, ...] = ()
    warnings: tuple[str, ...] = ()        # Early warnings detected


@dataclass(frozen=True, slots=True)
class StreamValidationConfig:
    """Configuration for streaming validation."""
    # When to run partial validation
    validate_every_n_chars: int = 500     # Run validators every N chars
    validate_on_sentence_end: bool = True # Run when sentence completes
    
    # What to validate during streaming
    enable_anti_pattern_detection: bool = True  # Check anti-heuristics
    enable_early_termination: bool = True       # Stop on critical errors
    
    # Post-completion behavior
    full_validation_on_complete: bool = True
    persona_testing_on_complete: bool = False   # Usually too expensive


@dataclass
class StreamingValidator:
    """
    Progressive validation during streaming.
    
    Strategy:
    1. During streaming: Run lightweight checks (anti-patterns, length limits)
    2. On sentence boundaries: Run pattern-match validators
    3. On completion: Run full validation suite
    4. If failures: Trigger refinement or return with warnings
    
    This provides early feedback without blocking the stream.
    """
    config: StreamValidationConfig
    lens: "Lens"
    model: "ModelProtocol"
    
    _accumulated: str = field(default="", init=False)
    _partial_results: list[ValidationResult] = field(default_factory=list, init=False)
    _early_warnings: list[str] = field(default_factory=list, init=False)
    
    async def process_stream(
        self,
        stream: AsyncIterator[str],
        on_chunk: Callable[[StreamChunk], Awaitable[None]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Process a stream with progressive validation.
        
        Yields StreamChunks that include:
        - The content chunk
        - Current state (generating/validating/etc.)
        - Any early warnings detected
        - Partial validation results
        """
        chars_since_validation = 0
        
        async for chunk in stream:
            self._accumulated += chunk
            chars_since_validation += len(chunk)
            
            # Check for early termination conditions
            if self.config.enable_early_termination:
                critical = await self._check_critical_violations()
                if critical:
                    yield StreamChunk(
                        content=chunk,
                        state=StreamState.FAILED,
                        cumulative_content=self._accumulated,
                        partial_validations=tuple(self._partial_results),
                        warnings=(critical,),
                    )
                    return
            
            # Run partial validation at intervals
            should_validate = (
                chars_since_validation >= self.config.validate_every_n_chars
                or (self.config.validate_on_sentence_end and self._ends_sentence(chunk))
            )
            
            if should_validate:
                await self._run_partial_validation()
                chars_since_validation = 0
            
            # Detect anti-patterns in real-time
            if self.config.enable_anti_pattern_detection:
                warnings = self._detect_anti_patterns(chunk)
                self._early_warnings.extend(warnings)
            
            stream_chunk = StreamChunk(
                content=chunk,
                state=StreamState.GENERATING,
                cumulative_content=self._accumulated,
                partial_validations=tuple(self._partial_results),
                warnings=tuple(self._early_warnings[-5:]),  # Last 5 warnings
            )
            
            if on_chunk:
                await on_chunk(stream_chunk)
            
            yield stream_chunk
        
        # Stream complete - run full validation
        if self.config.full_validation_on_complete:
            yield StreamChunk(
                content="",
                state=StreamState.VALIDATING,
                cumulative_content=self._accumulated,
            )
            
            final_results = await self._run_full_validation()
            
            yield StreamChunk(
                content="",
                state=StreamState.COMPLETE,
                cumulative_content=self._accumulated,
                partial_validations=tuple(final_results),
                warnings=tuple(self._early_warnings),
            )
    
    async def _check_critical_violations(self) -> str | None:
        """Check for violations that should terminate streaming early."""
        # Check content length limits
        if len(self._accumulated) > 100_000:  # 100KB sanity limit
            return "Content exceeds maximum length"
        
        # Check for blocked patterns (e.g., PII, secrets)
        for anti in self.lens.anti_heuristics:
            for trigger in anti.triggers:
                if trigger.lower() in self._accumulated.lower()[-500:]:
                    if any(t in trigger.lower() for t in ["secret", "password", "api_key"]):
                        return f"Blocked pattern detected: {anti.name}"
        
        return None
    
    async def _run_partial_validation(self) -> None:
        """Run lightweight validators on accumulated content."""
        # Only run pattern-match validators during streaming
        for validator in self.lens.heuristic_validators:
            if validator.method == ValidationMethod.PATTERN_MATCH:
                result = await self._quick_pattern_check(validator)
                if not result.passed:
                    self._partial_results.append(result)
    
    async def _run_full_validation(self) -> list[ValidationResult]:
        """Run complete validation suite after streaming completes."""
        from sunwell.validation.runner import ValidationRunner
        
        runner = ValidationRunner(
            lens=self.lens,
            model=self.model,
        )
        
        return await runner.run_all(self._accumulated)
    
    def _detect_anti_patterns(self, chunk: str) -> list[str]:
        """Detect anti-patterns in a chunk."""
        warnings = []
        
        for anti in self.lens.anti_heuristics:
            for trigger in anti.triggers:
                if trigger.lower() in chunk.lower():
                    warnings.append(f"Anti-pattern '{anti.name}': {anti.correction}")
        
        return warnings
    
    def _ends_sentence(self, chunk: str) -> bool:
        """Check if chunk ends a sentence."""
        return any(chunk.rstrip().endswith(p) for p in ".!?")
    
    async def _quick_pattern_check(self, validator: "HeuristicValidator") -> ValidationResult:
        """Quick pattern check without full LLM validation."""
        # Use regex or keyword matching for speed
        ...
```

---

## Observability & Telemetry

### `sunwell/telemetry/`

```python
"""Observability infrastructure for Sunwell."""

# sunwell/telemetry/types.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class EventType(Enum):
    """Types of telemetry events."""
    # Lifecycle events
    LENS_LOADED = "lens.loaded"
    LENS_RESOLVED = "lens.resolved"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    
    # Retrieval events
    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    
    # Validation events
    VALIDATION_STARTED = "validation.started"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATOR_RUN = "validator.run"
    PERSONA_RUN = "persona.run"
    
    # Model events
    MODEL_CALL_STARTED = "model.call.started"
    MODEL_CALL_COMPLETED = "model.call.completed"
    MODEL_CALL_FAILED = "model.call.failed"
    
    # Error events
    ERROR_OCCURRED = "error.occurred"
    
    # Performance events
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """A single telemetry event."""
    event_type: EventType
    timestamp: datetime
    trace_id: str                         # Links related events
    span_id: str                          # Unique event ID
    parent_span_id: str | None = None     # For hierarchical tracing
    
    # Event-specific data
    data: dict[str, Any] = field(default_factory=dict)
    
    # Performance metrics
    duration_ms: float | None = None
    
    # Context
    lens_name: str | None = None
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Aggregated metrics for a single execution."""
    trace_id: str
    lens_name: str
    model_id: str
    
    # Timing
    total_duration_ms: float
    retrieval_duration_ms: float
    model_duration_ms: float
    validation_duration_ms: float
    
    # Token usage
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    # Retrieval stats
    components_retrieved: int
    components_injected: int
    
    # Validation stats
    validators_run: int
    validators_passed: int
    validators_failed: int
    
    # Quality
    tier: "Tier"
    confidence_score: float
    refinement_count: int


# sunwell/telemetry/collector.py

from typing import Protocol, runtime_checkable, Callable
from contextlib import asynccontextmanager
import time


@runtime_checkable
class TelemetryCollector(Protocol):
    """Protocol for telemetry backends."""
    
    def emit(self, event: TelemetryEvent) -> None:
        """Emit a telemetry event."""
        ...
    
    def flush(self) -> None:
        """Flush any buffered events."""
        ...


class InMemoryCollector:
    """
    In-memory telemetry collector for development/testing.
    
    Stores events in a list for inspection.
    """
    
    def __init__(self, max_events: int = 10_000):
        self.events: list[TelemetryEvent] = []
        self.max_events = max_events
    
    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def flush(self) -> None:
        pass  # No-op for in-memory
    
    def get_trace(self, trace_id: str) -> list[TelemetryEvent]:
        """Get all events for a trace."""
        return [e for e in self.events if e.trace_id == trace_id]
    
    def get_metrics(self, trace_id: str) -> ExecutionMetrics | None:
        """Compute aggregated metrics for a trace."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        
        # Aggregate events into metrics
        ...


class LoggingCollector:
    """
    Telemetry collector that writes to standard logging.
    
    Integrates with Python's logging module for compatibility
    with existing log aggregation pipelines.
    """
    
    def __init__(self, logger_name: str = "sunwell.telemetry"):
        import logging
        self.logger = logging.getLogger(logger_name)
    
    def emit(self, event: TelemetryEvent) -> None:
        self.logger.info(
            f"[{event.event_type.value}] trace={event.trace_id} "
            f"span={event.span_id} duration={event.duration_ms}ms "
            f"data={event.data}"
        )
    
    def flush(self) -> None:
        pass


class OpenTelemetryCollector:
    """
    Telemetry collector using OpenTelemetry.
    
    Enables integration with observability platforms:
    - Jaeger
    - Zipkin
    - Datadog
    - Honeycomb
    - etc.
    """
    
    def __init__(self, service_name: str = "sunwell"):
        # Requires: opentelemetry-api, opentelemetry-sdk
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(service_name)
    
    def emit(self, event: TelemetryEvent) -> None:
        # Convert to OpenTelemetry span
        ...
    
    def flush(self) -> None:
        ...


# sunwell/telemetry/context.py

from contextvars import ContextVar, Token

# Context variables for trace propagation (Python 3.14 best practice)
_current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_current_span_stack: ContextVar[list[str]] = ContextVar("span_stack", default_factory=list)


class TelemetryContext:
    """
    Context manager for telemetry tracing using contextvars.
    
    Uses contextvars (instead of instance variables) for proper async
    context propagation - trace IDs automatically flow through await chains
    without explicit passing.
    
    Usage:
        async with telemetry.trace("execution", lens_name="tech-writer") as span:
            # ... do work ...
            span.set_attribute("components_retrieved", 5)
            
            # Nested spans automatically link to parent
            async with telemetry.trace("retrieval") as inner_span:
                # parent_span_id is automatically set
                ...
    """
    
    def __init__(self, collector: TelemetryCollector):
        self.collector = collector
    
    @asynccontextmanager
    async def trace(
        self,
        operation: str,
        **attributes,
    ):
        """Create a new trace span with automatic context propagation."""
        span_id = str(uuid.uuid4())[:8]
        
        # Get or create trace ID from context
        trace_id = _current_trace_id.get()
        if trace_id is None:
            trace_id = str(uuid.uuid4())[:16]
            trace_token = _current_trace_id.set(trace_id)
        else:
            trace_token = None
        
        # Get span stack from context, add new span
        span_stack = _current_span_stack.get().copy()
        parent_span = span_stack[-1] if span_stack else None
        span_stack.append(span_id)
        stack_token = _current_span_stack.set(span_stack)
        
        start_time = time.perf_counter()
        
        # Emit start event
        self.collector.emit(TelemetryEvent(
            event_type=EventType[f"{operation.upper()}_STARTED"],
            timestamp=datetime.now(),
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span,
            data=attributes,
        ))
        
        span = SpanContext(attributes)
        
        try:
            yield span
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Emit completion event
            self.collector.emit(TelemetryEvent(
                event_type=EventType[f"{operation.upper()}_COMPLETED"],
                timestamp=datetime.now(),
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span,
                duration_ms=duration_ms,
                data={**attributes, **span._attributes},
            ))
            
            # Restore context
            _current_span_stack.reset(stack_token)
            if trace_token is not None:
                _current_trace_id.reset(trace_token)
    
    @staticmethod
    def get_current_trace_id() -> str | None:
        """Get the current trace ID from context (for logging, etc.)."""
        return _current_trace_id.get()
    
    @staticmethod  
    def get_current_span_id() -> str | None:
        """Get the current span ID from context."""
        stack = _current_span_stack.get()
        return stack[-1] if stack else None


@dataclass
class SpanContext:
    """Context for adding attributes to a span."""
    _attributes: dict[str, Any] = field(default_factory=dict)
    
    def set_attribute(self, key: str, value: Any) -> None:
        self._attributes[key] = value
```

---

## Plugin System

### `sunwell/plugins/`

```python
"""Plugin system for custom validators and extensions."""

# sunwell/plugins/protocol.py

from typing import Protocol, runtime_checkable, Any
from pathlib import Path


@runtime_checkable
class ValidatorPlugin(Protocol):
    """
    Protocol for custom validator plugins.
    
    Plugins can be:
    1. Python modules with a `validate` function
    2. Classes implementing ValidatorPlugin
    3. External scripts (via script validators)
    """
    
    @property
    def name(self) -> str:
        """Unique validator name."""
        ...
    
    @property
    def description(self) -> str:
        """Human-readable description."""
        ...
    
    async def validate(
        self,
        content: str,
        context: "ValidationContext",
    ) -> "ValidationResult":
        """Run validation on content."""
        ...
    
    def configure(self, config: dict[str, Any]) -> None:
        """Configure the validator with lens-specific settings."""
        ...


@runtime_checkable
class EmbedderPlugin(Protocol):
    """Protocol for custom embedding providers."""
    
    @property
    def name(self) -> str:
        ...
    
    @property
    def dimensions(self) -> int:
        ...
    
    async def embed(self, texts: list[str]) -> "NDArray[np.float32]":
        ...


# sunwell/plugins/loader.py

import importlib.util
import sys
from dataclasses import dataclass


@dataclass
class PluginManifest:
    """Manifest describing a plugin."""
    name: str
    version: str
    type: Literal["validator", "embedder", "model", "hook"]
    entry_point: str                      # Module path or class name
    config_schema: dict | None = None     # JSON Schema for configuration
    dependencies: tuple[str, ...] = ()    # Required packages


class PluginLoader:
    """
    Load and manage Sunwell plugins.
    
    Plugin discovery:
    1. Built-in plugins (sunwell.plugins.builtin)
    2. Installed packages (entry_points: sunwell.plugins)
    3. Local plugins (~/.sunwell/plugins/)
    4. Lens-local plugins (./plugins/ relative to lens)
    
    Security:
    - Plugins run in the same process (no sandboxing by default)
    - Use sandbox mode for untrusted plugins
    """
    
    def __init__(
        self,
        plugin_dirs: list[Path] | None = None,
        enable_builtin: bool = True,
    ):
        self.plugin_dirs = plugin_dirs or [
            Path.home() / ".sunwell" / "plugins",
        ]
        self.enable_builtin = enable_builtin
        self._loaded: dict[str, Any] = {}
    
    def discover(self) -> list[PluginManifest]:
        """Discover all available plugins."""
        manifests = []
        
        # Built-in plugins
        if self.enable_builtin:
            manifests.extend(self._discover_builtin())
        
        # Entry points (pip-installed)
        manifests.extend(self._discover_entry_points())
        
        # Local plugins
        for plugin_dir in self.plugin_dirs:
            if plugin_dir.exists():
                manifests.extend(self._discover_directory(plugin_dir))
        
        return manifests
    
    def load_validator(self, name: str) -> ValidatorPlugin:
        """Load a validator plugin by name."""
        if name in self._loaded:
            return self._loaded[name]
        
        manifest = self._find_manifest(name, "validator")
        if not manifest:
            raise PluginError(f"Validator plugin not found: {name}")
        
        plugin = self._load_plugin(manifest)
        self._loaded[name] = plugin
        return plugin
    
    def load_from_lens(self, lens: "Lens") -> dict[str, ValidatorPlugin]:
        """Load all plugins referenced by a lens."""
        plugins = {}
        
        for validator in lens.deterministic_validators:
            if validator.script.startswith("plugin:"):
                plugin_name = validator.script[7:]  # Remove "plugin:" prefix
                plugins[validator.name] = self.load_validator(plugin_name)
        
        return plugins
    
    def _discover_builtin(self) -> list[PluginManifest]:
        """Discover built-in plugins."""
        return [
            PluginManifest(
                name="link_checker",
                version="1.0.0",
                type="validator",
                entry_point="sunwell.plugins.builtin.link_checker",
            ),
            PluginManifest(
                name="code_syntax",
                version="1.0.0",
                type="validator",
                entry_point="sunwell.plugins.builtin.code_syntax",
            ),
            PluginManifest(
                name="markdown_lint",
                version="1.0.0",
                type="validator",
                entry_point="sunwell.plugins.builtin.markdown_lint",
            ),
        ]
    
    def _discover_entry_points(self) -> list[PluginManifest]:
        """Discover plugins via setuptools entry points."""
        try:
            from importlib.metadata import entry_points
            eps = entry_points(group="sunwell.plugins")
            return [self._entry_point_to_manifest(ep) for ep in eps]
        except ImportError:
            return []
    
    def _discover_directory(self, path: Path) -> list[PluginManifest]:
        """Discover plugins in a directory."""
        manifests = []
        for manifest_path in path.glob("*/manifest.json"):
            manifests.append(self._load_manifest(manifest_path))
        return manifests
    
    def _load_plugin(self, manifest: PluginManifest) -> Any:
        """Load a plugin from its manifest."""
        spec = importlib.util.find_spec(manifest.entry_point)
        if spec is None:
            # Try loading as a file path
            spec = importlib.util.spec_from_file_location(
                manifest.name,
                manifest.entry_point,
            )
        
        if spec is None or spec.loader is None:
            raise PluginError(f"Cannot load plugin: {manifest.entry_point}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[manifest.name] = module
        spec.loader.exec_module(module)
        
        # Look for the plugin class or function
        if hasattr(module, "Plugin"):
            return module.Plugin()
        elif hasattr(module, "validate"):
            return FunctionValidatorWrapper(module.validate, manifest.name)
        else:
            raise PluginError(f"Plugin has no Plugin class or validate function: {manifest.name}")


# sunwell/plugins/builtin/link_checker.py

"""Built-in link checker validator plugin."""

import re
from dataclasses import dataclass


@dataclass
class LinkCheckerPlugin:
    """Validates that all links in content are well-formed."""
    
    name: str = "link_checker"
    description: str = "Validates URLs and relative links"
    
    _url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    _relative_link_pattern = re.compile(
        r'\[([^\]]+)\]\(([^)]+)\)'
    )
    
    async def validate(
        self,
        content: str,
        context: "ValidationContext",
    ) -> "ValidationResult":
        issues = []
        
        # Check URL format
        for match in self._url_pattern.finditer(content):
            url = match.group()
            if not self._is_valid_url(url):
                issues.append(f"Malformed URL: {url}")
        
        # Check markdown links
        for match in self._relative_link_pattern.finditer(content):
            link_text, link_target = match.groups()
            if not link_target:
                issues.append(f"Empty link target for: {link_text}")
        
        return ValidationResult(
            validator_name=self.name,
            passed=len(issues) == 0,
            severity=Severity.WARNING,
            message="; ".join(issues) if issues else None,
            details={"issues": issues},
        )
    
    def configure(self, config: dict) -> None:
        # Accept configuration options
        pass
    
    def _is_valid_url(self, url: str) -> bool:
        # Basic URL validation
        return url.startswith(("http://", "https://"))


# Create plugin instance
Plugin = LinkCheckerPlugin
```

---

## Security & Sandbox Model

### `sunwell/sandbox/`

```python
"""Sandbox for executing untrusted validator scripts."""

# sunwell/sandbox/executor.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import asyncio
import tempfile
import os


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Configuration for script sandboxing."""
    # Execution limits
    timeout_seconds: float = 30.0
    max_memory_mb: int = 256
    max_output_bytes: int = 1_048_576     # 1MB
    
    # Filesystem access
    allow_read: tuple[str, ...] = ()       # Allowed read paths
    allow_write: tuple[str, ...] = ()      # Allowed write paths (usually empty)
    
    # Network access
    allow_network: bool = False
    
    # Environment
    inherit_env: bool = False
    env_allowlist: tuple[str, ...] = ("PATH", "HOME", "USER")
    
    # Sandbox technology (subinterpreter is Python 3.14+ native isolation)
    sandbox_type: Literal["subinterpreter", "subprocess", "docker", "firejail", "bubblewrap"] = "subinterpreter"


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Result from sandbox execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    memory_exceeded: bool = False
    sandbox_violation: str | None = None


class SandboxExecutor:
    """
    Execute scripts in a sandboxed environment.
    
    Sandbox levels (in order of preference):
    1. subinterpreter (default, Python 3.14+): PEP 734 isolated interpreter
       - Lowest overhead, Python-native isolation
       - Separate GIL, separate globals, no shared state
       - Best for Python validator scripts
    2. subprocess: Basic isolation via subprocess with limits
    3. firejail: Linux namespace isolation (if available)
    4. bubblewrap: Lightweight container (if available)  
    5. docker: Full container isolation (if available)
    
    The executor automatically selects the best available sandbox.
    """
    
    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._sandbox_impl = self._select_sandbox()
    
    async def execute(
        self,
        script: str,
        input_data: str,
        working_dir: Path | None = None,
    ) -> SandboxResult:
        """
        Execute a script in the sandbox.
        
        Args:
            script: Path to script or inline script content
            input_data: Data to pass via stdin
            working_dir: Working directory for execution
        
        Returns:
            SandboxResult with exit code, output, and metadata
        """
        # Create temp directory for execution
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Write input data to temp file
            input_file = tmppath / "input.txt"
            input_file.write_text(input_data)
            
            # Determine if script is a path or inline
            if Path(script).exists():
                script_path = Path(script)
            else:
                # Write inline script to temp file
                script_path = tmppath / "script.sh"
                script_path.write_text(script)
                script_path.chmod(0o755)
            
            return await self._sandbox_impl.run(
                script_path=script_path,
                input_file=input_file,
                working_dir=working_dir or tmppath,
                config=self.config,
            )
    
    def _select_sandbox(self) -> "SandboxImplementation":
        """Select the best available sandbox implementation."""
        # PEP 734: Subinterpreters are the default for Python 3.14+
        if self.config.sandbox_type == "subinterpreter":
            return SubinterpreterSandbox()
        elif self.config.sandbox_type == "docker" and self._has_docker():
            return DockerSandbox()
        elif self.config.sandbox_type == "firejail" and self._has_firejail():
            return FirejailSandbox()
        elif self.config.sandbox_type == "bubblewrap" and self._has_bubblewrap():
            return BubblewrapSandbox()
        else:
            return SubprocessSandbox()
    
    def _has_docker(self) -> bool:
        return os.path.exists("/var/run/docker.sock")
    
    def _has_firejail(self) -> bool:
        return os.path.exists("/usr/bin/firejail")
    
    def _has_bubblewrap(self) -> bool:
        return os.path.exists("/usr/bin/bwrap")


class SubprocessSandbox:
    """
    Basic sandbox using subprocess with resource limits.
    
    Provides:
    - Timeout enforcement
    - Memory limits (via ulimit on Unix)
    - Restricted environment variables
    - No network isolation (use firejail/docker for that)
    """
    
    async def run(
        self,
        script_path: Path,
        input_file: Path,
        working_dir: Path,
        config: SandboxConfig,
    ) -> SandboxResult:
        import time
        import resource
        
        def set_limits():
            """Set resource limits for child process."""
            # Memory limit
            mem_bytes = config.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            
            # CPU time limit (slightly more than timeout)
            cpu_limit = int(config.timeout_seconds) + 5
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        
        # Build restricted environment
        env = {}
        if config.inherit_env:
            env = {k: v for k, v in os.environ.items() if k in config.env_allowlist}
        
        start_time = time.perf_counter()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                str(script_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
                preexec_fn=set_limits if os.name != "nt" else None,
            )
            
            input_data = input_file.read_bytes()
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input_data),
                    timeout=config.timeout_seconds,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()
                timed_out = True
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return SandboxResult(
                exit_code=proc.returncode or -1,
                stdout=stdout.decode("utf-8", errors="replace")[:config.max_output_bytes],
                stderr=stderr.decode("utf-8", errors="replace")[:config.max_output_bytes],
                duration_ms=duration_ms,
                timed_out=timed_out,
            )
        
        except MemoryError:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="Memory limit exceeded",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                memory_exceeded=True,
            )


class DockerSandbox:
    """
    Full container isolation using Docker.
    
    Provides:
    - Complete filesystem isolation
    - Network isolation
    - Resource limits via cgroups
    - Reproducible environment
    """
    
    async def run(
        self,
        script_path: Path,
        input_file: Path,
        working_dir: Path,
        config: SandboxConfig,
    ) -> SandboxResult:
        # Build docker run command
        cmd = [
            "docker", "run",
            "--rm",
            "--network", "none" if not config.allow_network else "bridge",
            "--memory", f"{config.max_memory_mb}m",
            "--cpus", "1",
            "-v", f"{working_dir}:/workspace:ro",
            "-v", f"{script_path}:/script:ro",
            "-v", f"{input_file}:/input:ro",
            "-w", "/workspace",
            "sunwell/sandbox:latest",  # Minimal sandbox image
            "/script",
        ]
        
        # Execute and capture result
        ...
```

---

## State Management

### `sunwell/state/`

```python
"""State management for multi-step workflows."""

# sunwell/state/store.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import json
import uuid


@dataclass(frozen=True, slots=True)
class WorkflowState:
    """State of a workflow execution."""
    workflow_id: str
    workflow_name: str
    lens_name: str
    
    # Current position
    current_step: int
    total_steps: int
    status: Literal["pending", "in_progress", "paused", "completed", "failed"]
    
    # Accumulated data
    step_outputs: tuple[dict[str, Any], ...]
    context: dict[str, Any]               # Shared context across steps
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None    # Auto-cleanup time


@runtime_checkable
class StateStore(Protocol):
    """Protocol for workflow state storage backends."""
    
    async def save(self, state: WorkflowState) -> None:
        """Persist workflow state."""
        ...
    
    async def load(self, workflow_id: str) -> WorkflowState | None:
        """Load workflow state by ID."""
        ...
    
    async def delete(self, workflow_id: str) -> None:
        """Delete workflow state."""
        ...
    
    async def list_active(self, lens_name: str | None = None) -> list[WorkflowState]:
        """List all active (non-completed) workflows."""
        ...
    
    async def cleanup_expired(self) -> int:
        """Remove expired states. Returns count deleted."""
        ...


class FileStateStore:
    """
    File-based state storage.
    
    Stores workflow state as JSON files in a directory.
    Good for single-user, local development.
    """
    
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path.home() / ".sunwell" / "state"
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def save(self, state: WorkflowState) -> None:
        path = self.base_dir / f"{state.workflow_id}.json"
        
        data = {
            "workflow_id": state.workflow_id,
            "workflow_name": state.workflow_name,
            "lens_name": state.lens_name,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "status": state.status,
            "step_outputs": list(state.step_outputs),
            "context": state.context,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "expires_at": state.expires_at.isoformat() if state.expires_at else None,
        }
        
        path.write_text(json.dumps(data, indent=2))
    
    async def load(self, workflow_id: str) -> WorkflowState | None:
        path = self.base_dir / f"{workflow_id}.json"
        
        if not path.exists():
            return None
        
        data = json.loads(path.read_text())
        
        return WorkflowState(
            workflow_id=data["workflow_id"],
            workflow_name=data["workflow_name"],
            lens_name=data["lens_name"],
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            status=data["status"],
            step_outputs=tuple(data["step_outputs"]),
            context=data["context"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None,
        )
    
    async def delete(self, workflow_id: str) -> None:
        path = self.base_dir / f"{workflow_id}.json"
        if path.exists():
            path.unlink()
    
    async def list_active(self, lens_name: str | None = None) -> list[WorkflowState]:
        states = []
        
        for path in self.base_dir.glob("*.json"):
            state = await self.load(path.stem)
            if state and state.status not in ("completed", "failed"):
                if lens_name is None or state.lens_name == lens_name:
                    states.append(state)
        
        return states
    
    async def cleanup_expired(self) -> int:
        count = 0
        now = datetime.now()
        
        for path in self.base_dir.glob("*.json"):
            state = await self.load(path.stem)
            if state and state.expires_at and state.expires_at < now:
                await self.delete(state.workflow_id)
                count += 1
        
        return count


# sunwell/state/workflow_executor.py

class WorkflowExecutor:
    """
    Execute multi-step workflows with state persistence.
    
    Features:
    - Resume from any step after interruption
    - Pass context between steps
    - Run quality gates after each step
    - Support for long-running workflows (hours/days)
    """
    
    def __init__(
        self,
        runtime: "RuntimeEngine",
        state_store: StateStore,
    ):
        self.runtime = runtime
        self.state_store = state_store
    
    async def start_workflow(
        self,
        workflow: "Workflow",
        initial_prompt: str,
        initial_context: dict[str, Any] | None = None,
    ) -> WorkflowState:
        """Start a new workflow execution."""
        workflow_id = str(uuid.uuid4())
        now = datetime.now()
        
        state = WorkflowState(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            lens_name=self.runtime.lens.metadata.name,
            current_step=0,
            total_steps=len(workflow.steps),
            status="in_progress",
            step_outputs=(),
            context={
                "initial_prompt": initial_prompt,
                **(initial_context or {}),
            },
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=7) if workflow.state_management else None,
        )
        
        await self.state_store.save(state)
        
        # Execute first step
        return await self.continue_workflow(workflow_id)
    
    async def continue_workflow(self, workflow_id: str) -> WorkflowState:
        """Continue a paused or in-progress workflow."""
        state = await self.state_store.load(workflow_id)
        if not state:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        if state.status == "completed":
            return state
        
        workflow = self._get_workflow(state.workflow_name)
        
        while state.current_step < state.total_steps:
            step = workflow.steps[state.current_step]
            
            # Build prompt for this step
            prompt = self._build_step_prompt(step, state)
            
            # Execute step
            result = await self.runtime.execute(prompt)
            
            # Run quality gates
            if step.quality_gates:
                passed = await self._run_quality_gates(step.quality_gates, result.content)
                if not passed:
                    state = self._update_state(state, status="failed")
                    await self.state_store.save(state)
                    return state
            
            # Update state
            step_output = {
                "step_name": step.name,
                "content": result.content,
                "confidence": result.confidence.score,
            }
            
            state = WorkflowState(
                workflow_id=state.workflow_id,
                workflow_name=state.workflow_name,
                lens_name=state.lens_name,
                current_step=state.current_step + 1,
                total_steps=state.total_steps,
                status="in_progress" if state.current_step + 1 < state.total_steps else "completed",
                step_outputs=state.step_outputs + (step_output,),
                context={**state.context, f"step_{state.current_step}_output": result.content},
                created_at=state.created_at,
                updated_at=datetime.now(),
                expires_at=state.expires_at,
            )
            
            await self.state_store.save(state)
        
        return state
    
    async def pause_workflow(self, workflow_id: str) -> WorkflowState:
        """Pause a running workflow for later resumption."""
        state = await self.state_store.load(workflow_id)
        if not state:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        state = self._update_state(state, status="paused")
        await self.state_store.save(state)
        return state
    
    def _build_step_prompt(self, step: "WorkflowStep", state: WorkflowState) -> str:
        """Build the prompt for a workflow step using accumulated context."""
        return f"""
Previous context:
{json.dumps(state.context, indent=2)}

Previous step outputs:
{json.dumps(list(state.step_outputs), indent=2)}

Current step: {step.name}
Action: {step.action}

Execute this step based on the context above.
"""
```

---

## Schema Versioning & Migration

### `sunwell/schema/versioning.py`

```python
"""Schema versioning and migration for LDL."""

from dataclasses import dataclass
from typing import Callable
from enum import Enum


class LDLVersion(Enum):
    """LDL schema versions."""
    V1_0 = "1.0"      # Initial release
    V1_1 = "1.1"      # Added anti_heuristics
    V1_2 = "1.2"      # Added refiners, provenance
    V2_0 = "2.0"      # Breaking: renamed validators structure


@dataclass(frozen=True, slots=True)
class SchemaVersion:
    """Parsed schema version."""
    major: int
    minor: int
    
    @classmethod
    def parse(cls, version_str: str) -> "SchemaVersion":
        parts = version_str.split(".")
        return cls(major=int(parts[0]), minor=int(parts[1]))
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"
    
    def is_compatible_with(self, other: "SchemaVersion") -> bool:
        """Check if this version is compatible with another."""
        # Same major version = compatible (minor changes are additive)
        return self.major == other.major


# Type for migration functions
MigrationFn = Callable[[dict], dict]


class SchemaMigrator:
    """
    Migrate lens definitions between schema versions.
    
    Migration strategy:
    - Minor version bumps: Additive changes, no migration needed
    - Major version bumps: Breaking changes, require explicit migration
    
    Each migration is a pure function that transforms the lens dict
    from one version to the next.
    """
    
    CURRENT_VERSION = SchemaVersion(2, 0)
    
    def __init__(self):
        self._migrations: dict[tuple[SchemaVersion, SchemaVersion], MigrationFn] = {
            # V1.0 -> V1.1: Add anti_heuristics field
            (SchemaVersion(1, 0), SchemaVersion(1, 1)): self._migrate_1_0_to_1_1,
            # V1.1 -> V1.2: Add refiners and provenance
            (SchemaVersion(1, 1), SchemaVersion(1, 2)): self._migrate_1_1_to_1_2,
            # V1.2 -> V2.0: Restructure validators
            (SchemaVersion(1, 2), SchemaVersion(2, 0)): self._migrate_1_2_to_2_0,
        }
    
    def migrate(self, lens_data: dict, from_version: str, to_version: str | None = None) -> dict:
        """
        Migrate lens data from one version to another.
        
        Args:
            lens_data: Raw lens dictionary
            from_version: Current version string
            to_version: Target version (defaults to CURRENT_VERSION)
        
        Returns:
            Migrated lens dictionary
        """
        from_v = SchemaVersion.parse(from_version)
        to_v = SchemaVersion.parse(to_version) if to_version else self.CURRENT_VERSION
        
        if from_v == to_v:
            return lens_data
        
        if from_v.major > to_v.major:
            raise ValueError(f"Cannot downgrade from {from_v} to {to_v}")
        
        # Apply migrations in sequence
        current = lens_data.copy()
        current_version = from_v
        
        for (src, dst), migration_fn in sorted(self._migrations.items()):
            if src >= current_version and dst <= to_v:
                current = migration_fn(current)
                current_version = dst
        
        # Update schema version in output
        current["schema_version"] = str(to_v)
        
        return current
    
    def _migrate_1_0_to_1_1(self, data: dict) -> dict:
        """Add anti_heuristics field (V1.0 -> V1.1)."""
        result = data.copy()
        
        # Add empty anti_heuristics if not present
        if "lens" in result and "heuristics" in result["lens"]:
            if "anti_heuristics" not in result["lens"]["heuristics"]:
                result["lens"]["heuristics"]["anti_heuristics"] = []
        
        return result
    
    def _migrate_1_1_to_1_2(self, data: dict) -> dict:
        """Add refiners and provenance fields (V1.1 -> V1.2)."""
        result = data.copy()
        
        if "lens" in result:
            if "refiners" not in result["lens"]:
                result["lens"]["refiners"] = []
            if "provenance" not in result["lens"]:
                result["lens"]["provenance"] = None
        
        return result
    
    def _migrate_1_2_to_2_0(self, data: dict) -> dict:
        """
        Restructure validators (V1.2 -> V2.0).
        
        Before (V1.x):
            validators:
              - name: "check"
                type: "deterministic"
                script: "..."
        
        After (V2.0):
            validators:
              deterministic:
                - name: "check"
                  script: "..."
              heuristic:
                - name: "check2"
                  check: "..."
        """
        result = data.copy()
        
        if "lens" in result and "validators" in result["lens"]:
            old_validators = result["lens"]["validators"]
            
            # Skip if already in V2 format
            if isinstance(old_validators, dict) and ("deterministic" in old_validators or "heuristic" in old_validators):
                return result
            
            # Convert flat list to categorized dict
            new_validators = {
                "deterministic": [],
                "heuristic": [],
            }
            
            for v in old_validators:
                if isinstance(v, dict):
                    v_type = v.pop("type", "deterministic")
                    if v_type == "deterministic":
                        new_validators["deterministic"].append(v)
                    elif v_type == "heuristic":
                        new_validators["heuristic"].append(v)
            
            result["lens"]["validators"] = new_validators
        
        return result


class SchemaValidator:
    """
    Validate lens files against the LDL schema.
    
    Uses JSON Schema for validation with version-specific schemas.
    """
    
    def __init__(self, schema_dir: Path | None = None):
        self.schema_dir = schema_dir or Path(__file__).parent / "schemas"
        self._schemas: dict[str, dict] = {}
    
    def validate(self, lens_data: dict, version: str | None = None) -> list[str]:
        """
        Validate lens data against schema.
        
        Returns list of validation errors (empty if valid).
        """
        version = version or lens_data.get("schema_version", "2.0")
        schema = self._load_schema(version)
        
        import jsonschema
        
        errors = []
        validator = jsonschema.Draft7Validator(schema)
        
        for error in validator.iter_errors(lens_data):
            path = ".".join(str(p) for p in error.path)
            errors.append(f"{path}: {error.message}")
        
        return errors
    
    def _load_schema(self, version: str) -> dict:
        """Load JSON Schema for a specific version."""
        if version not in self._schemas:
            schema_path = self.schema_dir / f"ldl-{version}.json"
            
            if not schema_path.exists():
                raise ValueError(f"Unknown schema version: {version}")
            
            import json
            self._schemas[version] = json.loads(schema_path.read_text())
        
        return self._schemas[version]
```

---

## Next Steps

1. **Phase 1**: Implement core models and schema loader
2. **Phase 2**: Build retriever with basic vector search
3. **Phase 3**: Implement runtime engine
4. **Phase 4**: Add model adapters (OpenAI, Anthropic)
5. **Phase 5**: Build CLI
6. **Phase 6**: Add validation system
7. **Phase 7**: Fount client

---

## Resolved Technical Questions

The following questions from the original vision have been addressed:

| Question | Resolution | Section |
|----------|------------|---------|
| **Vector DB** | `VectorIndexProtocol` enables pluggable backends. MVP uses `InMemoryIndex` (NumPy); production can use FAISS/Qdrant/Pinecone via protocol. | Embedding and Vector Search |
| **Caching** | `LensCache` (memory + filesystem) and `EmbeddingCache` with checksum-based invalidation. Configurable TTL, LRU eviction. | Caching Strategy |
| **Streaming validation** | `StreamingValidator` provides progressive validation during streaming with anti-pattern detection, partial validation at intervals, and full validation on completion. | Streaming Validation |
| **State management** | `WorkflowState` + `StateStore` protocol with `FileStateStore` for local persistence. Supports pause/resume, step context accumulation. | State Management |
| **Plugin system** | `ValidatorPlugin` protocol + `PluginLoader` with discovery via entry points, local directories, and manifest files. Built-in plugins included. | Plugin System |

---

## Remaining Open Questions

1. **Multi-tenant fount**: How do we handle namespace conflicts in the public fount? First-come-first-served? Verified organizations?

2. **Lens signing**: Should lenses be cryptographically signed for integrity verification? What PKI model?

3. **Federated registries**: Can lenses reference across multiple registries? How do we handle versioning across registries?

4. **Hot reloading**: Should the runtime support hot-reloading lenses without restart? What are the cache invalidation implications?

5. **Distributed execution**: For very large lenses (1000+ components), should retrieval/validation be distributed? What's the performance threshold?

6. **Backward compatibility policy**: When LDL 3.0 ships, how long do we support 2.0 lenses? Auto-migration? Deprecation warnings?
