"""
Pydantic models for ArchAI HTTP API (T-005).

This module defines all request/response models for the API endpoints.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from archai.http.config import validate_repo_path


class SubsystemConstraints(BaseModel):
    """Constraints that apply to a subsystem."""

    async_only: bool = False
    no_blocking_io: bool = False
    forbidden_dependencies: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)


class Subsystem(BaseModel):
    """A subsystem in the architecture."""

    name: str
    description: str
    files: list[str]
    constraints: SubsystemConstraints = Field(default_factory=SubsystemConstraints)


class ArchitectureModel(BaseModel):
    """Complete architecture model for a repository."""

    subsystems: list[Subsystem]
    file_to_subsystem: dict[str, str]


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


class ContextRequest(BaseModel):
    """Request for getting context about a query."""

    query: str
    repo_path: str

    validate_repo_path = field_validator("repo_path")(validate_repo_path)


class ProcessRequest(BaseModel):
    """Request for processing a repository."""

    repo_path: str

    validate_repo_path = field_validator("repo_path")(validate_repo_path)


class ProcessResponse(BaseModel):
    """Response for repository processing."""

    repo_path: str
    file_count: int
    edge_count: int
    cluster_count: int
    clusters: dict
    cluster_names: dict | None = None
    cluster_descriptions: dict | None = None
    cluster_reasonings: dict | None = None


class BlastRadiusRequest(BaseModel):
    """Request for blast radius analysis of a file change."""

    repo_path: str
    file_path: str
    depth: int = 2

    validate_repo_path = field_validator("repo_path")(validate_repo_path)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if not v.endswith(".py"):
            raise ValueError("file_path must be a Python file (.py)")
        return v

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("depth must be between 1 and 5")
        return v


class RepositoryResponse(BaseModel):
    """Response for repository information."""

    repo_id: str
    subsystems: list[Subsystem]
    file_count: int = Field(..., ge=0)


class ChangeItem(BaseModel):
    """A single code change item."""

    file_path: str
    patch: str
    change_type: Optional[str] = None


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


class ValidateChangeRequest(BaseModel):
    """Request for validating code changes."""

    repo_path: str
    changes: list[ChangeItem]


class Violation(BaseModel):
    """A constraint violation."""

    file: str
    rule: str
    message: str


class ValidateChangeResponse(BaseModel):
    """Response for change validation."""

    valid: bool
    violations: list[Violation]

    @model_validator(mode="after")
    def validate_consistency(self) -> "ValidateChangeResponse":
        """Ensure valid and violations are logically consistent."""
        if self.valid and self.violations:
            raise ValueError("valid=True but violations are not empty")
        if not self.valid and not self.violations:
            raise ValueError("valid=False but violations are empty")
        return self
