# Sunwell CLI Reference

Complete reference for all Sunwell CLI commands.

## Quick Reference

```bash
# Run a goal
sunwell "Build a REST API with auth"

# Use a skill shortcut
sunwell -s a-2 docs/api.md

# Interactive mode
sunwell chat

# Show all commands
sunwell --help
```

## Main Command

### `sunwell`

✦ Sunwell — AI agent for software tasks.


USAGE:
    sunwell [GOAL]           Run a goal
    sunwell -s [SHORTCUT]    Quick skills
    sunwell [COMMAND]        Subcommands


EXAMPLES:
    sunwell "Build a REST API with auth"
    sunwell -s a-2 docs/api.md
    sunwell -s p docs/cli.md
    sunwell config model


SHORTCUTS (use with -s):
    a, a-2      Audit (quick, deep)
    p           Polish
    health      Health check
    drift       Drift detection
    pipeline    Full docs pipeline


For interactive mode:

    sunwell chat


The light illuminates the path. ✧

**Options:**

- `-s/--skill` `text`: Run skill shortcut (a-2, p, health, etc.) (default: Sentinel.UNSET)
- `-t/--target` `text`: Target file/directory for skill (default: Sentinel.UNSET)
- `-l/--lens` `text`: Lens to use (default: tech-writer)
- `--plan` `boolean`: Show plan without executing (default: false)
- `--open` `boolean`: Open plan in Studio (with --plan) (default: false)
- `--json` `boolean`: Output as JSON (default: false)
- `--provider/-p` `choice`: Model provider (default: from config)
- `--model/-m` `text`: Override model selection (default: Sentinel.UNSET)
- `--verbose/-v` `boolean`: Show detailed output (default: false)
- `--time` `integer`: Max execution time (seconds) (default: 300)
- `--trust` `choice`: Override tool trust level
- `--workspace/-w` `path`: Project directory (default: auto-detect) (default: Sentinel.UNSET)
- `--quiet/-q` `boolean`: Suppress warnings (default: false)
- `--converge/--no-converge` `boolean`: Enable convergence loops (iterate until lint/types pass) (default: false)
- `--converge-gates` `text`: Gates for convergence (comma-separated: lint,type,test) (default: lint,type)
- `--converge-max` `integer`: Maximum convergence iterations (default: 5)
- `--all-commands` `boolean`: Show all commands including hidden (default: false)
- `--version` `boolean`: Show the version and exit. (default: false)

**Subcommands:**

- `autonomous`: Run fully autonomous multi-agent workflows (RFC-130).
- `chat`: Start an interactive headspace chat session.

Uses your default binding if no argument given. Can also specify
a binding name or lens path directly.

Your headspace (learnings, dead ends, context) persists across:
- Model switches: /switch anthropic:claude-sonnet-4-20250514
- Session restarts: sunwell chat --session my-project

Key commands:
- /switch <provider:model>: Switch models mid-conversation
- /branch <name>: Create a branch to try something
- /dead-end: Mark current path as dead end
- /learn <fact>: Add a persistent learning
- /quit: Exit (auto-saves)

Examples:

sunwell chat # Uses default binding

sunwell chat writer # Uses 'writer' binding

sunwell chat lenses/tech-writer.lens # Direct lens path

sunwell chat --session auth-debug # Named session

# Mid-conversation: /switch anthropic:claude-sonnet-4-20250514
- `config`: Manage Sunwell configuration.

Configuration is loaded from (in priority order):
1. Environment variables (SUNWELL_*)
2. .sunwell/config.yaml (project-local)
3. ~/.sunwell/config.yaml (user-global)
4. Built-in defaults

Examples:

    sunwell config show              # Show current config
    sunwell config init              # Create default config file
    sunwell config get model.default_provider
    sunwell config set model.default_model gemma3:12b

Environment overrides:

    SUNWELL_MODEL_DEFAULT_PROVIDER=anthropic sunwell ...
    SUNWELL_EMBEDDING_OLLAMA_MODEL=nomic-embed-text sunwell ...
- `debug`: Debugging and diagnostics tools.

Commands for collecting diagnostics, analyzing issues,
and generating shareable bug reports.
- `epic`: Hierarchical Goal Decomposition — Epic progress management.

Epics are ambitious goals that get decomposed into milestones.
Each milestone is then planned with HarmonicPlanner when reached.

Examples:

    sunwell epic status                # View current epic progress
    sunwell epic status <epic_id>      # View specific epic
    sunwell epic milestones            # List milestones for active epic
    sunwell epic skip-milestone        # Skip current milestone
    sunwell epic replan                # Re-plan current milestone
- `guard`: Manage guardrails and adaptive learning (RFC-130).
- `lens`: Lens management commands (RFC-064).
- `lineage`: Artifact lineage and provenance tracking.

Track the complete lineage of every artifact: which goal spawned it,
which model wrote it, what edits were made, and how it relates to other files.


Examples:
    sunwell lineage show src/auth.py
    sunwell lineage goal abc123
    sunwell lineage deps src/api.py
    sunwell lineage impact src/base.py
    sunwell lineage sync
