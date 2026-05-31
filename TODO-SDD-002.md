# TODO: SDD-002 Implementation

> Sprint: 1 hour | Branch: `feat/sdd-002-cli-mcp`

---

## Phase 1: CLI (typer) — 30 min

- [ ] T-100: Add `typer[all]>=0.9` and `rich>=13.0` to `pyproject.toml`
- [ ] T-101: Create `src/archai/cli/__init__.py`
- [ ] T-102: Create `src/archai/cli/app.py` — typer app with `start`, `ask`, `mcp` commands
- [ ] T-103: Create `src/archai/cli/output.py` — format output (human-readable tables + `--json` flag)
- [ ] T-104: Implement `archai start` — wraps existing `middleware/pipeline.py`
- [ ] T-105: Implement `archai ask` — auto-cache check, calls orchestrator, formats output
- [ ] T-106: Add `[project.scripts]` entry point in `pyproject.toml`

## Phase 2: MCP Server — 20 min

- [ ] T-110: Add `mcp>=1.0` to optional deps in `pyproject.toml`
- [ ] T-111: Create `src/archai/mcp_server.py` — MCP server with stdio transport
- [ ] T-112: Implement `get_architecture_context` tool
- [ ] T-113: Implement `validate_code_change` tool
- [ ] T-114: Implement `get_blast_radius` tool

## Phase 3: Cleanup — 10 min

- [ ] T-120: Remove `fastapi` and `uvicorn` from dependencies
- [ ] T-121: Remove `src/archai/http/` directory
- [ ] T-122: Update imports that referenced `archai.http`
- [ ] T-123: Remove HTTP-related tests (or update them)
- [ ] T-124: Run full test suite — ensure 237 tests pass (or updated count)

## Validation — after each phase

- [ ] `uv run archai --help` works
- [ ] `uv run archai start` processes repo
- [ ] `uv run archai ask "test query"` returns context
- [ ] `uv run archai mcp` starts (verify with MCP inspector or manual stdio test)
- [ ] All tests green

---

## Notes

- Core Logic (orchestrator, bootstrap, inference, middleware) is **NOT touched**
- `archai ask` auto-runs `archai start` if no cache
- CLI outputs human-readable by default, `--json` for scripting
- MCP outputs JSON only
- FastAPI is **removed**, not optional
