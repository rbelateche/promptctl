.PHONY: install lint fmt typecheck test ci clean

# Install all dev dependencies
install:
	uv pip install --system -e ".[dev]"

# Ruff lint check (mirrors CI)
lint:
	uv run ruff check cli/ core/ evals/ storage/ api/

# Ruff format check (mirrors CI)
fmt:
	uv run ruff format --check cli/ core/ evals/ storage/ api/

# Auto-fix lint + format issues
fix:
	uv run ruff check --fix cli/ core/ evals/ storage/ api/
	uv run ruff format cli/ core/ evals/ storage/ api/

# Mypy type check (mirrors CI)
typecheck:
	uv run mypy cli/ core/ evals/ storage/ api/

# Run tests (mirrors CI)
test:
	uv run pytest tests/ -v --tb=short

# Run everything CI runs, in the same order
ci: lint fmt typecheck test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -f coverage.xml