- `project`: Project analysis and workspace management (RFC-079, RFC-117).
- `review`: Review and recover from failed agent runs.

When Sunwell can't automatically fix errors, it saves progress for review.
Use this command to see what succeeded, what failed, and choose how to proceed.


EXAMPLES:
    sunwell review                    # Interactive review of pending recoveries
    sunwell review --list             # List all pending recoveries
    sunwell review abc123             # Review specific recovery
    sunwell review abc123 --auto-fix  # Retry with agent
    sunwell review abc123 --skip      # Write only passed files
    sunwell review abc123 --hint "User model is in models/user.py"


RECOVERY OPTIONS:
    --auto-fix    Let agent retry with full context of what failed
    --skip        Write the files that passed, abandon the rest
    --abort       Delete recovery state entirely
    --hint        Provide a hint to help agent fix the issue
- `serve`: Start the Sunwell Studio HTTP server.

In production mode (default), serves the Svelte UI from the same origin.
In development mode (--dev), enables CORS for Vite dev server on :5173.


Examples:
    sunwell serve              # Start on localhost:8080
    sunwell serve --open       # Start and open browser
    sunwell serve --dev        # API only, for Vite dev server
    sunwell serve --port 3000  # Custom port
- `sessions`: Manage conversation sessions and view activity summaries.

Sessions persist across restarts, enabling multi-day conversations
that never lose context. Activity summaries show what was accomplished.
- `setup`: Initialize Sunwell for this project.

One command that handles everything:
- Creates .sunwell/ directory with project manifest
- Builds workspace context cache for fast startup
- Registers project globally for easy access
- Optionally sets up lens bindings

Safe to run multiple times - only updates what's needed.


Examples:
    sunwell setup                    # Setup current directory
    sunwell setup ~/projects/myapp   # Setup specific path
    sunwell setup --provider openai  # Use OpenAI
    sunwell setup --minimal          # Just project, no bindings
- `skills`: Manage the local skill library.

Skills can be learned from successful sessions, composed from existing
skills, or imported from external sources.

## Commands

### Primary Commands

These are the main commands for everyday use.

#### `sunwell config`

Manage Sunwell configuration.

Configuration is loaded from (in priority order):
1. Environment variables (SUNWELL_*)
2. .sunwell/config.yaml (project-local)
3. ~/.sunwell/config.yaml (user-global)
4. Built-in defaults

Examples:

    sunwell config show              # Show current config
    sunwell config init              # Create default config file
    sunwell config get model.default_provider
    sunwell config set model.default_model gemma3:12b

Environment overrides:

    SUNWELL_MODEL_DEFAULT_PROVIDER=anthropic sunwell ...
    SUNWELL_EMBEDDING_OLLAMA_MODEL=nomic-embed-text sunwell ...

**Subcommands:**

- `edit`: Display config file for editing.

Shows the raw YAML content of the config file with syntax highlighting.
Use your preferred editor to make changes.

Examples:
    sunwell config edit
    sunwell config edit --global
- `get`: Get a configuration value.

Use dot notation to access nested values.

Examples:
    sunwell config get model.default_provider
    sunwell config get embedding.ollama_model
    sunwell config get naaru.wisdom
    sunwell config get headspace.spawn.enabled
- `init`: Create default config file.

Creates a well-documented configuration file with all available
options and their default values.

Examples:
    sunwell config init                    # Create .sunwell/config.yaml
    sunwell config init --global           # Create ~/.sunwell/config.yaml
    sunwell config init --path custom.yaml
- `set`: Set a configuration value.

Creates or updates the config file with the specified value.
Use dot notation for nested keys.

Type conversion:
- "true"/"false" → boolean
- numeric strings → int/float
- everything else → string

Examples:
    sunwell config set model.default_provider anthropic
    sunwell config set model.default_model claude-sonnet-4-20250514
    sunwell config set embedding.prefer_local false
    sunwell config set naaru.harmonic_candidates 7
- `show`: Show current configuration.

Displays all configuration values with their current settings,
including which files are active.

Examples:
    sunwell config show
    sunwell config show --path ~/.sunwell/config.yaml
- `unset`: Remove a configuration override.

Removes the specified key from the config file, reverting to
the default value.

Examples:
    sunwell config unset model.default_provider
    sunwell config unset embedding.prefer_local --global

##### `sunwell config edit`

Display config file for editing.

Shows the raw YAML content of the config file with syntax highlighting.
Use your preferred editor to make changes.

Examples:
    sunwell config edit
    sunwell config edit --global

**Options:**

- `--path` `path`: Config file to display (default: .sunwell/config.yaml)
- `--global` `boolean`: Show ~/.sunwell/config.yaml (default: false)

##### `sunwell config get`

Get a configuration value.

Use dot notation to access nested values.

Examples:
    sunwell config get model.default_provider
    sunwell config get embedding.ollama_model
    sunwell config get naaru.wisdom
    sunwell config get headspace.spawn.enabled

**Arguments:**

- `KEY`

**Options:**

