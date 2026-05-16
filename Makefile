.PHONY: help setup install test test-cov format lint type-check clean run

help:
	@echo "ArchAI - Available commands:"
	@echo ""
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make install   - Install dependencies (if venv already exists)"
	@echo "  make test      - Run tests"
	@echo "  make test-cov  - Run tests with coverage report"
	@echo "  make format    - Format code with black and ruff"
	@echo "  make lint      - Run ruff linter"
	@echo "  make type-check - Run mypy type checker"
	@echo "  make clean    - Remove cache files and coverage data"
	@echo "  make run      - Run the FastAPI server"
	@echo ""
	@echo "  source .venv/bin/activate  - Activate virtual environment"

setup:
	@if [ -d ".venv" ]; then \
		echo "Virtual environment already exists at .venv"; \
		echo "Activate with: source .venv/bin/activate"; \
	else \
		python3 -m venv .venv && \
		.venv/bin/pip install -e ".[dev]" && \
		echo "Setup complete! Activate with: source .venv/bin/activate"; \
	fi

install:
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest

test-cov:
	.venv/bin/pytest --cov=src --cov-report=html --cov-report=term

format:
	.venv/bin/black src/
	.venv/bin/ruff check src/ --fix

lint:
	.venv/bin/ruff check src/

type-check:
	.venv/bin/mypy src/

clean:
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

run:
	.venv/bin/uvicorn src.archai.http.main:app --reload --host 0.0.0.0 --port 8000