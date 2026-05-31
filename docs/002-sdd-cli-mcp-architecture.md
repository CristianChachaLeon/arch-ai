# SDD-002: CLI + MCP Architecture (Replace FastAPI)

## Overview

| Item | Detail |
|------|--------|
| **Project** | ArchAI |
| **Version** | 0.2.0 |
| **Status** | Accepted |
| **Date** | 2026-05-30 |
| **Supersedes** | Sections of 001-sdd related to HTTP Service |

---

## 1. Motivation

The original MVP (001-sdd) defined ArchAI as a **FastAPI HTTP server** that exposes endpoints for context, validation, and blast radius analysis. This design has three problems:

1. **Unnecessary complexity for local use**: A server requires process management (keep-alive, port allocation, startup/shutdown). For a tool that runs locally, this adds friction without benefit.

2. **Two servers for agent integration**: Agents (OpenCode, Claude Code, Cline) use MCP (Model Context Protocol) to discover and call tools. With FastAPI as the main interface, we'd need a **second** MCP server that proxies to FastAPI — doubling the process count and complexity.

3. **UX mismatch**: Humans don't call `curl POST /validate-change` — they run commands. Agents don't call `curl` — they call MCP tools. FastAPI serves neither audience well.

**Decision**: Replace FastAPI entirely with a **CLI** (for humans) and an **MCP Server** (for agents). FastAPI is **removed** — not optional, not deprecated, **gone**. The Core Logic (orchestrator, graph, LLM, models) remains unchanged.

---

## 2. Architecture

### 2.1 System Context (New)

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARCHAI SYSTEM                             │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │   Human     │──▶ CLI (typer)                                 │
│  │  (terminal) │    ├── archai start [repo]                     │
│  └─────────────┘    └── archai ask "query" [--repo path]        │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │   Agent     │──▶ MCP Server (stdio)                          │
│  │  (OpenCode) │    ├── get_architecture_context                │
│  └─────────────┘    ├── validate_code_change                    │
│                      └── get_blast_radius                       │
│                                                                  │
│                    ┌──────────────────────┐                      │
│                    │     Core Logic       │                      │
│                    │  (orchestrator,      │                      │
│                    │   graph, LLM,        │                      │
│                    │   models, config)    │                      │
│                    └──────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Mapping

| Component (001-sdd) | New Component | Change |
|---------------------|---------------|--------|
| HTTP Service (FastAPI) | CLI (typer) | **Replaced** — primary human interface |
| HTTP Service (FastAPI) | MCP Server (mcp lib) | **Replaced** — primary agent interface |
| HTTP Service (FastAPI) | — | **Removed** — no HTTP server |
| Context Orchestrator | Core Logic | **Unchanged** |
| Bootstrapping Engine | Core Logic | **Unchanged** |
| Inference Engine | Core Logic | **Unchanged** |
| Agent Integration | MCP Tools | **Changed** — now uses MCP protocol |
| Visualization UI | Deferred | **Unchanged** — post-MVP |

### 2.3 Security Model

| Interface | Security Model | repo_path Validation |
|-----------|---------------|---------------------|
| **CLI** | Inherited from OS user — the user can already access any file | Optional (`--repo` flag). CLI trusts the user. |
| **MCP** | Agent calls MCP tools — the agent is running as the user | **Required** — MCP validates repo_path against cwd |

The `validate_repo_path` guard exists in `config.py` and is used by MCP tools. The CLI does NOT use it — if you can run a command, you already have access to the file system.

---

## 3. CLI Interface

### 3.1 Commands

```bash
# Start ArchAI (bootstrap + inference pipeline)
archai start [repo_path]
# Default: cwd. Optional --repo for other directories.

# Ask about the architecture
# Automatically runs archai start if no cache exists
archai ask "query" [repo_path]
# Default: cwd. Optional --repo for other directories.

# MCP server mode (stdio, for agent integration)
archai mcp
```

**Auto-cache behavior**: `archai ask` checks for `.archai/cache.json`. If missing or stale (hash mismatch), it transparently runs `archai start` before answering. The user never needs to run `archai start` manually — but can if they want to pre-process.

### 3.2 Human Workflow

```bash
# 1. Navigate to project
cd /home/user/my-project

# 2. Ask questions — archai handles everything automatically
archai ask "how does the login work"
# → First run: auto-bootstraps, caches, then answers
# → Subsequent runs: uses cache instantly

archai ask "which files do I need to touch to add an endpoint"
archai ask "what constraints does the auth module have"

# Optional: pre-process if you want to warm the cache
archai start
```

### 3.3 What is NOT in the CLI

These commands do **not** exist in the CLI because they are agent-facing:

- `archai validate` → replaced by MCP tool `validate_code_change`
- `archai blast-radius` → replaced by MCP tool `get_blast_radius`

