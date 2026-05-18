# SDD - ArchAI MVP Architecture

## Overview

| Item | Detail |
|------|--------|
| **Project** | ArchAI |
| **Version** | 0.1.0 |
| **Status** | Draft |
| **Date** | 2026-05-15 |

---

## 1. Architecture Overview

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARCHAI SYSTEM                             │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │   Agent     │───▶│  ArchAI API   │───▶│  LLM Provider   │  │
│  │  (OpenCode) │    │  (FastAPI)    │    │ (Claude/Gemini) │  │
│  └─────────────┘    └──────────────┘    └─────────────────┘  │
│                            │                                     │
│                     ┌──────▼──────┐                             │
│                     │  Graph      │                             │
│                     │  (NetworkX) │                             │
│                     └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Pipeline Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Context Orchestrator                                   │
│  ├── Focus Resolution (¿Which subsystem?)              │
│  ├── Subgraph Extraction (Which files?)                │
│  └── Constraint Injection (What rules?)                │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Context Packet
    │
    ├── focus: str
    ├── constraints: dict
    ├── relevant_files: List[FileMetadata]
    └── metadata: dict
    │
    ▼
LLM / Agent
```

---

## 2. Component Design

### 2.1 Component Overview

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| **Bootstrapping Engine** | Parse repo → Graph | repo_path | FileGraph, SymbolGraph |
| **Inference Engine** | Detect subsystems + constraints | FileGraph | ArchitectureModel |
| **Context Orchestrator** | Build context packet | Query + ArchitectureModel | ContextPacket |
| **HTTP Service** | Expose API endpoints | HTTP Requests | HTTP Responses |
| **Agent Integration** | Tool definitions for agents | Tool calls from Agent | ContextPacket, ValidationResult |
| **Visualization UI** | Display architecture to user | ArchitectureModel | React UI (React Flow) |

### 2.2 Component Details

#### 2.2.1 Repository Bootstrapping Engine

```
Input:  /path/to/repo
Output: Graph data structure

Workflow (SRP - each module has one responsibility):
┌─────────────┐     ┌─────────────┐     ┌────────────────┐     ┌─────────────┐
│  File       │     │   AST       │     │  Dependency    │     │   Graph     │
│  Discovery  │────▶│  Parsing    │────▶│  Resolution    │────▶│  Building   │
│  (walk dir) │     │(ast module) │     │ (resolve names)│     │ (NetworkX)  │
└─────────────┘     └─────────────┘     └────────────────┘     └─────────────┘
```

**Modules** (each follows SRP):
- `file_discovery.py` - Walk directory, filter by extension (.py)
- `ast_parser.py` - Parse Python files, extract imports/functions/classes from AST
- `dependency_resolver.py` - Resolve raw imports to repo-relative paths (e.g., `"src.services.user"` → `"src/services/user.py"`)
- `graph_builder.py` - Build NetworkX graph from resolved FileNodes containing repo-relative paths only (no parsing)

#### 2.2.2 Semantic + Architectural Inference Engine

```
Input:  FileGraph
Output: ArchitectureModel

Workflow:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Semantic   │     │  Semantic   │     │  Constraint │
│  Clustering │────▶│  Labeling   │────▶│  Inference  │
│ (heuristics)│     │   (LLM)     │     │   (LLM)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Modules**:
- `clustering.py` - Cluster files by directory, imports, call density
- `labeler.py` - Use LLM to infer subsystem names and descriptions
- `constraint_inferrer.py` - Infer async_only, forbidden_deps, etc.
- `architecture_store.py` - Persist and cache ArchitectureModel

#### 2.2.3 Context Orchestrator

