# SDD-003: Agent-Native Architecture (archai as a Structural Engine)

## Overview

| Item | Detail |
|------|--------|
| **Project** | ArchAI |
| **Version** | 0.3.0 |
| **Status** | Accepted |
| **Date** | 2026-06-06 |
| **Supersedes** | Sections of 002-sdd related to CLI commands and MCP/LLM integration |
| **Removes** | `archai start`, `archai ask` CLI commands entirely |

---

## 1. Motivation

### 1.1 The Problem

The current architecture (002-sdd) defines archai as a dual-interface system:

```
CLI (typer)          MCP Server
  ├── archai start     ├── get_architecture_context
  ├── archai ask       ├── validate_code_change
  └── archai init      └── get_blast_radius
```

The MCP Server **always** initializes an internal LLM (LiteLLMProvider) to semantically label clusters and infer architecture constraints. This has three fundamental problems:

#### 1.1.1 Double LLM Call

When OpenCode uses archai:

```
OpenCode Agent                    archai MCP
    │                                  │
    │  get_architecture_context()      │
    │─────────────────────────────────►│
    │                                  ├─ Bootstrap (static) ✅
    │                                  ├─ Clustering (heuristic) ✅
    │                                  ├─ CALLS ITS OWN LLM 🔥
    │                                  │  → "name these clusters"
    │                                  │  → API call to Anthropic/OpenAI
    │                                  │  → latency + cost
    │    JSON with labels             │
    │◄──────────────────────────────── │
    │                                  │
    │  (OpenCode USES ITS OWN LLM     │
    │   to understand the JSON)       │  ← DOUBLE LLM CALL!
```

**Two LLM calls for a single task — one call could do it better.**

#### 1.1.2 Context-Free Inference

archai's LLM labels clusters **without knowing what the user is doing**. It looks at files and generically says "this is an API layer."

OpenCode, on the other hand, KNOWS the context: *"the user asked me to add a login endpoint."* It can name clusters and infer constraints **based on what's being built**, not in isolation.

#### 1.1.3 Configuration Friction

Currently the user needs:

1. `ARCHAI_LLM_MODEL` or API keys configured
2. archai to have its own LLM access
3. Two LLM systems to configure (OpenCode + archai)

For a static analysis tool, this is noise that shouldn't exist.

### 1.2 The Correct Direction

```
OpenCode Agent                    archai MCP
    │                                  │
    │  get_architecture_context()      │
    │─────────────────────────────────►│
    │                                  ├─ Bootstrap (static) ✅
    │                                  ├─ Clustering (heuristic) ✅
    │                                  │  ─── NO LLM ───
    │    PURE STRUCTURAL JSON          │
    │◄──────────────────────────────── │
    │                                  │
    │  (OpenCode uses ITS LLM to      │
    │   infer names, constraints,      │
    │   and validate changes)          │  ← SINGLE LLM CALL
```

**archai becomes a pure structural analysis engine.** No LLM needed, no API keys, no model configuration. Its job:

1. **Discover** files and parse their AST
2. **Build** the dependency graph
3. **Cluster** into cohesive subsystems
4. **Resolve** focus (which cluster matches a query)
5. **Compute** blast radius
6. **Expose** everything as structured data via MCP

**OpenCode (its agent + LLM) handles the rest:**

1. Interpret clusters and name them semantically
2. Infer architecture constraints
3. Validate changes against those constraints
4. Decide the order of operations

### 1.3 Why `start` and `ask` Must Go — Not Just Hidden

The `start` and `ask` commands exist so a **human** can use archai from the terminal. But:

- **archai is an MCP server.** Its sole purpose is to serve tools to an AI agent.
- Nobody runs MCP tool endpoints manually. That's like calling `curl POST /api/tool` because you want to inspect a function — it makes no sense.
- `archai start` produces JSON that a human doesn't read.
- `archai ask` returns context packets designed for agent consumption.
- Both were designed when archai had an HTTP API and the human was the primary user.

**The consumer today — and always — is the agent.** Keeping `start` and `ask` "for debugging" is a mistake: they add maintenance burden, confuse the CLI surface, and send the wrong message about what archai is.

