
# ArchAI MVP — Cognitive Middleware for Architecture-Aware AI Coding Agents

## Vision

ArchAI is not a code visualization tool.

It is a:

> Cognitive middleware layer that governs how AI coding agents perceive and reason about a software system.

The core hypothesis is:

> AI agents produce more coherent and architecturally aligned changes when their context is governed by architecture rather than only semantic retrieval.

---

# Core Concept

Traditional AI coding systems:

```text
User Query
   ↓
Semantic Retrieval
   ↓
LLM
```

ArchAI introduces an architectural cognition layer:

```text
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
LLM
```

---

# High-Level Architecture

```text
AGENT → ARCH-AI → LLM
```

Where:

## Agent

Examples:

* OpenCode
* Cursor
* Claude Code
* Gemini CLI
* Aider

Responsibilities:

* User interaction
* Tool execution
* Terminal actions
* File modifications
* Conversation management

---

## ArchAI

Responsibilities:

* Repository bootstrapping
* Architectural inference
* Focus resolution
* Context orchestration
* Constraint injection
* Execution tracing
* Architectural cognition

ArchAI acts as:

> An architecture-aware context operating layer for coding agents.

---

## LLM

Responsibilities:

* Reasoning
* Code generation
* Refactoring
* Planning

The LLM no longer sees the entire repository directly.

It sees:

```text
Architecturally curated reality
```

---

# MVP Goal

The MVP should validate one key hypothesis:

> Architecture-governed context improves agent coherence and reduces architectural drift.

The MVP is NOT intended to:

* Replace IDEs
* Replace agents
* Become a full orchestration framework
* Build a perfect graph engine
* Implement multi-agent coordination

The MVP should prove:

```text
Architecture can actively govern AI coding behavior.
```

---

# MVP Components

# 1. Repository Bootstrapping Engine

## Objective

Convert a repository into a structural graph.

## Input

```text
repo/
```

## Output

```json
{
  "modules": [...],
  "dependencies": [...],
  "symbols": [...]
}
```

## Technologies

* Python
* Tree-sitter
* networkx

## Responsibilities

* Parse ASTs
* Extract imports/includes
* Build file graph
* Build symbol graph
* Detect dependencies

## Important

This phase should be deterministic.

No LLM required.

---

# 2. Semantic + Architectural Inference Engine

## Objective

Transform structural graphs into architectural models.

## Inputs

* Dependency graph
* File graph
* Symbol graph
* Directory structure

## Outputs

```json
architecture.json
```

---

## 2.1 Semantic Clustering

### Goal

Detect logical subsystems.

### Signals

* Directory proximity
* Shared imports
* Call density
* Naming similarity
* Dependency locality

### Example

```text
telemetry/
can/
packet/
dispatcher/
```

↓

```text
Telemetry subsystem
```

---

## 2.2 Semantic Labeling

### Goal

Infer subsystem meaning.

### Example Input

```text
Cluster:
- telemetry/a.cpp
- telemetry/b.cpp
- telemetry/c.cpp

Imports:
- CANBus
- SharedProtocol
```

### Example Output

```text
Telemetry subsystem:
Handles real-time async data ingestion from CAN bus and external sensors.
```

This phase uses:

* LLM reasoning
* Graph metadata
* Structural heuristics

---

## 2.3 Architectural Constraint Inference

### Goal

Infer architectural rules.

### Example

```yaml
Telemetry:
  async_only: true
  no_blocking_io: true

  dependencies:
    allowed:
      - SharedProtocol

    forbidden:
      - MotorControl
      - UI
```

These constraints become runtime guidance for the agent.

---

# 3. Context Orchestrator (Core Innovation)

## Objective

Transform user intent into architecture-governed context.

This is the core differentiator of ArchAI.

---

## Input

```text
"add buffering to telemetry"
```

---

## Processing Pipeline

### 3.1 Focus Resolution

Determine the active subsystem.

Example:

```text
ACTIVE FOCUS = Telemetry
```

Signals:

* Query terms
* Graph proximity
* Cluster mapping
* Semantic similarity

---

### 3.2 Subgraph Extraction

Extract only the relevant architectural neighborhood.

Example:

```text
Telemetry:
- PacketEncoder
- Dispatcher
- CANBridge
```