```
Input:  user_query, ArchitectureModel
Output: ContextPacket

Workflow:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Focus     │     │  Subgraph   │     │  Constraint │
│  Resolution │────▶│  Extraction │────▶│  Injection  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Modules**:
- `focus_resolver.py` - Match query to subsystem (keyword matching)
- `subgraph_extractor.py` - Extract connected files from Graph
- `constraint_injector.py` - Merge subsystem constraints into context
- `context_builder.py` - Assemble final ContextPacket

#### 2.2.4 HTTP Service

```
Endpoints:
├── GET  /health
├── GET  /repository/{repo_id}
├── POST /context
└── POST /validate-change
```

**Modules**:
- `main.py` - FastAPI app initialization
- `routes/context.py` - POST /context handler
- `routes/validate.py` - POST /validate-change handler
- `routes/repository.py` - GET /repository/{repo_id} handler
- `middleware/tracing.py` - Request logging and tracing

#### 2.2.5 Agent Integration Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT (OpenCode)                           │
│                                                                 │
│   Tools available:                                             │
│   ├── read_file()                                              │
│   ├── edit_file()                                               │
│   ├── run_command()                                             │
│   ├── archai_context()        ← NEW                            │
│   └── archai_validate()       ← NEW                            │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ Tool call
                           ▼
                    ┌───────────────────────────────────┐
                    │              ARCHAI                 │
                    │                                      │
                    │  Agent decides to call tool when:  │
                    │  - Query mentions specific files   │
                    │  - User asks for code help         │
                    │  - Any code-related operation      │
                    └───────────────────────────────────┘
```

**Integration Flow**:

1. **Context Request**: Agent calls `archai_context(query, repo_path)`
   - ArchAI returns ContextPacket (focus, constraints, relevant files)

2. **Prompt Construction**: Agent builds LLM prompt with:
   - Focus subsystem context
   - Architectural constraints
   - Relevant code files

3. **LLM Execution**: Agent calls LLM with curated context

4. **Validation**: Before applying changes, Agent calls `archai_validate(changes)`
   - ArchAI checks against constraints
   - Returns violations (if any)

**Tool Definitions**:

```python
archai_context = {
    "name": "archai_context",
    "description": "Get architecture-aware context for a query",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "User query"},
            "repo_path": {"type": "string", "description": "Path to repository"}
        },
        "required": ["query", "repo_path"]
    }
}

archai_validate = {
    "name": "archai_validate",
    "description": "Validate code changes against architectural constraints",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string"},
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "action": {"type": "string"},
                        "new_imports": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },
        "required": ["repo_path", "changes"]
    }
}
```

**Note**: The LLM is NOT called by ArchAI directly. ArchAI provides curated context; the agent builds the prompt and calls the LLM.

#### 2.2.6 Visualization UI (Frontend - MVP Post-Backend)

```
Input:  ArchitectureModel, ContextPacket
Output: React UI with interactive graph

Workflow:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Subsystem  │     │   Active    │     │   Blast     │
│  Tree View  │────▶│   Focus     │────▶│   Radius    │
│             │     │  Highlighting│     │  Display    │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Tech Stack**:
- React 18+
- React Flow (graph visualization)
- Zustand (state management)

**Features**:
- Repository tree (subsystems hierarchy)
- Active subsystem highlighting
- Constraints display
- Blast radius visualization

**Note**: This component is planned for MVP 1.1 (post-backend completion)

---

## 3. Data Structures

### 3.1 FileGraph

```python
class FileNode:
    """Metadata for a single file in the repository."""
    path: str           # filename (e.g., "main.py")
    imports: List[str]  # resolved imports as repo-relative paths (e.g., ["src/helpers.py", "src/models/user.py"])
    functions: List[str]  # function names defined in the file
    classes: List[str]    # class names defined in the file

class FileGraph:
    """NetworkX graph wrapper with file metadata."""
    graph: nx.DiGraph    # NetworkX directed graph with edges
    _nodes: Dict[str, FileNode]  # metadata lookup by filename
```

### 3.2 ArchitectureModel

```python
class Subsystem:
    name: str
    description: str
    files: List[str]
    constraints: SubsystemConstraints

class SubsystemConstraints:
    async_only: bool
    no_blocking_io: bool
    forbidden_dependencies: List[str]
    allowed_dependencies: List[str]

class ArchitectureModel:
    subsystems: List[Subsystem]
    file_to_subsystem: Dict[str, str]  # file path -> subsystem name
    raw_graph: FileGraph
```

### 3.3 ContextPacket

```python
class ContextPacket:
    focus: str
    focus_reasoning: str
    constraints: SubsystemConstraints
    subgraph: List[str]
    relevant_files: List[FileMetadata]
    metadata: ContextMetadata

