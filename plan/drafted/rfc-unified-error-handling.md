# RFC: Unified Error Handling Across Python, Rust, and Svelte

**Status**: Implemented  
**Created**: 2026-01-22  
**Updated**: 2026-01-22  
**Authors**: Auto-generated  

## Problem Statement

Error handling is inconsistent across the Rust/Svelte boundary, causing raw error strings to surface to users instead of actionable, structured errors.

**Current Gap**:
- Python has a solid error system (`core/errors.py`) that IS used consistently ✅
- Rust uses ad-hoc `Result<T, String>` with raw error messages (200+ call sites) ❌
- Svelte displays `agent.error` strings with no structure or recovery hints ❌
- No shared error schema enables Rust to serialize structured errors for Svelte

**User Impact**:
When errors occur in Tauri commands, users see:
```
Failed to start agent: No such file or directory (os error 2)
```

Instead of:
```
[SW-3103] Skill execution failed
What you can do:
  1. Check if sunwell CLI is installed
  2. Verify the path exists
  3. Try running the command manually
```

## Current State Analysis

### Python (Solid Foundation) ✅

The Python error system is comprehensive and consistently used:

```python
# src/sunwell/core/errors.py - 30+ error codes, messages, recovery hints
class ErrorCode(IntEnum):
    MODEL_AUTH_FAILED = 1002
    MODEL_PROVIDER_UNAVAILABLE = 1009
    CONFIG_ENV_MISSING = 5003
    # ... 30+ codes

class SunwellError(Exception):
    code: ErrorCode
    context: dict
    message: str  # Formatted from template
    recovery_hints: list[str]
    is_recoverable: bool
    error_id: str  # "SW-1002"
    
    def to_dict(self) -> dict:
        """Serialize for API/logging."""
```

**Translation functions are called** at all model client boundaries:
- `openai.py:69,198,263` — `from_openai_error()` wraps all SDK exceptions
- `anthropic.py` — `from_anthropic_error()` wraps all SDK exceptions
- `ollama.py` — Native error handling with `SunwellError`

**API key validation** happens before client creation:
```python
# openai.py:56-64 — raises SunwellError before SDK can throw
if not self.api_key:
    raise SunwellError(
        code=ErrorCode.CONFIG_ENV_MISSING,
        context={"var": "OPENAI_API_KEY", "provider": "openai"},
    )
```

### Rust (Ad-hoc — Needs Work) ⚠️

**Audit Summary**: 200+ `map_err` calls use raw string formatting.

```rust
// Current pattern (200+ instances)
.map_err(|e| format!("Failed to start agent: {}", e))?;
.map_err(|e| e.to_string())?;
```

**Only `BriefingError`** uses proper structured errors:
```rust
// src-tauri/src/briefing.rs — good example to follow
#[derive(Debug, Error)]
pub enum BriefingError {
    #[error("Failed to read briefing: {0}")]
    ReadError(#[from] std::io::Error),
}
```

**Breakdown by module**:
| Module | `map_err` calls | Priority |
|--------|-----------------|----------|
| `commands.rs` | ~80 | High (user-facing) |
| `agent.rs` | ~15 | High (goal execution) |
| `dag.rs` | ~20 | Medium |
| `writer.rs` | ~15 | Medium |
| `security.rs` | ~10 | Medium |
| Other | ~60 | Low |

### Svelte (Minimal — Needs Work) ❌

Displays raw error strings with no parsing or structure:

```svelte
<!-- src/components/project/ErrorState.svelte -->
<p class="error-message">{agent.error}</p>
```

```typescript
// Error handling just converts to string
const errorMessage = e instanceof Error ? e.message : String(e);
homeState.error = errorMessage;
```

## Proposed Design

### 1. Shared Error Schema (JSON)

Create `schemas/error.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["error_id", "code", "category", "message"],
  "properties": {
    "error_id": {
      "type": "string",
      "pattern": "^SW-\\d{4}$",
      "description": "Human-readable error ID (e.g., SW-1002)"
    },
    "code": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 9999,
      "description": "Numeric error code"
    },
    "category": {
      "type": "string",
      "enum": ["model", "lens", "tool", "validation", "config", "runtime", "io"],
      "description": "Error category"
    },
    "message": {
      "type": "string",
      "description": "User-friendly error message"
    },
    "recoverable": {
      "type": "boolean",
      "default": true,
      "description": "Whether the operation can be retried"
    },
    "recovery_hints": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Actionable suggestions to fix the error"
    },
    "context": {
      "type": "object",
      "description": "Additional context for debugging"
    },
    "cause": {
      "type": "string",
      "description": "Original error message (for debugging)"
    }
  }
}
```

