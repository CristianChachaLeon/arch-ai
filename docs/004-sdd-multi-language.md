# SDD-004: Multi-Language Support

## Overview

| Item | Detail |
|------|--------|
| **Project** | ArchAI |
| **Version** | 0.4.0 |
| **Status** | Accepted |
| **Date** | 2026-06-06 |
| **Supersedes** | Language-specific sections of 001-sdd, 002-sdd, 003-sdd |

---

## 1. Motivation

### 1.1 The Problem

ArchAI currently supports **Python only**. Every phase of the bootstrap pipeline is hardcoded to Python:

| Phase | Current | Problem |
|-------|---------|---------|
| **File discovery** | `discover_python_files()` — hardcoded `**/*.py` | Ignores `.js`, `.ts`, `.go`, `.rs` |
| **AST parsing** | `ast` stdlib + `tree-sitter-python` | Can't extract imports from other languages |
| **Dep. resolution** | `STDLIB_MODULES` (Python), `__init__.py` conventions | Import syntax varies per language |

But the rest of archai is already **language-agnostic**:

| Phase | Agnostic? | Why |
|-------|-----------|-----|
| **Graph building** | ✅ | NetworkX, edges from resolved paths |
| **Clustering** | ✅ | Directory proximity, shared imports |
| **Focus resolution** | ✅ | File path matching |
| **Blast radius** | ✅ | Graph traversal |
| **MCP tools** | ✅ | All operate on file paths |

This means the path to multi-language is **narrow and well-defined**: only the 3 bootstrap phases need to change.

### 1.2 Real-World Use Case

```text
my-project/
├── src/
│   ├── api/          # TypeScript
│   ├── backend/      # Go
│   └── frontend/     # JavaScript + TypeScript
├── tests/
├── package.json
├── go.mod
└── Cargo.toml
```

archai should detect all languages, parse and resolve dependencies for each, build a unified graph, and let the agent understand the full polyglot architecture.

### 1.3 Design Goals

1. **Zero-config auto-detection** — archai detects languages from project files and extensions
2. **Strategy pattern** — each language implements a `LangHandler` interface
3. **Shared graph** — all languages feed into the same NetworkX graph
4. **Leverage tree-sitter** — already a dependency, supports 50+ languages
5. **Backward compatible** — Python-only repos work without changes
6. **Progressive enhancement** — start with Python + C/C++, add more later

---

## 2. Architecture

### 2.1 The LangHandler Protocol

```python
class ParsedFile(BaseModel):
    """Result of parsing a single file."""
    path: str
    imports: list[str]           # Raw import strings
    functions: list[str]
    classes: list[str]
    language: str                # "python", "typescript", "go"


class LangHandler(Protocol):
    """Interface each language must implement."""

    language: str
    extensions: frozenset[str]
    project_files: tuple[str, ...]
    excluded_dirs: frozenset[str]

    def is_project_root(self, path: Path) -> bool:
        ...

    def parse(self, file: Path) -> ParsedFile:
        ...

    def resolve_import(
        self, import_name: str, file_path: str,
        all_files: set[str], project_root: Path,
    ) -> str | None:
        ...
```

### 2.2 Updated Pipeline Flow

```text
Pipeline._run_bootstrap(repo):

  1. Detect languages
     -> Scan repo for project files, extensions
     -> Returns list of LangHandlers

  2. Discover files (per language)
     -> For each handler: glob *.{extensions}
     -> Exclude handler's excluded_dirs + common dirs

  3. Parse files (per language)
     -> For each file: handler.parse(file)
     -> Collect ParsedFile

  4. Resolve imports (per language)
     -> handler.resolve_import(import_name, ...)
     -> Cross-language imports = "external" (for now)

  5. Build graph (REUSABLE)
     -> build_graph(all_parsed_files)
     -> Single NetworkX graph
```

### 2.3 System Context

