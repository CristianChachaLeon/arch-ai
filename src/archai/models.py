"""Domain models for ArchAI.

These models are used across the orchestrator, CLI, and MCP server.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


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


class ValidateChangeResponse(BaseModel):
    """Response for change validation."""

    valid: bool
    violations: list[Violation]

    @model_validator(mode="after")
    def validate_consistency(self) -> ValidateChangeResponse:
        if self.valid and self.violations:
            raise ValueError("valid=True but violations are not empty")
        if not self.valid and not self.violations:
            raise ValueError("valid=False but violations are empty")
        return self