**Rationale**: A human never manually validates a change. The agent validates automatically before applying code.

### 3.4 Output Format

Each interface outputs in the format most useful for its audience:

| Interface | Format | Reason |
|-----------|--------|--------|
| **CLI** (`archai ask`) | Human-readable tables, colors, rich text | Humans read terminal output |
| **CLI** (`archai ask --json`) | JSON | Scripting and piping (`jq`, etc.) |
| **MCP** (agent tools) | JSON | Agents consume structured data |

```bash
# Human-friendly output (default)
archai ask "how does the login work"
# → Formatted table with focus, constraints, relevant files

# JSON output for scripting
archai ask "how does the login work" --json | jq '.focus'
```

---

## 4. MCP Interface

### 4.1 MCP Tools

| Tool | Description | When Agent Calls |
|------|-------------|-----------------|
| `get_architecture_context` | Get context packet for a query | Before writing code — needs to understand the subsystem |
| `validate_code_change` | Validate proposed changes against constraints | **Automatically** before applying changes |
| `get_blast_radius` | Analyze impact of changing a file | **Automatically** before applying changes — to warn about side effects |

### 4.2 Agent Workflow (Automatic)

```
1. Human: "Add a login endpoint in auth"
2. Agent: calls get_architecture_context("login auth")
   → receives: "auth is in src/api/auth/, async_only, no blocking I/O"
3. Agent: writes code respecting constraints
4. Agent: calls validate_code_change(file="src/api/auth/login.py", patch="...")
   → receives: valid=True, no violations
5. Agent: calls get_blast_radius(file="src/api/auth/login.py")
   → receives: "would affect src/api/routes.py, src/tests/test_auth.py"
6. Agent: applies the change
7. Human: code is done ✅
```

### 4.3 MCP Server Implementation

```
src/archai/mcp_server.py  (~60 lines)

- Uses `mcp` library with stdio transport
- Each tool maps to Core Logic functions
- No HTTP involved — agent reads JSON from stdin, writes to stdout
```

### 4.4 Agent Configuration

```json
// .opencode/mcp.json
{
  "mcpServers": {
    "archai": {
      "command": "uv",
      "args": ["run", "archai", "mcp"]
    }
  }
}
```

---

## 5. Core Logic (Unchanged)

The following modules are **NOT modified** by this SDD:

| Module | Responsibility |
|--------|---------------|
| `orchestrator/orchestrator.py` | Focus resolution, subgraph extraction, constraint injection |
| `middleware/pipeline.py` | Bootstrap + inference pipeline with caching |
| `inference/llm.py` | LLM provider abstraction (LiteLLM) |
| `inference/labeler.py` | Semantic labeling for clusters |
| `inference/constraint_inferrer.py` | Constraint inference from LLM |
| `bootstrap/` | File discovery, AST parsing, graph building |
| `models/` | Pydantic models for architecture |
| `config.py` | detect_repo_root(), validate_repo_path() |
| `http/models.py` | Request/response models (become CLI output models) |

---

## 6. File Structure (New)

```
src/archai/
├── cli/                    # NEW — CLI interface
│   ├── __init__.py
│   ├── app.py              # Typer app with commands
│   └── output.py           # Format output for terminal (JSON, tables)
│
├── mcp_server.py           # NEW — MCP server (stdio)
│
├── orchestrator/           # UNCHANGED
├── middleware/              # UNCHANGED
├── inference/              # UNCHANGED
├── bootstrap/              # UNCHANGED
└── config.py               # UNCHANGED
```

---

## 7. Dependency Changes

```toml
# pyproject.toml

[project]
dependencies = [
    # ... existing ...
    "typer[all]>=0.9",        # NEW — CLI framework
    "rich>=13.0",              # NEW — terminal formatting
]

[project.optional-dependencies]
mcp = [
    "mcp>=1.0",               # NEW — MCP protocol
]

[project.scripts]
archai = "archai.cli.app:app"  # NEW — CLI entry point
```

---

## 8. Migration Plan

### Phase 1: CLI (this SDD)

1. Create `src/archai/cli/app.py` with typer
2. Add `archai start` and `archai ask` commands
3. Update `pyproject.toml` with CLI deps and entry point
4. Remove FastAPI and http/ module

### Phase 2: MCP Server (this SDD)

1. Create `src/archai/mcp_server.py`
2. Implement 3 MCP tools using Core Logic directly
3. Add `.opencode/mcp.json` configuration
4. Test with OpenCode

### Phase 3: Cleanup

1. Remove `src/archai/http/` directory
2. Remove FastAPI and uvicorn from dependencies
3. Update imports across the codebase
4. Remove HTTP-related tests

---

## 9. What Changes vs 001-sdd

