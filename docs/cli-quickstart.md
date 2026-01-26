# Sunwell CLI Quickstart

Get started with Sunwell in under 5 minutes.

## Installation

```bash
# Using uv (recommended)
uv add sunwell

# Or with pip
pip install sunwell
```

## Initial Setup

Run the setup wizard to configure your first model provider:

```bash
sunwell setup
```

This will guide you through:
- Choosing a model provider (Ollama, Anthropic, or OpenAI)
- Setting up API keys if needed
- Testing your configuration

## Your First Goal

Sunwell's primary interface is goal-first. Just describe what you want:

```bash
# Simple goal
sunwell "Create a Python function that calculates fibonacci numbers"

# More complex goal
sunwell "Build a REST API with user authentication using FastAPI"

# Goal with constraints
sunwell "Refactor this code to be more readable" --trust workspace
```

## Using Skill Shortcuts

Shortcuts provide quick access to common skills:

```bash
# Deep audit a document
sunwell -s a-2 docs/api.md

# Polish/improve a document
sunwell -s p README.md

# Health check
sunwell -s health

# Show available shortcuts
sunwell -s ?
```

## Interactive Mode

For multi-turn conversations:

```bash
# Start chat
sunwell chat

# Or with a specific lens
sunwell chat --lens tech-writer
```

## Configuration

View and manage your configuration:

```bash
# Show current config
sunwell config show

# Set a value
sunwell config set model.default claude-sonnet

# Get a specific value
sunwell config get model.provider

# Initialize default config
sunwell config init
```

## Working with Lenses

Lenses define AI behavior and available skills:

```bash
# List available lenses
sunwell lens list

# Show lens details
sunwell lens show tech-writer

# Fork a lens for customization
sunwell lens fork tech-writer my-lens
```

## Project Context

Open a project to give Sunwell context:

```bash
# Current directory
sunwell .

# Specific path
sunwell ~/projects/my-app
```

## Common Options

These options work with most commands:

| Option | Description |
|--------|-------------|
| `--help` | Show help for any command |
| `--verbose, -v` | Show detailed output |
| `--quiet, -q` | Suppress warnings |
| `--json` | Output as JSON |
| `--plan` | Show plan without executing |
| `--time N` | Max execution time (seconds) |
| `--trust LEVEL` | Tool trust level (read_only, workspace, shell) |

## Examples

### Document Audit

```bash
# Quick audit
sunwell -s a docs/getting-started.md

# Deep audit with verbose output
sunwell -s a-2 docs/api-reference.md --verbose
```

### Code Generation

```bash
# Generate with plan preview
sunwell "Create a CLI for managing TODO items" --plan

# Generate with workspace trust
sunwell "Add unit tests for auth module" --trust workspace
```

### Content Creation

```bash
# Create documentation
sunwell "Write API documentation for the User service"

# With specific lens
sunwell "Create architecture diagram" --lens tech-writer
```

## Getting Help

```bash
# General help
sunwell --help

# Command-specific help
sunwell config --help
sunwell lens --help

# Show all commands (including hidden)
sunwell --all-commands

# Full CLI reference
# See docs/cli-reference.md
```

## Next Steps

- Read the [CLI Reference](cli-reference.md) for complete command documentation
- Set up [Shell Completion](cli-shell-completion.md) for tab completion
- Explore available lenses with `sunwell lens list`
- Try interactive mode with `sunwell chat`

---

*The light illuminates the path.*
