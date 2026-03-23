.PHONY: test lint format coverage security clean install

# Install package and dev dependencies
install:
	pip install -e ".[dev]"
	pip install pytest-cov hypothesis ruff mypy pytest-asyncio anyio rich httpx

# Run the full test suite
test:
	python -m pytest -v --tb=short

# Run tests with coverage report
coverage:
	python -m pytest --cov=traceagent --cov-report=term-missing --cov-fail-under=90

# Lint with ruff
lint:
	python -m ruff check src/ tests/

# Format with ruff
format:
	python -m ruff format src/ tests/
	python -m ruff check --fix src/ tests/

# Type-check with mypy
typecheck:
	python -m mypy src/ --ignore-missing-imports

# Run all examples to verify they work
examples:
	python examples/basic_tracing.py
	python examples/decorator_usage.py
	python examples/file_storage_dashboard.py

# Remove bytecode and build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache dist build *.egg-info .coverage htmlcov

# Run all checks (CI equivalent)
check: lint coverage
