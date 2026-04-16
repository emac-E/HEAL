.PHONY: help test test-imports lint format type-check quality-checks install clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	uv sync --extra dev

test: ## Run all tests
	uv run pytest tests/ -v

test-imports: ## Run import tests only
	uv run pytest tests/test_imports.py -v

test-cov: ## Run tests with coverage report
	uv run pytest tests/ --cov=heal --cov-report=term-missing --cov-report=html

format: ## Format code with black
	uv run black src/ tests/

lint: ## Check code with ruff
	uv run ruff check src/ tests/

type-check: ## Type check with mypy
	uv run mypy src/

quality-checks: format lint type-check ## Run all quality checks
	@echo "✅ All quality checks complete"

clean: ## Clean up generated files
	rm -rf .venv/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