### 2. Error Code Registry

Single source of truth for all error codes in `schemas/error-codes.yaml`:

```yaml
# Error codes - single source of truth
# Python, Rust, and TypeScript generate from this

categories:
  1: model
  2: lens
  3: tool
  4: validation
  5: config
  6: runtime
  7: io

errors:
  # Model/Provider (1xxx)
  MODEL_NOT_FOUND:
    code: 1001
    message: "Model '{model}' not found. Check if it's installed or available."
    recoverable: true
    hints:
      - "Run 'ollama list' to see available models"
      - "Install with 'ollama pull {model}'"

  MODEL_AUTH_FAILED:
    code: 1002
    message: "Authentication failed for {provider}. Check your API key."
    recoverable: false
    hints:
      - "Set the API key: export {env_var}=<your-key>"
      - "Check if your API key is valid and not expired"
      - "For local models, use --provider ollama (no API key needed)"

  MODEL_PROVIDER_UNAVAILABLE:
    code: 1009
    message: "Provider '{provider}' is unavailable. Is it running?"
    recoverable: true
    hints:
      - "For Ollama: run 'ollama serve'"
      - "Check the provider URL is correct"
      - "Switch to a different provider with --provider"

  # Tool/Skill (3xxx)
  TOOL_EXECUTION_FAILED:
    code: 3003
    message: "Tool '{tool}' failed: {detail}"
    recoverable: true
    hints:
      - "Check if the tool is installed"
      - "Try running the command manually"
      - "Check permissions for the target path"

  SKILL_EXECUTION_FAILED:
    code: 3103
    message: "Skill '{skill}' execution failed: {detail}"
    recoverable: true
    hints:
      - "Check if sunwell CLI is installed"
      - "Verify the project path exists"
      - "Try running 'sunwell --help' to verify installation"

  # Config (5xxx)
  CONFIG_ENV_MISSING:
    code: 5003
    message: "Environment variable '{var}' not set."
    recoverable: false
    hints:
      - "Set the variable: export {var}=<value>"
      - "Add it to your .env file"
      - "For local-first usage, use --provider ollama (no keys needed)"

  # Runtime (6xxx)
  RUNTIME_PROCESS_FAILED:
    code: 6010
    message: "Process failed to start: {detail}"
    recoverable: true
    hints:
      - "Check if the command exists in PATH"
      - "Verify permissions"
      - "Try running the command manually"

  # IO (7xxx)
  FILE_NOT_FOUND:
    code: 7003
    message: "File not found: {path}"
    recoverable: false
    hints:
      - "Check if the path is correct"
      - "Verify the file exists"
```

### 3. Python CLI Integration

Ensure CLI outputs JSON-structured errors for Tauri to parse:

```python
# src/sunwell/cli/error_handler.py

import json
import sys
from sunwell.core.errors import SunwellError

def handle_error(error: SunwellError, json_output: bool = False) -> None:
    """Handle error with optional JSON output for machine consumption."""
    if json_output:
        # Structured output for Tauri/programmatic use
        print(json.dumps(error.to_dict()), file=sys.stderr)
        sys.exit(1)
    
    # Human-readable output for CLI
    from rich.console import Console
    console = Console(stderr=True)
    
    console.print(f"[bold red]{error.error_id}[/] {error.message}")
    
    if error.recovery_hints:
        console.print("\n[bold]What you can do:[/]")
        for i, hint in enumerate(error.recovery_hints, 1):
            console.print(f"  {i}. {hint}")
    
    sys.exit(1)
```

### 4. Rust Implementation

Create `src-tauri/src/error.rs`:

```rust
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Error codes matching Python's ErrorCode enum.
/// Generated from schemas/error-codes.yaml
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u16)]
pub enum ErrorCode {
    // Model errors (1xxx)
    ModelNotFound = 1001,
    ModelAuthFailed = 1002,
    ModelRateLimited = 1003,
    ModelProviderUnavailable = 1009,
    
    // Tool/Skill errors (3xxx)
    ToolExecutionFailed = 3003,
    SkillExecutionFailed = 3103,
    
    // Config errors (5xxx)
    ConfigMissing = 5001,
    ConfigInvalid = 5002,
    ConfigEnvMissing = 5003,
    
    // Runtime errors (6xxx)
    RuntimeProcessFailed = 6010,
    
    // IO errors (7xxx)
    FileNotFound = 7003,
    
    // Unknown/fallback
    Unknown = 0,
}

impl ErrorCode {
    pub fn category(&self) -> &'static str {
        match (*self as u16) / 1000 {
            1 => "model",
            2 => "lens",
            3 => "tool",
            4 => "validation",
            5 => "config",
            6 => "runtime",
            7 => "io",
            _ => "unknown",
        }
    }
    
    pub fn is_recoverable(&self) -> bool {
        !matches!(self, 
            ErrorCode::ModelAuthFailed | 
            ErrorCode::ConfigMissing | 
            ErrorCode::ConfigInvalid |
            ErrorCode::FileNotFound
        )
    }
    
    /// Default recovery hints for this error code
    pub fn default_hints(&self) -> Vec<&'static str> {
        match self {
            ErrorCode::ModelProviderUnavailable => vec![
                "For Ollama: run 'ollama serve'",
                "Check the provider URL is correct",
            ],
            ErrorCode::SkillExecutionFailed => vec![
                "Check if sunwell CLI is installed",
                "Try running 'sunwell --help' to verify",
            ],
            ErrorCode::RuntimeProcessFailed => vec![
                "Check if the command exists in PATH",
                "Try running the command manually",
            ],
            ErrorCode::FileNotFound => vec![
                "Check if the path is correct",
                "Verify the file exists",
            ],
            _ => vec![],
        }
    }
}

/// Structured error matching the JSON schema.
#[derive(Debug, Clone, Serialize, Deserialize, Error)]
#[error("[{error_id}] {message}")]
pub struct SunwellError {
    pub error_id: String,
    pub code: u16,
    pub category: String,
    pub message: String,
    pub recoverable: bool,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub recovery_hints: Vec<String>,
    #[serde(default, skip_serializing_if = "serde_json::Value::is_null")]
    pub context: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cause: Option<String>,
}

impl SunwellError {
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        let hints = code.default_hints();
        Self {
            error_id: format!("SW-{:04}", code as u16),
            code: code as u16,
            category: code.category().to_string(),
            message: message.into(),
            recoverable: code.is_recoverable(),
            recovery_hints: hints.into_iter().map(String::from).collect(),
            context: serde_json::Value::Null,
            cause: None,
        }
    }
    
    pub fn with_hints(mut self, hints: Vec<&str>) -> Self {
        self.recovery_hints = hints.into_iter().map(String::from).collect();
        self
    }
    
    pub fn with_context(mut self, context: serde_json::Value) -> Self {
        self.context = context;
        self
    }
    
    pub fn with_cause(mut self, cause: impl Into<String>) -> Self {
        self.cause = Some(cause.into());
        self
    }
    
    /// Create from a raw error, preserving original message as cause
    pub fn from_error<E: std::error::Error>(code: ErrorCode, error: E) -> Self {
        Self::new(code, error.to_string()).with_cause(format!("{:?}", error))
    }
    
    /// Parse from CLI JSON output
    pub fn from_cli_json(json_str: &str) -> Option<Self> {
        serde_json::from_str(json_str).ok()
    }
    
    /// Create unknown error for fallback
    pub fn unknown(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Unknown, message)
    }
}

// Convenience macro for common pattern
#[macro_export]
macro_rules! sunwell_err {
    ($code:ident, $msg:expr) => {
        $crate::error::SunwellError::new($crate::error::ErrorCode::$code, $msg)
    };
    ($code:ident, $fmt:expr, $($arg:tt)*) => {
        $crate::error::SunwellError::new(
            $crate::error::ErrorCode::$code,
            format!($fmt, $($arg)*)
        )
    };
}

// Helper trait for converting std::io::Error
impl From<std::io::Error> for SunwellError {
    fn from(e: std::io::Error) -> Self {
        match e.kind() {
            std::io::ErrorKind::NotFound => {
                SunwellError::from_error(ErrorCode::FileNotFound, e)
            }
            _ => SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
        }
    }
}
```