| 001-sdd Design | 002-sdd Design | Impact |
|----------------|----------------|--------|
| FastAPI is the primary interface | CLI is primary for humans | Humans get better UX |
| Agent calls HTTP endpoints | Agent calls MCP tools | Standard protocol, any agent works |
| `validate` and `blast-radius` are HTTP endpoints | `validate` and `blast-radius` are MCP-only | Humans don't need them |
| `repo_path` always validated | CLI trusts user, MCP validates | Less friction for humans |
| 2 processes (FastAPI + MCP) | 1 process (MCP) or 0 (CLI) | Simpler ops |
| FastAPI exists as optional `archai serve` | FastAPI removed entirely | Less code to maintain |

---

## 10. Open Questions (RESOLVED)

| ID | Question | Decision |
|----|----------|----------|
| OQ-001 | Cache persistence? | **Yes** — `archai start` writes `.archai/cache.json` with hash-based invalidation. Subsequent `archai ask` calls skip re-processing. |
| OQ-002 | Auto-process on `archai ask`? | **Yes** — if no cache exists, `archai ask` transparently runs `archai start` first. |
| OQ-003 | Output format? | **Interface-specific**: CLI outputs human-readable tables/text. MCP outputs JSON. `archai ask --json` available for scripting. |

---

## 11. Success Criteria

- [ ] `archai start` processes a repo and caches results
- [ ] `archai ask "query"` returns architecture context without specifying repo
- [ ] `archai ask "query" --repo /other/path` works for other repos
- [ ] `archai ask "query" --json` outputs machine-readable JSON
- [ ] `archai mcp` starts MCP server and exposes 3 tools
- [ ] OpenCode discovers and calls ArchAI MCP tools
- [ ] Agent can validate changes and get blast radius automatically
- [ ] All 237 existing tests pass
- [ ] FastAPI and http/ module removed from codebase

---

## 12. Post-MVP: Real-Time Architecture Visualization

### 12.1 Motivation

When an AI agent is working on a codebase, the human has no visibility into what the agent is doing at an architectural level. The agent modifies files, but the human can't see which subsystem is being touched, what the blast radius looks like in real time, or whether constraints are being respected.

**Goal**: A web-based dashboard that visualizes the architecture graph and highlights, in real time, which modules and files the AI agent is currently modifying.

### 12.2 Features

| Feature | Description |
|---------|-------------|
| **Architecture Graph** | Interactive web view of subsystems and file dependencies |
| **Real-Time Highlighting** | Glowing/highlighted nodes showing what the agent is touching RIGHT NOW |
| **Constraint Overlay** | Visual indicators when the agent approaches or violates constraints |
| **Blast Radius Pulse** | Animated expansion showing affected files before changes are applied |
| **History Trail** | Faded trail of previously modified files during the session |

### 12.3 Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React + React Flow |
| Real-Time | WebSocket (agent pushes events) |
| State | Zustand |
| Integration | Agent emits events via MCP or sidecar |

### 12.4 Agent Event Protocol

The agent emits structured events that the dashboard consumes:

```json
{
  "type": "file_modified",
  "file": "src/api/auth/login.py",
  "subsystem": "auth",
  "action": "create",
  "timestamp": "2026-05-30T10:00:00Z"
}
```

```json
{
  "type": "constraint_check",
  "file": "src/api/auth/login.py",
  "constraints_valid": true,
  "violations": []
}
```

```json
{
  "type": "blast_radius",
  "file": "src/api/auth/login.py",
  "affected_files": ["src/api/routes.py", "tests/test_auth.py"],
  "affected_subsystems": ["auth", "api"]
}
```

### 12.5 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  WEB DASHBOARD (React + React Flow)                         │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │   ┌──────┐    ┌──────┐    ┌──────────┐              │  │
│  │   │ auth │════│ api  │════│ payment  │  ← highlight  │  │
│  │   └──┬───┘    └──────┘    └──────────┘    = active   │  │
│  │      │                                                 │  │
│  │      ▼                                                 │  │
│  │   ┌──────┐                                             │  │
│  │   │ db   │                                             │  │
│  │   └──────┘                                             │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Activity Feed                                        │  │
│  │  10:00:01 → auth/login.py created                     │  │
│  │  10:00:03 → auth/models.py modified                   │  │
│  │  10:00:05 → blast radius: routes.py, test_auth.py     │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ARCHAI CORE                                                │
│  - MCP Server emits events during tool execution            │
│  - Or: sidecar process monitors agent file changes          │
└─────────────────────────────────────────────────────────────┘
```

### 12.6 Launch Command

```bash
archai dashboard [--port 3000]
# Opens web dashboard, listens for agent events
```

### 12.7 Status

**Post-MVP** — This feature is deferred until the core CLI + MCP pipeline is stable and working end-to-end. It provides significant UX value but is not required to validate the core hypothesis (architecture-governed context improves agent coherence).