- `--path` `path`: Config file path (default: Sentinel.UNSET)

##### `sunwell config init`

Create default config file.

Creates a well-documented configuration file with all available
options and their default values.

Examples:
    sunwell config init                    # Create .sunwell/config.yaml
    sunwell config init --global           # Create ~/.sunwell/config.yaml
    sunwell config init --path custom.yaml

**Options:**

- `--path` `path`: Config file path (default: .sunwell/config.yaml) (default: .sunwell/config.yaml)
- `--global` `boolean`: Create in ~/.sunwell/ instead (default: false)

##### `sunwell config set`

Set a configuration value.

Creates or updates the config file with the specified value.
Use dot notation for nested keys.

Type conversion:
- "true"/"false" → boolean
- numeric strings → int/float
- everything else → string

Examples:
    sunwell config set model.default_provider anthropic
    sunwell config set model.default_model claude-sonnet-4-20250514
    sunwell config set embedding.prefer_local false
    sunwell config set naaru.harmonic_candidates 7

**Arguments:**

- `KEY`
- `VALUE`

**Options:**

- `--path` `path`: Config file to modify (default: .sunwell/config.yaml) (default: .sunwell/config.yaml)
- `--global` `boolean`: Modify ~/.sunwell/config.yaml (default: false)

##### `sunwell config show`

Show current configuration.

Displays all configuration values with their current settings,
including which files are active.

Examples:
    sunwell config show
    sunwell config show --path ~/.sunwell/config.yaml

**Options:**

- `--path` `path`: Config file path to show (default: Sentinel.UNSET)

##### `sunwell config unset`

Remove a configuration override.

Removes the specified key from the config file, reverting to
the default value.

Examples:
    sunwell config unset model.default_provider
    sunwell config unset embedding.prefer_local --global

**Arguments:**

- `KEY`

**Options:**

- `--path` `path`: Config file to modify (default: .sunwell/config.yaml) (default: .sunwell/config.yaml)
- `--global` `boolean`: Modify ~/.sunwell/config.yaml (default: false)

#### `sunwell project`

Project analysis and workspace management (RFC-079, RFC-117).

**Subcommands:**

- `analyze`: Analyze a project to understand its intent and state.

Detects project type, infers goals, suggests next actions,
and recommends appropriate workspace.

Examples:
    sunwell project analyze
    sunwell project analyze ~/projects/myapp --json
    sunwell project analyze . --fresh
- `cache`: Manage project analysis cache.

View or clear cached analysis for a project.
- `cleanup`: Find and clean up orphaned project data (RFC-141).

Finds:
- Runs that reference non-existent projects
- Registry entries with missing project paths


Examples:
    sunwell project cleanup              # Dry run
    sunwell project cleanup --confirm    # Actually clean up
    sunwell project cleanup --no-dry-run # Same as --confirm
- `current`: Show current project/workspace (RFC-140).

Shows the current workspace context, falling back to default project.

Examples:
    sunwell project current
    sunwell project current --json
- `default`: Get or set the default project (RFC-117).

Without argument, shows current default.
With argument, sets the default project.

Examples:
    sunwell project default          # Show default
    sunwell project default my-app   # Set default
- `delete`: Fully delete a project (RFC-141).

WARNING: This is destructive and cannot be undone.

Removes the project from the registry and DELETES the entire
project directory including all source code.


Examples:
    sunwell project delete my-app --confirm-full-delete
- `info`: Show detailed project information (RFC-117).

Without argument, shows info for cwd project or default.
With argument, shows info for specified project.

Examples:
    sunwell project info            # Current project
    sunwell project info my-app     # Specific project
- `init`: Initialize a new project workspace (RFC-117).

Creates .sunwell/project.toml and registers in global registry.

Examples:
    sunwell project init
    sunwell project init ~/projects/my-app
    sunwell project init . --id my-app --name "My Application"
- `list`: List registered projects (RFC-117).

Shows all projects in the global registry with their paths
and last used timestamps.
- `monorepo`: Detect sub-projects in a monorepo.

Shows all detected sub-projects with their types.
- `move`: Update project path after manual move (RFC-141).

Call this AFTER manually moving a project directory to update
the registry and current project state.


Examples:
    # First: mv ~/old-location/my-app ~/new-location/my-app
    sunwell project move my-app ~/new-location/my-app
- `purge`: Purge Sunwell data from a project (RFC-141).

Removes the project from the registry and deletes the .sunwell/
directory, but keeps source code and other files intact.


Examples:
    sunwell project purge my-app --confirm
    sunwell project purge my-app --confirm --delete-runs
- `remove`: Remove a project from the registry (RFC-117).

This only removes from the registry, not the actual files.

Examples:
    sunwell project remove my-app
    sunwell project remove my-app --force
- `rename`: Rename a project (RFC-141).

Changes the project ID and optionally the display name.
Updates all references including runs.


Examples:
    sunwell project rename old-name new-name
    sunwell project rename my-app my-awesome-app --name "My Awesome App"
- `signals`: Show raw project signals (for debugging).

