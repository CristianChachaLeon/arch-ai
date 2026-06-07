# Changelog

## 0.5.0 (2026-06-07)

- **Renamed `archai mcp` → `archai serve`** — `mcp` kept as deprecated alias
- `archai init` now generates `["archai", "serve"]` in `.opencode.json`

## 0.4.0 (2026-06-07)

- **Multi-language support** — SDD-004: AST parsing for Python and C/C++ via tree-sitter
- **Intra-file clustering** — function-level dependency resolution for C/C++
- Cross-language unresolved imports normalized to `external` marker

## 0.3.3 (2026-06-06)

- Removed `LiteLLMProvider` and `litellm` dependency completely
- Cleaned up leftover `.opencode/mcp.json` file

## 0.3.2 (2026-06-06)

- Moved `litellm` and `python-dotenv` from core dependencies to dev dependencies

## 0.3.1 (2026-06-06)

- Added `--version` flag to CLI
- Suppressed litellm startup warnings

## 0.3.0 (2026-06-06)

- **Agent-native architecture** — SDD-003: removed CLI dependency, archai runs exclusively as MCP server
- **Focus resolution** — maps user query to a specific subsystem via LLM
- **Semantic cluster labeling** — names and describes clusters using a configurable LLM model
- **Constraint inference** — extracts architecture rules from cluster structure
- **Context resolution** — caching layer with API endpoint for architecture context packets
- **Blast radius** — `POST /blast-radius` endpoint for dependency impact analysis
- **Change validation** — `POST /validate-change` endpoint for structural compliance checks
- Cluster-aware test file detection and context injection
- `.env` auto-loading via `python-dotenv`

## 0.2.0 (2026-06-01)

- **CLI + MCP architecture** — SDD-002: Typer CLI with `start`, `ask`, `mcp` commands
- MCP server exposing 3 tools (architecture context, blast radius, validate change)
- LLM JSON response sanitization for malformed output

## 0.1.0 (2026-06-05)

- Package renamed to `archai-mcp` and prepared for PyPI publishing
- **OpenCode MCP integration** — `archai init` generates project-level `.opencode.json`
- LLM provider auto-detection from OpenCode config and environment variables
- Interactive LLM provider selection during init (`--interactive` flag)
- CI/CD pipeline for automated PyPI publishing