**Migration helper for existing code**:

```rust
// Before (current)
.map_err(|e| format!("Failed to start agent: {}", e))?;

// After (using macro)
.map_err(|e| sunwell_err!(RuntimeProcessFailed, "Failed to start agent: {}", e))?;

// Or using From trait
.map_err(SunwellError::from)?;
```

### 5. TypeScript/Svelte Implementation

Create `src/lib/error.ts`:

```typescript
/** Error codes matching Python/Rust enums */
export enum ErrorCode {
  // Model errors (1xxx)
  MODEL_NOT_FOUND = 1001,
  MODEL_AUTH_FAILED = 1002,
  MODEL_RATE_LIMITED = 1003,
  MODEL_PROVIDER_UNAVAILABLE = 1009,
  
  // Tool/Skill errors (3xxx)
  TOOL_EXECUTION_FAILED = 3003,
  SKILL_EXECUTION_FAILED = 3103,
  
  // Config errors (5xxx)
  CONFIG_MISSING = 5001,
  CONFIG_INVALID = 5002,
  CONFIG_ENV_MISSING = 5003,
  
  // Runtime errors (6xxx)
  RUNTIME_PROCESS_FAILED = 6010,
  
  // IO errors (7xxx)
  FILE_NOT_FOUND = 7003,
  
  // Unknown
  UNKNOWN = 0,
}

/** Category names by prefix */
const CATEGORIES: Record<number, string> = {
  0: 'unknown',
  1: 'model',
  2: 'lens',
  3: 'tool',
  4: 'validation',
  5: 'config',
  6: 'runtime',
  7: 'io',
};

/** Structured error matching JSON schema */
export interface SunwellError {
  error_id: string;
  code: number;
  category: string;
  message: string;
  recoverable: boolean;
  recovery_hints?: string[];
  context?: Record<string, unknown>;
  cause?: string;
}

/** Type guard for structured errors */
export function isSunwellError(obj: unknown): obj is SunwellError {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'error_id' in obj &&
    typeof (obj as SunwellError).error_id === 'string' &&
    (obj as SunwellError).error_id.startsWith('SW-') &&
    'code' in obj &&
    'message' in obj
  );
}

/** Parse error from backend (JSON string, SunwellError, or raw) */
export function parseError(error: unknown): SunwellError {
  // Already structured
  if (isSunwellError(error)) {
    return error;
  }
  
  // Try to parse JSON string from Tauri
  if (typeof error === 'string') {
    // Try JSON first
    try {
      const parsed = JSON.parse(error);
      if (isSunwellError(parsed)) {
        return parsed;
      }
    } catch {
      // Not JSON, continue
    }
    
    // Detect common error patterns and categorize
    const lowerError = error.toLowerCase();
    
    if (lowerError.includes('not found') || lowerError.includes('no such file')) {
      return createError(ErrorCode.FILE_NOT_FOUND, error);
    }
    if (lowerError.includes('permission denied')) {
      return createError(ErrorCode.TOOL_EXECUTION_FAILED, error, ['Check file permissions']);
    }
    if (lowerError.includes('connection refused') || lowerError.includes('unavailable')) {
      return createError(ErrorCode.MODEL_PROVIDER_UNAVAILABLE, error);
    }
    
    // Fallback to unknown
    return createError(ErrorCode.UNKNOWN, error);
  }
  
  // Error object
  if (error instanceof Error) {
    return createError(ErrorCode.UNKNOWN, error.message, undefined, error.stack);
  }
  
  // Unknown type
  return createError(ErrorCode.UNKNOWN, String(error));
}

/** Create a structured error */
function createError(
  code: ErrorCode,
  message: string,
  hints?: string[],
  cause?: string
): SunwellError {
  const category = CATEGORIES[Math.floor(code / 1000)] ?? 'unknown';
  return {
    error_id: `SW-${code.toString().padStart(4, '0')}`,
    code,
    category,
    message,
    recoverable: ![ErrorCode.CONFIG_MISSING, ErrorCode.CONFIG_INVALID, ErrorCode.MODEL_AUTH_FAILED].includes(code),
    recovery_hints: hints ?? getDefaultHints(code),
    cause,
  };
}

/** Default recovery hints by error code */
function getDefaultHints(code: ErrorCode): string[] {
  switch (code) {
    case ErrorCode.MODEL_PROVIDER_UNAVAILABLE:
      return ['For Ollama: run "ollama serve"', 'Check if the provider is running'];
    case ErrorCode.SKILL_EXECUTION_FAILED:
      return ['Check if sunwell CLI is installed', 'Try running "sunwell --help"'];
    case ErrorCode.FILE_NOT_FOUND:
      return ['Check if the path is correct', 'Verify the file exists'];
    default:
      return ['Try again', 'Check logs for details'];
  }
}

/** Get category icon */
export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    model: '🤖',
    lens: '🔍',
    tool: '🔧',
    validation: '✓',
    config: '⚙️',
    runtime: '⚡',
    io: '📁',
    unknown: '❌',
  };
  return icons[category] ?? '❌';
}
```