Displays all detected signals from the filesystem
without classification or inference.
- `switch`: Switch project context (RFC-140).

Alias for `sunwell workspace switch`. Sets the project as current workspace.

Examples:
    sunwell project switch my-app
    sunwell project switch /path/to/project

##### `sunwell project analyze`

Analyze a project to understand its intent and state.

Detects project type, infers goals, suggests next actions,
and recommends appropriate workspace.

Examples:
    sunwell project analyze
    sunwell project analyze ~/projects/myapp --json
    sunwell project analyze . --fresh

**Arguments:**

- `PATH` (optional)

**Options:**

- `--json` `boolean`: Output as JSON (default: false)
- `--fresh` `boolean`: Force fresh analysis (skip cache) (default: false)
- `--provider/-p` `choice`: Model provider (default: from config)
- `--model/-m` `text`: Model to use for LLM classification

##### `sunwell project cache`

Manage project analysis cache.

View or clear cached analysis for a project.

**Arguments:**

- `PATH` (optional)

**Options:**

- `--clear` `boolean`: Clear the cache (default: false)

##### `sunwell project cleanup`

Find and clean up orphaned project data (RFC-141).

Finds:
- Runs that reference non-existent projects
- Registry entries with missing project paths


Examples:
    sunwell project cleanup              # Dry run
    sunwell project cleanup --confirm    # Actually clean up
    sunwell project cleanup --no-dry-run # Same as --confirm

**Options:**

- `--dry-run/--no-dry-run` `boolean`: Only report what would be cleaned (default: dry-run) (default: true)
- `--confirm` `boolean`: Actually perform cleanup (same as --no-dry-run) (default: false)

##### `sunwell project current`

Show current project/workspace (RFC-140).

Shows the current workspace context, falling back to default project.

Examples:
    sunwell project current
    sunwell project current --json

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell project default`

Get or set the default project (RFC-117).

Without argument, shows current default.
With argument, sets the default project.

Examples:
    sunwell project default          # Show default
    sunwell project default my-app   # Set default

**Arguments:**

- `PROJECT_ID` (optional)

##### `sunwell project delete`

Fully delete a project (RFC-141).

WARNING: This is destructive and cannot be undone.

Removes the project from the registry and DELETES the entire
project directory including all source code.


Examples:
    sunwell project delete my-app --confirm-full-delete

**Arguments:**

- `PROJECT_ID`

**Options:**

- `--confirm-full-delete` `boolean`: Confirm full deletion (required) (default: false)
- `--delete-runs` `boolean`: Also delete associated runs (default: false)
- `--force` `boolean`: Force delete even if runs are active (default: false)

##### `sunwell project info`

Show detailed project information (RFC-117).

Without argument, shows info for cwd project or default.
With argument, shows info for specified project.

Examples:
    sunwell project info            # Current project
    sunwell project info my-app     # Specific project

**Arguments:**

- `PROJECT_ID` (optional)

##### `sunwell project init`

Initialize a new project workspace (RFC-117).

Creates .sunwell/project.toml and registers in global registry.

Examples:
    sunwell project init
    sunwell project init ~/projects/my-app
    sunwell project init . --id my-app --name "My Application"

**Arguments:**

- `PATH` (optional)

**Options:**

- `--id` `text`: Project identifier (default: directory name) (default: Sentinel.UNSET)
- `--name` `text`: Human-readable name (default: same as id) (default: Sentinel.UNSET)
- `--trust` `choice`: Default trust level for agent (default: workspace)
- `--no-register` `boolean`: Don't add to global registry (default: false)

##### `sunwell project list`

List registered projects (RFC-117).

Shows all projects in the global registry with their paths
and last used timestamps.

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell project monorepo`

Detect sub-projects in a monorepo.

Shows all detected sub-projects with their types.

**Arguments:**

- `PATH` (optional)

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell project move`

Update project path after manual move (RFC-141).

Call this AFTER manually moving a project directory to update
the registry and current project state.


Examples:
    # First: mv ~/old-location/my-app ~/new-location/my-app
    sunwell project move my-app ~/new-location/my-app

**Arguments:**

- `PROJECT_ID`
- `NEW_PATH`

##### `sunwell project purge`

Purge Sunwell data from a project (RFC-141).

Removes the project from the registry and deletes the .sunwell/
directory, but keeps source code and other files intact.


Examples:
    sunwell project purge my-app --confirm
    sunwell project purge my-app --confirm --delete-runs

**Arguments:**

- `PROJECT_ID`

**Options:**

- `--confirm` `boolean`: Confirm purge operation (default: false)
- `--delete-runs` `boolean`: Also delete associated runs (default: false)
- `--force` `boolean`: Force purge even if runs are active (default: false)

##### `sunwell project remove`

Remove a project from the registry (RFC-117).

This only removes from the registry, not the actual files.

Examples:
    sunwell project remove my-app
    sunwell project remove my-app --force

**Arguments:**

- `PROJECT_ID`

**Options:**

- `--force/-f` `boolean`: Remove without confirmation (default: false)

##### `sunwell project rename`

Rename a project (RFC-141).

Changes the project ID and optionally the display name.
Updates all references including runs.


Examples:
    sunwell project rename old-name new-name
    sunwell project rename my-app my-awesome-app --name "My Awesome App"

**Arguments:**

- `PROJECT_ID`
- `NEW_ID`

**Options:**

- `--name` `text`: New display name (defaults to new_id) (default: Sentinel.UNSET)

##### `sunwell project signals`

Show raw project signals (for debugging).

Displays all detected signals from the filesystem
without classification or inference.

**Arguments:**

- `PATH` (optional)

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell project switch`