**Decision**: `start` and `ask` are **removed entirely**, not hidden, not deprecated. archai becomes:

```
archai init    → Configure the project for OpenCode
archai mcp     → MCP server (called by OpenCode automatically)
```

Two commands. That's the entire product surface.

---

## 2. Architecture

### 2.1 System Context (New)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ARCHAI ARCHITECTURE v0.3.0                      │
│                                                                      │
│  ┌─────────────────────────────────────┐                             │
│  │  Human                             │                             │
│  │  $ pip install archai-mcp          │                             │
│  │  $ cd my-project                   │                             │
│  │  $ archai init                     │                             │
│  │  $ opencode .                      │                             │
│  └──────────┬──────────────────────────┘                             │
│             │                                                        │
│             ▼                                                        │
│  ┌─────────────────────────────────────┐                             │
│  │  OpenCode Agent                     │                             │
│  │  (with its own LLM)                │                             │
│  │                                     │                             │
│  │  1. get_architecture_context()     │                             │
│  │     ← clusters + dependencies      │                             │
│  │     → ITS LLM: "this is auth, async"│                             │
│  │                                     │                             │
│  │  2. Writes code                    │                             │
│  │                                     │                             │
│  │  3. get_blast_radius()             │                             │
│  │     ← dependents + subsystems      │                             │
│  │     → ITS LLM: "safe change"       │                             │
│  └──────────┬──────────────────────────┘                             │
│             │                                                        │
│             │  MCP stdio                                             │
│             ▼                                                        │
│  ┌─────────────────────────────────────┐                             │
│  │  archai MCP Server                  │                             │
│  │  (no LLM, no API keys)             │                             │
│  │                                     │                             │
│  │  ┌───────────────────────────────┐  │                             │
│  │  │  Core Engine (unchanged)      │  │                             │
│  │  │  - bootstrap → graph          │  │                             │
│  │  │  - clustering                 │  │                             │
│  │  │  - focus resolution           │  │                             │
│  │  │  - blast radius               │  │                             │
│  │  │  - cache                      │  │                             │
│  │  └───────────────────────────────┘  │                             │
│  └─────────────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Design Principles

| Principle | Implication |
|-----------|-------------|
| **Zero LLM in MCP** | The MCP server never initializes an LLM. OpenCode's agent uses its own. |
| **Rich data, not decisions** | archai returns raw structure (clusters, edges, dependencies). The agent decides. |
| **Zero LLM configuration** | No more `ARCHAI_LLM_MODEL`, no more API keys for archai. `pip install && archai init && done`. |
| **`litellm` stays in core** | Not removed — useful if someone uses archai's core library directly. But the MCP server doesn't touch it. |
| **Product surface: init + mcp** | Two commands. `start`/`ask` removed entirely — archai is an MCP server, not a CLI tool for humans. |
| **No rigid rules on OpenCode side** | No special OpenCode configuration needed. The agent's LLM processes the data naturally. |

### 2.3 Agent Flow (Automatic, Zero Configuration)

When a user requests a change in OpenCode:

```
User: "Add a login endpoint in the auth module"

OpenCode Agent:
  1. get_architecture_context("auth", repo_path)
     ← focus_cluster: "cluster_2"
     ← focus_files: ["src/auth/login.py", "src/auth/tokens.py"]
     ← all_clusters: {cluster_1: [db/...], cluster_2: [auth/...], cluster_3: [api/...]}
     ← cluster_edges: [{from: "cluster_2", to: "cluster_1"}, {from: "cluster_3", to: "cluster_2"}]
     ← file_dependencies: {"src/auth/login.py": ["src/db/models.py"]}

  2. ITS LLM processes:
     "cluster_2 has auth files, depends on cluster_1 (db).
      It's an authentication module → async operations, no blocking I/O.
      cluster_3 (API) depends on auth → if I change auth's interface, I affect API."

  3. Writes code respecting inferences

  4. get_blast_radius("src/auth/login.py", repo_path, depth=2)
     ← direct_dependents: ["src/api/routes.py"]
     ← transitive_dependents: [...]
     ← subsystems_affected: {"API": 2, "tests": 3}

  5. ITS LLM processes:
     "The change affects API routes and tests. That's expected —
      API already depends on auth. No breaking changes."

  6. Applies the change ✅
```

