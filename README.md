# Sunwell

**RAG for Judgment** — Dynamic expertise retrieval for LLMs.

```
RAG:      Query → Retrieve FACTS → Inject → Generate
Sunwell:  Query → Retrieve HEURISTICS → Inject → Generate → Validate
```

## What is Sunwell?

Sunwell retrieves professional heuristics from an expertise graph, injecting only relevant components into LLM context. Instead of stuffing all rules into every request, Sunwell uses vector search to select what matters.

| System | Retrieves | Output |
|--------|-----------|--------|
| **RAG** | Facts, documents | Informed response |
| **Sunwell** | Heuristics, judgment | Professional-quality response |

## Installation

### Production Installation

```bash
pip install sunwell

# With model providers
pip install sunwell[openai]
pip install sunwell[anthropic]
pip install sunwell[all]
```

### Development Setup (Free-Threading Recommended)

Sunwell is optimized for Python 3.14t (free-threaded) for optimal parallelism. For development:

**Quick Setup:**
```bash
# Using the setup script (recommended)
./setup-free-threading.sh

# Or using Make
make setup-env
```

**Manual Setup:**
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv with Python 3.14t (free-threaded)
uv venv --python python3.14t .venv

# Activate and install
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Verify Free-Threading:**
```bash
python -c "import sys; print('Free-threaded:', hasattr(sys, '_is_gil_enabled'))"
# Should print: Free-threaded: True
```

**Note:** If Python 3.14t is not available, the setup will fall back to standard Python (GIL enabled). For optimal performance with Naaru's parallel workers, use Python 3.14t.

## Quick Start

```bash
# One-time setup (creates writer, reviewer, helper bindings)
sunwell setup

# Now just ask! No flags needed.
sunwell ask "Write API docs for auth.py"           # Uses default (writer)
sunwell ask reviewer "Review this code"            # Uses reviewer binding
sunwell ask helper "Quick question about Python"   # Uses helper (fast)

# Your learnings persist across calls!
sunwell ask "What did we discuss yesterday?"
```

**Custom bindings for specific projects:**
```bash
sunwell bind create my-project --lens tech-writer.lens --provider anthropic
sunwell ask my-project "Document the auth module"
```

**Interactive chat with model switching:**
```bash
sunwell chat tech-writer.lens --session auth-project
# /switch anthropic:claude-sonnet-4-20250514  ← switch models mid-chat!
```

## Creating a Lens

A lens is a YAML file defining professional expertise:

```yaml
lens:
  metadata:
    name: "Code Reviewer"
    domain: "software"
    version: "0.1.0"

  heuristics:
    - name: "Security First"
      rule: "Every code change must consider security implications"
      always:
        - "Check for injection vulnerabilities"
        - "Validate all inputs"
      never:
        - "Trust user input"
        - "Hardcode secrets"

    - name: "Readability"
      rule: "Code is read more than written"
      always:
        - "Descriptive names"
        - "Small functions"
```

## Key Concepts

### Lenses
A **lens** is an expertise graph containing:
- **Heuristics**: How to think about problems
- **Framework**: Domain methodology (e.g., Diataxis for docs)
- **Personas**: Stakeholder simulation for testing
- **Validators**: Quality gates
- **Skills**: Action capabilities (see RFC-011)

### Bindings (Your Soul Stone)
A **binding** attunes you to a lens with your preferences:
```bash
sunwell bind create my-project --lens code-reviewer.lens --provider anthropic
```
Now `sunwell ask my-project "..."` remembers your lens, model, and headspace.

### Headspace (Accumulated Wisdom)
A **headspace** persists learnings across conversations:
- **Learnings**: Facts, constraints, patterns discovered
- **Dead Ends**: Approaches that didn't work (won't repeat)
- **Focus**: Auto-detects what you're working on

Headspaces survive model switches! Start with GPT-4o, switch to Claude mid-conversation, your context travels with you.

### Selective Retrieval
Unlike flat rule injection, Sunwell embeds lens components and retrieves only relevant ones via vector search. This means:
- Lower token usage per request
- Higher signal-to-noise ratio
- Scales to larger expertise sets

### Composition
Lenses support inheritance and composition:

```yaml
lens:
  extends: "sunwell/tech-writer@1.0"
  
  heuristics:
    - name: "Company Standard"
      rule: "Use ACME logging format"
```

## Architecture

```
User Prompt → Classifier → Retriever → Injector → LLM → Validator
                  │            │
                  │      Vector Index
                  │      (expertise embeddings)
                  │
              Tier Routing
              (Fast/Standard/Deep)
```

## License

MIT