Switch project context (RFC-140).

Alias for `sunwell workspace switch`. Sets the project as current workspace.

Examples:
    sunwell project switch my-app
    sunwell project switch /path/to/project

**Arguments:**

- `PROJECT_ID`

#### `sunwell sessions`

Manage conversation sessions and view activity summaries.

Sessions persist across restarts, enabling multi-day conversations
that never lose context. Activity summaries show what was accomplished.

**Subcommands:**

- `archive`: Archive old turns to cold storage (compressed).

Examples:

    sunwell sessions archive

    sunwell sessions archive --older-than 24  # Archive anything older than 1 day
- `history`: List recent session summaries.


Examples:
    sunwell sessions history
    sunwell sessions history --limit 20
- `list`: List all saved conversation sessions.

Examples:

    sunwell sessions list

    sunwell sessions list --path ~/my-sessions/
- `stats`: Show storage statistics.

Examples:

    sunwell sessions stats
- `summary`: Show session activity summary.

Displays what was accomplished during a coding session:
- Goals completed/failed
- Files created/modified
- Lines added/removed
- Top edited files
- Timeline of activity


Examples:
    sunwell sessions summary           # Current/recent session
    sunwell sessions summary --format json
    sunwell sessions summary -s abc123  # Specific session

##### `sunwell sessions archive`

Archive old turns to cold storage (compressed).

Examples:

    sunwell sessions archive

    sunwell sessions archive --older-than 24  # Archive anything older than 1 day

**Options:**

- `--path/-p` `path`: Memory store path (default: .sunwell/memory)
- `--older-than/-o` `integer`: Archive turns older than N hours (default: 168 = 1 week) (default: 168)

##### `sunwell sessions history`

List recent session summaries.


Examples:
    sunwell sessions history
    sunwell sessions history --limit 20

**Options:**

- `--limit/-l` `integer`: Maximum sessions to show (default: 10)

##### `sunwell sessions list`

List all saved conversation sessions.

Examples:

    sunwell sessions list

    sunwell sessions list --path ~/my-sessions/

**Options:**

- `--path/-p` `path`: Memory store path (default: .sunwell/memory)

##### `sunwell sessions stats`

Show storage statistics.

Examples:

    sunwell sessions stats

**Options:**

- `--path/-p` `path`: Memory store path (default: .sunwell/memory)

##### `sunwell sessions summary`

Show session activity summary.

Displays what was accomplished during a coding session:
- Goals completed/failed
- Files created/modified
- Lines added/removed
- Top edited files
- Timeline of activity


Examples:
    sunwell sessions summary           # Current/recent session
    sunwell sessions summary --format json
    sunwell sessions summary -s abc123  # Specific session

**Options:**

- `--session-id/-s` `text`: Specific session ID to summarize
- `--format` `choice`:  (default: human)

#### `sunwell lens`

Lens management commands (RFC-064).

**Subcommands:**

- `delete`: Delete a user lens.

Only user lenses (in ~/.sunwell/lenses/) can be deleted.
Built-in lenses cannot be deleted.

Examples:

    sunwell lens delete my-old-lens

    sunwell lens delete my-old-lens --yes
- `export`: Export a lens to a standalone file (RFC-100).

Exports a lens with all its content to a file that can be
shared, backed up, or imported into another Sunwell installation.

Examples:

    sunwell lens export coder

    sunwell lens export tech-writer -o my-backup.lens

    sunwell lens export coder --format json
- `fork`: Fork a lens to create an editable copy.

Creates a new lens in ~/.sunwell/lenses/ based on an existing lens.
The forked lens gets its own version history.

Examples:

    sunwell lens fork coder my-team-coder

    sunwell lens fork tech-writer my-docs -m "Forked for team standards"
- `library`: Browse the lens library with full metadata.

Lists all available lenses with library metadata including
heuristics count, skills count, use cases, and tags.

Examples:

    sunwell lens library

    sunwell lens library --filter user

    sunwell lens library --filter documentation --json
- `list`: List all available lenses.

By default, searches current directory and ~/.sunwell/lenses/

Examples:

    sunwell lens list

    sunwell lens list --path ./my-lenses/

    sunwell lens list --json
- `record-usage`: Record lens activation for usage tracking (RFC-100).

Internal command used by Studio to track lens usage.
- `resolve`: Resolve which lens would be used for a goal.

Useful for debugging lens selection without running the agent.

Examples:

    sunwell lens resolve "Build a REST API"

    sunwell lens resolve "Write documentation" --json
