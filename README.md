# ArchAI

Cognitive Middleware for Architecture-Aware AI Coding Agents.

## Overview

ArchAI is a middleware layer that governs how AI coding agents perceive and reason about software systems. It provides architecture-aware context to agents, reducing context pollution and architectural drift.

## Quick Start

```bash
# Using Makefile (recommended)
make setup
make run
curl http://localhost:8000/health
```

## Setup

### Option 1: Using Makefile (recommended)

```bash
make setup          # Create venv and install dependencies
make run            # Run the server
```

### Option 2: Manual

```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate it (Linux/Mac)
source .venv/bin/activate

# OR (Windows)
.venv\Scripts\activate

# 3. Install dependencies (including dev tools)
pip install -e ".[dev]"
```

## Development

### Using Makefile (recommended)

```bash
make test           # Run tests
make test-cov      # Run tests with coverage
make format        # Format code (black + ruff)
make lint          # Run ruff linter
make type-check   # Run mypy type checker
make clean         # Remove cache files
```

### Manual commands

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Format code (black + ruff)
black src/
ruff check src/

# Check types (mypy)
mypy src/
```

## Running the Server

```bash
make run
# or manually:
source .venv/bin/activate
uvicorn archai.http.main:app --reload --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

## Architecture

See `docs/001-sdd-mvp-architecture.md` for detailed specifications.

## License

MIT