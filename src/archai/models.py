"""Domain models for ArchAI.

These models are used across the orchestrator, CLI, and MCP server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


@dataclass
class LabeledCluster:
    cluster_id: str
    name: str
    description: str
    reasoning: str
    files: list[str]
    async_only: bool = False
    no_blocking_io: bool = False
    forbidden_dependencies: list[str] = field(default_factory=list)
    allowed_dependencies: list[str] = field(default_factory=list)


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
    test_files: list[str] = Field(default_factory=list)
    sub_clusters: dict[str, dict[str, list[str]]] = {}
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuralChangeValidation(BaseModel):
    """Structural validation response — the agent decides validity."""

    file_cluster: str
    cluster_files: list[str]
    cluster_dependencies: dict[str, list[str]]
    file_dependencies: dict[str, list[str]]
    new_imports_in_patch: list[str] = Field(default_factory=list)
    patch_summary: dict[str, Any] = Field(default_factory=dict)


class SubsystemConstraints(BaseModel):
    """Constraints that apply to a subsystem."""

    async_only: bool = False
    no_blocking_io: bool = False
    forbidden_dependencies: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)


class FileMetadata(BaseModel):
    """Metadata about a relevant file."""

    path: str
    reason: str
    importance: float = Field(ge=0.0, le=1.0)


class ContextPacket(BaseModel):
    """Context packet returned to the agent."""

    focus: str
    focus_reasoning: str
    constraints: SubsystemConstraints
    subgraph: list[str]
    relevant_files: list[FileMetadata]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeItem(BaseModel):
    """A single code change item."""

    file_path: str
    patch: str
    change_type: Optional[str] = None


class Violation(BaseModel):
    """A constraint violation."""

    file: str
    rule: str
    message: str


class BlastRadiusResponse(BaseModel):
    """Response for blast radius analysis of a file change."""

    focus_file: str
    direct_dependents: list[str] = Field(
        default_factory=list,
        description="Files that directly import the focus file (would break if API changes)",
    )
    direct_dependencies: list[str] = Field(
        default_factory=list, description="Files that the focus file directly imports"
    )
    transitive_dependents: list[str] = Field(
        default_factory=list,
        description="Files that transitively depend on the focus file (beyond direct)",
    )
    subsystems_affected: dict[str, int] = Field(
        default_factory=dict, description="Subsystem names mapped to count of affected files"
    )
    function_name: str | None = None
    function_dependents: list[str] = []
    function_dependencies: list[str] = []


class ValidateChangeResponse(BaseModel):
    """Response for change validation."""

    valid: bool
    violations: list[Violation]
    intra_file_violations: list[Violation] = []

    @model_validator(mode="after")
    def validate_consistency(self) -> ValidateChangeResponse:
        if self.valid and self.violations:
            raise ValueError("valid=True but violations are not empty")
        if not self.valid and not self.violations:
            raise ValueError("valid=False but violations are empty")
        return self


class FunctionDetail(BaseModel):
    """Detail for a single function in a file."""

    name: str
    line: int
    calls_internal: list[str] = Field(default_factory=list)
    calls_external: list[str] = Field(default_factory=list)


class VariableAccess(BaseModel):
    """A function that reads or writes a global variable."""

    function: str
    file_path: str
    line: int = 0
    access_type: str = "read"  # "read" or "write"


class SharedVariable(BaseModel):
    """A global variable and its access pattern."""

    name: str
    type_hint: str = ""
    declared_in: str = ""  # file_path
    line: int = 0
    is_static: bool = False
    writers: list[VariableAccess] = Field(default_factory=list)
    readers: list[VariableAccess] = Field(default_factory=list)


class SharedStateResponse(BaseModel):
    """Complete shared state analysis for a repository."""

    variables: list[SharedVariable] = Field(default_factory=list)
    total_count: int = 0
    most_written: list[str] = Field(default_factory=list)
    most_read: list[str] = Field(default_factory=list)


class FileDetailResponse(BaseModel):
    """Detailed analysis of a single file."""

    file_path: str
    cluster: str | None = None
    functions: list[FunctionDetail] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    """Project files this file imports (external/system deps excluded)."""
    external_import_count: int = 0
    """Number of external/system dependencies (not included in imports)."""
    dependents: list[str] = Field(default_factory=list)
    """Files that depend on this file (import it)."""
    dependencies: list[str] = Field(default_factory=list)
    """Project files this file depends on (external/system deps excluded)."""
    external_dependency_count: int = 0
    """Number of external/system dependencies at file level."""