- `rollback`: Rollback a lens to a previous version.

Restores the content from a previous version and creates
a new version entry with a rollback message.

Examples:

    sunwell lens rollback my-team-coder 1.0.0
- `save`: Save changes to a user lens with version tracking.

Reads content from the specified file and saves it to the lens,
bumping the version number and creating a version snapshot.

Examples:

    sunwell lens save my-coder --file edited.lens -m "Added heuristic"

    sunwell lens save my-coder --file edited.lens --bump minor
- `set-default`: Set or clear the global default lens.

When no name is provided, shows the current default.
Use --clear to remove the default and return to auto-select.

Examples:

    sunwell lens set-default my-team-coder

    sunwell lens set-default

    sunwell lens set-default --clear
- `show`: Show details of a specific lens.

Examples:

    sunwell lens show coder

    sunwell lens show tech-writer --json
- `skill-graph`: Show the skill dependency graph for a lens (RFC-087).

Displays skills and their dependencies as a DAG, with execution
waves showing which skills can run in parallel.

Examples:

    sunwell lens skill-graph tech-writer

    sunwell lens skill-graph tech-writer --json

    sunwell lens skill-graph coder --mermaid
- `skill-plan`: Show execution plan with cache predictions (RFC-087).

Predicts which skills will execute vs skip based on cache state.

Examples:

    sunwell lens skill-plan tech-writer --json

    sunwell lens skill-plan coder --context-hash abc123
- `skills`: List skills for a lens with DAG information (RFC-087).

Shows skills with their dependencies, produces, and requires.
Used by Studio UI for skill panel.

Examples:

    sunwell lens skills tech-writer

    sunwell lens skills tech-writer --json
- `versions`: Show version history for a lens.

Displays the version history including timestamps and messages.

Examples:

    sunwell lens versions my-team-coder

    sunwell lens versions my-team-coder --json

##### `sunwell lens delete`

Delete a user lens.

Only user lenses (in ~/.sunwell/lenses/) can be deleted.
Built-in lenses cannot be deleted.

Examples:

    sunwell lens delete my-old-lens

    sunwell lens delete my-old-lens --yes

**Arguments:**

- `NAME`

**Options:**

- `--yes` `boolean`: Skip confirmation (default: false)
- `--keep-versions` `boolean`: Keep version history (default: true)

##### `sunwell lens export`

Export a lens to a standalone file (RFC-100).

Exports a lens with all its content to a file that can be
shared, backed up, or imported into another Sunwell installation.

Examples:

    sunwell lens export coder

    sunwell lens export tech-writer -o my-backup.lens

    sunwell lens export coder --format json

**Arguments:**

- `NAME`

**Options:**

- `--output/-o` `path`: Output file path (defaults to <name>.lens) (default: Sentinel.UNSET)
- `--format` `choice`:  (default: yaml)

##### `sunwell lens fork`

Fork a lens to create an editable copy.

Creates a new lens in ~/.sunwell/lenses/ based on an existing lens.
The forked lens gets its own version history.

Examples:

    sunwell lens fork coder my-team-coder

    sunwell lens fork tech-writer my-docs -m "Forked for team standards"

**Arguments:**

- `SOURCE_NAME`
- `NEW_NAME`

**Options:**

- `--message/-m` `text`: Version message (default: Sentinel.UNSET)

##### `sunwell lens library`

Browse the lens library with full metadata.

Lists all available lenses with library metadata including
heuristics count, skills count, use cases, and tags.

Examples:

    sunwell lens library

    sunwell lens library --filter user

    sunwell lens library --filter documentation --json

**Options:**

- `--json` `boolean`: Output as JSON (default: false)
- `--filter` `text`: Filter by: builtin, user, or domain name (default: Sentinel.UNSET)

##### `sunwell lens list`

List all available lenses.

By default, searches current directory and ~/.sunwell/lenses/

Examples:

    sunwell lens list

    sunwell lens list --path ./my-lenses/

    sunwell lens list --json

**Options:**

- `--path/-p` `path`: Path to search for lenses (default: Sentinel.UNSET)
- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell lens record-usage`

Record lens activation for usage tracking (RFC-100).

Internal command used by Studio to track lens usage.

**Arguments:**

- `NAME`

##### `sunwell lens resolve`

Resolve which lens would be used for a goal.

Useful for debugging lens selection without running the agent.

Examples:

    sunwell lens resolve "Build a REST API"

    sunwell lens resolve "Write documentation" --json

**Arguments:**

- `GOAL`

**Options:**

- `--explicit/-e` `text`: Explicit lens to use
- `--no-auto` `boolean`: Disable auto-selection (default: false)
- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell lens rollback`

Rollback a lens to a previous version.

Restores the content from a previous version and creates
a new version entry with a rollback message.

Examples:

    sunwell lens rollback my-team-coder 1.0.0

**Arguments:**

- `NAME`
- `VERSION`

##### `sunwell lens save`

Save changes to a user lens with version tracking.

Reads content from the specified file and saves it to the lens,
bumping the version number and creating a version snapshot.

