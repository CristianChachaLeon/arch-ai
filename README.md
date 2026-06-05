# archai-mcp

[![PyPI Version](https://img.shields.io/pypi/v/archai-mcp)](https://pypi.org/project/archai-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/archai-mcp)](https://pypi.org/project/archai-mcp/)
[![License](https://img.shields.io/pypi/l/archai-mcp)](https://github.com/CristianChachaLeon/arch-ai/blob/main/LICENSE)

Cognitive Middleware for Architecture-Aware AI Coding Agents.

## Overview

ArchAI is a middleware layer that governs how AI coding agents perceive and reason about software systems. It provides architecture-aware context to agents, reducing context pollution and architectural drift.

## Installation

```bash
# Install from PyPI
pip install archai-mcp

# Or install with uv
uv tool install archai-mcp
```

After installation, the `archai` CLI is available globally.

For MCP integration, add `uvx archai-mcp mcp` to your `.opencode/mcp.json` (see [MCP Integration](#mcp-integration-agents)).

## Quick Start

```bash
# Install
uv sync

# Process a repository
uv run archai start .

# Ask about the architecture
uv run archai ask "how does the login work"
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `archai start [repo_path]` | Process a repository (bootstrap + inference pipeline) |
| `archai ask "query"` | Ask a question about the architecture |
| `archai mcp` | Start MCP server (stdio, for agent integration) |

### Examples

```bash
# Process current directory
archai start

# Process another repo
archai start /path/to/repo

# Ask questions
archai ask "how does the orchestrator work"
archai ask "what constraints does the auth module have"

# JSON output for scripting
archai ask "orchestrator" --json | jq '.focus'
```

### Auto-Cache

`archai ask` automatically runs `archai start` if no cache exists. You never need to run `archai start` manually — but can if you want to pre-process.

## MCP Integration (Agents)

ArchAI exposes 3 MCP tools for AI agents:

| Tool | Description |
|------|-------------|
| `get_architecture_context` | Get context packet for a query |
| `validate_code_change` | Validate changes against constraints |
| `get_blast_radius` | Analyze impact of changing a file |

### Agent Configuration

```json
// .opencode/mcp.json
{
  "mcpServers": {
    "archai": {
      "command": "uvx",
      "args": ["archai-mcp", "mcp"],
      "description": "Architecture-aware context for AI coding agents"
    }
  }
}
```

## Development

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Format code
uv run black src/
uv run ruff check src/
```

## Architecture

See `docs/002-sdd-cli-mcp-architecture.md` for the current architecture spec.

See `docs/001-sdd-mvp-architecture.md` for the original MVP spec (superseded by 002 for CLI/MCP sections).

## License

MIT
