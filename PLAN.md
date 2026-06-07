# Archai — Plan de Implementación

## Estado Actual

| Fase | Feature | Branch | PR | Estado |
|------|---------|--------|----|--------|
| 0 | Rename `mcp` → `serve` | `feat/rename-mcp-to-serve` | #38 | ✅ Mergeado |
| — | Cleanup dead code (cache, llm, labeler) | `chore/remove-dead-code` | #39 | ✅ Mergeado |
| **2.1** | **`get_file_detail` / `archai file`** | **`feat/mcp-file-detail`** | **#40** | **🟡 En review — coverage 78.6%** |

---

## Bloqueantes

### 1. Coverage < 80% en PR #40

**Problema:** El código nuevo de `get_file_detail` (orchestrator + CLI) no tiene tests de cobertura suficientes → 78.61% < 80% threshold.

**Solución:** Agregar tests para:
- `FileDetailResponse`, `FunctionDetail` (modelos)
- `get_file_detail()` en orchestrator
- `archai file --json` en CLI

### 2. Publish to PyPI falló en v0.4.0

**Problema:** El workflow `publish.yml` falla al hacer `uv publish` — probablemente falta `PYPI_API_TOKEN` en secrets del repo.

**Solución:** Verificar `https://github.com/CristianChachaLeon/arch-ai/settings/secrets/actions`

---

## Roadmap

### Fase 2 — Consulta específica

| # | Comando | MCP Tool | Descripción |
|---|---------|----------|-------------|
| 2.1 | `archai file <path>` | `get_file_detail` | ✅ PR #40. Análisis de un archivo |
| 2.2 | `archai state [--var]` | `get_shared_state` | Mapa de variables globales: writers + readers |
| 2.3 | `archai trace <feature>` | `trace_feature_flow` | Entry point → call chain → shared state → risks |

### Fase 3 — Impacto

| # | Comando | MCP Tool | Descripción |
|---|---------|----------|-------------|
| 3.1 | `archai blast <path>` | `get_blast_radius` | Ya existe MCP, falta CLI y mejorar output |
| 3.2 | `archai plan <description>` | `propose_change` | Dado un cambio deseado, sugiere archivos afectados |

### Fase 4 — Validación

| # | Comando | MCP Tool | Descripción |
|---|---------|----------|-------------|
| 4.1 | `archai validate <patch>` | `validate_code_change` | Ya existe MCP, falta CLI |
| 4.2 | `archai check` | `validate_design` | Reglas predefinidas (cyclic deps, forbidden imports) |

### Fase 5 — Dev workflow

| # | Comando | Descripción |
|---|---------|-------------|
| 5.1 | `archai watch` | Modo watch que re-analiza en cambios |
| 5.2 | `archai ci` | Output para CI con exit code |
| 5.3 | `archai init` | ✅ Ya existe, mejorar |

### Fase 1 — Onboarding

| # | Comando | MCP Tool | Descripción |
|---|---------|----------|-------------|
| 1.1 | `archai context <query>` | `get_architecture_context` | Ya existe MCP, falta CLI |

---

## Orden de Prioridad

```
1. Subir coverage de PR #40 a >= 80%
2. Mergear PR #40
3. Fase 2.2 — archai state (get_shared_state)
4. Verificar CI/CD verde
5. Fase 2.3 — archai trace (trace_feature_flow)
6. Fase 3.1 — archai blast
```

## Convenciones

- Branch por feature: `feat/<nombre>`
- Branch por chore: `chore/<nombre>`
- PR por feature individual (~100-200 lines)
- Toda MCP tool tiene su equivalente CLI
- `--json` flag en todos los CLI commands