Examples:

    sunwell lens save my-coder --file edited.lens -m "Added heuristic"

    sunwell lens save my-coder --file edited.lens --bump minor

**Arguments:**

- `NAME`

**Options:**

- `--file/-f` `path` **(required)**: Path to edited lens file (default: Sentinel.UNSET)
- `--message/-m` `text`: Version message (default: Sentinel.UNSET)
- `--bump` `choice`: Version bump type (default: patch)

##### `sunwell lens set-default`

Set or clear the global default lens.

When no name is provided, shows the current default.
Use --clear to remove the default and return to auto-select.

Examples:

    sunwell lens set-default my-team-coder

    sunwell lens set-default

    sunwell lens set-default --clear

**Arguments:**

- `NAME` (optional)

**Options:**

- `--clear` `boolean`: Clear the default lens (default: false)

##### `sunwell lens show`

Show details of a specific lens.

Examples:

    sunwell lens show coder

    sunwell lens show tech-writer --json

**Arguments:**

- `LENS_NAME`

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell lens skill-graph`

Show the skill dependency graph for a lens (RFC-087).

Displays skills and their dependencies as a DAG, with execution
waves showing which skills can run in parallel.

Examples:

    sunwell lens skill-graph tech-writer

    sunwell lens skill-graph tech-writer --json

    sunwell lens skill-graph coder --mermaid

**Arguments:**

- `LENS_NAME`

**Options:**

- `--json` `boolean`: Output as JSON (default: false)
- `--mermaid` `boolean`: Output as Mermaid diagram (default: false)

##### `sunwell lens skill-plan`

Show execution plan with cache predictions (RFC-087).

Predicts which skills will execute vs skip based on cache state.

Examples:

    sunwell lens skill-plan tech-writer --json

    sunwell lens skill-plan coder --context-hash abc123

**Arguments:**

- `LENS_NAME`

**Options:**

- `--context-hash` `text`: Context hash for cache key computation (default: Sentinel.UNSET)
- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell lens skills`

List skills for a lens with DAG information (RFC-087).

Shows skills with their dependencies, produces, and requires.
Used by Studio UI for skill panel.

Examples:

    sunwell lens skills tech-writer

    sunwell lens skills tech-writer --json

**Arguments:**

- `LENS_NAME`

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

##### `sunwell lens versions`

Show version history for a lens.

Displays the version history including timestamps and messages.

Examples:

    sunwell lens versions my-team-coder

    sunwell lens versions my-team-coder --json

**Arguments:**

- `NAME`

**Options:**

- `--json` `boolean`: Output as JSON (default: false)

#### `sunwell setup`

Initialize Sunwell for this project.

One command that handles everything:
- Creates .sunwell/ directory with project manifest
- Builds workspace context cache for fast startup
- Registers project globally for easy access
- Optionally sets up lens bindings

Safe to run multiple times - only updates what's needed.


Examples:
    sunwell setup                    # Setup current directory
    sunwell setup ~/projects/myapp   # Setup specific path
    sunwell setup --provider openai  # Use OpenAI
    sunwell setup --minimal          # Just project, no bindings

**Arguments:**

- `PATH` (optional)

**Options:**

- `--provider/-p` `text`: LLM provider (default: config/ollama)
- `--model/-m` `text`: Model name (auto-selected based on provider)
- `--trust` `choice`: Default tool trust level (default: workspace)
- `--force/-f` `boolean`: Overwrite existing configuration (default: false)
- `--minimal` `boolean`: Skip lens bindings (project only) (default: false)
- `--quiet/-q` `boolean`: Minimal output (default: false)

#### `sunwell serve`

Start the Sunwell Studio HTTP server.

In production mode (default), serves the Svelte UI from the same origin.
In development mode (--dev), enables CORS for Vite dev server on :5173.


Examples:
    sunwell serve              # Start on localhost:8080
    sunwell serve --open       # Start and open browser
    sunwell serve --dev        # API only, for Vite dev server
    sunwell serve --port 3000  # Custom port

**Options:**

- `--port` `integer`: Port to listen on (default: 8080)
- `--host` `text`: Host to bind to (127.0.0.1 for local only) (default: 127.0.0.1)
- `--open` `boolean`: Open browser automatically (default: false)
- `--dev` `boolean`: Development mode (CORS enabled for Vite on :5173) (default: false)

### Additional Commands

Utility commands for debugging and analysis.

#### `sunwell debug`

Debugging and diagnostics tools.

Commands for collecting diagnostics, analyzing issues,
and generating shareable bug reports.

**Subcommands:**

- `dump`: Collect diagnostics for bug reports.

Creates a tarball containing:
- Sunwell version and environment info
- Configuration (sanitized of secrets)
- Recent events and logs
- Run history and plan snapshots
- Memory state (learnings, dead ends)


Examples:
    sunwell debug dump
    sunwell debug dump -o my-debug.tar.gz
    sunwell debug dump --no-include-system


The output is designed for sharing in bug reports.
Secrets are automatically redacted.

#### `sunwell lineage`

Artifact lineage and provenance tracking.

