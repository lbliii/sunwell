# 🌟 Sunwell

[![PyPI version](https://img.shields.io/pypi/v/sunwell.svg)](https://pypi.org/project/sunwell/)
[![Build Status](https://github.com/lbliii/sunwell/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/sunwell/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/sunwell/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**AI agent for software tasks — just say what you want.**

```bash
sunwell "Build a REST API with auth"
```

---

## Why Sunwell?

- **Goal-first** — Describe what you want, not how to do it
- **Artifact planning** — Plans what must exist, parallelizes automatically
- **Local-first** — Optimized for small models (Gemma 3B, Llama 8B)
- **Free-threading** — Python 3.14t for true parallelism

---

## Installation

```bash
pip install sunwell

# With model providers
pip install sunwell[ollama]     # Local models (recommended)
pip install sunwell[openai]     # OpenAI
pip install sunwell[anthropic]  # Anthropic
pip install sunwell[all]        # All providers
```

Requires Python 3.14+

---

## Quick Start

| Command | Description |
|---------|-------------|
| `sunwell "goal"` | Execute goal with AI agent |
| `sunwell "goal" --plan` | Show plan without executing |
| `sunwell chat` | Interactive conversation mode |
| `sunwell setup` | First-time configuration |

---

## Usage

<details>
<summary><strong>Execute Goals</strong> — Tell it what you want</summary>

```bash
# Build something
sunwell "Build a REST API with auth and database"

# Write documentation
sunwell "Write docs for the auth module"

# Refactor code
sunwell "Refactor auth.py to use async"

# Fix bugs
sunwell "Fix the race condition in cache.py"
```

The agent discovers what artifacts need to exist, plans dependencies, and executes in parallel where possible.

</details>

<details>
<summary><strong>Plan First</strong> — Review before executing</summary>

```bash
sunwell "Build an e-commerce backend" --plan
```

Shows the artifact graph without executing:

```
Plan for: Build an e-commerce backend

┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ ID           ┃ Description          ┃ Requires    ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ db_schema    │ Database schema      │ -           │
│ user_model   │ User model           │ db_schema   │
│ product_mod  │ Product model        │ db_schema   │
│ auth_service │ Authentication       │ user_model  │
│ cart_service │ Shopping cart        │ product_mod │
└──────────────┴──────────────────────┴─────────────┘

Execution Waves (parallel):
  Wave 1: db_schema
  Wave 2: user_model, product_mod
  Wave 3: auth_service, cart_service
```

</details>

<details>
<summary><strong>Interactive Chat</strong> — Conversational mode</summary>

```bash
sunwell chat
```

For ongoing conversations with context persistence.

</details>

<details>
<summary><strong>Override Model</strong> — Use specific models</summary>

```bash
# Use a specific model
sunwell "Explain this codebase" --model gemma3:8b

# Use a larger model for complex tasks
sunwell "Design the architecture" --model llama3.1:70b
```

</details>

---

## Features

| Feature | Description |
|---------|-------------|
| **Artifact-First Planning** | Identifies what must exist, derives execution order from dependencies |
| **Parallel Execution** | Independent artifacts build simultaneously |
| **Model Distribution** | Assigns small/medium/large models to tasks by complexity |
| **Tool Use** | File operations, shell commands, code analysis |
| **Harmonic Synthesis** | Multiple perspectives for higher-quality outputs |

---

## How It Works

Traditional agents plan procedurally: "First do X, then Y, then Z." Sunwell plans declaratively: "These artifacts must exist."

```
PROCEDURAL:     Goal → [Step 1] → [Step 2] → [Step 3] → Done

ARTIFACT-FIRST: [Artifact A] [Artifact B] [Artifact C]
                      ↘          ↓         ↙
                           [Done]
```

This enables automatic parallelization — all independent artifacts execute simultaneously.

---

## Configuration

<details>
<summary><strong>sunwell.yaml</strong> — Project configuration</summary>

```yaml
# sunwell.yaml
naaru:
  voice: gemma3:1b          # Default model
  max_parallel: 4           # Concurrent tasks
  trust_level: workspace    # Tool permissions

# Model routing
models:
  small: gemma3:1b          # Simple tasks
  medium: gemma3:8b         # Standard tasks  
  large: llama3.1:70b       # Complex reasoning
```

</details>

<details>
<summary><strong>Environment Variables</strong></summary>

```bash
# API keys
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...

# Ollama configuration
export OLLAMA_HOST=http://localhost:11434
```

</details>

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
```

---

## Architecture

```
User Goal → Planner → Artifact Graph → Executor → Results
               │            │
               │      ┌─────┴─────┐
               │      ↓           ↓
            Naaru   [Parallel] [Parallel]
          (coordinator)   Artifacts
```

**Naaru** is the coordinated intelligence layer that:
- Plans using artifact-first discovery
- Routes tasks to appropriately-sized models
- Executes with tool use and validation
- Synthesizes results from multiple perspectives

---

## Requirements

- **Python 3.14+** (free-threading recommended)
- **Ollama** for local models (or OpenAI/Anthropic API keys)
- Linux, macOS, Windows

---

## License

MIT
