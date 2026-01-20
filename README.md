# 🌟 Sunwell

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/sunwell/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**Local-first AI agent that learns your codebase and works while you sleep.**

*Powered by the Naaru — coordinated intelligence for small local models.*

```bash
sunwell "Build a REST API with auth"
```

---

## Why Sunwell?

| Feature | Claude/Cursor | Sunwell |
|---------|---------------|---------|
| **Memory** | Stateless (forgets you) | Persistent (remembers decisions, learns patterns) |
| **Mode** | Reactive (waits for commands) | Proactive (finds issues, proposes work) |
| **Cost** | Per-request ($$$) | Local models ($0 forever) |
| **Privacy** | Cloud-based | Nothing leaves your machine |
| **Autonomy** | Human-in-loop | Can work unsupervised (with guardrails) |

**The bet**: Memory + Privacy + Autonomy > Raw model quality for most development work.

---

## Quick Start

```bash
# Install
pip install sunwell

# First-time setup (pulls local models via Ollama)
sunwell setup

# Just tell it what you want
sunwell "Build a REST API with auth"

# Or let it propose work
sunwell backlog show
```

Requires Python 3.14+ and [Ollama](https://ollama.ai) for local models.

---

## What It Does

### 1. Executes Goals Intelligently

```bash
sunwell "Build a forum app with users and posts"
```

The agent:
- Discovers what artifacts need to exist (models, routes, tests)
- Plans execution order from dependencies
- Runs independent work in parallel
- Validates results at quality gates
- Learns from success/failure for next time

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

### 4. Works Autonomously (With Guardrails)

```bash
# View proposed work
sunwell backlog show

# Let it work while you sleep
sunwell backlog execute
```

Guardrails ensure safety:
- File scope limits (can't touch `secrets.py`)
- Time/cost budgets per goal
- Mandatory verification before commits
- Auto-approvable only for safe categories (tests, docs)
- Skip or block goals you don't want: `sunwell backlog skip <id>`

---

## Commands

| Command | Description |
|---------|-------------|
| `sunwell "goal"` | Execute a goal with the AI agent |
| `sunwell "goal" --plan` | Show the plan without executing |
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

### Verification & Safety

| Command | Description |
|---------|-------------|
| `sunwell verify <file>` | Deep verification beyond syntax |
| `sunwell guardrails show` | Show current safety configuration |
| `sunwell guardrails check` | Validate goals against guardrails |
| `sunwell guardrails history` | View session history |

### External Integration

| Command | Description |
|---------|-------------|
| `sunwell external start` | Start webhook server for CI/Git events |
| `sunwell external status` | Show integration status |

---

## Architecture

### The Naaru — Coordinated Intelligence

At the heart of Sunwell is **the Naaru** — a coordinated intelligence layer that maximizes quality from small local models.

> *In World of Warcraft lore, the Naaru are beings of pure Light that coordinate and guide. The Sunwell was restored by a Naaru named M'uru. The metaphor fits: local models are weak alone, but coordinated by the Naaru, they become powerful.*

```
              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
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

**Naaru Components**:

| Component | Role | Model |
|-----------|------|-------|
| **Voice** | Creates, synthesizes, generates code | `gemma3:4b` (fast) |
| **Wisdom** | Judges, evaluates, validates quality | `gemma3:12b` (reasoning) |
| **Convergence** | Shared working memory (7±2 slots) | — |
| **Shards** | Parallel CPU helpers while GPU generates | — |
| **Harmonic** | Multiple personas generating in parallel, then voting | Voice × 3 |
| **Resonance** | Feedback loop: rejected → refine → retry | Voice + Wisdom |
| **Discernment** | Fast insight before deep judgment | Tiered cascade |
| **Attunement** | Intent-aware routing to the right lens | Router model |

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
│  │  Project Intelligence │ Autonomous Backlog │ Deep Verification │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    NAARU (Planning + Execution)               │  │
│  │  Harmonic Synthesis │ Resonance │ Artifact-First Planning     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    MODEL LAYER                                │  │
│  │  Ollama │ Voice (gemma3:4b) │ Wisdom (gemma3:12b) │ Router    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Techniques

- **Artifact-First Planning**: Discovers what must exist, derives execution order from dependencies
- **Harmonic Synthesis**: Voice generates with multiple personas (pragmatist, quality engineer, security expert), then they vote on the best
- **Resonance**: When Wisdom rejects code, Voice refines it with feedback and retries (up to N attempts)
- **Discernment**: Fast structural checks first, escalate to full Wisdom only when uncertain
- **Project Intelligence**: Persistent memory that survives sessions — decisions, patterns, failures
- **Autonomous Backlog**: Self-directed goal generation from codebase analysis

---

## Configuration

Sunwell uses a tiered model system optimized for local development:

```yaml
# .sunwell/config.yaml
naaru:
  # Name your Naaru! (used when someone asks "what's your name?")
  name: "M'uru"
  title: "The Naaru"
  
  # Voice = fast generation, Wisdom = careful judgment
  voice: "gemma3:4b"           # 80% of tasks (fast)
  wisdom: "gemma3:12b"         # Planning, validation (quality)
  
  # Coordinated intelligence techniques
  harmonic_synthesis: true     # Multi-persona generation
  resonance: 2                 # Max refinement attempts
  discernment: true            # Fast checks before full validation

model:
  default_provider: "ollama"
  default_model: "gemma3:4b"

guardrails:
  max_files_per_goal: 10
  forbidden_paths: ["secrets.py", ".env"]
  auto_approve: ["tests/*", "docs/*"]
```

### Environment Variables

```bash
# For cloud model fallback (optional)
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...

# Ollama configuration
export OLLAMA_HOST=http://localhost:11434
```

---

## Sunwell Studio (Optional)

A minimal GUI built with Tauri + Svelte:

```bash
cd studio
npm install
npm run tauri dev
```

Features:
- One input, focused output (Ollama-inspired simplicity)
- Adaptive layouts for code, prose, and creative work
- Live DAG visualization of planning
- Project intelligence dashboard

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

Monday:        You review, approve, ship. Start the next feature.

Cost: $0
Data shared: None
Sleep lost: None
```

*The Naaru's light reveals the best path forward.*

---

## License

MIT