Track the complete lineage of every artifact: which goal spawned it,
which model wrote it, what edits were made, and how it relates to other files.


Examples:
    sunwell lineage show src/auth.py
    sunwell lineage goal abc123
    sunwell lineage deps src/api.py
    sunwell lineage impact src/base.py
    sunwell lineage sync

**Subcommands:**

- `deps`: Show dependency graph for a file.

Displays what this file imports and what imports it.


Examples:
    sunwell lineage deps src/api/routes.py
    sunwell lineage deps src/base.py --direction imports
- `goal`: Show all artifacts from a goal.

Lists files created and modified by a specific goal.


Examples:
    sunwell lineage goal abc123
    sunwell lineage goal goal-xyz --json
- `impact`: Analyze impact of modifying/deleting a file.

Shows all files that depend on this file (directly or transitively)
and the goals that created those dependencies.


Examples:
    sunwell lineage impact src/base.py
    sunwell lineage impact src/auth/base.py --json
- `init`: Initialize lineage tracking for a project.

Creates the .sunwell/lineage/ directory and optionally scans
existing files to build dependency graph.


Examples:
    sunwell lineage init
    sunwell lineage init --scan
- `show`: Show lineage for a file.

Displays creation info, edit history, model attribution, and dependencies.


Examples:
    sunwell lineage show src/auth/oauth.py
    sunwell lineage show src/api/routes.py --json
- `stats`: Show lineage statistics.

Displays counts of tracked artifacts, edits, and dependency relationships.


Examples:
    sunwell lineage stats
    sunwell lineage stats --json
- `sync`: Detect and sync untracked changes.

Finds files that were modified outside of Sunwell and optionally
marks them as human edits in the lineage.


Examples:
    sunwell lineage sync
    sunwell lineage sync --json

#### `sunwell review`

Review and recover from failed agent runs.

When Sunwell can't automatically fix errors, it saves progress for review.
Use this command to see what succeeded, what failed, and choose how to proceed.


EXAMPLES:
    sunwell review                    # Interactive review of pending recoveries
    sunwell review --list             # List all pending recoveries
    sunwell review abc123             # Review specific recovery
    sunwell review abc123 --auto-fix  # Retry with agent
    sunwell review abc123 --skip      # Write only passed files
    sunwell review abc123 --hint "User model is in models/user.py"


RECOVERY OPTIONS:
    --auto-fix    Let agent retry with full context of what failed
    --skip        Write the files that passed, abandon the rest
    --abort       Delete recovery state entirely
    --hint        Provide a hint to help agent fix the issue

**Arguments:**

- `RECOVERY_ID` (optional)

**Options:**

- `--list/-l` `boolean`: List pending recoveries (default: false)
- `--auto-fix` `boolean`: Auto-fix with agent (default: false)
- `--skip` `boolean`: Write only passed files, skip failed (default: false)
- `--abort` `boolean`: Delete recovery state (default: false)
- `--hint/-H` `text`: Hint for agent when using --auto-fix
- `--errors` `boolean`: Show detailed error list (default: false)
- `--context` `boolean`: Show healing context for agent (default: false)
- `--provider/-p` `choice`: Model provider for auto-fix
- `--model/-m` `text`: Model for auto-fix
- `--verbose/-v` `boolean`: Show detailed output (default: false)

#### `sunwell chat`

Start an interactive headspace chat session.

Uses your default binding if no argument given. Can also specify
a binding name or lens path directly.

Your headspace (learnings, dead ends, context) persists across:
- Model switches: /switch anthropic:claude-sonnet-4-20250514
- Session restarts: sunwell chat --session my-project

Key commands:
- /switch <provider:model>: Switch models mid-conversation
- /branch <name>: Create a branch to try something
- /dead-end: Mark current path as dead end
- /learn <fact>: Add a persistent learning
- /quit: Exit (auto-saves)

Examples:

sunwell chat # Uses default binding

sunwell chat writer # Uses 'writer' binding

sunwell chat lenses/tech-writer.lens # Direct lens path

sunwell chat --session auth-debug # Named session

# Mid-conversation: /switch anthropic:claude-sonnet-4-20250514

**Arguments:**

- `BINDING_OR_LENS` (optional)

**Options:**

- `--session/-s` `text`: Session name (creates new or resumes existing) (default: Sentinel.UNSET)
- `--model/-m` `text`: Model to use
- `--provider/-p` `text`: Provider
- `--memory-path` `path`: Memory store path (default: .sunwell/memory)
- `--tools/--no-tools` `boolean`: Override tool calling (Agent mode)
- `--trust` `choice`: Override tool trust level
- `--smart` `boolean`: Enable Adaptive Model Selection (default: false)
- `--mirror` `boolean`: Enable Mirror Neurons (self-introspection) (default: false)
- `--model-routing` `boolean`: Enable Model-Aware Task Routing (default: false)
- `--router-model` `text`: Tiny LLM for cognitive routing
- `--naaru/--no-naaru` `boolean`: : Enable Naaru Shards for parallel processing (default: true)

---

*Generated from Click command definitions*