```text
+------------------------------------------------------------------+
|                    ARCHAI v0.4.0 (Multi-Lang)                     |
|                                                                   |
|  +------------------------------------------------------------+  |
|  |  Language Handlers Registry                                |  |
|  |  +----------+  +----------+  +----------+  +---------+     |  |
|  |  |  Python  |  |    TS    |  |    Go    |  |  Rust   |     |  |
|  |  | handler  |  |  handler |  |  handler |  | handler |     |  |
|  |  +----+-----+  +----+-----+  +----+-----+  +----+----+     |  |
|  |       |             |             |             |           |  |
|  |       +------+------+------+------+------+------+           |  |
|  |              |             |             |                  |  |
|  |       +------+-------------+-------------+------+           |  |
|  |       |         Unified NetworkX Graph          |           |  |
|  |       |   (all languages, all files, all edges) |           |  |
|  |       +-----------------------------------------+           |  |
|  |                                                              |  |
|  |  Agnostic (unchanged): Clustering, Focus, Blast Radius      |  |
|  +------------------------------------------------------------+  |
|                                                                   |
|  MCP Tools (unchanged): get_architecture_context,                 |
|  validate_code_change, get_blast_radius                           |
+------------------------------------------------------------------+
```

---

## 3. Language Handlers

### 3.1 Built-in Handlers

| Language | Extensions | Project Files | Parser | Priority |
|----------|------------|---------------|--------|----------|
| Python | `.py` | `setup.py`, `pyproject.toml` | stdlib `ast` | **P0** |
| TypeScript | `.ts`, `.tsx`, `.mts`, `.cts` | `tsconfig.json` | tree-sitter-ts | **P1** |
| JavaScript | `.js`, `.jsx`, `.mjs`, `.cjs` | `package.json` | tree-sitter-js | **P1** |
| Go | `.go` | `go.mod` | tree-sitter-go | **P2** |
| Rust | `.rs` | `Cargo.toml` | tree-sitter-rust | **P2** |
| C | `.c`, `.h` | `Makefile`, `CMakeLists.txt` | tree-sitter-c | **P1** |
| C++ | `.cpp`, `.hpp`, `.cc`, `.cxx`, `.hh` | `Makefile`, `CMakeLists.txt` | tree-sitter-cpp | **P1** |

### 3.2 Python Handler (Refactored)

The current Python-specific code (`ast_parser.py`, `dependency_resolver.py`) is **extracted into a `PythonLangHandler`** class. No functionality changes — just repackaged.

This ensures **backward compatibility**: existing Python projects work identically.

### 3.3 C/C++ Handler (P1)

Uses tree-sitter-c and tree-sitter-cpp grammars.

**Include Resolution:**
- **Local includes**: `#include "my_header.h"` → search relative to the including file, then project-wide
- **System includes**: `#include <stdio.h>` → external (not resolved)
- **Header mapping**: `.h` files map to `.c` or `.cpp` implementations — both are graph nodes
- **Project files**: `Makefile`, `CMakeLists.txt`, `compile_commands.json`, `.clang-format`

The handler handles both C and C++ with shared include resolution logic.

### 3.4 TypeScript/JavaScript Handler (P1)

Uses tree-sitter grammars.

Resolver rules:
- **ESM**: `import { x } from './foo'` -> `./foo.ts`, `./foo/index.ts`
- **CJS**: `require('./foo')` -> same resolution
- **Bare imports**: `import 'react'` -> external (not resolved)
- **Index files**: `./components` -> `./components/index.ts`

### 3.5 Go Handler (P2)

Resolver rules:
- `import "pkg/path"` -> local if within module (from `go.mod`), external otherwise
- Resolved relative to module root
- No index files

### 3.6 Future Handlers

Rust, Java, C#, Ruby — all follow the same `LangHandler` pattern.

---

## 4. Language Detection

### 4.1 Auto-Detection

```python
def detect_languages(repo: Path) -> list[LangHandler]:
    handlers = []
    for handler in REGISTERED_HANDLERS:
        for pf in handler.project_files:
            if (repo / pf).exists():
                handlers.append(handler)
                break
        else:
            if any(repo.rglob(f"*{ext}") for ext in handler.extensions):
                handlers.append(handler)
    return handlers
```

### 4.2 Explicit Configuration (Optional)

```yaml
# .archai.yaml (future)
languages:
  - python
  - typescript
```

Zero config by default.

---

## 5. Cross-Language Dependencies

### 5.1 Current Limitation

