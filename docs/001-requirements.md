# ArchAI - Requirements Document

## Overview

| Item | Detail |
|------|--------|
| **Project** | ArchAI - Cognitive Middleware for Architecture-Aware AI Coding Agents |
| **Version** | 0.1.0 |
| **Status** | Draft |
| **Date** | 2026-05-15 |

---

## 1. Problem Statement

AI coding agents treat repositories as text corpora, lacking architectural awareness. This leads to:

- **Context pollution**: Agents receive irrelevant files and tokens
- **Architectural drift**: Changes violate system boundaries and constraints
- **Low coherence**: Modifications span multiple subsystems unnecessarily
- **Poor reasoning**: No understanding of architectural constraints

---

## 2. Solution Overview

ArchAI is a **cognitive middleware layer** that governs how AI coding agents perceive and reason about software systems.

```
User Query
   ↓
Architectural Focus Resolution
   ↓
Subgraph Extraction
   ↓
Constraint Injection
   ↓
Governed Context
   ↓
LLM / Agent
```

---

## 3. Scope - MVP 1.0

### 3.1 In Scope

#### Core Components
- [ ] Repository Bootstrapping Engine (Python parser)
- [ ] Semantic + Architectural Inference Engine
- [ ] Context Orchestrator (Focus Resolution → Subgraph Extraction → Constraint Injection → Context Packet)
- [ ] HTTP Context Service API
- [ ] Basic Visualization UI

#### Features
- [ ] AST parsing for Python files
- [ ] File graph construction
- [ ] Symbol graph construction
- [ ] Dependency detection
- [ ] Semantic clustering (directory proximity, shared imports, call density)
- [ ] Semantic labeling with configurable LLM provider
- [ ] Architectural constraint inference
- [ ] Focus resolution from user query
- [ ] Context packet generation (includes related test files)
- [ ] Real-time constraint validation
- [ ] REST API endpoints: `POST /context`, `POST /validate-change`, `GET /health`, `GET /repository/{repo_id}`
- [ ] Basic UI for repository overview

#### Language Support
- [x] Python (MVP)

#### Agent Integration
- [x] OpenCode (primary test)
- [ ] Design must support: Cursor, Claude Code, Gemini CLI, Aider (future)

### 3.2 Out of Scope (MVP 1.0)

- Multi-language support (Go, TypeScript, Rust, etc.)
- Multi-agent orchestration
- Runtime architectural enforcement
- IDE plugins
- CI/CD integration
- Continuous architectural learning

---

## 4. Technical Requirements

### 4.1 Architecture

**Design Principles**:
- Modular: Each component must be replaceable/swappable
- Extensible: Easy to add new languages, agents, LLM providers
- Observable: Full tracing of context pipeline
- Decoupled: HTTP service architecture

**Multi-Agent Ready**:
- Abstract agent interface
- Agent-specific context adapters
- Protocol-agnostic design

### 4.2 Backend Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| AST Parsing | Tree-sitter |
| Graph Processing | NetworkX |
| LLM Integration | Abstract Provider Interface (Claude, Gemini, OpenAI, etc.) |
| Configuration | Pydantic Settings |

### 4.3 API Specification

#### POST /context

**Request**:
```json
{
  "query": "string",
  "repo_path": "string",
  "agent_type": "opencode" // optional
}
```

**Response**:
```json
{
  "focus": "string",
  "focus_reasoning": "string",
  "constraints": {
    "async_only": "boolean",
    "no_blocking_io": "boolean",
    "forbidden_dependencies": ["string"],
    "allowed_dependencies": ["string"]
  },
  "subgraph": ["string"],
  "relevant_files": [
    {
      "path": "string",
      "reason": "string",
      "importance": "float"
    }
  ],
  "metadata": {
    "token_estimate": "integer",
    "subsystems_detected": ["string"]
  }
}
```

#### GET /health

**Response**: `{"status": "ok"}`

#### GET /repository/{repo_id}

Returns repository overview and detected subsystems.

#### POST /validate-change

Real-time constraint validation for proposed changes. Used by agents before applying modifications.

**Request**:
```json
{
  "repo_path": "string",
  "changes": [
    {
      "file": "string",
      "action": "create|modify|delete",
      "new_imports": ["string"]
    }
  ]
}
```

**Response**:
```json
{
  "valid": "boolean",
  "violations": [
    {
      "type": "boundary_violation",
      "file": "string",
      "from_subsystem": "string",
      "to_subsystem": "string",
      "message": "string"
    }
  ],
  "warnings": [
    {
      "type": "constraint_risk",
      "file": "string",
      "message": "string"
    }
  ]
}
```

### 4.4 Frontend Stack (MVP 1.1 - Post Backend)

| Component | Technology |
|-----------|------------|
| Framework | React |
| Graph Visualization | React Flow |
| State | Zustand |

---

## 5. Functional Requirements

### 5.1 Repository Bootstrapping Engine

**FR-001**: Parse Python files to AST using tree-sitter
**FR-002**: Extract imports and dependencies from each file
**FR-003**: Build file graph (node: file, edge: import relationship)
**FR-004**: Build symbol graph (node: function/class, edge: call/reference)
**FR-005**: Store graph in memory for querying

**Output**:
```json
{
  "files": [
    {
      "path": "string",
      "language": "python",
      "imports": ["string"],
      "exports": ["string"]
    }
  ],
  "dependencies": [
    {
      "from": "string",
      "to": "string",
      "type": "import"
    }
  ]
}
```

