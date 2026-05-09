.PHONY: install lint fmt typecheck test ci clean

PYTHON  = .venv/bin/python
UV      = .venv/bin/uv
SRCDIRS = cli/ core/ evals/ storage/ api/

# Create venv and install all dev dependencies
install:
	python3 -m venv .venv
	$(PYTHON) -m pip install uv -q
	$(UV) pip install -e ".[dev]" -q

# Ruff lint check (mirrors CI)
lint:
	$(UV) run ruff check $(SRCDIRS)

# Ruff format check (mirrors CI)
fmt:
	$(UV) run ruff format --check $(SRCDIRS)

# Auto-fix lint + format issues
fix:
	$(UV) run ruff check --fix $(SRCDIRS)
	$(UV) run ruff format $(SRCDIRS)

# Mypy type check (mirrors CI)
typecheck:
	$(UV) run mypy $(SRCDIRS)

# Run tests (mirrors CI); exit 5 = no tests collected, treated as pass
test:
	$(UV) run pytest tests/ -v --tb=short; e=$$?; [ $$e -eq 0 ] || [ $$e -eq 5 ]

# Run everything CI runs, in the same order
ci: lint fmt typecheck test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -f coverage.xml
