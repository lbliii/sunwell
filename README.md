# )✧( Sunwell

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/sunwell/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**An Agent Control Plane.**

Sunwell is an experiment in infrastructure for autonomous AI agents. The hypothesis: if you give humans proper visibility, control, and trust signals over AI agents, those agents can work autonomously on real projects.

```bash
sunwell "Build a REST API with auth"
```

> **Status**: Experimental. We're testing whether this approach works.

---

## The Problem

Current AI coding tools have two modes:

1. **Too much human involvement** — You direct every action, review every output. The AI is just autocomplete with extra steps.

2. **Too little visibility** — The AI runs autonomously but you can't see what it's doing, can't constrain it, and can't trust its outputs.

Sunwell tries to find a middle ground: agents that can work autonomously *because* you have the infrastructure to let them.

---

## The Approach

Sunwell provides five capabilities:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   🔭 OBSERVE     See what the agent is doing and thinking           │
│                                                                     │
│   🎮 CONTROL     Define what the agent is allowed to do             │
│                                                                     │
│   ✅ TRUST       Know when to believe agent outputs                 │
│                                                                     │
│   🧠 MEMORY      Persistent knowledge across sessions               │
│                                                                     │
│   📈 PROGRESS    Track goal completion and velocity                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

If these work well enough, autonomous local development becomes possible:
- Agent works while you're away
- $0 cost (local models)
- Nothing leaves your machine

---

## Quick Start

```bash
# Install
pip install sunwell

# Setup (pulls local models via Ollama)
sunwell setup

# Run a goal
sunwell "Build a REST API with auth"

# Interactive mode
sunwell chat
```