**All of this happens with zero user configuration.** The OpenCode agent already has reasoning capabilities — it just needs the right data.

---

## 3. MCP Interface (Changes)

### 3.1 Tool: `get_architecture_context`

**Before (v0.2.0):**

```json
{
  "focus": "Authentication Module",
  "focus_reasoning": "Files related to authentication",
  "constraints": { "async_only": true },
  "subgraph": ["src/auth/login.py"],
  "relevant_files": [{"path": "src/auth/login.py", "reason": "focus", "importance": 1.0}],
  "metadata": { "cluster_count": 3 }
}
```

**After (v0.3.0):**

```json
{
  "focus_cluster": "cluster_2",
  "focus_files": ["src/auth/login.py", "src/auth/tokens.py", "src/auth/register.py"],
  "focus_reasoning": "Query matched files in cluster_2",
  "all_clusters": {
    "cluster_1": ["src/db/models.py", "src/db/repository.py", "src/db/migrations.py"],
    "cluster_2": ["src/auth/login.py", "src/auth/tokens.py", "src/auth/register.py"],
    "cluster_3": ["src/api/routes.py", "src/api/middleware.py", "src/api/handlers.py"],
    "cluster_4": ["src/config/settings.py", "src/config/logging.py"]
  },
  "cluster_edges": [
    {"from": "cluster_3", "to": "cluster_2"},
    {"from": "cluster_3", "to": "cluster_1"},
    {"from": "cluster_3", "to": "cluster_4"},
    {"from": "cluster_2", "to": "cluster_1"},
    {"from": "cluster_2", "to": "cluster_4"}
  ],
  "file_dependencies": {
    "src/api/routes.py": ["src/auth/login.py", "src/db/models.py", "src/config/settings.py"],
    "src/auth/login.py": ["src/db/models.py", "src/config/settings.py"]
  },
  "test_files": ["tests/test_auth.py", "tests/test_routes.py"],
  "metadata": {
    "cluster_count": 4,
    "file_count": 12,
    "edge_count": 5
  }
}
```

**Removed from response:**

- `focus` (semantic string) → replaced by `focus_cluster` + `focus_files`
- `constraints` → OpenCode infers from the data
- `relevant_files` → replaced by `focus_files` + `test_files`
- `subgraph` → implicit in `focus_files` + `test_files`

**Rationale**:

- The agent needs to see ALL clusters to understand the full landscape
- Cluster edges reveal the layered architecture
- Per-file dependencies enable granular validation
- The agent's LLM infers constraints better because it has context

### 3.2 Tool: `validate_code_change`

**Before (v0.2.0):**

```json
{
  "valid": true,
  "violations": []
}
```

(Always empty without LLM — no constraints to validate against)

**After (v0.3.0):**

```json
{
  "file_cluster": "cluster_2",
  "cluster_files": ["src/auth/login.py", "src/auth/tokens.py"],
  "cluster_dependencies": {
    "imports_from_cluster": ["cluster_1", "cluster_4"],
    "imported_by_clusters": ["cluster_3"]
  },
  "file_dependencies": {
    "src/auth/login.py": ["src/db/models.py"]
  },
  "new_imports_in_patch": ["src/db/models.py"],
  "patch_summary": {
    "files_changed": ["src/auth/login.py"],
    "new_imports": ["src/db/models.py"],
    "new_functions": ["login_user"],
    "existing_functions_modified": []
  }
}
```

**Rationale**: Without an LLM, archai cannot decide whether a change is valid. But it CAN return all the structural information needed for the agent to decide. The agent (with its LLM + user context) can reason:

> *"login_user in auth/login.py imports from db/models.py — that's fine because auth already depends on db. No new cross-cluster dependencies. The change is safe."*

### 3.3 Tool: `get_blast_radius`

**Unchanged.** This tool is already purely structural. It stays identical.

