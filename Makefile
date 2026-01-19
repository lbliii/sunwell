.PHONY: install dev test lint format clean build setup-env check-uv check-python314t

# Detect Python interpreter
PYTHON := python3.14t
ifeq ($(shell command -v python3.14t 2>/dev/null),)
	# Fallback to system Python if 3.14t not found
	PYTHON := python3
	$(warning python3.14t not found, using $(PYTHON). For optimal performance, install Python 3.14t)
endif

# Check if uv is installed
check-uv:
	@command -v uv >/dev/null 2>&1 || ( \
		echo ""; \
		echo "❌ uv is not installed or not in PATH"; \
		echo ""; \
		echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"; \
		echo ""; \
		exit 1; \
	)

# Check if Python 3.14t is available
check-python314t:
	@command -v python3.14t >/dev/null 2>&1 || ( \
		echo ""; \
		echo "⚠️  python3.14t not found. Using standard Python (GIL enabled)."; \
		echo ""; \
		echo "For free-threading, install Python 3.14t:"; \
		echo "  macOS: brew install python@3.14t"; \
		echo "  Or build from source: https://github.com/python/cpython"; \
		echo ""; \
	)

# Setup free-threading environment with uv
setup-env: check-uv check-python314t
	@echo "🔧 Setting up free-threading environment..."
	@if command -v python3.14t >/dev/null 2>&1; then \
		echo "✅ Using Python 3.14t (free-threaded)"; \
		uv venv --python python3.14t .venv; \
	else \
		echo "⚠️  Using standard Python (GIL enabled)"; \
		uv venv .venv; \
	fi
	@echo "📥 Installing dependencies..."
	@uv pip install -e ".[dev]"
	@echo ""
	@echo "✅ Environment ready!"
	@echo ""
	@echo "To activate:"
	@echo "  source .venv/bin/activate"
	@echo ""
	@echo "To verify free-threading:"
	@echo "  python -c \"import sys; print('Free-threaded:', hasattr(sys, '_is_gil_enabled'))\""

# Install production dependencies
install: check-uv
	uv pip install -e .

# Install development dependencies
dev: check-uv
	uv pip install -e ".[dev]"

# Install all optional dependencies
all: check-uv
	uv pip install -e ".[all,dev]"

# Run tests (uses venv Python if available)
test:
	@if [ -f .venv/bin/python ]; then \
		.venv/bin/python -m pytest tests/ -v; \
	else \
		$(PYTHON) -m pytest tests/ -v; \
	fi

# Run tests with coverage
test-cov:
	@if [ -f .venv/bin/python ]; then \
		.venv/bin/python -m pytest tests/ -v --cov=sunwell --cov-report=html --cov-report=term; \
	else \
		$(PYTHON) -m pytest tests/ -v --cov=sunwell --cov-report=html --cov-report=term; \
	fi

# Lint code
lint:
	@if [ -f .venv/bin/ruff ]; then \
		.venv/bin/ruff check src/sunwell tests; \
		.venv/bin/python -m mypy src/sunwell; \
	else \
		ruff check src/sunwell tests; \
		mypy src/sunwell; \
	fi

# Format code
format:
	@if [ -f .venv/bin/ruff ]; then \
		.venv/bin/ruff format src/sunwell tests; \
		.venv/bin/ruff check --fix src/sunwell tests; \
	else \
		ruff format src/sunwell tests; \
		ruff check --fix src/sunwell tests; \
	fi

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Build distribution
build: clean
	@if [ -f .venv/bin/python ]; then \
		.venv/bin/python -m build; \
	else \
		$(PYTHON) -m build; \
	fi

# Validate example lenses
validate-lenses:
	sunwell validate lenses/tech-writer.lens
	sunwell validate lenses/code-reviewer.lens
	sunwell validate lenses/base-writer.lens

# Run a quick smoke test
smoke:
	sunwell --help
	sunwell list --path lenses/
	sunwell validate lenses/tech-writer.lens
	@echo "✅ Smoke test passed"

# Apply tech-writer lens with mock model
demo:
	sunwell apply lenses/tech-writer.lens "Write API documentation for a user authentication module" --provider mock -v