Requires Python 3.14+ and [Ollama](https://ollama.ai).

Install-time dependencies resolve from **PyPI** (no monorepo paths required). Contributors
working against local `chirp` / `kida` / `chirp-ui` checkouts should see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## The Five Capabilities

### 🔭 Observe

See what the agent is doing:

```bash
sunwell "goal" --verbose  # Detailed execution output
sunwell lineage show <file>  # Track what changed and why
```

Without this, you can't debug problems or understand failures.

### 🎮 Control

Define constraints:

```yaml
# .sunwell/config.yaml
guardrails:
  max_files_per_goal: 10
  forbidden_paths: ["secrets.py", ".env"]
  auto_approve: ["tests/*", "docs/*"]
  require_approval: ["src/core/*"]
```

Without this, autonomous operation is dangerous.

### ✅ Trust

Know when to believe outputs:

```bash
sunwell review              # Review failed runs and recover
sunwell "goal" --converge   # Iterate until lint/type gates pass
```

The agent validates its own work through convergence loops and gate checks before completing.

Without this, you have to manually verify everything anyway.

### 🧠 Memory

Persistent knowledge:

```bash
sunwell chat --session my-project   # Named sessions persist context
sunwell sessions list               # View past sessions
```

Sunwell remembers:
- Decisions: "We chose OAuth over JWT"
- Failures: "That approach failed before"
- Patterns: "User prefers explicit types"

Without this, the agent repeats mistakes and forgets context.

### 📈 Progress

Track what's getting done:

```bash
sunwell epic status         # View current epic progress
sunwell sessions summary    # What was accomplished
```

For autonomous operation, Sunwell finds work from codebase signals (TODOs, missing tests, etc) and tracks completion across sessions.

---

## How Quality Works

Small local models (3B-12B) produce mediocre output in single-shot prompting. Sunwell uses structured techniques to improve quality:

| Technique | Effect |
|-----------|--------|
| **Harmonic Synthesis** | Multiple perspectives generate in parallel, select best |
| **Resonance** | Feedback loops refine output iteratively |
| **Lenses** | Domain expertise injection |

Verified results on benchmarks:
- 3B model: 1.0/10 → 8.5/10 quality with resonance
- Token reduction: -58% with lenses

See [THESIS-VERIFICATION.md](docs/THESIS-VERIFICATION.md) for methodology.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  📈 PROGRESS    backlog/ │ execution/ │ incremental/                │
├─────────────────────────────────────────────────────────────────────┤
│  🧠 MEMORY      intelligence/ │ memory/ │ indexing/ │ project/      │
├─────────────────────────────────────────────────────────────────────┤
│  ✅ TRUST       verification/ │ confidence/ │ eval/                 │
├─────────────────────────────────────────────────────────────────────┤
│  🎮 CONTROL     guardrails/ │ security/ │ workflow/                 │
├─────────────────────────────────────────────────────────────────────┤
│  🔭 OBSERVE     reasoning/ │ navigation/ │ analysis/ │ lineage/     │
├─────────────────────────────────────────────────────────────────────┤
│  ⚡ ENGINE      naaru/ │ simulacrum/ │ lens/ │ convergence/         │
├─────────────────────────────────────────────────────────────────────┤
│  🔌 INFRA       models/ │ providers/ │ tools/ │ cli/ │ server/      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Commands

| Command | Description |
|---------|-------------|
| `sunwell "goal"` | Execute a goal |
| `sunwell "goal" --plan` | Show plan without executing |
| `sunwell chat` | Interactive conversation mode |
| `sunwell setup` | Initialize project for Sunwell |
| `sunwell config show` | View current configuration |
| `sunwell lens list` | List available lenses |
| `sunwell project info` | Show project details |
| `sunwell sessions list` | View past sessions |
| `sunwell review` | Recover from failed runs |

See `sunwell --help` for all available commands.

---

## Configuration

```yaml
# .sunwell/config.yaml
model:
  default_provider: "ollama"
  voice: "gemma3:4b"      # Fast, 80% of tasks
  wisdom: "gemma3:12b"    # Complex reasoning

guardrails:
  max_files_per_goal: 10
  forbidden_paths: ["secrets.py", ".env"]
  auto_approve: ["tests/*", "docs/*"]
```

---

## Installation

```bash
pip install sunwell

# Prerequisites
# 1. Python 3.14+
# 2. Ollama: https://ollama.ai
# 3. Models:
ollama pull gemma3:4b
ollama pull gemma3:12b
```

---

## Development

```bash
git clone https://github.com/lbliii/sunwell.git
cd sunwell
./setup-free-threading.sh  # Python 3.14t recommended
uv pip install -e ".[dev]"
pytest
```

---

## Project Structure

```
sunwell/
├── src/sunwell/
│   ├── reasoning/      # 🔭 Reasoning traces
│   ├── navigation/     # 🔭 ToC navigation
│   ├── analysis/       # 🔭 State analysis
│   ├── guardrails/     # 🎮 Constraints
│   ├── security/       # 🎮 Permissions
│   ├── verification/   # ✅ Verification
│   ├── confidence/     # ✅ Confidence scoring
│   ├── intelligence/   # 🧠 Project knowledge
│   ├── memory/         # 🧠 Memory tiers
│   ├── indexing/       # 🧠 Knowledge retrieval
│   ├── backlog/        # 📈 Goal tracking
│   ├── execution/      # 📈 Execution
│   ├── naaru/          # ⚡ Cognitive techniques
│   ├── simulacrum/     # ⚡ Persona simulation
│   ├── lens/           # ⚡ Domain expertise
│   ├── models/         # 🔌 LLM providers
│   ├── tools/          # 🔌 Tool implementations
│   └── cli/            # 🔌 Command interface
├── studio/             # Desktop GUI (Tauri + Svelte)
├── lenses/             # Expertise definitions
└── docs/               # Design documents
```

---

## Further Reading

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Technical details
- [THESIS-VERIFICATION.md](docs/THESIS-VERIFICATION.md) — Benchmark results
- [docs/](docs/) — RFCs and design documents

---

## License

MIT
