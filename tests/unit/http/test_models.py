"""
Tests: Pydantic request/response models.

These tests verify the structure of API models for the ArchAI HTTP service.
"""

import pytest
from pydantic import ValidationError

from archai.http.models import (
    SubsystemConstraints,
    Subsystem,
    ArchitectureModel,
    FileMetadata,
    ContextPacket,
    ContextRequest,
    RepositoryResponse,
    ValidateChangeRequest,
    ValidateChangeResponse,
)


class TestSubsystemConstraints:
    """Tests for SubsystemConstraints model."""

    def test_valid_constraints(self):
        """Test creating valid constraints."""
        constraints = SubsystemConstraints(
            async_only=False,
            no_blocking_io=False,
            forbidden_dependencies=[],
            allowed_dependencies=["fastapi", "pydantic"],
        )
        assert constraints.async_only is False
        assert "fastapi" in constraints.allowed_dependencies

    def test_constraints_defaults(self):
        """Test default values for constraints."""
        constraints = SubsystemConstraints()
        assert constraints.async_only is False
        assert constraints.no_blocking_io is False
        assert constraints.forbidden_dependencies == []
        assert constraints.allowed_dependencies == []


class TestSubsystem:
    """Tests for Subsystem model."""

    def test_valid_subsystem(self):
        """Test creating a valid subsystem."""
        subsystem = Subsystem(
            name="http",
            description="HTTP service layer",
            files=["src/archai/http/main.py"],
            constraints=SubsystemConstraints(),
        )
        assert subsystem.name == "http"
        assert len(subsystem.files) == 1

    def test_subsystem_with_constraints(self):
        """Test subsystem with custom constraints."""
        constraints = SubsystemConstraints(
            async_only=True,
            forbidden_dependencies=["requests", "urllib"],
        )
        subsystem = Subsystem(
            name="api",
            description="API layer",
            files=[],
            constraints=constraints,
        )
        assert subsystem.constraints.async_only is True
        assert "requests" in subsystem.constraints.forbidden_dependencies


class TestArchitectureModel:
    """Tests for ArchitectureModel."""

    def test_valid_model(self):
        """Test creating a valid architecture model."""
        subsystem = Subsystem(
            name="http",
            description="HTTP service",
            files=["main.py"],
            constraints=SubsystemConstraints(),
        )
        model = ArchitectureModel(
            subsystems=[subsystem],
            file_to_subsystem={"main.py": "http"},
        )
        assert len(model.subsystems) == 1
        assert model.file_to_subsystem["main.py"] == "http"

    def test_empty_subsystems(self):
        """Test model with no subsystems."""
        model = ArchitectureModel(subsystems=[], file_to_subsystem={})
        assert model.subsystems == []


class TestFileMetadata:
    """Tests for FileMetadata."""

    def test_valid_file_metadata(self):
        """Test creating valid file metadata."""
        metadata = FileMetadata(
            path="src/main.py",
            reason="imported by entrypoint",
            importance=0.9,
        )
        assert metadata.path == "src/main.py"
        assert 0.0 <= metadata.importance <= 1.0

    def test_importance_clamping(self):
        """Test importance value is validated."""
        with pytest.raises(ValidationError):
            FileMetadata(path="test.py", reason="test", importance=1.5)


class TestContextPacket:
    """Tests for ContextPacket."""

    def test_valid_context_packet(self):
        """Test creating a valid context packet."""
        packet = ContextPacket(
            focus="http",
            focus_reasoning="User asked about API endpoints",
            constraints=SubsystemConstraints(),
            subgraph=["main.py", "routes.py"],
            relevant_files=[FileMetadata(path="main.py", reason="entry point", importance=1.0)],
            metadata={"repo_id": "test-repo"},
        )
        assert packet.focus == "http"
        assert len(packet.relevant_files) == 1


class TestContextRequest:
    """Tests for ContextRequest."""

    def test_valid_request(self):
        """Test creating a valid context request."""
        request = ContextRequest(
            query="How does the health endpoint work?",
            repo_path="/path/to/repo",
        )
        assert request.query == "How does the health endpoint work?"
        assert request.repo_path == "/path/to/repo"

    def test_missing_query_fails(self):
        """Test that missing query raises validation error."""
        with pytest.raises(ValidationError):
            ContextRequest(repo_path="/path/to/repo")

    def test_missing_repo_path_fails(self):
        """Test that missing repo_path raises validation error."""
        with pytest.raises(ValidationError):
            ContextRequest(query="test query")


class TestRepositoryResponse:
    """Tests for RepositoryResponse."""

    def test_valid_response(self):
        """Test creating a valid repository response."""
        subsystem = Subsystem(
            name="http",
            description="HTTP service",
            files=["main.py"],
            constraints=SubsystemConstraints(),
        )
        response = RepositoryResponse(
            repo_id="test-repo",
            subsystems=[subsystem],
            file_count=1,
        )
        assert response.repo_id == "test-repo"
        assert len(response.subsystems) == 1
        assert response.file_count == 1


class TestValidateChangeRequest:
    """Tests for ValidateChangeRequest."""

    def test_valid_request(self):
        """Test creating a valid validate change request."""
        request = ValidateChangeRequest(
            repo_path="/path/to/repo",
            changes=[
                {
                    "file_path": "src/main.py",
                    "patch": "@@ -1,3 +1,4 @@\n+import fastapi",
                    "change_type": "modify",
                }
            ],
        )
        assert len(request.changes) == 1
        assert request.changes[0].file_path == "src/main.py"
        assert request.changes[0].patch == "@@ -1,3 +1,4 @@\n+import fastapi"
        assert request.changes[0].change_type == "modify"


class TestValidateChangeResponse:
    """Tests for ValidateChangeResponse."""

    def test_valid_response_no_violations(self):
        """Test valid response with no violations."""
        response = ValidateChangeResponse(
            valid=True,
            violations=[],
        )
        assert response.valid is True
        assert response.violations == []

    def test_valid_response_with_violations(self):
        """Test valid response with violations."""
        response = ValidateChangeResponse(
            valid=False,
            violations=[
                {
                    "file": "src/http/main.py",
                    "rule": "forbidden_dependency",
                    "message": "Cannot use 'requests' library in async subsystem",
                }
            ],
        )
        assert response.valid is False
        assert len(response.violations) == 1

    def test_validation_error_when_valid_true_with_violations(self):
        """Test that valid=True with non-empty violations raises ValidationError."""
        with pytest.raises(ValidationError):
            ValidateChangeResponse(
                valid=True,
                violations=[{"file": "x", "rule": "y", "message": "z"}],
            )

    def test_validation_error_when_valid_false_without_violations(self):
        """Test that valid=False with empty violations raises ValidationError."""
        with pytest.raises(ValidationError):
            ValidateChangeResponse(valid=False, violations=[])