```json
{
  "focus_file": "src/auth/login.py",
  "direct_dependents": ["src/api/routes.py"],
  "direct_dependencies": ["src/db/models.py", "src/config/settings.py"],
  "transitive_dependents": ["src/api/handlers.py", "tests/test_auth.py"],
  "subsystems_affected": {
    "API": 2,
    "tests": 1
  }
}
```

### 3.4 MCP Changes Summary

| Tool | Change |
|------|--------|
| `get_architecture_context` | **New response**: returns `all_clusters`, `cluster_edges`, `file_dependencies`. Removes semantic `focus` and `constraints`. |
| `validate_code_change` | **New response**: returns structural data about the change. Doesn't decide valid/invalid — the agent decides. |
| `get_blast_radius` | **Unchanged** |

---

## 4. CLI Interface (Changes)

### 4.1 Commands

```
BEFORE (v0.2.0):                    AFTER (v0.3.0):
  archai [OPTIONS] COMMAND            archai [OPTIONS] COMMAND

  Commands:                           Commands:
    start   Process a repository        mcp     MCP server mode
    ask     Ask a question              init    Initialize project
    mcp     MCP server mode           (removed)
    init    Initialize project           start   (removed)
                                         ask     (removed)
```

- `archai start` → **Removed**. archai is an MCP server — humans don't call tools.
- `archai ask` → **Removed**. Only agents consume architecture context.
- `archai init` → **Kept**. The user's entry point.
- `archai mcp` → **Kept**. The interface for OpenCode.

The CLI output module (`cli/output.py`) is also removed — no human-facing output is needed.

### 4.2 `archai init` — Simplified Behavior

No more LLM auto-detection, no `ARCHAI_LLM_MODEL`, no interactive provider selection:

```json
// .opencode.json (v0.3.0)
{
  "mcp": {
    "archai": {
      "type": "local",
      "command": ["archai", "mcp"],
      "enabled": true
      // No "environment" block — archai needs no API keys
    }
  }
}
```

### 4.3 User Flow

```
# 1. Single global installation
pip install archai-mcp

# 2. In each project where archai is needed
cd my-project
archai init
  → Creates .opencode.json with MCP config

# 3. Open OpenCode and work
opencode .
  → OpenCode auto-detects archai MCP server
  → The agent uses the tools transparently
  → All analysis happens without user interaction
```

**The user never touches `start` or `ask`.** They don't even know these commands existed.

---

## 5. Core Logic (Changes)

### 5.1 `mcp_server.py` — No LLM

```python
# BEFORE (v0.2.0):
LLM_MODEL = os.environ.get("ARCHAI_LLM_MODEL")
LLM_API_KEY = os.environ.get("ARCHAI_LLM_API_KEY")
llm_provider = LiteLLMProvider(model=LLM_MODEL, ...)
middleware = ArchaiMiddleware(llm_provider=llm_provider)

# AFTER (v0.3.0):
middleware = ArchaiMiddleware(llm_provider=None)
# No ARCHAI_LLM_MODEL, no API keys, no LLM provider
```

### 5.2 `pipeline.py` — No Structural Changes

The pipeline already supports `llm_provider=None` and degrades gracefully. No changes needed.

### 5.3 `orchestrator/orchestrator.py` — New Data Access Methods

New methods to expose complete structural data:

```python
def get_cluster_edges(graph, clusters) -> list[dict]:
    """Return dependency relationships between clusters.
    
    For each cluster, finds all imports to files in other clusters.
    Returns edges like: [{"from": "cluster_3", "to": "cluster_2"}, ...]
    """

def get_file_dependencies(graph, files=None) -> dict[str, list[str]]:
    """Return per-file import lists.
    
    Maps each file to all files it imports (with resolved paths).
    Optionally filters to a specific file list.
    """

async def get_structural_context(query, repo_path) -> StructuralContext:
    """New method replacing get_context() for MCP.
    
    Returns rich structural data without LLM labeling.
    """
```

The existing `get_context()` method is kept (for anyone using the library directly) but the MCP server uses `get_structural_context()`.

### 5.4 `models.py` — New Models