**Error display component** (`src/components/ui/ErrorDisplay.svelte`):

```svelte
<script lang="ts">
  import { type SunwellError, getCategoryIcon } from '$lib/error';
  import { fly } from 'svelte/transition';
  
  interface Props {
    error: SunwellError;
    onDismiss?: () => void;
    onRetry?: () => void;
    compact?: boolean;
  }
  
  let { error, onDismiss, onRetry, compact = false }: Props = $props();
</script>

<div 
  class="error-display" 
  class:compact
  role="alert" 
  transition:fly={{ y: -20, duration: 200 }}
>
  <header class="error-header">
    <span class="error-icon">{getCategoryIcon(error.category)}</span>
    <span class="error-id">{error.error_id}</span>
    {#if onDismiss}
      <button class="dismiss" onclick={onDismiss} aria-label="Dismiss">✕</button>
    {/if}
  </header>
  
  <p class="error-message">{error.message}</p>
  
  {#if !compact && error.recovery_hints?.length}
    <div class="recovery-hints">
      <strong>What you can do:</strong>
      <ol>
        {#each error.recovery_hints as hint}
          <li>{hint}</li>
        {/each}
      </ol>
    </div>
  {/if}
  
  {#if onRetry || !compact}
    <footer class="error-actions">
      {#if error.recoverable && onRetry}
        <button class="retry" onclick={onRetry}>Try Again</button>
      {/if}
    </footer>
  {/if}
</div>

<style>
  .error-display {
    background: var(--surface-error, #2d1b1b);
    border: 1px solid var(--error, #e53935);
    border-radius: var(--radius-md, 8px);
    padding: var(--space-4, 16px);
    max-width: 480px;
  }
  
  .error-display.compact {
    padding: var(--space-2, 8px) var(--space-3, 12px);
  }
  
  .error-header {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    margin-bottom: var(--space-2, 8px);
  }
  
  .compact .error-header {
    margin-bottom: 0;
  }
  
  .error-icon { font-size: 1.25rem; }
  .compact .error-icon { font-size: 1rem; }
  
  .error-id {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm, 0.875rem);
    color: var(--error, #e53935);
    font-weight: 600;
  }
  
  .dismiss {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: var(--space-1, 4px);
    border-radius: var(--radius-sm, 4px);
  }
  
  .dismiss:hover {
    background: var(--surface-2);
  }
  
  .error-message {
    color: var(--text-primary);
    margin: 0 0 var(--space-3, 12px);
    line-height: 1.5;
  }
  
  .compact .error-message {
    display: inline;
    margin: 0 0 0 var(--space-2, 8px);
  }
  
  .recovery-hints {
    background: var(--surface-1);
    border-radius: var(--radius-sm, 4px);
    padding: var(--space-3, 12px);
    font-size: var(--text-sm, 0.875rem);
  }
  
  .recovery-hints ol {
    margin: var(--space-2, 8px) 0 0;
    padding-left: var(--space-4, 16px);
  }
  
  .recovery-hints li {
    margin: var(--space-1, 4px) 0;
    color: var(--text-secondary);
  }
  
  .error-actions {
    margin-top: var(--space-3, 12px);
    display: flex;
    gap: var(--space-2, 8px);
    justify-content: flex-end;
  }
  
  .retry {
    background: var(--error, #e53935);
    color: white;
    border: none;
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
    font-weight: 500;
    transition: opacity 0.15s;
  }
  
  .retry:hover {
    opacity: 0.9;
  }
</style>
```

