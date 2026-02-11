# ═══════════════════════════════════════════════════════════════════════════════
# Sunwell — AI-Native Development
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help dev studio studio-dev studio-build studio-test studio-test-watch studio-test-coverage install check test test-all clean schema schema-verify schema-test schema-demo run-types unwired unwired-strict lint-layers

# Default target
help:
	@echo ""
	@echo "  ╔═══════════════════════════════════════════════════════════════╗"
	@echo "  ║              ☀️  SUNWELL DEVELOPMENT COMMANDS                  ║"
	@echo "  ╚═══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  Usage: make <command>"
	@echo ""
	@echo "  ┌─────────────────────────────────────────────────────────────────┐"
	@echo "  │ DEVELOPMENT                                                     │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ dev           🔥 Start API + Frontend (recommended)             │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ STUDIO (GUI)                                                    │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ studio        Run Sunwell Studio (demo mode)                    │"
	@echo "  │ studio-dev    Run Studio with hot reload                        │"
	@echo "  │ studio-build  Build Studio for production                       │"
	@echo "  │ studio-test   Run Studio frontend tests                         │"
	@echo "  │ studio-test-watch  Run Studio tests in watch mode               │"
	@echo "  │ studio-test-coverage  Run Studio tests with coverage           │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ CORE (CLI)                                                      │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ install       Install Sunwell CLI (editable)                    │"
	@echo "  │ agent         Run agent with a goal (GOAL='...')                │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ DEVELOPMENT                                                     │"
	@echo "  ├─────────────────────────────────────────────────────────────────┤"
	@echo "  │ check         Run linters and type checks                       │"
	@echo "  │ test          Run Python tests                                  │"
	@echo "  │ test-all      Run all tests (Python + Frontend)                │"
	@echo "  │ schema        Generate event schemas (JSON + TypeScript)        │"
	@echo "  │ schema-verify Verify schemas are up-to-date (for CI)           │"
	@echo "  │ schema-test   Test schema contract                              │"
	@echo "  │ schema-demo   Demo schema contract system                      │"
	@echo "  │ lint-layers   Check architectural layer imports                  │"
	@echo "  │ unwired       Find unwired/incomplete code                     │"
	@echo "  │ unwired-strict  Find unwired code (high confidence only)       │"
	@echo "  │ clean         Clean build artifacts                             │"
	@echo "  └─────────────────────────────────────────────────────────────────┘"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED DEV COMMAND (API + FRONTEND)
# ═══════════════════════════════════════════════════════════════════════════════

# Start both API server and Vite frontend in one command
dev: studio-deps
	@./scripts/dev.sh

# ═══════════════════════════════════════════════════════════════════════════════
# STUDIO COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

# Run Sunwell Studio (demo mode, hot reload)
studio: studio-deps
	@echo "☀️  Starting Sunwell Studio..."
	@cd studio && npm run tauri dev

# Alias for studio
studio-dev: studio

# Install studio dependencies if needed
studio-deps:
	@if [ ! -d "studio/node_modules" ]; then \
		echo "📦 Installing Studio dependencies..."; \
		cd studio && npm install; \
	fi
	@if ! command -v cargo &> /dev/null; then \
		echo "⚠️  Rust not found. Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"; \
		exit 1; \
	fi

# Build Studio for production
studio-build: studio-deps
	@echo "🔨 Building Sunwell Studio..."
	@cd studio && npm run tauri build

# Run Studio frontend tests
studio-test: studio-deps
	@echo "🧪 Running Studio frontend tests..."
	@cd studio && npm test -- --run

# Run Studio tests in watch mode
studio-test-watch: studio-deps
	@echo "👀 Running Studio tests in watch mode..."
	@cd studio && npm run test:watch

# Run Studio tests with coverage
studio-test-coverage: studio-deps
	@echo "📊 Running Studio tests with coverage..."
	@cd studio && npm run test:coverage

# ═══════════════════════════════════════════════════════════════════════════════
# CORE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

# Install Sunwell CLI in development mode
install:
	@echo "📦 Installing Sunwell..."
	@pip install -e ".[dev]"