In v0.4.0, imports **between languages** are **not resolved**. Marked as `external` in the graph.

This is acceptable because:
- Cross-language deps are typically runtime (HTTP, RPC), not compile-time
- The graph still provides complete intra-language analysis
- The agent can infer cross-language relationships from cluster structure

### 5.2 Future Enhancement

Cross-language resolution could be added via convention-based mapping (e.g., TypeScript types generated from Go protobufs).

---

## 6. Dependencies

### 6.1 New Optional Dependencies

```toml
[project.optional-dependencies]
python = []                          # Built-in
javascript = [
    "tree-sitter-javascript>=0.20",
    "tree-sitter-typescript>=0.20",
]
c = ["tree-sitter-c>=0.20"]
cpp = ["tree-sitter-cpp>=0.20"]
go = ["tree-sitter-go>=0.20"]
rust = ["tree-sitter-rust>=0.20"]
```

Core deps stay unchanged: `typer`, `rich`, `pydantic`, `tree-sitter`, `networkx`, `mcp`.

### 6.2 Handler Auto-Install (Future)

When archai detects a language whose handler isn't installed:

```text
Warning: TypeScript files detected. Install: pip install archai-mcp[javascript]
```

---

## 7. Files Modified

| File | Change |
|------|--------|
| `src/archai/bootstrap/language.py` | **New** — LangHandler protocol + registry |
| `src/archai/bootstrap/python_handler.py` | **New** — extracted from current code |
| `src/archai/bootstrap/ast_parser.py` | **Removed** |
| `src/archai/bootstrap/dependency_resolver.py` | **Removed** |
| `src/archai/bootstrap/file_discovery.py` | **Refactored** — generic `discover_files()` |
| `src/archai/bootstrap/__init__.py` | **Updated** — new exports |
| `src/archai/middleware/pipeline.py` | **Refactored** — language detection + dispatch |
| `src/archai/bootstrap/c_handler.py` | **New** — C/C++ handler using tree-sitter |
| `src/archai/bootstrap/cpp_handler.py` | **New** — C++ handler (or combined with C) |
| `pyproject.toml` | **Updated** — new optional-dependencies |

---

## 8. Implementation Plan

### Phase 1: Refactor Python Handler

1. Define `LangHandler` protocol in `bootstrap/language.py`
2. Extract `PythonLangHandler` from existing code
3. Refactor `file_discovery.py` to generic `discover_files()`
4. Update `pipeline.py` to use language detection
5. Verify all tests pass

### Phase 2: C/C++ Handler

1. Add tree-sitter-c and tree-sitter-cpp grammars
2. Implement CLangHandler + CppLangHandler (or combined CLikeLangHandler)
3. Include resolution: `#include "local.h"` → project files, `#include <system>` → external
4. Header-to-source mapping for graph edges
5. Add tests with sample .c/.cpp/.h fixtures
6. Integration test: polyglot repo with Python + C

### Phase 3: TypeScript/JavaScript Handler

1. Add tree-sitter JS/TS grammars
2. Implement `TypeScriptLangHandler`
3. Add tests with sample fixtures
4. Integration test: polyglot repo

### Phase 4: Go Handler

1. Add tree-sitter-go grammar
2. Implement `GoLangHandler`
3. Add tests

### Phase 5: Rust Handler

1. Add tree-sitter-rust grammar
2. Implement `RustLangHandler`
3. Add tests

---

## 9. Success Criteria

- [ ] Python-only repos work identically (backward compatible)
- [ ] LangHandler protocol defined and documented
- [ ] PythonLangHandler extracts existing logic
- [ ] discover_files() handles multiple extension sets
- [ ] Pipeline auto-detects languages in a repo
- [ ] JS/TS handler parses and resolves imports correctly
- [ ] Go handler works for basic cases
- [ ] C handler parses `.c` and `.h` files correctly
- [ ] C++ handler parses `.cpp`, `.hpp`, `.cc` files correctly
- [ ] Include resolution distinguishes local vs system includes
- [ ] Graph contains C/C++ nodes with proper dependency edges
- [ ] Unified graph contains nodes from all detected languages
- [ ] All existing tests still pass