---

### 3.3 Constraint Injection

Inject architectural rules into context.

Example:

```yaml
constraints:
  async_only: true
  no_blocking_io: true
  forbidden_dependencies:
    - MotorControl
    - UI
```

---

### 3.4 Context Packet Generation

Final output:

```json
{
  "focus": "Telemetry",
  "constraints": {
    "async_only": true
  },
  "subgraph": [
    "PacketEncoder",
    "Dispatcher"
  ],
  "relevant_files": [...]
}
```

This is the:

> Architecture Context Packet

---

# 4. Agent Integration Layer

## Objective

Connect coding agents with ArchAI.

---

# Recommended MVP Architecture

Use:

```text
HTTP Context Service
```

Example:

```text
POST /context
```

---

# Integration Flow

```text
User → OpenCode
        ↓
OpenCode → ArchAI /context
        ↓
ArchAI returns Context Packet
        ↓
OpenCode builds prompt
        ↓
LLM execution
```

---

# Why HTTP Service First?

Advantages:

* Decoupled architecture
* Easy debugging
* Full observability
* Faster iteration
* Agent-agnostic design
* Easy experimentation
* Works with multiple agents

Future compatible with:

* Cursor
* Claude Code
* Gemini CLI
* Aider
* OpenCode

---

# 5. Visualization + Trace UI

## Objective

Visualize architectural cognition in real time.

---

# UI Features

## Repository Overview

```text
System
 ├── Firmware
 ├── Backend
 └── UI
```

---

## Active Focus Highlighting

Example:

```text
Telemetry subsystem (active)
```

---

## Constraint Display

```text
async only
no blocking IO
```

---

## Blast Radius Visualization

Example:

```text
Modified:
- TelemetryBuffer.cpp
```

---

## Architectural Drift Detection

Example:

```text
⚠ Telemetry → UI dependency detected
```

---

# Technical Stack

## Backend

* Python
* FastAPI
* Tree-sitter
* networkx

## Graph Processing

* networkx
* graph clustering heuristics

## LLM Layer

* Gemini
* Claude
* GPT

## Frontend

* React
* React Flow

---

# Recommended MVP Architecture Diagram

```text
        ┌────────────────┐
        │   React UI     │
        └──────┬─────────┘
               │
        state / trace
               │
        ┌──────▼─────────┐
        │    ArchAI      │
        │ Context Engine │
        │                │
        │ - graph        │
        │ - clustering   │
        │ - focus        │
        │ - constraints  │
        └──────┬─────────┘
               │
       Context Packet API
               │
        ┌──────▼─────────┐
        │   OpenCode     │
        │   Agent CLI    │
        └──────┬─────────┘
               │
               ▼
              LLM
```

---

# Evaluation Metrics

## 1. Boundary Violations

Example:

```text
Telemetry → UI dependency
```

Measure reduction in architectural violations.

---

## 2. Blast Radius

Measure how many subsystems/files are modified.

Goal:

```text
Localized modifications
```

---

## 3. Context Precision

Measure how much retrieved context belongs to the active subsystem.

---

## 4. Token Reduction

Measure the token count difference between naive context retrieval vs architecture-governed context.

> **Hypothesis**: Architecture-guided context should require significantly fewer tokens while maintaining relevance.

**To be validated during MVP testing** (VC-004 in requirements).

---

# Strategic Positioning

ArchAI is NOT:

* A graph viewer
* Another RAG system
* A coding assistant
* An IDE plugin

ArchAI IS:

> A cognitive middleware layer for architecture-aware AI coding agents.

---

# Key Insight

Traditional systems treat repositories as:

```text
Text corpora
```

ArchAI treats repositories as:

```text
Architectural cognitive spaces
```

This allows AI agents to reason within:

* subsystem boundaries
* architectural constraints
* focused execution contexts
* graph-aware operational scopes

---

# Long-Term Vision

Future evolution may include:

* Multi-agent orchestration
* Dynamic model routing
* Runtime architectural enforcement
* Autonomous subsystem ownership
* Continuous architectural learning
* CI/CD architectural governance
* IDE integrations
* Agent federation

But the MVP should remain focused on:

```text
Architecture-governed context orchestration
```
