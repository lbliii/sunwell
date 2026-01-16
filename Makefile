.PHONY: install dev test lint format clean build

# Install production dependencies
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"

# Install all optional dependencies
all:
	pip install -e ".[all,dev]"

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=sunwell --cov-report=html --cov-report=term

# Lint code
lint:
	ruff check src/sunwell tests
	mypy src/sunwell

# Format code
format:
	ruff format src/sunwell tests
	ruff check --fix src/sunwell tests

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
	python -m build

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