# Run agent with a goal
# Usage: make agent GOAL="Build a Flask API"
agent:
ifndef GOAL
	@echo "Usage: make agent GOAL='your goal here'"
	@exit 1
endif
	@sunwell agent run "$(GOAL)"

# ═══════════════════════════════════════════════════════════════════════════════
# DEVELOPMENT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

# Verify Python environment
env:
	@python -c "import sys; ft = not sys._is_gil_enabled() if hasattr(sys, '_is_gil_enabled') else False; print('Python:', sys.version.split()[0], '(free-threaded)' if ft else '(GIL enabled - WRONG!)')"

# Run all checks
check: env lint-layers
	@echo "🔍 Running checks..."
	@ruff check src/
	@ty check src/
	@echo "🔗 Validating hypermedia contracts..."
	@chirp check sunwell.interface.chirp:create_app

# Check architectural layer imports (strict mode + ratchet)
lint-layers:
	@echo "Checking layer imports..."
	@python scripts/check_layer_imports.py --ratchet

# Run tests
test:
	@echo "🧪 Running Python tests..."
	@pytest tests/ -v

# Run all tests (Python + Frontend)
test-all: test studio-test
	@echo "✅ All tests complete!"

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA COMMANDS (RFC-060)
# ═══════════════════════════════════════════════════════════════════════════════

# Generate event schemas (JSON Schema + TypeScript types)
schema:
	@echo "📐 Generating event schemas..."
	@python scripts/generate_event_schema.py
	@echo ""
	@echo "✅ Schemas generated:"
	@echo "   • schemas/agent-events.schema.json"
	@echo "   • studio/src/lib/agent-events.ts"

# RFC-060: Verify schemas are up-to-date (for CI)
# Regenerates schemas and checks for uncommitted changes
schema-verify:
	@echo "🔍 Verifying schemas are up-to-date (RFC-060)..."
	@python scripts/generate_event_schema.py
	@if git diff --exit-code schemas/ studio/src/lib/agent-events.ts > /dev/null 2>&1; then \
		echo "✅ Schemas are up-to-date"; \
	else \
		echo "❌ Schema drift detected! Run 'make schema' and commit the changes."; \
		echo ""; \
		echo "Changed files:"; \
		git diff --name-only schemas/ studio/src/lib/agent-events.ts; \
		exit 1; \
	fi

# Test schema contract
schema-test:
	@echo "🧪 Testing schema contract..."
	@pytest tests/test_event_schema_contract.py tests/test_cli_json_output.py -v

# Demo schema contract system
schema-demo:
	@echo "🔍 Demonstrating schema contract system..."
	@python scripts/demo_schema_contract.py

# RFC-066: Run analysis types (manual - TypeScript types are in lib/types.ts)
# Rust types are in studio/src-tauri/src/run_analysis.rs
# Python types are in src/sunwell/tools/run_analyzer.py
run-types:
	@echo "📐 Run Analysis types are manually maintained across:"
	@echo "   • schemas/run-analysis.schema.json (source of truth)"
	@echo "   • studio/src/lib/types.ts (TypeScript)"
	@echo "   • studio/src-tauri/src/run_analysis.rs (Rust)"
	@echo "   • src/sunwell/tools/run_analyzer.py (Python)"
	@echo ""
	@echo "To validate schema consistency, run: make test"

# Find unwired/incomplete code
unwired:
	@echo "🔍 Finding unwired code..."
	@python scripts/find_unwired.py

# Find unwired code (high confidence only)
unwired-strict:
	@echo "🔍 Finding unwired code (high confidence)..."
	@python scripts/find_unwired.py -m 90

# Clean build artifacts
clean:
	@echo "🧹 Cleaning..."
	@rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	@rm -rf studio/dist studio/node_modules/.cache
	@rm -rf studio/src-tauri/target
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✨ Clean!"

# ═══════════════════════════════════════════════════════════════════════════════
# QUICK START
# ═══════════════════════════════════════════════════════════════════════════════

# First-time setup
setup: install studio-deps
	@echo ""
	@echo "✅ Setup complete! Run 'make studio' to start."