class FileMetadata:
    path: str
    reason: str
    importance: float  # 0.0 to 1.0
```

---

## 4. TDD (Test-Driven Development)

### 4.1 Philosophy

All code will be developed using TDD:
1. **Write test first** - Define the expected behavior before implementation
2. **Run test** - Verify it fails (red)
3. **Write minimal code** - Make the test pass (green)
4. **Refactor** - Improve code while keeping tests green (refactor)

### 4.2 Testing Stack

| Tool | Purpose |
|------|---------|
| **pytest** | Test runner and framework |
| **pytest-asyncio** | Async test support (for LLM calls) |
| **pytest-cov** | Code coverage reporting |
| **Hypothesis** | Property-based testing for data structures |
| **pytest-mock** | Mocking dependencies |

### 4.3 Test Structure

```
tests/
├── unit/
│   ├── bootstrap/
│   │   ├── test_file_discovery.py
│   │   ├── test_ast_parser.py
│   │   └── test_graph_builder.py
│   ├── inference/
│   │   ├── test_clustering.py
│   │   ├── test_labeler.py
│   │   └── test_constraint_inferrer.py
│   └── orchestrator/
│       ├── test_focus_resolver.py
│       ├── test_subgraph_extractor.py
│       └── test_context_builder.py
├── integration/
│   ├── test_api_context.py
│   ├── test_api_validate.py
│   └── test_agent_integration.py
├── performance/
│   ├── test_bootstrapping_performance.py
│   └── test_memory_usage.py
└── fixtures/
    ├── sample_repos/
    └── test_data.json
```

### 4.4 Test Naming Convention

```
test_<module>_<functionality>_<expected_behavior>

Examples:
- test_file_discovery_finds_all_py_files
- test_graph_builder_creates_edges_from_imports
- test_context_packet_includes_test_files
```

### 4.5 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/bootstrap/test_file_discovery.py
```

### 4.6 TDD Workflow

```
For each task (T-XXX):

1. Write test(s) in tests/ directory
   └─ Should fail initially (RED)

2. Run test to confirm failure
   └─ pytest tests/.../test_xxx.py

3. Implement the feature in src/
   └─ Make test pass (GREEN)

4. Run full test suite
   └─ Ensure no regressions (GREEN)

5. Refactor if needed
   └─ Keep tests green (REFACTOR)

6. Run performance tests
   └─ Verify non-functional requirements

7. Commit with passing tests
```

### 4.7 Test Coverage Targets

| Type | Target |
|------|--------|
| Unit tests | > 80% |
| Integration tests | All API endpoints |
| Performance tests | All NFR targets |

---

## 5. Technical Tasks

### Phase 1: Foundation

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-001 | Project | Setup Python project with pyproject.toml | HIGH |
| T-002 | Project | Configure virtual environment and dependencies | HIGH |
| T-003 | Project | Setup logging (structured JSON) | MEDIUM |
| T-004 | HTTP | Create FastAPI app with health endpoint | HIGH |
| T-005 | HTTP | Add request/response models with Pydantic | HIGH |
| T-006 | TDD | Setup pytest with pytest-asyncio and coverage | HIGH |
| T-007 | TDD | Create test directory structure and fixtures | HIGH |

### Phase 2: Bootstrapping Engine

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-010 | Bootstrap | File discovery - walk directory, filter by .py | HIGH |
| T-011 | Bootstrap | AST parsing with tree-sitter (Python) | HIGH |
| T-012 | Bootstrap | Extract imports/exports from AST | HIGH |
| T-013 | Bootstrap | Build NetworkX graph from parsed files | HIGH |
| T-014 | Bootstrap | Handle circular imports (collapse cycles) | MEDIUM |
| T-015 | Bootstrap | Add disk cache with hash invalidation | MEDIUM |