```python
class ClusterEdge(BaseModel):
    """A dependency edge between two clusters."""
    from_cluster: str
    to_cluster: str
    files: list[str] = Field(default_factory=list)
    """Specific files causing the cross-cluster dependency."""

class StructuralContext(BaseModel):
    """Pure structural response for MCP (no LLM)."""
    focus_cluster: str
    focus_files: list[str]
    focus_reasoning: str
    all_clusters: dict[str, list[str]]
    cluster_edges: list[ClusterEdge]
    file_dependencies: dict[str, list[str]]
    test_files: list[str]
    metadata: dict[str, Any]

class StructuralChangeValidation(BaseModel):
    """Structural validation — the agent decides validity."""
    file_cluster: str
    cluster_files: list[str]
    cluster_dependencies: dict[str, list[str]]
    file_dependencies: dict[str, list[str]]
    new_imports_in_patch: list[str]
    patch_summary: dict[str, Any]
```

### 5.5 `cli/app.py` — Remove start/ask, Simplify init

- Remove `start` and `ask` commands entirely
- `init`: remove LLM auto-detection (`_detect_llm_config`, `_discover_providers`, `_read_opencode_config`, `_extract_opencode_llm` — all the LLM-related helper functions)
- `init`: generate `.opencode.json` without environment passthrough

### 5.6 `cli/output.py` — Remove

No CLI commands need human-friendly output anymore. The entire module is removed.

---

## 6. OpenCode Integration

### 6.1 How Does OpenCode Infer Automatically?

**No special configuration needed.** OpenCode's agent (which is an LLM) receives the structured data from archai and processes it naturally.

But we can improve inference quality in two ways:

#### Tool Descriptions (Recommended)

Update MCP tool descriptions to guide the agent:

```python
@mcp.tool()
async def get_architecture_context(query: str, repo_path: str) -> str:
    """Analyze a repository's architecture for a given query.

    Returns cluster structure and file dependencies.
    YOUR LLM should analyze the files in each cluster to infer
    the subsystem name and architecture constraints (async-only,
    forbidden dependencies, etc.). Use this before writing code.

    Example inference from clusters:
    - An API-layer cluster (depends on many others) → async, no blocking I/O
    - A database cluster (no dependents) → leaf module
    - Leaf clusters should not import from API clusters
    """
```

The agent's LLM reads these descriptions and knows what to do. No additional instructions needed.

#### Project Rules (Optional, for Consistency)

Users who want more predictable behavior can add rules to their project:

```markdown
# .agent/rules/archai-integration.md

## Architecture Enforcement with archai

When archai MCP returns cluster data:
1. Name each cluster based on its files (e.g., "API Layer", "Database", "Auth")
2. Infer constraints from cluster dependencies:
   - Clusters depending on many others → likely API/entry points → async
   - Clusters with no dependents → leaf modules → no restrictions
   - Leaf clusters should not import from API clusters
3. Before applying changes, verify against inferred constraints
4. Use get_blast_radius for any file with >5 dependents
```

This is **optional**. The system works without these rules — they only improve consistency.

### 6.2 What Changes for the OpenCode User?

**Nothing.** The workflow is identical:

```
pip install archai-mcp
cd project
archai init
opencode .
```

The agent uses archai automatically. The difference is:

- **No API keys needed for archai**
- **No `ARCHAI_LLM_MODEL` to configure**
- **No extra LLM latency** — archai responds instantly
- **The agent understands the architecture better** because it has full context

---

## 7. Dependencies

### 7.1 pyproject.toml — No Changes

```toml
[project]
dependencies = [
    # ... everything stays ...
    "litellm>=1.0.0",      # Stays in core — not used by MCP server, but part of the library
]
```

`litellm` stays as a core dependency because:

- It's used by anyone importing the core library directly
- Removing it would break existing imports without real benefit
- It doesn't affect the MCP server path

**Decision**: No dependency changes. Only change how the MCP server initializes.

---

## 8. Files Modified

