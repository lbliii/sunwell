# RFC-068: Unified Health Check

**Status:** Ready for Implementation  
**Created:** 2026-01-20  
**Updated:** 2026-01-20  
**Author:** Sunwell Team

---

## Summary

Consolidate Python, Rust, and Svelte linting/type-checking into a single `make health` command with unified output format, making it easy to see all codebase issues in one place.

---

## Goals

1. **Single command visibility**: `make health` shows issues from all stacks
2. **Auto-fix support**: `make health-fix` clears fixable issues
3. **CI-ready**: Exit codes enable CI/CD integration
4. **Scannable output**: Results readable in < 10 seconds

## Non-Goals

- **Not replacing IDE linting** — Cursor/VS Code integration is complementary
- **Not enforcing pre-commit hooks** — `health` is on-demand, not blocking
- **Not a test runner** — Tests remain separate via `make test`
- **Not cross-repo** — Scoped to Sunwell monorepo only

---

## Problem

Currently, checking code health requires running multiple commands across different stacks:

```bash
# Python
make check          # ruff + ty
make test           # pytest

# Rust (Tauri)
cd studio/src-tauri && cargo check

# Svelte
cd studio && npm run check
```

Issues are scattered across:
- Terminal output from `make studio-dev` (Rust + Svelte mixed)
- Separate `make check` output (Python only)
- Test output from `make test`

**Pain points:**
1. No single view of all issues
2. Different output formats per tool
3. Easy to miss issues in one stack while focused on another
4. CI/CD requires multiple check steps

---

## Proposal

### 1. Unified `make health` Command

```makefile
# Strict mode: STRICT=1 make health (treats warnings as errors)
STRICT ?= 0

health:
	@echo "🏥 Running unified health check..."
	@$(MAKE) health-python
	@$(MAKE) health-rust  
	@$(MAKE) health-svelte
	@echo "✅ Health check complete"

health-python:
	@echo "\n═══ PYTHON ═══"
	@command -v ruff >/dev/null || { echo "❌ ruff not found. Run: pip install ruff"; exit 1; }
	@ruff check src/ --output-format=concise 2>&1 | head -50 || true
	@echo "---"
	@ty check src/ 2>&1 | head -20 || true

health-rust:
	@echo "\n═══ RUST ═══"
	@command -v cargo >/dev/null || { echo "⚠️  cargo not found, skipping Rust"; exit 0; }
	@cd studio/src-tauri && cargo check --message-format=short 2>&1 | grep -E "^(error|warning)" | head -20 || echo "✓ No issues"

health-svelte:
	@echo "\n═══ SVELTE ═══"
	@test -d studio/node_modules || { echo "⚠️  Run 'cd studio && npm install' first"; exit 0; }
	@cd studio && npm run check 2>&1 | grep -E "^(Error|Warning|src/)" | head -30 || echo "✓ No issues"
```

### 2. JSON Output for Tooling

```makefile
health-json:
	@python scripts/health_check.py --json
```

Output format:
```json
{
  "timestamp": "2026-01-20T16:00:00Z",
  "summary": {
    "python": { "errors": 12, "warnings": 0, "fixable": 8 },
    "rust": { "errors": 0, "warnings": 1 },
    "svelte": { "errors": 0, "warnings": 3 }
  },
  "issues": [
    {
      "stack": "python",
      "file": "src/sunwell/example.py",
      "line": 42,
      "code": "E501",
      "message": "Line too long (108 > 100)",
      "fixable": true
    }
  ]
}
```

### 3. Studio Integration (Future)

*Deferred to Phase 3 — not required for MVP.*

Add a "Health" panel to Sunwell Studio that displays issues from all stacks:

```
┌─────────────────────────────────────────┐
│ 🏥 Codebase Health                      │
├─────────────────────────────────────────┤
│ Python    ████████░░  12 issues         │
│ Rust      ██████████  ✓ clean           │
│ Svelte    █████████░  3 warnings        │
├─────────────────────────────────────────┤
│ ▸ E501 Line too long (8 fixable)        │
│ ▸ F401 Unused import (4)                │
└─────────────────────────────────────────┘
```

### 4. Auto-Fix Command

```makefile
health-fix:
	@echo "🔧 Auto-fixing issues..."
	@ruff check src/ --fix
	@cd studio && npm run lint -- --fix 2>/dev/null || true
	@echo "✅ Fixed what we could"
```

---

## Implementation

### Phase 1: Makefile Targets (MVP, 1 hour)
- Add `health`, `health-python`, `health-rust`, `health-svelte` targets
- Add `health-fix` for auto-fixing
- Update `.PHONY` and help text

### Phase 2: JSON Output Script (2 hours)
- Create `scripts/health_check.py`
- Parse output from ruff, cargo, svelte-check
- Output unified JSON for CI/tooling

### Phase 3: Studio Integration (Future, 4 hours)
- Add Tauri command `get_health_status`
- Create `HealthPanel.svelte` component
- Wire into Project view

**MVP = Phase 1 + Phase 2** (3 hours total)

---

## Alternatives Considered

### 1. Use trunk.io or similar unified linter
**Rejected:** Adds external dependency, overkill for our needs

### 2. Pre-commit hooks only
**Rejected:** Doesn't provide on-demand visibility

### 3. IDE-only (rely on Cursor/VS Code)
**Rejected:** Not everyone uses same IDE, no CI integration

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tool not installed (cargo, npm, ruff) | Command fails with unclear error | Check tool availability first, print actionable error |
| Windows path handling | `cd &&` chains may fail | Use `$(MAKE) -C dir` or cross-platform scripts |
| Output overwhelms terminal | Unreadable for large issue counts | Already handled: `head -N` truncation per stack |
| CI flakiness from transient errors | False failures | `|| true` for non-critical commands, explicit exit codes |

---

## Design Decisions

### 1. Collect all vs fail fast?
**Decision: Collect all.** The goal is visibility — users want to see everything at once. Fail-fast would require multiple runs to discover all issues.

### 2. Include test failures?
**Decision: No.** Keep `health` for static analysis (fast, no execution). Tests remain separate via `make test`. Rationale: health check should complete in seconds, tests may take minutes.

### 3. Warnings as errors in CI?
**Decision: Configurable.** Default: warnings don't fail. Strict mode via environment variable:
```bash
STRICT=1 make health  # Treat warnings as errors
```

---

## Success Criteria

1. `make health` shows all issues from Python, Rust, and Svelte
2. `make health-fix` auto-fixes what it can
3. `make health-json` outputs machine-readable format for CI
4. Output is scannable in < 10 seconds
5. Exit code reflects error state (0 = clean, non-zero = issues)

---

## References

- [ruff output formats](https://docs.astral.sh/ruff/configuration/#output-format)
- [cargo message formats](https://doc.rust-lang.org/cargo/reference/external-tools.html)
- [svelte-check](https://github.com/sveltejs/language-tools/tree/master/packages/svelte-check)
