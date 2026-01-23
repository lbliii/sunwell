# 🌟 Sunwell

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/sunwell/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**The Agent Control Plane.**

Other tools let agents write. Sunwell lets you **direct** them.

> *IDE = human writes*  
> *Agent = AI writes*  
> *ACP = human directs agents*

Works for code, documentation, configuration — any text-based project.

```bash
sunwell "Build a REST API with auth"
```

---

## The Shift

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHERE SUNWELL FITS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   IDE (VS Code, Cursor)          AGENTS (Claude, Copilot)       │
│   ─────────────────────          ────────────────────────       │
│   Human writes code              AI writes code                 │
│   File-centric view              File-centric view              │
│   No project model               No project model               │
│                                                                 │
│                         SUNWELL (ACP)                           │
│                         ─────────────                           │
│                    Human directs agents                         │
│                                                                 │
│                    ┌─────────────────────┐                      │
│                    │    STATE DAG        │                      │
│                    │  (Project Health)   │                      │
│                    └─────────────────────┘                      │
│                              │                                  │
│                    ┌─────────┴─────────┐                        │
│                    │   TRUST LAYER     │                        │
│                    │ (Confidence 🟢🟡🔴)│                        │
│                    └───────────────────┘                        │
│                              │                                  │
│                    ┌─────────┴─────────┐                        │
│                    │  ORCHESTRATION    │                        │
│                    │ (Multi-Perspective)│                        │
│                    └───────────────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**What's different**:

| Capability | IDE / Cursor | Sunwell |
|------------|--------------|---------|
| **Project model** | Files and folders | Semantic State DAG |
| **Trust** | Implicit ("does it compile?") | Explicit (confidence + provenance) |
| **Quality source** | Model size | Structured cognition |
| **Mode** | Reactive | Proactive (finds issues, proposes work) |
| **Memory** | Stateless | Persistent (remembers decisions) |
| **Cost** | Per-request | Local models ($0) |

---

## See It Work

Same model. Same prompt. Different architecture.

```bash
sunwell demo  # Run this yourself in < 2 minutes
```

**Single-shot (llama3.2:3b) — Score: 1.0/10**

```python
def add(a, b): return a + b
```

**Sunwell + Resonance (same 3B model) — Score: 8.5/10**

```python
def add(a: int | float, b: int | float) -> int | float:
    """Returns the sum of two numbers.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The sum of a and b.

    Raises:
        TypeError: If inputs aren't numeric.
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both inputs must be integers or floats.")
    return a + b
```

The 3B model *knows* how to write production code. Single-shot prompting doesn't access it. **Structured cognition reveals what's already there.**

---

## Verified Results

| Technique | Small Model (3B) | Large Model (20B) | What It Does |
|-----------|------------------|-------------------|--------------|
| **Harmonic Planning** | +30% score | +150% score, +127% parallelism | Multiple personas plan in parallel, select best |
| **Resonance** | +650% quality (1→8.5/10) | +850% quality (1→9.5/10) | Feedback loops reveal hidden capability |
| **Lenses** | +17% quality, -58% tokens | +5% quality, -58% tokens | Domain-specific expertise injection |

See [THESIS-VERIFICATION.md](docs/THESIS-VERIFICATION.md) for full benchmark data and methodology.

---

## Quick Start

```bash
# Install
pip install sunwell

# First-time setup (pulls local models via Ollama)
sunwell setup

# See the difference in 2 minutes
sunwell demo

# Direct the agent
sunwell "Build a REST API with auth"

# Or let it propose work
sunwell backlog show
```