**Update ErrorState.svelte to use structured errors**:

```svelte
<!-- src/components/project/ErrorState.svelte -->
<script lang="ts">
  import { parseError } from '$lib/error';
  import ErrorDisplay from '$components/ui/ErrorDisplay.svelte';
  import Button from '$components/ui/Button.svelte';
  
  interface Props {
    agent: { error: string | unknown };
    onBack: () => void;
    onRetry?: () => void;
  }
  
  let { agent, onBack, onRetry }: Props = $props();
  
  const parsedError = $derived(parseError(agent.error));
</script>

<div class="error-state">
  <ErrorDisplay 
    error={parsedError} 
    onRetry={parsedError.recoverable ? onRetry : undefined}
  />
  
  <div class="actions">
    <Button variant="secondary" onclick={onBack}>Go Back</Button>
  </div>
</div>

<style>
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8, 32px);
    gap: var(--space-4, 16px);
  }
  
  .actions {
    margin-top: var(--space-4, 16px);
  }
</style>
```

## Implementation Plan

### Phase 0: Audit & Preparation (Day 1)

1. **Audit Rust error sites**
   - Grep all `map_err` calls: `rg "map_err" studio/src-tauri/src --type rust`
   - Categorize by user-facing vs internal
   - Prioritize: `agent.rs`, `commands.rs` (user-facing) first

2. **Verify Python CLI JSON output**
   - Confirm `SunwellError.to_dict()` is called on CLI errors
   - Add `--json` flag for machine-readable output if missing

3. **Create migration tracking**
   - Create `docs/error-migration-status.md` to track progress

### Phase 1: Schema & Codegen (Week 1)

1. **Create schemas**
   - `schemas/error.schema.json` — JSON Schema
   - `schemas/error-codes.yaml` — Code registry (source of truth)

2. **Create codegen scripts**
   - `scripts/generate_error_codes.py` — Generate Python from YAML
   - `scripts/generate_error_codes_rs.py` — Generate Rust from YAML
   - `scripts/generate_error_codes_ts.py` — Generate TypeScript from YAML

3. **Add to build**
   - Add codegen to `Makefile`
   - Verify generated code matches existing Python codes

### Phase 2: Rust Integration (Week 2)

1. **Create error module**
   - `src-tauri/src/error.rs` — SunwellError struct
   - Add `sunwell_err!` macro for easy migration

2. **Migrate high-priority modules** (user-facing)
   - `agent.rs` — Goal execution errors (~15 sites)
   - `commands.rs` — Tauri command errors (~80 sites)

3. **Parse CLI JSON errors**
   - When calling Python CLI, parse stderr for JSON errors
   - Fall back to string wrapping for non-JSON

### Phase 3: Svelte Integration (Week 2)

1. **Create error utilities**
   - `src/lib/error.ts` — parseError, types, helpers

2. **Create ErrorDisplay component**
   - `src/components/ui/ErrorDisplay.svelte`
   - Support compact mode for inline errors

3. **Update existing error displays**
   - `ErrorState.svelte` — Use parseError + ErrorDisplay
   - `GoalInput.svelte` — Use parseError
   - `WorkflowPanel.svelte` — Use parseError

### Phase 4: Remaining Migration (Week 3)

1. **Migrate medium-priority Rust modules**
   - `dag.rs`, `writer.rs`, `security.rs`

2. **Add logging integration**
   - Log structured errors with tracing
   - Include error_id in all log entries

3. **Documentation**
   - Update CONTRIBUTING.md with error handling guidelines
   - Document error codes in user docs

## Testing Strategy

### Unit Tests

```python
# tests/test_errors.py
def test_error_serialization_roundtrip():
    """SunwellError serializes and deserializes correctly."""
    error = SunwellError(
        code=ErrorCode.MODEL_AUTH_FAILED,
        context={"provider": "openai", "env_var": "OPENAI_API_KEY"}
    )
    json_str = json.dumps(error.to_dict())
    parsed = json.loads(json_str)
    
    assert parsed["error_id"] == "SW-1002"
    assert parsed["code"] == 1002
    assert parsed["category"] == "model"
    assert "openai" in parsed["message"]
```