| File | Change |
|------|--------|
| `src/archai/mcp_server.py` | Remove `LiteLLMProvider`. Pass `llm_provider=None`. New structural responses. |
| `src/archai/orchestrator/orchestrator.py` | Add `get_structural_context()`, `get_cluster_edges()`, `get_file_dependencies()`. |
| `src/archai/models.py` | Add `StructuralContext`, `StructuralChangeValidation`, `ClusterEdge`. |
| `src/archai/cli/app.py` | Remove `start`/`ask` commands. Remove LLM auto-detection from `init`. Simplify. |
| `src/archai/cli/output.py` | **Remove** entire file — no CLI commands need it. |
| `src/archai/cli/__init__.py` | Update if needed. |
| `docs/003-sdd-agent-native-architecture.md` | This document. |

---

## 9. Implementation Plan

### Phase 1: Models + Orchestrator

1. Add `ClusterEdge`, `StructuralContext`, `StructuralChangeValidation` to `models.py`
2. Add `get_cluster_edges()` to `orchestrator.py`
3. Add `get_file_dependencies()` to `orchestrator.py`
4. Add `get_structural_context()` to `orchestrator.py`

### Phase 2: MCP Server

1. Remove `LiteLLMProvider` import from `mcp_server.py`
2. Change to `middleware = ArchaiMiddleware(llm_provider=None)`
3. Rewrite `get_architecture_context` to return `StructuralContext`
4. Rewrite `validate_code_change` to return `StructuralChangeValidation`
5. Update tool descriptions for agent inference guidance

### Phase 3: CLI Cleanup

1. Remove `start` and `ask` commands from `app.py`
2. Remove all LLM auto-detection helpers: `_detect_llm_config`, `_discover_providers`, `_read_opencode_config`, `_extract_opencode_llm`, `_read_json`, etc.
3. Simplify `init` — generate `.opencode.json` without environment passthrough
4. Remove `cli/output.py`
5. Remove `--model`, `--interactive`, `--force`, `--uv` flags from `init`

### Phase 4: Tests

1. Remove or rewrite tests for `start`/`ask` commands
2. Remove or rewrite tests for MCP server (new responses)
3. Remove tests for `output.py`
4. Add tests for `get_cluster_edges()`, `get_file_dependencies()`, `get_structural_context()`
5. Add tests for simplified `init`
6. Verify everything passes

---

## 10. Success Criteria

- [ ] `pip install archai-mcp && archai init && opencode .` — works with zero configuration
- [ ] `get_architecture_context` returns clusters + edges + dependencies (no LLM)
- [ ] `validate_code_change` returns structural analysis (no valid/invalid decision)
- [ ] `get_blast_radius` works identically to before
- [ ] `archai --help` shows only `init` and `mcp`
- [ ] `archai init` generates `.opencode.json` without environment vars
- [ ] `archai init` has no `--model`, `--interactive`, `--force`, `--uv` flags
- [ ] All existing bootstrap/orchestrator/inference tests still pass
- [ ] No dependencies removed from core
- [ ] OpenCode's agent can infer cluster names and constraints from structural data

---

## 11. Open Questions

| ID | Question | Status |
|----|----------|--------|
| OQ-001 | Should `litellm` be moved to optional-dependencies? | **Not now.** It stays in core. Can be moved later if the library clearly doesn't need it. |
| OQ-002 | OpenCode-side validation needs special rules? | **No.** The agent's LLM processes the data naturally. Rules are optional consistency improvements. |
| OQ-003 | What about users who depend on `archai start`/`ask`? | **They don't exist.** archai has always been agent-first. These commands were transitional. |

---

## 12. Risks

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Agent's LLM infers constraints incorrectly | Low | Modern LLMs (Claude, GPT-4, Gemini) are excellent at reading file structures. Users can add explicit project rules if needed. |
| MCP responses are too large | Medium | `all_clusters` and `file_dependencies` can grow. Solution: add optional filtering or pagination if it becomes an issue. |
| `litellm` dependency becomes unused bloat | Low | Doesn't affect the product. `litellm` is lightweight. Can be made optional in a future release. |
| Breaking change for anyone scripting `archai start`/`ask` | None | These exist as CLI experiments, not public API. No users depend on them. |