### Phase 3: Inference Engine

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-020 | Inference | Implement clustering heuristics | HIGH |
| T-021 | Inference | Create LLM provider abstraction | HIGH |
| T-022 | Inference | Implement semantic labeling (LLM call) | HIGH |
| T-023 | Inference | Implement constraint inference (LLM call) | MEDIUM |
| T-024 | Inference | Store and cache ArchitectureModel | MEDIUM |
| T-025 | Inference | Add async processing for LLM calls | MEDIUM |

### Phase 4: Context Orchestrator

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-030 | Orchestrator | Implement focus resolution (keyword matching) | HIGH |
| T-031 | Orchestrator | Implement subgraph extraction | HIGH |
| T-032 | Orchestrator | Implement constraint injection | HIGH |
| T-033 | Orchestrator | Build ContextPacket | HIGH |
| T-034 | Orchestrator | Add test file detection (test_*, tests/) | MEDIUM |
| T-035 | Orchestrator | Add validation endpoint | HIGH |

### Phase 5: API & Integration

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-040 | API | Implement POST /context endpoint | HIGH |
| T-041 | API | Implement POST /validate-change endpoint | HIGH |
| T-042 | API | Implement GET /repository/{repo_id} endpoint | MEDIUM |
| T-043 | Agent | Define OpenCode tool schema (archai_context, archai_validate) | HIGH |
| T-044 | Agent | Add OpenCode integration test | MEDIUM |
| T-042 | API | Implement GET /repository/{repo_id} endpoint | MEDIUM |
| T-043 | Integration | Add OpenCode integration test | MEDIUM |
| T-044 | Integration | Add error handling and validation | MEDIUM |

### Phase 6: Performance & Testing

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-050 | Testing | Add performance tests (bootstrapping < 15s) | MEDIUM |
| T-051 | Testing | Add memory usage tests (< 100MB) | LOW |
| T-052 | Testing | Add cache hit rate tests | LOW |
| T-053 | Testing | Add integration tests | MEDIUM |

### Phase 7: Visualization UI (MVP 1.1 - Post-Backend)

| Task | Component | Description | Priority |
|------|-----------|-------------|----------|
| T-060 | UI | Setup React project with Vite | LOW |
| T-061 | UI | Install React Flow and Zustand | LOW |
| T-062 | UI | Create subsystem tree component | LOW |
| T-063 | UI | Create active focus highlighting | LOW |
| T-064 | UI | Create constraints display panel | LOW |
| T-065 | UI | Create blast radius visualization | LOW |
| T-066 | UI | Connect UI to API endpoints | LOW |

---

## 6. Dependency Graph (General View)

> **Note**: This is a high-level overview of task dependencies. It shows the general flow of how phases relate to each other. Detailed dependencies are implicit in the task descriptions above.

```
T-001 ──▶ T-002 ──▶ T-003 ──▶ T-004 ──▶ T-005
                                      │
                                      ▼
T-010 ──▶ T-011 ──▶ T-012 ──▶ T-013 ──▶ T-014 ──▶ T-015
                                      │
                                      ▼
T-020 ──▶ T-021 ──▶ T-022 ──▶ T-023 ──▶ T-024 ──▶ T-025
                    │                     │
                    └─────────┬───────────┘
                              ▼
T-030 ──▶ T-031 ──▶ T-032 ──▶ T-033 ──▶ T-034 ──▶ T-035
                                      │
                                      ▼
T-040 ──▶ T-041 ──▶ T-042 ──▶ T-043 ──▶ T-044
                                      │
                                      ▼
T-050 ──▶ T-051 ──▶ T-052 ──▶ T-053
```

---

## 7. Acceptance Criteria

| Task | Criteria |
|------|-----------|
| T-001 | pyproject.toml created, venv works |
| T-006 | pytest runs, test discovery works |
| T-007 | Test directory structure created with fixtures |
| T-004 | GET /health returns {"status": "ok"} |
| T-010 | Can discover all .py files in a directory |
| T-011 | Can parse Python files to AST |
| T-012 | Can extract imports from parsed AST |
| T-013 | Can build NetworkX graph from files |
| T-020 | Can cluster files into subsystems |
| T-030 | Can resolve focus from user query |
| T-040 | POST /context returns valid ContextPacket |
| T-041 | POST /validate-change returns violations |

---

*Document Status: Draft - Ready for Implementation*