### 5.2 Inference Engine

**FR-006**: Cluster files into logical subsystems using graph heuristics
**FR-007**: Label clusters using LLM (semantic meaning inference)
**FR-008**: Infer architectural constraints per subsystem
**FR-009**: Store architectural model for repository

**Output**:
```json
{
  "subsystems": [
    {
      "name": "string",
      "description": "string",
      "files": ["string"],
      "constraints": {
        "async_only": "boolean",
        "forbidden_dependencies": ["string"]
      }
    }
  ]
}
```

### 5.3 Context Orchestrator

**FR-010**: Resolve focus from user query (match query to subsystem)
**FR-011**: Extract relevant subgraph (connected files in focus, including related test files: `test_*.py`, `*_test.py`, `tests/` directory, `conftest.py`)
**FR-012**: Inject constraints into context
**FR-013**: Generate context packet for agent
**FR-014**: Validate proposed changes against architectural constraints (real-time boundary enforcement)

### 5.4 Visualization UI

**FR-015**: Display repository tree (subsystems hierarchy)
**FR-016**: Highlight active focus subsystem
**FR-017**: Show constraints for active focus
**FR-018**: Display blast radius (affected files)

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Operation | Target | Notes |
|-----------|--------|-------|
| **Bootstrapping** | < 15s for 500 files |Includes AST parsing, graph construction, dependency resolution |
| **Query (local)** | < 500ms | Focus resolution + subgraph extraction + constraint injection (no LLM) |
| **Query (LLM)** | async / background | LLM calls for semantic labeling are non-blocking |
| **Memory** | < 100MB | Graph storage for typical codebase (5k files) |
| **Cache** | LLM responses cached | Repeated queries return cached results instantly |

### 6.1.1 Performance Notes

- **Bootstrapping**: 5s target achievable only with SSD + warm cache. 15s is realistic for cold start.
- **LLM calls**: Semantic labeling and constraint inference run async. Client receives immediate response with `status: processing` and polls for results.
- **Caching**: Architectural model cached in memory. LLM responses cached by query hash.
- **Scaling**: For 1000+ files, bootstrapping scales linearly (~30s for 2000 files)

### 6.2 Observability

- **Logging**: Structured logs (JSON)
- **Tracing**: Each pipeline stage logged
- **Metrics**: Token count, processing time

### 6.3 Extensibility

- **Language plugins**: Architecture supports pluggable language parsers
- **LLM providers**: Abstract provider interface for Claude, Gemini, OpenAI, etc.
- **Agent adapters**: Protocol-agnostic design for OpenCode, Cursor, Claude Code, Aider

---

## 7. Validation Criteria

### 7.1 Success Conditions

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| VC-001 | Parse target repository (sample: FastAPI) completely | Automated test |
| VC-002 | Detect subsystems with >80% accuracy | Manual inspection |
| VC-003 | Focus resolution matches intent | Manual test queries |
| VC-004 | Context packet < 20% tokens vs naive | Token comparison |
| VC-005 | OpenCode integration works | End-to-end test |

### 7.2 Evaluation Metrics

- **Boundary Violations**: Count cross-subsystem dependencies in changes
- **Blast Radius**: Files modified per change
- **Context Precision**: % of retrieved context relevant to focus
- **Token Reduction**: Naive vs ArchAI token count

---

## 8. Future Considerations (Post-MVP)

### 8.1 Multi-Language Support
- TypeScript/JavaScript
- Go
- Rust

### 8.2 Multi-Agent Support
- Cursor
- Claude Code
- Gemini CLI
- Aider

### 8.3 Advanced Features
- Real-time architectural drift detection
- Runtime constraint enforcement
- CI/CD integration
- IDE plugins

---

## 9. Dependencies

### 9.1 External Services

| Service | Purpose | Required |
|---------|---------|----------|
| LLM Provider | Claude, Gemini, GPT (configurable) | Yes (at least one required) |
| OpenCode | Primary agent integration | Yes (for testing) |

### 9.2 Open Source Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.100 | HTTP service |
| tree-sitter | >=0.20 | AST parsing |
| networkx | >=3.0 | Graph operations |
| anthropic | >=0.25 | LLM integration |
| pydantic | >=2.0 | Data validation |
| uvicorn | >=0.25 | ASGI server |
| react-flow | >=11 | Graph UI |
| zustand | >=4 | State management |

---

## 10. Open Questions (RESOLVED)

| ID | Question | Solution |
|----|----------|----------|
| OQ-001 | How to handle circular imports? | Collapse cycles into virtual nodes (cyclic module) |
| OQ-002 | How to cache bootstrapped repos? | Disk cache (`~/.archai/cache/`) with hash-based invalidation |
| OQ-003 | How to validate constraint inference? | Test corpus with known cases (expected vs inferred) |
| OQ-004 | How to measure "architectural drift"? | Boundary violations as proxy (count forbidden dependencies) |

---

## 11. Appendix

### A.1 References

- ArchAI Concept Document: `001-concept.md`
- Target Repository (sample): https://github.com/fastapi/fastapi

### A.2 Terminology

| Term | Definition |
|------|-------------|
| **Cognitive Middleware** | Layer that governs how agents perceive and reason |
| **Focus Resolution** | Determining active subsystem from query |
| **Context Packet** | Architecture-governed context for agent |
| **Architectural Drift** | Deviation from established architecture |
| **Blast Radius** | Scope of files affected by a change |

---

*Document Status: Draft - Ready for Review*