```rust
// src-tauri/src/error_test.rs
#[test]
fn test_error_serialization() {
    let error = SunwellError::new(ErrorCode::SkillExecutionFailed, "Test failed");
    let json = serde_json::to_string(&error).unwrap();
    let parsed: SunwellError = serde_json::from_str(&json).unwrap();
    
    assert_eq!(parsed.error_id, "SW-3103");
    assert_eq!(parsed.category, "tool");
    assert!(parsed.recoverable);
}
```

```typescript
// src/lib/error.test.ts
describe('parseError', () => {
  it('parses JSON string from Tauri', () => {
    const json = '{"error_id":"SW-3103","code":3103,"category":"tool","message":"Test","recoverable":true}';
    const error = parseError(json);
    
    expect(error.error_id).toBe('SW-3103');
    expect(error.category).toBe('tool');
  });
  
  it('wraps raw string with pattern detection', () => {
    const error = parseError('No such file or directory');
    expect(error.code).toBe(ErrorCode.FILE_NOT_FOUND);
  });
});
```

### Integration Tests

```python
# tests/integration/test_error_flow.py
async def test_error_flows_to_studio():
    """Errors from Python CLI are parsed correctly by Tauri."""
    # Simulate missing API key
    result = subprocess.run(
        ["sunwell", "run", "--provider", "openai", "--json"],
        capture_output=True,
        env={**os.environ, "OPENAI_API_KEY": ""},
    )
    
    error = json.loads(result.stderr)
    assert error["error_id"] == "SW-5003"
    assert "OPENAI_API_KEY" in error["message"]
```

## Visual Examples

### Before (Current)

**CLI**:
```
Error: Processing failed: Traceback (most recent call last):
  File "/.../sunwell", line 7...
  [50 lines of stack trace]
openai.OpenAIError: The api_key client option must be set...
```

**Studio**:
```
┌────────────────────────────────────┐
│ ✗ Error                            │
│                                    │
│ Failed to start agent: No such     │
│ file or directory (os error 2)     │
│                                    │
│              [Go Back]             │
└────────────────────────────────────┘
```

### After (Proposed)

**CLI**:
```
[SW-5003] Environment variable 'OPENAI_API_KEY' not set.

What you can do:
  1. Set the variable: export OPENAI_API_KEY=<your-key>
  2. Add it to your .env file
  3. For local-first usage, use --provider ollama (no keys needed)
```

**Studio**:
```
┌─────────────────────────────────────────────┐
│ ⚙️  SW-5003                              ✕  │
├─────────────────────────────────────────────┤
│ Environment variable 'OPENAI_API_KEY'       │
│ not set.                                    │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ What you can do:                        │ │
│ │ 1. Set the variable: export OPENAI...   │ │
│ │ 2. Add it to your .env file             │ │
│ │ 3. Use --provider ollama (no keys)      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│                         [Try Again]         │
└─────────────────────────────────────────────┘
```

## Success Criteria

1. **No raw stack traces** surface to users in Studio
2. **Every error has a code** (SW-XXXX) visible in UI
3. **Recovery hints** displayed for all common errors
4. **Consistent display** across CLI and Studio
5. **Single source of truth** — error-codes.yaml generates all implementations
6. **Test coverage** — Unit tests for serialization, integration tests for flow

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large Rust migration (200+ sites) | High effort | Prioritize user-facing paths; use macro for easy migration |
| Schema drift between languages | Inconsistent errors | Codegen from single YAML source |
| Breaking existing error handling | Regression | Maintain backward compat in parseError() |
| Performance overhead | Slower error paths | Minimal (struct creation only on error) |

## Dependencies

- None (can implement incrementally)
- Optional: `thiserror` crate for Rust (already used in briefing.rs)

## References

- `src/sunwell/core/errors.py` — Existing Python error system (comprehensive)
- `src-tauri/src/briefing.rs` — Good Rust error pattern to follow
- `schemas/` — Existing JSON schemas for events
- [Tauri Error Handling](https://tauri.app/v1/guides/features/command/#error-handling)