Requires Python 3.14+ and [Ollama](https://ollama.ai) for local models.

---

## The Prism Principle

```
                          ╱╲
                         ╱  ╲
                        ╱    ╲ 
    ━━━━━━━━━━━━━━━━━━╱      ╲━━━━━━ critic
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

| Component | What It Does | The Prism Metaphor |
|-----------|--------------|-------------------|
| **Lenses** | Domain expertise containers | Color filters selecting wavelengths |
| **Harmonic Synthesis** | Multiple personas generate in parallel | Multiple wavelengths simultaneously |
| **Resonance** | Feedback loops refine output | Iterative wavelength tuning |
| **Artifact-First Planning** | Discovers what must exist, derives order | Structural decomposition of light |
| **Convergence** | Recombines perspectives into final output | Where the Naaru emerges |

---

## What Sunwell Does

### 1. Executes Goals with Coordinated Intelligence

```bash
sunwell "Build a forum app with users and posts"
```

The Naaru coordinates:
- **Artifact-First Planning** — Discovers what must exist, derives execution order from dependencies
- **Harmonic Synthesis** — Multiple perspectives generate in parallel, then vote on the best
- **Resonance** — Rejected outputs get structured feedback and refinement
- **Parallel Execution** — Independent artifacts build simultaneously
- **Integration Verification** — Detects orphans, stubs, and missing connections

### 2. Remembers Everything

```bash
sunwell intel status
```

Unlike stateless assistants, Sunwell remembers:
- **Decisions**: "We chose OAuth over JWT last week"
- **Failures**: "That migration approach failed 3 times"
- **Patterns**: "User prefers snake_case and explicit type hints"
- **Codebase**: "billing.py is fragile, auth.py is stable"

### 3. Works Proactively

```bash
sunwell backlog show
```

```
📋 Found 12 goals:
  HIGH   [BUG]  Fix race condition in cache.py:89
  HIGH   [TEST] Add coverage for auth module (currently 45%)
  MEDIUM [TODO] Address TODO in api/routes.py:156
  LOW    [DEBT] Refactor duplicate code in models/
```

Sunwell scans your codebase and proposes work you haven't asked for yet.

### 4. Uses Lenses for Domain Expertise

Lenses are expertise containers with heuristics, personas, and validators:

```yaml
# lenses/tech-writer.lens
name: tech-writer
description: Technical documentation expert

heuristics:
  - name: BLUF
    rule: Put the conclusion first
    always: [lead with key takeaway]
    never: [bury the lede]

personas:
  - name: confused-junior
    background: New to programming
    attack_vectors:
      - "Is this explained simply enough?"
      - "Would I understand this term?"

validators:
  - name: readability
    script: "flesch-kincaid --target 8"
```

```bash
sunwell "Document the auth module" --lens tech-writer
```

### 5. Has Skills for Structured Actions

Skills define what the AI can do with explicit permissions:

```yaml
skills:
  - name: extract-api-surface
    description: Extract public API from source code
    preset: safe-shell
    instructions: |
      Parse source files, identify exports, extract signatures...
```

```bash
sunwell skills list
sunwell "Extract the API surface" --skill extract-api-surface
```

---

## Architecture

### The Naaru — Coordinated Intelligence

The Naaru emerges when refracted wavelengths recombine. It's not a component you can point to — it's the meta-cognition that arises from structured perspective integration.

```
              ┌─────────────────┐
              │      NAARU      │  ← What emerges from coordination
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
┌────────┐       ┌────────┐       ┌────────┐
│ VOICE  │       │ WISDOM │       │ SHARDS │  ← Parallel workers
│ (gen)  │       │ (judge)│       │ (help) │
└────────┘       └────────┘       └────────┘
```

| Component | Role | Implementation |
|-----------|------|----------------|
| **Voice** | Creates, synthesizes, generates | Fast model (gemma3:4b) |
| **Wisdom** | Judges, evaluates, validates | Reasoning model (gemma3:12b) |
| **Convergence** | Working memory (7±2 slots) | Shared context |
| **Harmonic** | Multiple personas in parallel | Voice × 3-5, then voting |
| **Resonance** | Feedback loop refinement | Voice + Wisdom iteration |
| **Discernment** | Fast checks before deep judgment | Tiered cascade |
| **Simulacrum** | Persona simulation, conversation DAG | 40+ components |

### Full Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SUNWELL STACK                                 │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    AUTONOMY LAYER                             │  │
│  │  Guardrails │ External Integration │ Multi-Instance Workers   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   INTELLIGENCE LAYER                          │  │
│  │  Project Intel │ Autonomous Backlog │ Deep Verification       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    INTEGRATION LAYER                          │  │
│  │  Wire Tasks │ Orphan Detection │ Stub Detection │ AST Analysis│  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    NAARU (Coordination)                       │  │
│  │  Harmonic │ Resonance │ Lenses │ Skills │ Simulacrum          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    MODEL LAYER                                │  │
│  │  Ollama │ OpenAI │ Anthropic │ Voice │ Wisdom │ Router        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `sunwell "goal"` | Execute a goal with the AI agent |
| `sunwell "goal" --plan` | Show the plan without executing |
| `sunwell "goal" --lens coder` | Execute with specific expertise lens |
| `sunwell demo` | See the Prism Principle in action (< 2 min) |
| `sunwell chat` | Interactive conversation mode |
| `sunwell setup` | First-time configuration |

### Intelligence

| Command | Description |
|---------|-------------|
| `sunwell intel status` | Show what Sunwell knows about your codebase |
| `sunwell intel decisions` | List remembered decisions |
| `sunwell intel patterns` | Show learned coding patterns |
| `sunwell bootstrap run` | Re-scan codebase for intelligence |

### Autonomous Backlog

| Command | Description |
|---------|-------------|
| `sunwell backlog show` | Show proposed goals |
| `sunwell backlog execute` | Run the autonomous loop |
| `sunwell backlog refresh` | Regenerate goals from codebase signals |
| `sunwell backlog add "goal"` | Add an explicit goal |
| `sunwell backlog skip <id>` | Skip a goal |

### Lenses & Skills

| Command | Description |
|---------|-------------|
| `sunwell lens list` | List available lenses |
| `sunwell lens show <name>` | Show lens details |
| `sunwell skills list` | List available skills |
| `sunwell skills run <name>` | Execute a specific skill |

### Verification & Safety

| Command | Description |
|---------|-------------|
| `sunwell verify <file>` | Deep verification beyond syntax |
| `sunwell weakness scan` | Find code weaknesses and integration gaps |
| `sunwell guardrails show` | Show current safety configuration |

---

## Configuration

```yaml
# .sunwell/config.yaml
naaru:
  name: "M'uru"                      # Name your Naaru
  voice: "gemma3:4b"                 # Fast generation (80% of tasks)
  wisdom: "gemma3:12b"               # Planning, validation (quality)
  harmonic_synthesis: true           # Multi-persona generation
  resonance: 2                       # Max refinement attempts
  discernment: true                  # Fast checks before full validation

model:
  default_provider: "ollama"
  default_model: "gemma3:4b"

guardrails:
  max_files_per_goal: 10
  forbidden_paths: ["secrets.py", ".env"]
  auto_approve: ["tests/*", "docs/*"]

integration:
  verify_on_complete: true           # Run integration checks after tasks
  detect_stubs: true                 # Find pass/TODO/NotImplementedError
  detect_orphans: true               # Find unused files
```

---

## Sunwell Studio (Optional)

A minimal desktop GUI built with Tauri + Svelte:

```bash
cd studio
npm install
npm run tauri dev
```

Features:
- One input, focused output (Ollama-inspired simplicity)
- Adaptive layouts for each mode (code, writing, planning, etc.)
- Live DAG visualization of planning and execution
- Integration status on DAG edges
- Project intelligence dashboard
- Lens picker and browser
- Weakness cascade panel

---

## Installation Options

```bash
# Core (local models via Ollama)
pip install sunwell

# With specific providers
pip install sunwell[ollama]     # Local models (recommended)
pip install sunwell[openai]     # OpenAI fallback
pip install sunwell[anthropic]  # Anthropic fallback
pip install sunwell[all]        # Everything
```

### Prerequisites

1. **Python 3.14+** (free-threading recommended for parallelism)
2. **Ollama** for local models: https://ollama.ai
3. Pull the recommended models:
   ```bash
   ollama pull gemma3:4b
   ollama pull gemma3:12b
   ```

---

## Development Setup

Sunwell is optimized for Python 3.14t (free-threaded) for true parallelism.

```bash
git clone https://github.com/lbliii/sunwell.git
cd sunwell

# Setup with free-threading (recommended)
./setup-free-threading.sh

# Or manually
uv venv --python python3.14t .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Verify free-threading
python -c "import sys; print('Free-threaded:', hasattr(sys, '_is_gil_enabled'))"

# Run tests
pytest

# Run linter
ruff check src/
```

---

## Project Structure

```
sunwell/
├── src/sunwell/
│   ├── naaru/          # Coordinated intelligence (61 files)
│   │   ├── planners/   # Artifact-first, harmonic, agent planning
│   │   ├── resonance/  # Feedback loop refinement
│   │   └── convergence/# Result synthesis
│   ├── simulacrum/     # Persona simulation (40 files)
│   ├── mirror/         # Self-improvement system (9 files)
│   ├── adaptive/       # Adaptive agent with learning
│   ├── backlog/        # Autonomous goal generation
│   ├── guardrails/     # Safety and policy enforcement
│   ├── intelligence/   # Codebase analysis and project memory
│   ├── verification/   # Deep verification beyond syntax
│   ├── skills/         # Skill system and execution
│   ├── lens/           # Lens loading and resolution
│   ├── team/           # Team coordination features
│   ├── tools/          # Tool executor and implementations
│   ├── models/         # LLM provider adapters
│   ├── core/           # Core types, heuristics, errors
│   └── cli/            # Command-line interface (46 files)
├── studio/             # Tauri + Svelte desktop GUI
├── lenses/             # Example expertise lenses
├── skills/             # Skill definition libraries
├── benchmark/          # Benchmark tasks and results
└── docs/               # RFCs and design documents (80+ docs)
```

---

## The Dream

```
Monday 9am:    "sunwell, let's build a SaaS app this week"

Monday 9pm:    Basic CRUD, auth, database — all working
               M'uru: "I found 3 edge cases in your auth flow.
                       Fixed them while you were at dinner."

Wednesday:     Billing integration, Stripe webhooks
               The Naaru: "I noticed we discussed OAuth last month.
                           Should I add Google/GitHub login?"

Friday:        Deploy to production
               M'uru: "CI passed. I'll monitor for errors overnight."

Saturday:      The Naaru fixes 2 bugs from production logs
               Proposes 3 improvements for Monday review
               ✓ All integrations verified — no orphans, no stubs

Monday:        You review, approve, ship. Start the next feature.

Cost: $0
Data shared: None
Sleep lost: None
```

*The Naaru's light reveals the best path forward.*

---

## Further Reading

- [TECHNICAL-VISION.md](TECHNICAL-VISION.md) — Deep dive into architecture and implementation
- [THESIS-VERIFICATION.md](docs/THESIS-VERIFICATION.md) — Verified benchmark results
- [VISION-universal-creative-platform.md](docs/VISION-universal-creative-platform.md) — The complete platform vision
- [docs/](docs/) — 80+ RFCs and design documents

---

## License

MIT
