# Changelog

## [0.4.5] - 2026-06-13

### Added
- Persistent disk cache for analysis results (`/tmp/archai_cache/`)
- `--force` flag on `analyze` CLI to bypass all caches
- SHA-256 based cache keys for repo path + context

## 0.4.4 (2026-06-13)

- **New CLI command `archai context <query>`** — wraps `get_architecture_context` MCP tool (Fase 1.1 del roadmap)
- **Cleanup and fixes** — removed `plan` CLI (duplicaba `get_architecture_context`), refactored `validate` output, fixed misleading shared state dump in `trace`
- **Coverage boost** — `cli/app.py` 76%→93%, `orchestrator/orchestrator.py` 79%→96%, overall 86%→94%
- **49 new tests** (372→421 total)
- Fixed `json.loads` unprotected call in `context` command (JSONDecodeError handling)
- Fixed `__version__` in `__init__.py` from stale `0.1.0` to `0.4.4`

## 0.4.3 (2026-06-10)

- **`archai state` now shows Writers/Readers** — wired existing `_extract_var_access()` through all 4 layers (c_handler → ParsedFile → FileNode → SharedVariable) to populate function names instead of dashes
- Fixed `test_pipeline.py` unused variable warning

## 0.5.0 (2026-06-07)

- **New MCP tool `get_file_detail`** — detailed per-file analysis (functions, classes, imports, dependents)
- **New CLI command `archai file <path>`** — same analysis from terminal
- Fixed pipeline not passing `functions_detail` to FileNode (functions now show in analysis)
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
